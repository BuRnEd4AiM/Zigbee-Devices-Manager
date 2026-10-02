"""Backend des Zigbee Devices Manager (Home Assistant Add-on, Ingress)."""
import asyncio
import json
import os
import re
import time
import unicodedata
from pathlib import Path

from aiohttp import ClientSession, web

DATA = Path(os.environ.get("DATA_DIR", "/data"))
WEB = Path(__file__).parent / "web"
TOKEN = os.environ.get("SUPERVISOR_TOKEN")
WS_URL = os.environ.get("HA_WS_URL", "ws://supervisor/core/websocket")
STORE_FILE = DATA / "store.json"
HA_CONFIG_DIR = Path(os.environ.get("HA_CONFIG_DIR", "/homeassistant"))
ADDON_CONFIGS_DIR = Path(os.environ.get("ADDON_CONFIGS_DIR", "/addon_configs"))
SKIP_DIRS = {".storage", ".git", ".cloud", "custom_components", "deps", "__pycache__", "backups", "node_modules", "www"}
UI_MANAGED_YAML = {"automations.yaml", "scripts.yaml", "scenes.yaml"}
MAX_FILE_BYTES = 5_000_000
CORE_API = os.environ.get("HA_API_URL", "http://supervisor/core/api")


TOPIC_RE = re.compile(r"^[A-Za-z0-9_\-]+(/[A-Za-z0-9_\-]+)*$")


def safe_topic(value):
    """Basis-Topic eines Zigbee2MQTT-Gateways; ungültige Werte (z. B. Wildcards) fallen auf den Standard zurück."""
    return value if isinstance(value, str) and TOPIC_RE.match(value) else z2m_base_topic()


def z2m_base_topic():
    try:
        return json.loads((DATA / "options.json").read_text()).get("z2m_base_topic") or "zigbee2mqtt"
    except (OSError, ValueError):
        return "zigbee2mqtt"


async def ha(commands):
    """Führt Websocket-Kommandos gegen Home Assistant aus und liefert die Ergebnisse."""
    if not TOKEN:
        raise web.HTTPServiceUnavailable(text="Kein SUPERVISOR_TOKEN – läuft nicht als Add-on")
    async with ClientSession() as session, session.ws_connect(WS_URL) as ws:
        await ws.receive_json()
        await ws.send_json({"type": "auth", "access_token": TOKEN})
        if (await ws.receive_json())["type"] != "auth_ok":
            raise web.HTTPBadGateway(text="Authentifizierung bei Home Assistant fehlgeschlagen")
        results = []
        for i, cmd in enumerate(commands, 1):
            await ws.send_json({**cmd, "id": i})
            while True:
                reply = await ws.receive_json()
                if reply.get("id") == i:
                    break
            if not reply.get("success"):
                raise web.HTTPBadGateway(text=reply.get("error", {}).get("message", "HA-Fehler"))
            results.append(reply["result"])
        return results


def slugify(text):
    text = text.replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def zigbee_source(device):
    """Liefert (Quelle, IEEE) für ZHA- oder Zigbee2MQTT-Geräte, sonst None."""
    for domain, ident in device.get("identifiers", []):
        if domain == "zha":
            return "zha", ident
        if domain == "mqtt" and ident.startswith("zigbee2mqtt_"):
            return "z2m", ident.removeprefix("zigbee2mqtt_")
    return None


def load_store():
    try:
        return json.loads(STORE_FILE.read_text())
    except (OSError, ValueError):
        return {}


async def get_state(request):
    devices, areas = await ha([
        {"type": "config/device_registry/list"},
        {"type": "config/area_registry/list"},
    ])
    area_names = {a["area_id"]: a["name"] for a in areas}
    out, bridges = [], {}
    for d in devices:
        if any(dom == "mqtt" and ident.startswith("zigbee2mqtt_bridge_") for dom, ident in d.get("identifiers", [])):
            bridges[d["id"]] = {"id": d["id"], "source": "z2m", "name": d.get("name_by_user") or d.get("name") or "Zigbee2MQTT"}
            continue
        found = zigbee_source(d)
        if not found:
            continue
        source, ieee = found
        bridge = d.get("via_device_id") or source
        if bridge not in bridges:
            bridges.setdefault(bridge, {"id": bridge, "source": source, "name": "ZHA" if source == "zha" else "Zigbee2MQTT"})
        out.append({
            "bridge": bridge,
            "id": d["id"],
            "name": d.get("name_by_user") or d.get("name") or ieee,
            "orig_name": d.get("name") or "",
            "is_new": not d.get("name_by_user"),
            "manufacturer": d.get("manufacturer") or "",
            "model": d.get("model") or "",
            "ieee": ieee,
            "source": source,
            "area": area_names.get(d.get("area_id"), ""),
        })
    used = {d["bridge"] for d in out}
    return web.json_response({"devices": out, "store": load_store(),
                              "bridges": [b for b in bridges.values() if b["id"] in used or b["source"] == "z2m"]})


