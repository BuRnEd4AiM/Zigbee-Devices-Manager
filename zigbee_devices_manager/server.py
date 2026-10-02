"""Backend des Zigbee Devices Manager (Home Assistant Add-on, Ingress)."""
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
    out = []
    for d in devices:
        found = zigbee_source(d)
        if not found:
            continue
        source, ieee = found
        out.append({
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
    return web.json_response({"devices": out, "store": load_store()})


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
                "topic": f"{z2m_base_topic()}/bridge/request/device/rename",
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
    return web.json_response({"ok": not errors, "renamed_devices": done, "renamed_entities": renamed,
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
        web.post("/api/plan", plan),
        web.post("/api/apply", apply),
    ])
    return app


if __name__ == "__main__":
    web.run_app(make_app(), host="0.0.0.0", port=int(os.environ.get("PORT", 8099)))
