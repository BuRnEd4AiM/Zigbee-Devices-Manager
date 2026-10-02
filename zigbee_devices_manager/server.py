"""Backend des Zigbee Devices Manager (Home Assistant Add-on, Ingress)."""
import asyncio
import json
import logging
import os
import re
import time
import uuid
import unicodedata
from pathlib import Path

from aiohttp import ClientError, ClientSession, ClientTimeout, web

DATA = Path(os.environ.get("DATA_DIR", "/data"))
WEB = Path(__file__).parent / "web"
S6_ENV_DIR = Path(os.environ.get("S6_ENV_DIR", "/run/s6/container_environment"))


def read_token():
    """SUPERVISOR_TOKEN aus der Umgebung, sonst aus dem s6-Container-Environment (HA-Add-on-Standard)."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        try:
            token = (S6_ENV_DIR / "SUPERVISOR_TOKEN").read_text().strip()
        except OSError:
            token = None
    return token or None


TOKEN = read_token()
WS_URL = os.environ.get("HA_WS_URL", "ws://supervisor/core/websocket")
STORE_FILE = DATA / "store.json"
log = logging.getLogger("zdm")
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
    try:
        # max_msg_size=0: große Antworten (viele Entitäten) dürfen die Verbindung nicht abbrechen
        async with ClientSession(timeout=ClientTimeout(total=60)) as session, session.ws_connect(WS_URL, max_msg_size=0) as ws:
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
                    raise web.HTTPBadGateway(text=f"{cmd['type']}: {reply.get('error', {}).get('message', 'HA-Fehler')}")
                results.append(reply["result"])
            return results
    except (ClientError, asyncio.TimeoutError, ValueError) as err:
        raise web.HTTPBadGateway(text=f"Keine Verbindung zu Home Assistant ({WS_URL}): {err!r}")


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
    ok, floors = await ha_try({"type": "config/floor_registry/list"})  # ältere HA-Versionen kennen keine Etagen
    if not ok:
        floors = []
    out, bridges = [], {}
    for d in devices:
        if any(dom == "mqtt" and ident.startswith("zigbee2mqtt_bridge_") for dom, ident in d.get("identifiers", [])):
            ident = next(i for dom, i in d["identifiers"] if dom == "mqtt" and i.startswith("zigbee2mqtt_bridge_"))
            bridges[d["id"]] = {"id": d["id"], "source": "z2m", "name": d.get("name_by_user") or d.get("name") or "Zigbee2MQTT",
                                "ieee": ident.removeprefix("zigbee2mqtt_bridge_")}
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
            "area_id": d.get("area_id") or "",
        })
    used = {d["bridge"] for d in out}
    return web.json_response({"devices": out, "store": load_store(),
                              "areas": [{"id": a["area_id"], "name": a["name"], "floor_id": a.get("floor_id") or ""} for a in areas],
                              "floors": [{"id": f["floor_id"], "name": f["name"], "level": f.get("level")} for f in floors],
                              "bridges": [b for b in bridges.values() if b["id"] in used or b["source"] == "z2m"]})


PROGRESS = {}


def prog_start(pid, total):
    if pid:
        PROGRESS[pid] = {"done": 0, "total": max(total, 1), "label": "Starte …"}
        for old in list(PROGRESS)[:-20]:  # alte Einträge verwerfen
            PROGRESS.pop(old, None)


def prog(pid, label, inc=1):
    if pid and pid in PROGRESS:
        p = PROGRESS[pid]
        p["label"] = label
        p["done"] = min(p["done"] + inc, p["total"] - 1)


def prog_end(pid):
    if pid and pid in PROGRESS:
        PROGRESS[pid].update(done=PROGRESS[pid]["total"], label="Fertig")


async def progress(request):
    return web.json_response(PROGRESS.get(request.query.get("id", ""), {"done": 0, "total": 1, "label": "…"}))


async def mqtt_collect(filters, seconds=2.5):
    """Abonniert MQTT-Topics über Home Assistant und sammelt die (auch zurückgehaltenen) Nachrichten."""
    if not TOKEN:
        raise web.HTTPServiceUnavailable(text="Kein SUPERVISOR_TOKEN – läuft nicht als Add-on")
    out = []
    try:
        async with ClientSession() as session, session.ws_connect(WS_URL, max_msg_size=0) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": TOKEN})
            if (await ws.receive_json())["type"] != "auth_ok":
                raise web.HTTPBadGateway(text="Authentifizierung bei Home Assistant fehlgeschlagen")
            for i, topic in enumerate(filters, 1):
                await ws.send_json({"id": i, "type": "mqtt/subscribe", "topic": topic})
            end = time.monotonic() + seconds
            while (left := end - time.monotonic()) > 0:
                try:
                    msg = await asyncio.wait_for(ws.receive_json(), left)
                except asyncio.TimeoutError:
                    break
                if msg.get("type") == "event":
                    out.append((msg["event"].get("topic", ""), msg["event"].get("payload", "")))
    except (ClientError, asyncio.TimeoutError, ValueError) as err:
        raise web.HTTPBadGateway(text=f"Keine Verbindung zu Home Assistant ({WS_URL}): {err!r}")
    return out


async def z2m_devices():
    """IEEE (klein) → {base, name} aus den zurückgehaltenen Nachrichten <base>/bridge/devices aller Z2M-Instanzen."""
    out = {}
    try:
        messages = await mqtt_collect(["+/bridge/devices", "+/+/bridge/devices"], 2.5)
    except web.HTTPException:
        return out
    for topic, payload in messages:
        base = topic.removesuffix("/bridge/devices")
        try:
            data = json.loads(payload)
        except ValueError:
            continue
        for dev in data if isinstance(data, list) else []:
            ieee = (dev.get("ieee_address") or "").lower()
            if ieee:
                out[ieee] = {"base": base, "name": dev.get("friendly_name", "")}
    return out


async def z2m_bases(request):
    """Findet die Zigbee2MQTT-Instanzen über ihre zurückgehaltene Nachricht <base>/bridge/info."""
    found, seen = [], set()
    for topic, payload in await mqtt_collect(["+/bridge/info", "+/+/bridge/info"]):
        base = topic.removesuffix("/bridge/info")
        try:
            info = json.loads(payload)
        except ValueError:
            continue
        if base in seen or not isinstance(info, dict):
            continue
        seen.add(base)
        found.append({"base_topic": base, "ieee": (info.get("coordinator") or {}).get("ieee_address", ""),
                      "version": info.get("version", "")})
    return web.json_response(found)


async def z2m_request(base, action, payload, timeout=12):
    """Sendet eine Anfrage an Zigbee2MQTT und wartet auf dessen Antwort unter <base>/bridge/response/<action>.
    Liefert Z2Ms Antwort ({"status": "ok"|"error", ...}) oder {"status": "timeout"}."""
    if not TOKEN:
        raise web.HTTPServiceUnavailable(text="Kein SUPERVISOR_TOKEN – läuft nicht als Add-on")
    txn = uuid.uuid4().hex
    request_msg = {**payload, "transaction": txn}
    publish = {"type": "call_service", "domain": "mqtt", "service": "publish", "service_data": {
        "topic": f"{base}/bridge/request/{action}", "payload": json.dumps(request_msg)}}
    try:
        async with ClientSession() as session, session.ws_connect(WS_URL, max_msg_size=0) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": TOKEN})
            if (await ws.receive_json())["type"] != "auth_ok":
                raise web.HTTPBadGateway(text="Authentifizierung bei Home Assistant fehlgeschlagen")
            await ws.send_json({"id": 1, "type": "mqtt/subscribe", "topic": f"{base}/bridge/response/{action}"})
            while True:
                reply = await asyncio.wait_for(ws.receive_json(), 10)
                if reply.get("id") == 1 and reply.get("type") == "result":
                    break
            subscribed = reply.get("success", False)
            await ws.send_json({"id": 2, **publish})
            deadline = time.monotonic() + timeout
            while True:
                left = deadline - time.monotonic()
                if left <= 0:
                    return {"status": "timeout" if subscribed else "unknown"}
                try:
                    msg = await asyncio.wait_for(ws.receive_json(), left)
                except asyncio.TimeoutError:
                    return {"status": "timeout" if subscribed else "unknown"}
                if msg.get("id") == 2 and msg.get("type") == "result" and not msg.get("success"):
                    return {"status": "error", "error": msg.get("error", {}).get("message", "mqtt.publish fehlgeschlagen")}
                if msg.get("id") == 2 and msg.get("type") == "result" and not subscribed:
                    return {"status": "unknown"}  # ohne Abo keine Antwort lesbar
                if msg.get("id") == 1 and msg.get("type") == "event":
                    try:
                        data = json.loads(msg["event"]["payload"])
                    except (KeyError, ValueError):
                        continue
                    if data.get("transaction") == txn:
                        return data
    except (ClientError, asyncio.TimeoutError, ValueError) as err:
        raise web.HTTPBadGateway(text=f"Keine Verbindung zu Home Assistant ({WS_URL}): {err!r}")


async def known_bases_hint():
    try:
        bases = [b for t, _ in await mqtt_collect(["+/bridge/info", "+/+/bridge/info"], 2.0) if (b := t.removesuffix("/bridge/info"))]
    except web.HTTPException:
        return ""
    return f" Gefundene Zigbee2MQTT-Basis-Topics: {', '.join(sorted(set(bases)))}." if bases else " Es wurde kein Zigbee2MQTT über MQTT gefunden."


async def z2m_failure(base, result):
    """Menschenlesbare Fehlermeldung, wenn Zigbee2MQTT die Anfrage nicht ausgeführt hat (sonst None)."""
    status = result.get("status")
    if status == "ok" or status == "unknown":
        return None
    if status == "timeout":
        return f"Keine Antwort von Zigbee2MQTT auf „{base}“ – stimmt der Basis-Topic? Läuft Z2M?" + await known_bases_hint()
    return f"Zigbee2MQTT: {result.get('error') or result}"


async def permit_join(request):
    """Aktiviert/beendet das Anlernen (Pairing) am Zigbee2MQTT-Gateway oder bei ZHA."""
    body = await request.json()
    seconds = max(0, min(int(body.get("time", 240)), 254))
    if body.get("source") == "zha":
        cmd = {"type": "call_service", "domain": "zha", "service": "permit", "service_data": {"duration": seconds}}
    else:
        base = safe_topic(body.get("base_topic"))
        failure = await z2m_failure(base, await z2m_request(base, "permit_join", {"time": seconds}, timeout=8))
        if failure:
            raise web.HTTPBadGateway(text=failure)
        return web.json_response({"ok": True, "time": seconds})
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


def common_prefix(object_ids):
    """Gemeinsamer Anfang (an Unterstrichen getrennt) aller Entity-Namen eines Geräts, z. B. s2_bad_tem01 – nur bei ≥ 2 Entitäten."""
    if len(object_ids) < 2:
        return ""
    parts = [o.split("_") for o in object_ids]
    out = []
    for group in zip(*parts):
        if len(set(group)) != 1:
            break
        out.append(group[0])
    return "_".join(out)


def entity_changes(items, entities):
    """Bestimmt, welche Entity-IDs sich beim Umbenennen der Geräte ändern würden.
    Liefert (Änderungen, Übersprungenes, Erklärung je Gerät)."""
    by_dev = {}
    for ent in entities:
        by_dev.setdefault(ent.get("device_id"), []).append(ent)
    existing = {e["entity_id"] for e in entities}
    changes, skipped, info = [], [], []
    for it in items:
        new_slug = slugify(it["name"])
        devents = by_dev.get(it["device_id"], [])
        objs = [e["entity_id"].partition(".")[2] for e in devents]
        candidates = list(dict.fromkeys(
            c for c in (slugify(it.get("old_name") or ""), slugify(it.get("orig_name") or ""), common_prefix(objs)) if c))
        mine = {"device": it["name"], "entities": [e["entity_id"] for e in devents][:6], "count": len(devents), "reason": ""}
        n_before = len(changes) + len(skipped)
        for ent in devents:
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
        if len(changes) + len(skipped) == n_before:
            if not devents:
                mine["reason"] = "none"       # Gerät hat keine Entitäten
            elif new_slug and all(o == new_slug or o.startswith(new_slug + "_") for o in objs):
                mine["reason"] = "already"    # Entity-IDs enthalten den neuen Namen bereits
            else:
                mine["reason"] = "nomatch"    # keine ID beginnt mit dem alten Namen
        info.append(mine)
    return changes, skipped, info


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


async def resolve_areas(body, items):
    """Ziel-Bereich je Gerät (nur wenn „Raum als Bereich setzen“ aktiv und der Bereich sich ändert)."""
    out = {}
    if not body.get("set_area"):
        return out
    areas = (await ha([{"type": "config/area_registry/list"}]))[0]
    by_id = {a["area_id"]: a for a in areas}
    by_name = {a["name"].lower(): a["area_id"] for a in areas}
    for it in items:
        aid = it.get("area_id") if it.get("area_id") in by_id else ""
        name = (it.get("area_name") or "").strip()
        if not aid and name:
            aid = by_name.get(name.lower(), "")
        if not aid and not name:
            continue
        if aid and aid == it.get("current_area_id"):
            continue
        out[it["device_id"]] = {"id": aid, "name": by_id[aid]["name"] if aid else name, "create": not aid}
    return out


async def create_missing_areas(targets, errors):
    """Legt fehlende Bereiche in Home Assistant an (einmal je Name) und trägt die neuen IDs in die Ziele ein."""
    created = {}
    for tgt in targets.values():
        if not tgt["create"]:
            continue
        key = tgt["name"].lower()
        if key not in created:
            ok, res = await ha_try({"type": "config/area_registry/create", "name": tgt["name"]})
            if ok:
                created[key] = res["area_id"]
            else:
                errors.append({"device": f"Bereich {tgt['name']}", "error": res})
        tgt["id"] = created.get(key, "")
    return created


async def plan(request):
    body = await request.json()
    items = parse_request(body)
    changes, skipped, usages, unreadable, notes, info = [], [], [], 0, [], []
    if body.get("rename_entities") and items:
        entities = (await ha([{"type": "config/entity_registry/list"}]))[0]
        changes, skipped, info = entity_changes(items, entities)
        if changes:
            usages, unreadable, notes = await collect_usages(body, {c["old"]: c["new"] for c in changes})
    targets = await resolve_areas(body, items)
    area_changes = [{"device": it["name"], "from": it.get("current_area") or "", "to": targets[it["device_id"]]["name"],
                     "create": targets[it["device_id"]]["create"]} for it in items if it["device_id"] in targets]
    return web.json_response({"entities": changes, "skipped": skipped, "usages": usages,
                              "unreadable": unreadable, "notes": notes, "areas": area_changes, "entity_info": info})


def use_z2m(body):
    """Ob in Zigbee2MQTT umbenannt werden soll (ältere Clients: gekoppelt an „Entity-IDs mitziehen“)."""
    return bool(body.get("rename_z2m", body.get("rename_entities")))


def check(name, status, detail=""):
    return {"name": name, "status": status, "detail": detail}


async def verify_changes(items, renamed, opts, wait=True):
    """Prüft nach dem Umbenennen, ob Geräte, Entity-IDs und Verweise wirklich angepasst sind."""
    checks = []
    # 1. Gerätenamen (Zigbee2MQTT bestätigt asynchron, daher kurz warten)
    deadline = time.monotonic() + (15 if wait and not opts.get("skip_names") else 0)
    while True:
        devices = (await ha([{"type": "config/device_registry/list"}]))[0]
        by_id = {d["id"]: d for d in devices}
        wrong = [it for it in items
                 if (by_id.get(it["device_id"], {}).get("name_by_user") or by_id.get(it["device_id"], {}).get("name")) != it["name"]]
        if not wrong or time.monotonic() >= deadline:
            break
        await asyncio.sleep(1.5)
    if opts.get("skip_names") or not items:
        pass
    elif not wrong:
        checks.append(check("Gerätenamen", "ok", f"{len(items)} Gerät(e) heißen jetzt wie geplant"))
    else:
        names = ", ".join(it["name"] for it in wrong)
        z2m = any(it.get("source") == "z2m" and use_z2m(opts) for it in wrong)
        checks.append(check("Gerätenamen", "warn" if z2m else "fail",
                            f"Noch nicht übernommen: {names}" + (
                                " – Zigbee2MQTT hat die Umbenennung noch nicht bestätigt (Basis-Topic und Z2M-Log prüfen, später erneut prüfen)" if z2m else "")))
    if opts.get("set_area"):
        want = [it for it in items if it.get("area_id")]
        off = [it["name"] for it in want if by_id.get(it["device_id"], {}).get("area_id") != it["area_id"]]
        if want:
            checks.append(check("Bereiche (Räume)", "fail" if off else "ok",
                                f"Bereich nicht gesetzt bei: {', '.join(off)}" if off else f"{len(want)} Gerät(e) sind dem gewählten Bereich zugeordnet"))
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


async def assign_area(request):
    """Ordnet Geräte nur einem Bereich (Raum) zu – ohne sie umzubenennen."""
    body = await request.json()
    body["set_area"] = True
    items = parse_request(body)
    if not items:
        raise web.HTTPBadRequest(text="Keine Geräte angegeben")
    errors, done = [], []
    targets = await resolve_areas(body, items)
    await create_missing_areas(targets, errors)
    for it in items:
        tgt = targets.get(it["device_id"])
        if not tgt or not tgt["id"]:
            continue
        ok, res = await ha_try({"type": "config/device_registry/update", "device_id": it["device_id"], "area_id": tgt["id"]})
        if ok:
            it["area_id"] = tgt["id"]
            done.append(it["device_id"])
        else:
            errors.append({"device": it["name"], "error": res})
    checks = await verify_changes([i for i in items if i["device_id"] in done], [], {"set_area": True, "skip_names": True}, wait=False)
    return web.json_response({"ok": not errors, "checks": checks, "errors": errors, "items": items, "areas_set": len(done)})


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
    z2m_mode = bool(body.get("rename_entities"))  # Entity-IDs in Home Assistant anpassen
    z2m_on = use_z2m(body)                          # Gerät in Zigbee2MQTT umbenennen
    errors, done = [], []
    pid = body.get("progress_id")
    prog_start(pid, len(items) * 2 + 4)
    prog(pid, "Lese Entitäten …", 0)
    entities = (await ha([{"type": "config/entity_registry/list"}]))[0] if z2m_mode else []
    changes, skipped, _info = entity_changes(items, entities) if z2m_mode else ([], [], [])
    targets = await resolve_areas(body, items)
    await create_missing_areas(targets, errors)
    for it in items:
        tgt = targets.get(it["device_id"])
        if tgt and tgt["id"]:
            it["area_id"] = tgt["id"]

    failed_ids = set()
    owners = {}
    if z2m_on and any(i.get("source") == "z2m" for i in items):
        prog(pid, "Suche die Zigbee2MQTT-Instanz der Geräte …", 0)
        owners = await z2m_devices()
    for n, it in enumerate(items, 1):
        prog(pid, f"Benenne um ({n}/{len(items)}): {it['name']}", 0)
        if z2m_on and it.get("source") == "z2m" and it.get("ieee"):
            # In Zigbee2MQTT umbenennen und Z2Ms Antwort abwarten; die HA-Entity-IDs ändern wir selbst, damit wir sie kennen
            owner = owners.get(it["ieee"].lower())
            base = owner["base"] if owner else safe_topic(it.get("base_topic"))  # die Instanz, in der das Gerät wirklich steckt
            result = await z2m_request(base, "device/rename", {"from": it["ieee"], "to": it["name"], "homeassistant_rename": z2m_mode})
            if result.get("status") == "timeout":  # keine Antwort: prüfen, ob Z2M den neuen Namen trotzdem schon führt
                now = (await z2m_devices()).get(it["ieee"].lower())
                if now and now["name"] == it["name"]:
                    result = {"status": "ok"}
            failure = await z2m_failure(base, result)
            if failure and owner is None and owners:
                failure += f" Das Gerät {it['ieee']} wurde in keiner gefundenen Zigbee2MQTT-Instanz gelistet."
            ok, res = (failure is None), failure
            cmd = {}
        else:
            cmd = {"type": "config/device_registry/update", "device_id": it["device_id"], "name_by_user": it["name"]}
            if targets.get(it["device_id"], {}).get("id"):
                cmd["area_id"] = targets[it["device_id"]]["id"]
            ok, res = await ha_try(cmd)
        if ok:
            done.append(it["device_id"])
        else:
            failed_ids.add(it["device_id"])
            errors.append({"device": it["name"], "device_id": it["device_id"], "error": res})
        prog(pid, f"Benannt ({n}/{len(items)}): {it['name']}")
        tgt = targets.get(it["device_id"])
        if ok and tgt and tgt["id"] and "area_id" not in cmd:  # Z2M-Weg: Bereich separat setzen
            ok2, res2 = await ha_try({"type": "config/device_registry/update", "device_id": it["device_id"], "area_id": tgt["id"]})
            if not ok2:
                errors.append({"device": f"Bereich für {it['name']}", "error": res2})

    renamed = []
    z2m_ok = {i["device_id"] for i in items if i["device_id"] in done and i.get("source") == "z2m" and z2m_on}
    ids_by_entity = {e["entity_id"]: e.get("device_id") for e in entities}
    changes = [c for c in changes if ids_by_entity.get(c["old"]) not in failed_ids]  # nichts ändern, wenn Z2M nicht umbenannt hat
    # Z2M benennt mit homeassistant_rename die Entity-IDs ggf. selbst um: kurz abwarten, dann nur Fehlendes selbst erledigen
    fresh = {e["entity_id"] for e in entities}
    if z2m_ok and changes:
        prog(pid, "Warte auf Zigbee2MQTT (Entity-IDs) …", 0)
        for _ in range(4):
            await asyncio.sleep(1.5)
            fresh = {e["entity_id"] for e in (await ha([{"type": "config/entity_registry/list"}]))[0]}
            if all(c["new"] in fresh or ids_by_entity.get(c["old"]) not in z2m_ok for c in changes):
                break
    for ch in changes:
        prog(pid, f"Entity-ID: {ch['old']}")
        if ch["new"] in fresh and ch["old"] not in fresh:
            renamed.append(ch)  # hat Zigbee2MQTT bereits umbenannt
            continue
        ok, res = await ha_try({"type": "config/entity_registry/update",
                                "entity_id": ch["old"], "new_entity_id": ch["new"]})
        (renamed.append(ch) if ok else errors.append({"device": ch["old"], "error": res}))

    changed_refs, unreadable = [], 0
    notes = []
    prog(pid, "Suche Verweise …", 0)
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
    prog(pid, "Prüfe das Ergebnis …", 0)
    checks = await verify_changes([i for i in items if i["device_id"] not in failed_ids], renamed, body) if not body.get("skip_verify") else []
    prog_end(pid)
    return web.json_response({"ok": not errors, "checks": checks, "renamed_devices": done, "renamed_entities": renamed,
                              "skipped": skipped, "updated_references": changed_refs,
                              "unreadable": unreadable, "notes": notes, "errors": errors,
                              "items": items, "areas_set": sum(1 for t in targets.values() if t["id"])})


async def index(request):
    return web.FileResponse(WEB / "index.html")


@web.middleware
async def errors(request, handler):
    """Gibt Fehler als lesbaren Text zurück und schreibt sie ins Add-on-Log."""
    try:
        return await handler(request)
    except web.HTTPException as err:
        if err.status >= 500:
            log.error("%s %s -> %s %s", request.method, request.path, err.status, err.text)
        raise
    except Exception as err:  # noqa: BLE001
        log.exception("%s %s fehlgeschlagen", request.method, request.path)
        return web.Response(status=500, text=f"Interner Fehler: {err!r}")


async def diag(request):
    """Schritt-für-Schritt-Diagnose der Verbindung zu Home Assistant."""
    out = {"supervisor_token": bool(TOKEN), "ws_url": WS_URL, "steps": []}
    for name, cmd in (("Geräte-Registry", {"type": "config/device_registry/list"}),
                      ("Entitäten-Registry", {"type": "config/entity_registry/list"})):
        try:
            res = (await ha([cmd]))[0]
            out["steps"].append({"step": name, "ok": True, "count": len(res)})
            if name == "Geräte-Registry":
                out["zigbee_devices"] = sum(1 for d in res if zigbee_source(d))
        except web.HTTPException as err:
            out["steps"].append({"step": name, "ok": False, "error": err.text})
    out["config_dir"] = {"path": str(HA_CONFIG_DIR), "exists": HA_CONFIG_DIR.is_dir()}
    out["addon_configs_dir"] = {"path": str(ADDON_CONFIGS_DIR), "exists": ADDON_CONFIGS_DIR.is_dir()}
    return web.json_response(out)


async def selftest(app):
    """Beim Start ins Log schreiben, ob Home Assistant erreichbar ist."""
    class Dummy:  # nur für den Aufruf der Diagnose
        pass
    result = json.loads((await diag(Dummy())).text)
    log.info("Start: Token=%s, Zigbee-Geräte=%s, Schritte=%s", result["supervisor_token"],
             result.get("zigbee_devices"), result["steps"])


def make_app():
    app = web.Application(middlewares=[errors])
    app.on_startup.append(selftest)
    app.add_routes([
        web.get("/", index),
        web.get("/api/state", get_state),
        web.get("/api/diag", diag),
        web.put("/api/store", put_store),
        web.post("/api/permit_join", permit_join),
        web.get("/api/permit_state", permit_state),
        web.post("/api/plan", plan),
        web.post("/api/apply", apply),
        web.post("/api/verify", verify),
        web.get("/api/progress", progress),
        web.get("/api/z2m_bases", z2m_bases),
        web.post("/api/assign_area", assign_area),
    ])
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    web.run_app(make_app(), host="0.0.0.0", port=int(os.environ.get("PORT", 8099)))