async def permit_join(request):
    """Aktiviert/beendet das Anlernen (Pairing) am Zigbee2MQTT-Gateway oder bei ZHA."""
    body = await request.json()
    seconds = max(0, min(int(body.get("time", 240)), 254))
    if body.get("source") == "zha":
        cmd = {"type": "call_service", "domain": "zha", "service": "permit", "service_data": {"duration": seconds}}
    else:
        cmd = {"type": "call_service", "domain": "mqtt", "service": "publish", "service_data": {
            "topic": f"{safe_topic(body.get('base_topic'))}/bridge/request/permit_join",
            "payload": json.dumps({"time": seconds})}}
    await ha([cmd])
    return web.json_response({"ok": True, "time": seconds})


async def permit_state(request):
    """Liefert je Gateway den Zustand des Z2M-Schalters „Anlernen erlauben“ (falls vorhanden)."""
    entities, states = await ha([{"type": "config/entity_registry/list"}, {"type": "get_states"}])
    by_entity = {st["entity_id"]: st["state"] for st in states}
    out = {}
    for ent in entities:
        if ent["entity_id"].startswith("switch.") and "permit_join" in ent["entity_id"] and ent.get("device_id"):
            out[ent["device_id"]] = by_entity.get(ent["entity_id"])
    return web.json_response(out)


async def put_store(request):
    DATA.mkdir(parents=True, exist_ok=True)
    STORE_FILE.write_text(json.dumps(await request.json(), indent=2, ensure_ascii=False))
    return web.json_response({"ok": True})


def entity_changes(items, entities):
    """Bestimmt, welche Entity-IDs sich beim Umbenennen der Geräte ändern würden."""
    by_dev = {}
    for ent in entities:
        by_dev.setdefault(ent.get("device_id"), []).append(ent)
    existing = {e["entity_id"] for e in entities}
    changes, skipped = [], []
    for it in items:
        new_slug = slugify(it["name"])
        candidates = list(dict.fromkeys(
            c for c in (slugify(it.get("old_name") or ""), slugify(it.get("orig_name") or "")) if c))
        for ent in by_dev.get(it["device_id"], []):
            domain, _, obj = ent["entity_id"].partition(".")
            for cand in candidates:
                if new_slug and (obj == cand or obj.startswith(cand + "_")):
                    new_id = f"{domain}.{new_slug}{obj[len(cand):]}"
                    if new_id == ent["entity_id"]:
                        break
                    if new_id in existing:
                        skipped.append({"old": ent["entity_id"], "new": new_id, "reason": "ID existiert bereits"})
                    else:
                        existing.add(new_id)
                        changes.append({"old": ent["entity_id"], "new": new_id})
                    break
    return changes, skipped


async def scan_configs():
    """Liest alle per Oberfläche bearbeitbaren Automationen, Skripte, Szenen und Dashboards."""
    states, dashboards = await ha([{"type": "get_states"}, {"type": "lovelace/dashboards/list"}])
    items, unreadable = [], 0
    async with ClientSession(headers={"Authorization": f"Bearer {TOKEN}"}) as http:
        for st in states:
            domain, _, obj = st["entity_id"].partition(".")
            cid = obj if domain == "script" else st["attributes"].get("id")
            if domain not in ("automation", "script", "scene") or not cid:
                if domain in ("automation", "scene"):
                    unreadable += 1
                continue
            path = f"config/{domain}/config/{cid}"
            async with http.get(f"{CORE_API}/{path}") as r:
                if r.status != 200:
                    unreadable += 1
                    continue
                cfg = await r.json()
            items.append({"kind": domain, "id": cid, "path": path,
                          "title": cfg.get("alias") or cfg.get("name") or st["attributes"].get("friendly_name") or cid,
                          "config": cfg})
    for url_path in [None] + [d["url_path"] for d in dashboards if d.get("mode") == "storage"]:
        cmd = {"type": "lovelace/config", "force": False}
        if url_path:
            cmd["url_path"] = url_path
        try:
            cfg = (await ha([cmd]))[0]
        except web.HTTPException:
            continue
        title = next((d["title"] for d in dashboards if d["url_path"] == url_path), None) or "Übersicht"
        items.append({"kind": "dashboard", "id": url_path or "", "title": title, "url_path": url_path, "config": cfg})
    return items, unreadable


def scan_files(want_yaml, want_nodered, skip_ui_yaml):
    """Findet YAML-Dateien in /config und Node-RED-Flows. Gibt (Einträge, Hinweise) zurück."""
    items, notes = [], []

    def add(kind, path, title):
        try:
            if path.stat().st_size <= MAX_FILE_BYTES:
                items.append({"kind": kind, "id": str(path), "path": path, "title": title,
                              "text": path.read_text(encoding="utf-8")})
        except (OSError, UnicodeDecodeError):
            pass

    if want_yaml:
        if not HA_CONFIG_DIR.is_dir():
            notes.append(f"{HA_CONFIG_DIR} ist nicht eingebunden – YAML-Dateien werden nicht durchsucht")
        else:
            for root, dirs, files in os.walk(HA_CONFIG_DIR):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for f in files:
                    path = Path(root) / f
                    if path.suffix not in (".yaml", ".yml") or f == "secrets.yaml":
                        continue
                    if skip_ui_yaml and path.parent == HA_CONFIG_DIR and f in UI_MANAGED_YAML:
                        continue
                    add("yaml", path, str(path.relative_to(HA_CONFIG_DIR)))
    if want_nodered:
        flows = [p for p in ADDON_CONFIGS_DIR.glob("*/flows*.json") if "cred" not in p.name] if ADDON_CONFIGS_DIR.is_dir() else []
        if not flows:
            notes.append("Keine Node-RED-Flows gefunden (Add-on-Konfigurationen nicht eingebunden oder Node-RED nicht installiert)")
        for path in flows:
            add("nodered", path, f"{path.parent.name}/{path.name}")
    return items, notes


def mapping_regex(mapping):
    keys = sorted(mapping, key=len, reverse=True)
    return re.compile(r"(?<!\w)(" + "|".join(re.escape(k) for k in keys) + r")(?!\w)")


def item_text(it):
    return it["text"] if "text" in it else json.dumps(it["config"], ensure_ascii=False)


def find_usages(items, mapping):
    if not mapping:
        return []
    rx = mapping_regex(mapping)
    out = []
    for it in items:
        found = sorted(set(rx.findall(item_text(it))))
        if found:
            out.append({**{k: it[k] for k in ("kind", "id", "title")}, "entities": found})
    return out


def parse_request(body):
    items = [i for i in body.get("items", []) if i.get("device_id") and (i.get("name") or "").strip()]
    for i in items:
        i["name"] = i["name"].strip()
    return items


async def collect_usages(body, mapping):
    """Sucht Verweise in UI-Konfigurationen, YAML-Dateien und Node-RED-Flows (je nach Optionen)."""
    items, unreadable, notes = [], 0, []
    if body.get("update_references"):
        items, unreadable = await scan_configs()
    if body.get("update_yaml") or body.get("update_nodered"):
        files, notes = scan_files(body.get("update_yaml"), body.get("update_nodered"),
                                  skip_ui_yaml=bool(body.get("update_references")))
        items += files
    return find_usages(items, mapping), unreadable, notes


async def plan(request):
    body = await request.json()
    items = parse_request(body)
    changes, skipped, usages, unreadable, notes = [], [], [], 0, []
    if body.get("rename_entities") and items:
        entities = (await ha([{"type": "config/entity_registry/list"}]))[0]
        changes, skipped = entity_changes(items, entities)
        if changes:
            usages, unreadable, notes = await collect_usages(body, {c["old"]: c["new"] for c in changes})
    return web.json_response({"entities": changes, "skipped": skipped, "usages": usages,
                              "unreadable": unreadable, "notes": notes})


def check(name, status, detail=""):
    return {"name": name, "status": status, "detail": detail}


async def verify_changes(items, renamed, opts, wait=True):
    """Prüft nach dem Umbenennen, ob Geräte, Entity-IDs und Verweise wirklich angepasst sind."""
    checks = []
    # 1. Gerätenamen (Zigbee2MQTT bestätigt asynchron, daher kurz warten)
    deadline = time.monotonic() + (15 if wait else 0)
    while True:
        devices = (await ha([{"type": "config/device_registry/list"}]))[0]
        by_id = {d["id"]: d for d in devices}
        wrong = [it for it in items
                 if (by_id.get(it["device_id"], {}).get("name_by_user") or by_id.get(it["device_id"], {}).get("name")) != it["name"]]
        if not wrong or time.monotonic() >= deadline:
            break
        await asyncio.sleep(1.5)
    if not wrong:
        checks.append(check("Gerätenamen", "ok", f"{len(items)} Gerät(e) heißen jetzt wie geplant"))
    else:
        names = ", ".join(it["name"] for it in wrong)
        z2m = any(it.get("source") == "z2m" and opts.get("rename_entities") for it in wrong)
        checks.append(check("Gerätenamen", "warn" if z2m else "fail",
                            f"Noch nicht übernommen: {names}" + (
                                " – Zigbee2MQTT hat die Umbenennung noch nicht bestätigt (Basis-Topic und Z2M-Log prüfen, später erneut prüfen)" if z2m else "")))
    # 2. Entity-IDs
    if renamed:
        existing = {e["entity_id"] for e in (await ha([{"type": "config/entity_registry/list"}]))[0]}
        missing = [c["new"] for c in renamed if c["new"] not in existing]
        still_old = [c["old"] for c in renamed if c["old"] in existing]
        if missing or still_old:
            checks.append(check("Entity-IDs", "fail", "; ".join(filter(None, [
                f"Neue ID fehlt: {', '.join(missing)}" if missing else "",
                f"Alte ID existiert noch: {', '.join(still_old)}" if still_old else ""]))))
        else:
            checks.append(check("Entity-IDs", "ok", f"{len(renamed)} Entity-ID(s) umbenannt, alte IDs gibt es nicht mehr"))
    elif opts.get("rename_entities"):
        checks.append(check("Entity-IDs", "info", "Keine Entity-ID musste geändert werden"))
    # 3. Verweise
    wants_refs = opts.get("update_references") or opts.get("update_yaml") or opts.get("update_nodered")
    if renamed and wants_refs:
        usages, unreadable, notes = await collect_usages(opts, {c["old"]: c["new"] for c in renamed})
        if usages:
            checks.append(check("Verweise", "fail", "Alte Entity-IDs kommen noch vor in: " + "; ".join(
                f"{u['kind']} {u['title']} ({', '.join(u['entities'])})" for u in usages)))
        else:
            parts = [k for k, on in (("Automationen/Skripte/Szenen/Dashboards", opts.get("update_references")),
                                     ("YAML-Dateien", opts.get("update_yaml")), ("Node-RED-Flows", opts.get("update_nodered"))) if on]
            checks.append(check("Verweise", "ok", "Keine alten Entity-IDs mehr gefunden in: " + ", ".join(parts)))
        if unreadable:
            checks.append(check("Nicht prüfbar", "warn", f"{unreadable} Automationen/Szenen sind nicht über die Oberfläche lesbar (YAML-Include) und wurden nicht geprüft"))
        checks += [check("Hinweis", "warn", n) for n in notes]
        if opts.get("update_nodered"):
            checks.append(check("Node-RED", "info", "Dateien sind angepasst. Node-RED jetzt neu starten – das Add-on kann den Deploy-Stand nicht prüfen"))
        if opts.get("update_yaml"):
            checks.append(check("YAML", "info", "Dateien sind angepasst. Konfiguration prüfen und neu laden (Entwicklerwerkzeuge → YAML)"))
    elif renamed:
        checks.append(check("Verweise", "info", "Nicht geprüft/angepasst (Haken aus). Automationen mit alten IDs laufen ins Leere"))
    return checks


async def verify(request):
    body = await request.json()
    items = parse_request(body)
    renamed = [c for c in body.get("renamed", []) if c.get("old") and c.get("new")]
    return web.json_response({"checks": await verify_changes(items, renamed, body, wait=False)})


async def ha_try(cmd):
    try:
        return True, (await ha([cmd]))[0]
    except web.HTTPException as err:
        return False, err.text


async def apply(request):
    body = await request.json()
    items = parse_request(body)
    if not items:
        raise web.HTTPBadRequest(text="Keine Geräte angegeben")
    z2m_mode = bool(body.get("rename_entities"))
    errors, done = [], []
    entities = (await ha([{"type": "config/entity_registry/list"}]))[0] if z2m_mode else []
    changes, skipped = entity_changes(items, entities) if z2m_mode else ([], [])

    for it in items:
        if z2m_mode and it.get("source") == "z2m" and it.get("ieee"):
            # In Zigbee2MQTT umbenennen; die HA-Entity-IDs ändern wir selbst, damit wir sie kennen
            cmd = {"type": "call_service", "domain": "mqtt", "service": "publish", "service_data": {
                "topic": f"{safe_topic(it.get('base_topic'))}/bridge/request/device/rename",
                "payload": json.dumps({"from": it["ieee"], "to": it["name"]})}}
        else:
            cmd = {"type": "config/device_registry/update", "device_id": it["device_id"], "name_by_user": it["name"]}
        ok, res = await ha_try(cmd)
        (done if ok else errors).append(it["device_id"] if ok else {"device": it["name"], "error": res})

    renamed = []
    for ch in changes:
        ok, res = await ha_try({"type": "config/entity_registry/update",
                                "entity_id": ch["old"], "new_entity_id": ch["new"]})
        (renamed.append(ch) if ok else errors.append({"device": ch["old"], "error": res}))

    changed_refs, unreadable = [], 0
    notes = []
    if renamed and (body.get("update_references") or body.get("update_yaml") or body.get("update_nodered")):
        configs, unreadable = await scan_configs() if body.get("update_references") else ([], 0)
        if body.get("update_yaml") or body.get("update_nodered"):
            files, notes = scan_files(body.get("update_yaml"), body.get("update_nodered"),
                                      skip_ui_yaml=bool(body.get("update_references")))
            configs += files
        mapping = {c["old"]: c["new"] for c in renamed}
        rx = mapping_regex(mapping)
        backup = DATA / "backups" / time.strftime("%Y%m%d-%H%M%S")
        async with ClientSession(headers={"Authorization": f"Bearer {TOKEN}"}) as http:
            for it in configs:
                text = item_text(it)
                if not rx.search(text):
                    continue
                backup.mkdir(parents=True, exist_ok=True)
                label = it["title"] if it["kind"] in ("yaml", "nodered") else str(it["id"])
                (backup / f"{it['kind']}__{slugify(label) or 'default'}.bak").write_text(text)
                new_text = rx.sub(lambda m: mapping[m.group(1)], text)
                if it["kind"] in ("yaml", "nodered"):
                    try:
                        if it["kind"] == "nodered":
                            json.loads(new_text)  # nur schreiben, wenn das Ergebnis gültiges JSON bleibt
                        it["path"].write_text(new_text, encoding="utf-8")
                        ok, res = True, ""
                    except (OSError, ValueError) as err:
                        ok, res = False, str(err)
                    if ok:
                        changed_refs.append({"kind": it["kind"], "title": it["title"]})
                    else:
                        errors.append({"device": f"{it['kind']} {it['title']}", "error": res})
                    continue
                new_cfg = json.loads(new_text)
                if it["kind"] == "dashboard":
                    cmd = {"type": "lovelace/config/save", "config": new_cfg}
                    if it["url_path"]:
                        cmd["url_path"] = it["url_path"]
                    ok, res = await ha_try(cmd)
                else:
                    async with http.post(f"{CORE_API}/{it['path']}", json=new_cfg) as r:
                        ok, res = r.status == 200, await r.text()
                if ok:
                    changed_refs.append({"kind": it["kind"], "title": it["title"]})
                else:
                    errors.append({"device": f"{it['kind']} {it['title']}", "error": res})
    checks = await verify_changes(items, renamed, body) if not body.get("skip_verify") else []
    return web.json_response({"ok": not errors, "checks": checks, "renamed_devices": done, "renamed_entities": renamed,
                              "skipped": skipped, "updated_references": changed_refs,
                              "unreadable": unreadable, "notes": notes, "errors": errors})


async def index(request):
    return web.FileResponse(WEB / "index.html")


def make_app():
    app = web.Application()
    app.add_routes([
        web.get("/", index),
        web.get("/api/state", get_state),
        web.put("/api/store", put_store),
        web.post("/api/permit_join", permit_join),
        web.get("/api/permit_state", permit_state),
        web.post("/api/plan", plan),
        web.post("/api/apply", apply),
        web.post("/api/verify", verify),
    ])
    return app


if __name__ == "__main__":
    web.run_app(make_app(), host="0.0.0.0", port=int(os.environ.get("PORT", 8099)))
