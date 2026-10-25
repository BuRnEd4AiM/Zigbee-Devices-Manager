"""Backend des Zigbee Devices Manager (Home Assistant Add-on, Ingress)."""
import asyncio
import hashlib
import json
import logging
import os
import re
import time
import uuid
import unicodedata
from datetime import datetime
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
SUPERVISOR_API = os.environ.get("SUPERVISOR_API", "http://supervisor")
BACKUP_KEEP = 60          # so viele Sicherungen bleiben erhalten
BACKUP_EVERY = 3600       # nach dem Speichern höchstens stündlich automatisch sichern
BACKUP_DAILY = 86400
BACKUP_NAME_RE = re.compile(r"^sicherung-[0-9_-]+-[a-z-]+(-\d+)?\.json$")


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


SOURCE_NAMES = {"zha": "ZHA", "z2m": "Zigbee2MQTT", "matter": "Matter"}
# Matter-Integration: deviceid_<Fabric>-<Node>-MatterNodeDevice, hinter einer Matter-Bridge -<Endpunkt> statt MatterNodeDevice
MATTER_ID_RE = re.compile(r"^deviceid_[0-9A-Fa-f]+-([0-9A-Fa-f]+)-(\w+)$")


def device_source(device):
    """Liefert (Quelle, Kennung) für ZHA-, Zigbee2MQTT- und Matter-Geräte, sonst None. Kennung: IEEE bzw. Matter-Geräte-ID."""
    for domain, ident in device.get("identifiers", []):
        if domain == "zha":
            return "zha", ident
        if domain == "mqtt" and ident.startswith("zigbee2mqtt_"):
            return "z2m", ident.removeprefix("zigbee2mqtt_")
        if domain == "matter" and ident.startswith("deviceid_"):
            return "matter", ident
    return None


def matter_node(ident):
    """Node-ID und Endpunkt (nur bei Geräten hinter einer Matter-Bridge) aus der Matter-Geräte-ID."""
    m = MATTER_ID_RE.match(ident)
    if not m:
        return None, None
    return int(m.group(1), 16), int(m.group(2)) if m.group(2).isdigit() else None


def load_store():
    try:
        return json.loads(STORE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def write_json(path, data):
    """Schreibt erst in eine Hilfsdatei und tauscht dann aus – ein Absturz mitten im Schreiben hinterlässt keine halbe Datei."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, path)


def collect_devices(devices, areas):
    """Zigbee-Geräte (ZHA und Zigbee2MQTT), Matter-Geräte (Thread/WLAN) und ihre Gateways aus der Geräte-Registry."""
    area_names = {a["area_id"]: a["name"] for a in areas}
    out, bridges = [], {}
    for d in devices:
        if any(dom == "mqtt" and ident.startswith("zigbee2mqtt_bridge_") for dom, ident in d.get("identifiers", [])):
            ident = next(i for dom, i in d["identifiers"] if dom == "mqtt" and i.startswith("zigbee2mqtt_bridge_"))
            bridges[d["id"]] = {"id": d["id"], "source": "z2m", "name": d.get("name_by_user") or d.get("name") or "Zigbee2MQTT",
                                "ieee": ident.removeprefix("zigbee2mqtt_bridge_"), "config_url": d.get("configuration_url") or ""}
            continue
        found = device_source(d)
        if not found:
            continue
        source, ident = found
        matter = source == "matter"
        ieee = "" if matter else ident
        # Matter: ein gemeinsames Gateway – auch für Geräte hinter einer Matter-Bridge (deren via_device ist die Bridge selbst)
        bridge = "matter" if matter else d.get("via_device_id") or source
        if bridge not in bridges:
            bridges.setdefault(bridge, {"id": bridge, "source": source, "name": SOURCE_NAMES[source]})
        out.append({
            "bridge": bridge,
            "id": d["id"],
            "name": d.get("name_by_user") or d.get("name") or ident,
            "orig_name": d.get("name") or "",
            # Z2M liefert den Friendly-Name als Gerätenamen; neu ist ein Z2M-Gerät nur, solange es noch seine IEEE als Namen trägt
            "is_new": not d.get("name_by_user") and (source != "z2m" or (d.get("name") or "").lower() in ("", ieee.lower())),
            "manufacturer": d.get("manufacturer") or "",
            "model": d.get("model") or "",
            "ieee": ieee,
            "source": source,
            "area": area_names.get(d.get("area_id"), ""),
            "area_id": d.get("area_id") or "",
            # Link zur Geräteseite in der Z2M-Oberfläche – setzt Zigbee2MQTT selbst, wenn dort frontend.url eingetragen ist
            "config_url": d.get("configuration_url") or "",
        })
        if matter:
            out[-1]["node"], out[-1]["endpoint"] = matter_node(ident)
    return out, bridges


async def get_state(request):
    devices, areas = await ha([
        {"type": "config/device_registry/list"},
        {"type": "config/area_registry/list"},
    ])
    ok, floors = await ha_try({"type": "config/floor_registry/list"})  # ältere HA-Versionen kennen keine Etagen
    if not ok:
        floors = []
    out, bridges = collect_devices(devices, areas)
    ok, entities = await ha_try({"type": "config/entity_registry/list"})
    if ok:
        mark_stale_ids(out, entities, devices, areas)
    used = {d["bridge"] for d in out}
    restored = dict(RESTORED)
    RESTORED.clear()  # Hinweis nur einmal zeigen
    return web.json_response({"devices": out, "store": load_store(), "restored": restored or None,
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
        frontend = (info.get("config") or {}).get("frontend") or {}
        found.append({"base_topic": base, "ieee": (info.get("coordinator") or {}).get("ieee_address", ""),
                      "version": info.get("version", ""),
                      # Oberfläche: Paket bestimmt das Link-Format (#/device/0/<ieee> bei windfront), url ist frontend.url
                      "frontend": {"package": frontend.get("package", ""), "url": frontend.get("url", "")}})
    return web.json_response(found)


async def supervisor_get(http, path):
    async with http.get(f"{SUPERVISOR_API}{path}") as r:
        if r.status != 200:
            raise web.HTTPBadGateway(text=f"Supervisor {path}: HTTP {r.status}")
        return (await r.json()).get("data") or {}


async def z2m_uis(request):
    """Installierte Zigbee2MQTT-Add-ons mit Oberfläche (Ingress) – Ziel für den Knopf „Gerät in Z2M öffnen“."""
    out = []
    if not TOKEN:
        return web.json_response(out)
    try:
        async with ClientSession(headers={"Authorization": f"Bearer {TOKEN}"}, timeout=ClientTimeout(total=10)) as http:
            for app in (await supervisor_get(http, "/supervisor/info")).get("addons") or []:
                if "zigbee2mqtt" not in f"{app.get('slug', '')} {app.get('name', '')}".lower().replace(" ", ""):
                    continue
                info = await supervisor_get(http, f"/addons/{app['slug']}/info")
                if info.get("ingress") and info.get("ingress_url"):
                    out.append({"slug": app["slug"], "name": info.get("name") or app.get("name") or app["slug"],
                                "url": info["ingress_url"], "state": info.get("state", "")})
    except (ClientError, asyncio.TimeoutError, ValueError, KeyError, web.HTTPException) as err:
        log.warning("Zigbee2MQTT-Add-ons nicht lesbar: %r", err)
    return web.json_response(out)


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


async def found_bases():
    """Basis-Topics der laufenden Zigbee2MQTT-Instanzen (über ihr zurückgehaltenes <base>/bridge/info); None = MQTT nicht lesbar."""
    try:
        return sorted({b for t, _ in await mqtt_collect(["+/bridge/info", "+/+/bridge/info"], 2.0) if (b := t.removesuffix("/bridge/info"))})
    except web.HTTPException:
        return None


async def known_bases_hint():
    bases = await found_bases()
    if bases is None:
        return ""
    return f" Gefundene Zigbee2MQTT-Basis-Topics: {', '.join(bases)}." if bases else " Es wurde kein Zigbee2MQTT über MQTT gefunden."


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
        payload = {"time": seconds}
        via = body.get("device")
        if seconds and isinstance(via, str) and 0 < len(via) <= 100:
            payload["device"] = via  # nur über diesen Router (IEEE oder Name) anlernen – das Gerät hängt danach an ihm
        failure = await z2m_failure(base, await z2m_request(base, "permit_join", payload, timeout=8))
        if failure:
            raise web.HTTPBadGateway(text=failure)
        return web.json_response({"ok": True, "time": seconds, "device": payload.get("device", "")})
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
    save_store(await request.json())
    # höchstens stündlich sichern; ein unveränderter Stand wird übersprungen und erst nach 5 Minuten erneut verglichen
    if time.time() - newest_backup_time() >= BACKUP_EVERY and time.time() - LAST_AUTO[0] >= 300:
        LAST_AUTO[0] = time.time()
        background(safe_backup("auto"))
    return web.json_response({"ok": True})


# ---------- Sicherungen ----------
RESTORED = {}       # wurde beim Start aus einer Sicherung wiederhergestellt: Hinweis für die Oberfläche
LAST_AUTO = [0.0]
BACKUP_LOCK = asyncio.Lock()
TASKS = set()


def background(coro):
    task = asyncio.create_task(coro)
    TASKS.add(task)
    task.add_done_callback(TASKS.discard)


def backup_root():
    """Im HA-Konfigurationsordner überstehen die Sicherungen eine Neuinstallation des Add-ons und sind in jedem HA-Backup;
    ohne eingebundenen Ordner bleiben sie unter /data."""
    root = HA_CONFIG_DIR / "zigbee_devices_manager"
    if HA_CONFIG_DIR.is_dir():  # nicht eingebunden: sonst landete alles im flüchtigen Container-Dateisystem
        try:
            (root / "backups").mkdir(parents=True, exist_ok=True)
            return root
        except OSError:
            pass
    return DATA / "sicherung"


def backup_files():
    folder = backup_root() / "backups"
    if not folder.is_dir():
        return []
    # neueste zuerst; der Zeitstempel im Namen hat nur Sekunden
    return sorted((p for p in folder.glob("sicherung-*.json") if BACKUP_NAME_RE.match(p.name)), key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True)


def newest_backup_time():
    files = backup_files()
    return files[0].stat().st_mtime if files else 0


def read_backup(name):
    if not BACKUP_NAME_RE.match(name or ""):
        raise web.HTTPBadRequest(text="Ungültiger Dateiname")
    try:
        return json.loads((backup_root() / "backups" / name).read_text())
    except (OSError, ValueError) as err:
        raise web.HTTPNotFound(text=f"Sicherung {name} nicht lesbar: {err}")


def save_store(store):
    """Speichert die Einstellungen und legt eine Kopie neben die Sicherungen (für die Wiederherstellung nach Neuinstallation)."""
    write_json(STORE_FILE, store)
    try:
        write_json(backup_root() / "store.json", store)
    except OSError as err:
        log.warning("Kopie der Einstellungen nicht schreibbar: %r", err)


def valid_store(data):
    return isinstance(data, dict) and isinstance(data.get("scheme"), dict) and bool(data["scheme"].get("pattern"))


async def snapshot_devices():
    devices, areas = await ha([{"type": "config/device_registry/list"}, {"type": "config/area_registry/list"}])
    out, _ = collect_devices(devices, areas)
    keys = ("id", "ieee", "source", "name", "area", "manufacturer", "model")
    return [{k: d[k] for k in keys} for d in out]


async def make_backup(reason, force=False):
    """Sichert Einstellungen (Schema, Zuordnungen, Gateways …) und die Geräteliste aus HA. Unveränderter Stand wird nicht doppelt gesichert."""
    async with BACKUP_LOCK:
        store = load_store()
        if not valid_store(store):
            return None
        try:
            devices = await snapshot_devices()
        except web.HTTPException as err:
            log.warning("Sicherung ohne Geräteliste (HA nicht erreichbar): %s", err.text)
            devices = None
        digest = hashlib.sha256(json.dumps({"store": store, "devices": devices}, sort_keys=True).encode()).hexdigest()
        files = backup_files()
        if not force and files:
            try:
                last = json.loads(files[0].read_text())
                if last.get("hash") == digest or (devices is None and last.get("store") == store):
                    return None
            except (OSError, ValueError):
                pass
        now = datetime.now().astimezone()
        folder = backup_root() / "backups"
        path, n = folder / f"sicherung-{now:%Y-%m-%d_%H%M%S}-{reason}.json", 1
        while path.exists():
            n += 1
            path = folder / f"sicherung-{now:%Y-%m-%d_%H%M%S}-{reason}-{n}.json"
        write_json(path, {"format": "zigbee-devices-manager-backup", "version": 1, "created": now.isoformat(timespec="seconds"),
                          "reason": reason, "hash": digest, "store": store, "devices": devices or []})
        for old in backup_files()[BACKUP_KEEP:]:
            old.unlink(missing_ok=True)
        log.info("Sicherung angelegt: %s", path)
        return path.name


async def safe_backup(reason):
    """Sicherung vor einer Änderung – ein Fehler hier darf das Umbenennen nicht verhindern."""
    try:
        await make_backup(reason)
    except Exception:  # noqa: BLE001
        log.exception("Sicherung „%s“ fehlgeschlagen", reason)


def backup_entry(path):
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    store = data.get("store") or {}
    return {"file": path.name, "created": data.get("created", ""), "reason": data.get("reason", ""),
            "devices": len(data.get("devices") or []), "assigned": len(store.get("meta") or {}),
            "rooms": len((store.get("scheme") or {}).get("rooms") or []), "pattern": (store.get("scheme") or {}).get("pattern", "")}


async def list_backups(request):
    root = backup_root()
    persistent = root.parent == HA_CONFIG_DIR
    # so heißt der Ordner im File editor / in der Samba-Freigabe von HA
    return web.json_response({"dir": "/config/zigbee_devices_manager/backups" if persistent else str(root / "backups"), "persistent": persistent,
                              "keep": BACKUP_KEEP, "items": [e for p in backup_files() if (e := backup_entry(p))]})


async def create_backup(request):
    name = await make_backup("manuell", force=True)
    if not name:
        raise web.HTTPConflict(text="Noch nichts zu sichern – es sind keine Einstellungen gespeichert")
    return web.json_response({"ok": True, "file": name})


async def get_backup(request):
    data = read_backup(request.match_info["name"])
    return web.json_response(data, headers={"Content-Disposition": f'attachment; filename="{request.match_info["name"]}"'})


async def restore_backup(request):
    """Spielt eine Sicherung (aus dem Ordner oder hochgeladen) zurück. Der aktuelle Stand wird vorher selbst gesichert.
    Namen in HA/Z2M bleiben unverändert – zurück kommen Schema, Zuordnungen, geplante Geräte, Gateways und Haken."""
    body = await request.json()
    data = read_backup(body["file"]) if body.get("file") else body.get("backup")
    store = data.get("store") if isinstance(data, dict) and "store" in data else data
    if not valid_store(store):
        raise web.HTTPBadRequest(text="Keine gültige Sicherung (Namensschema fehlt)")
    await make_backup("vor-wiederherstellen")
    save_store(store)
    return web.json_response({"ok": True})


def restore_on_start():
    """Fehlt /data/store.json (z. B. nach Neuinstallation) oder ist sie kaputt, kommt der letzte gesicherte Stand zurück."""
    if STORE_FILE.exists():
        try:
            json.loads(STORE_FILE.read_text())
            return
        except OSError:
            return
        except ValueError:
            broken = STORE_FILE.with_name(f"store.json.defekt-{time.strftime('%Y%m%d-%H%M%S')}")
            os.replace(STORE_FILE, broken)
            log.warning("store.json war unlesbar, beiseitegelegt als %s", broken)
    root = backup_root()
    candidates = [(root / "store.json", "Kopie der Einstellungen")] + [(p, p.name) for p in backup_files()]
    for path, label in candidates:
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        store = data.get("store") if isinstance(data, dict) and "store" in data else data
        if valid_store(store):
            write_json(STORE_FILE, store)
            RESTORED.update(source=label, created=data.get("created") or datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds"))
            log.warning("Einstellungen aus %s wiederhergestellt", path)
            return


async def backup_loop(app):
    """Einmal am Tag sichern (erstmals kurz nach dem Start) – auch Umbenennungen außerhalb des Add-ons landen so in der Geräteliste."""
    async def run():
        await asyncio.sleep(60)
        checked = 0
        while True:
            if time.time() - max(newest_backup_time(), checked) >= BACKUP_DAILY - 120:
                checked = time.time()
                await safe_backup("taeglich")
            await asyncio.sleep(3600)
    restore_on_start()
    app["backup_task"] = asyncio.create_task(run())


async def stop_backup_loop(app):
    app["backup_task"].cancel()


# ---------- Netzwerk (Reiter „Netzwerk“) ----------
NETMAP_TIMEOUT = 900   # Z2M fragt jeden Router einzeln ab; antwortet einer nicht, kostet er ~25 s (Wartezeit, 5 s Pause, 2. Versuch)
SCANS = {}             # Basis-Topic → {"running", "started", "finished", "error", "z2m": Fortschritt laut Z2M-Log}
NO_LQI_RE = re.compile(r"Failed to execute LQI for '(.+)'")


def netmap_file(base):
    return DATA / "networkmap" / f"{slugify(base) or 'zigbee2mqtt'}.json"


def iso_now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def newer(a, b):
    """Liefert True, wenn Zeitpunkt a (ISO) nach b liegt; Unlesbares zählt als älter."""
    def parse(v):
        try:
            return datetime.fromisoformat(v).timestamp()
        except (TypeError, ValueError):
            return 0
    return parse(a) > parse(b)


async def sensor_networkmap(coordinator):
    """Networkmap aus einem vorhandenen HA-Sensor (json_attributes mit nodes/links), erkannt am Koordinator der Instanz."""
    if not coordinator:
        return None
    ok, states = await ha_try({"type": "get_states"})
    for st in states if ok else []:
        attrs = st.get("attributes") or {}
        if not (st["entity_id"].startswith("sensor.") and isinstance(attrs.get("nodes"), list) and isinstance(attrs.get("links"), list)):
            continue
        if any(isinstance(n, dict) and n.get("type") == "Coordinator" and str(n.get("ieeeAddr", "")).lower() == coordinator.lower()
               for n in attrs["nodes"]):
            return {"value": {"nodes": attrs["nodes"], "links": attrs["links"]}, "scanned_at": st.get("last_updated", ""),
                    "source": st["entity_id"]}
    return None


async def get_networkmap(request):
    """Letzter Scan einer Instanz: eigener Scan des Add-ons oder – wenn neuer – ein vorhandener Networkmap-Sensor in HA."""
    base = safe_topic(request.query["base_topic"]) if request.query.get("base_topic") else ""
    if request.query.get("status"):  # nur der Stand eines laufenden Scans (wird während des Scans alle 2 s abgefragt)
        return web.json_response({"base_topic": base, "scan": SCANS.get(base) or {}})
    data = {}
    if base:
        try:
            data = json.loads(netmap_file(base).read_text())
        except (OSError, ValueError):
            pass
    sensor = await sensor_networkmap(request.query.get("coordinator", ""))
    if sensor and newer(sensor["scanned_at"], data.get("scanned_at")):
        data = sensor
    return web.json_response({"base_topic": base, "scan": SCANS.get(base) or {}, **data})


async def watch_scan_log(base, state):
    """Liest während des Scans das Log von Zigbee2MQTT (<base>/bridge/logging, Stufe info und höher) mit:
    ob Z2M den Scan begonnen/beendet hat und welche Router nicht antworten – für die Statuszeile im Reiter."""
    prog = state["z2m"]
    try:
        async with ClientSession() as session, session.ws_connect(WS_URL, max_msg_size=0) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": TOKEN})
            if (await ws.receive_json())["type"] != "auth_ok":
                return
            await ws.send_json({"id": 1, "type": "mqtt/subscribe", "topic": f"{base}/bridge/logging"})
            while True:
                msg = await ws.receive_json()
                if msg.get("type") != "event":
                    continue
                try:
                    text = str(json.loads(msg["event"]["payload"]).get("message", ""))
                except (KeyError, ValueError, AttributeError):
                    continue
                if text.startswith("Starting network scan"):
                    prog["started"] = True
                elif text.startswith("Network scan finished"):
                    prog["finished"] = True
                elif m := NO_LQI_RE.search(text):
                    if m.group(1) not in prog["no_answer"]:
                        prog["no_answer"].append(m.group(1))
    except (ClientError, asyncio.TimeoutError, ValueError, TypeError):
        pass  # nur Anzeige – der Scan selbst läuft unabhängig davon


async def run_networkmap(base):
    state = SCANS[base]
    watcher = asyncio.create_task(watch_scan_log(base, state))
    try:
        await asyncio.sleep(0.5)  # Log-Abo steht, bevor die Anfrage rausgeht
        result = await z2m_request(base, "networkmap", {"type": "raw", "routes": False}, timeout=NETMAP_TIMEOUT)
        failure = await z2m_failure(base, result)
        prog = state["z2m"]
        if result.get("status") == "timeout" and prog["finished"]:
            failure = "Zigbee2MQTT meldet den Scan als fertig, die Antwort kam aber nicht beim Add-on an. Bitte erneut versuchen."
        elif result.get("status") == "timeout" and prog["started"]:
            failure = f"Zigbee2MQTT scannt nach {NETMAP_TIMEOUT // 60} Minuten noch immer. Router ohne Antwort: {', '.join(prog['no_answer']) or 'keine gemeldet'}."
        elif result.get("status") == "timeout" and base in (await found_bases() or []):
            # Basis-Topic stimmt – Z2M ist nur langsam (meist Router, die nicht antworten); das Ergebnis kommt evtl. noch über den Sensor
            failure = (f"Zigbee2MQTT („{base}“) hat nach {NETMAP_TIMEOUT // 60} Minuten nicht geantwortet. Der Basis-Topic stimmt – "
                       "meist antworten einzelne Router nicht (z. B. Lampen am Wandschalter aus). Kommt das Ergebnis später, zeigt der Reiter es über den Networkmap-Sensor an.")
        value = (result.get("data") or {}).get("value") if isinstance(result.get("data"), dict) else None
        if not failure and not (isinstance(value, dict) and isinstance(value.get("nodes"), list)):
            failure = "Zigbee2MQTT hat keine Networkmap geliefert" + (f" ({result.get('status')})" if result.get("status") else "")
        if failure:
            state.update(error=failure)
            return
        write_json(netmap_file(base), {"base_topic": base, "scanned_at": iso_now(), "value": value, "source": "scan"})
        state.update(error="")
    except Exception as err:  # noqa: BLE001
        log.exception("Netzwerk-Scan für %s fehlgeschlagen", base)
        state.update(error=f"Scan fehlgeschlagen: {getattr(err, 'text', None) or err!r}")
    finally:
        watcher.cancel()
        state.update(running=False, finished=iso_now())


async def start_networkmap(request):
    """Startet den Scan im Hintergrund (er dauert oft länger als eine HTTP-Anfrage warten sollte); die Oberfläche fragt nach."""
    base = safe_topic((await request.json()).get("base_topic"))
    if not (SCANS.get(base) or {}).get("running"):
        SCANS[base] = {"running": True, "started": iso_now(), "finished": "", "error": "",
                       "z2m": {"started": False, "finished": False, "no_answer": []}}
        background(run_networkmap(base))
    return web.json_response(SCANS[base])


def store_networkmap(topic, payload):
    """Speichert eine Netzwerkkarte, die Zigbee2MQTT auf <base>/bridge/response/networkmap verschickt hat (raw-Format)."""
    base = topic.removesuffix("/bridge/response/networkmap")
    if base == topic or not TOPIC_RE.match(base):
        return
    try:
        msg = json.loads(payload)
    except (TypeError, ValueError):
        return
    data = msg.get("data") if isinstance(msg, dict) else None
    if not isinstance(data, dict) or msg.get("status") != "ok" or data.get("type") != "raw":
        return  # Fehlermeldung oder anderes Format (graphviz/plantuml)
    value = data.get("value")
    if isinstance(value, dict) and isinstance(value.get("nodes"), list):
        write_json(netmap_file(base), {"base_topic": base, "scanned_at": iso_now(), "value": value, "source": "zigbee2mqtt"})
        log.info("Netzwerkkarte von %s übernommen (%d Geräte)", base, len(value["nodes"]))


async def netmap_listener(app):
    """Hört dauerhaft auf die Netzwerkkarten aller Zigbee2MQTT-Instanzen. Wird die Karte irgendwo geladen – in der Oberfläche
    von Zigbee2MQTT („Netzwerk“), per Automation oder hier –, landet sie automatisch im Reiter „Netzwerk“."""
    async def run():
        delay = 5
        while True:
            try:
                async with ClientSession() as session, session.ws_connect(WS_URL, max_msg_size=0) as ws:
                    await ws.receive_json()
                    await ws.send_json({"type": "auth", "access_token": TOKEN})
                    if (await ws.receive_json())["type"] != "auth_ok":
                        raise ValueError("Authentifizierung fehlgeschlagen")
                    for i, topic in enumerate(["+/bridge/response/networkmap", "+/+/bridge/response/networkmap"], 1):
                        await ws.send_json({"id": i, "type": "mqtt/subscribe", "topic": topic})
                    delay = 5
                    while True:
                        msg = await ws.receive_json()
                        if msg.get("type") == "event":
                            store_networkmap(msg["event"].get("topic", ""), msg["event"].get("payload", ""))
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 – Verbindung weg (z. B. HA-Neustart): später neu verbinden
                log.debug("Netzwerkkarten-Abo unterbrochen: %r", err)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 300)
    if TOKEN:
        app["netmap_task"] = asyncio.create_task(run())


async def stop_netmap_listener(app):
    if "netmap_task" in app:
        app["netmap_task"].cancel()


async def tree_js(request):
    return web.FileResponse(WEB / "zigbee-tree.js", headers={"Cache-Control": "no-cache"})


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


Z2M_UID_RE = re.compile(r"^0x[0-9a-fA-F]{16}_(.+)$")


def z2m_suffix(ent, domain, obj):
    """Endung einer Zigbee2MQTT-Entität hinter dem Gerätenamen (z. B. "_update_available", beim Licht selbst ""), abgelesen
    an der unique_id <IEEE>_<Objekt-ID>_<Basis-Topic>. Z2M lässt den Typ vorn weg (light → light.<name>, light_l1 → _l1).
    None, wenn die ID nicht dazu passt (keine Z2M-Entität oder eigene Entity-ID)."""
    m = Z2M_UID_RE.match(ent.get("unique_id") or "") if ent.get("platform") == "mqtt" else None
    if not m:
        return None
    tokens = m.group(1).split("_")
    start = 1 if tokens[0] == domain else 0
    for k in range(len(tokens), start - 1, -1):  # längste zuerst; hinten hängt der Basis-Topic
        suffix = "".join("_" + t for t in tokens[start:k])
        if obj.endswith(suffix) and len(obj) > len(suffix):
            return suffix
    return None


def id_stems(names, area_names, devents, new_slug=""):
    """Mögliche Gerätenamen-Teile am Anfang der Entity-IDs eines Geräts, wichtigste zuerst: alter Name und Name der
    Integration – auch mit einem Bereich davor, denn Home Assistant legt neue Entity-IDs als <Bereich>_<Gerät>_<Entität> an
    (z. B. light.wohnzimmer_s2_wzel03). Sonst eine Vermutung aus den IDs, die noch keinem dieser Namen folgen: ihr
    gemeinsamer Anfang (ab zwei IDs), bei nur einer die ID der Haupt-Entität (ohne eigenen Namen, z. B. das Licht selbst).
    Eine Entität ohne eigenen Namen, die über den gemeinsamen Anfang hinausgeht (h1_wz_tas02_update_available), ist keine
    Haupt-Entität. Und folgen manche IDs schon dem neuen Namen (h1_wzfl_tas02_…), andere nicht (h1_wz_tas02_…), bliebe
    über alle nur „h1“ – daraus würde h1_wzfl_tas02_wz_tas02_…; eine Vermutung, die nur der Anfang des neuen Namens ist,
    fällt deshalb weg."""
    names = [n for n in names if n]
    named = [s for s in dict.fromkeys([slugify(n) for n in names] + [slugify(f"{a} {n}") for a in area_names for n in names]) if s]
    follows = lambda o, stem: o == stem or o.startswith(stem + "_")  # noqa: E731
    rest = [(e, o) for e in devents if not any(follows(o := e["entity_id"].partition(".")[2], s) for s in [new_slug, *named] if s)]
    plausible = lambda g: g and not new_slug.startswith(g + "_")  # noqa: E731
    common = common_prefix([o for _, o in rest])
    main = sorted({o for e, o in rest if "original_name" in e and not e["original_name"]}, key=lambda o: (len(o), o))
    return list(dict.fromkeys(named + ([common] if plausible(common) else [g for g in main if plausible(g)])))


def entity_changes(items, entities, devices=(), areas=()):
    """Bestimmt, welche Entity-IDs sich beim Umbenennen der Geräte ändern würden. devices/areas (Registries) liefern
    die Bereichsnamen, die Home Assistant vor neue Entity-IDs setzt. Liefert (Änderungen, Übersprungenes, Erklärung je Gerät)."""
    by_dev = {}
    for ent in entities:
        by_dev.setdefault(ent.get("device_id"), []).append(ent)
    area_names = {a["area_id"]: a["name"] for a in areas}
    dev_area = {d["id"]: d.get("area_id") for d in devices}
    existing = {e["entity_id"] for e in entities}
    changes, skipped, info = [], [], []
    for it in items:
        new_slug = slugify(it["name"])
        devents = by_dev.get(it["device_id"], [])
        objs = [e["entity_id"].partition(".")[2] for e in devents]
        # Bereich des Geräts und seiner Entitäten zuerst, dann alle übrigen (das Gerät kann inzwischen umgezogen sein)
        own = [area_names[a] for a in [dev_area.get(it["device_id"])] + [e.get("area_id") for e in devents] if a in area_names]
        candidates = id_stems([it.get("old_name"), it.get("orig_name")], list(dict.fromkeys(own + list(area_names.values()))), devents, new_slug)
        mine = {"device": it["name"], "entities": [e["entity_id"] for e in devents][:6], "count": len(devents), "reason": ""}
        n_before = len(changes) + len(skipped)
        for ent in devents:
            domain, _, obj = ent["entity_id"].partition(".")
            suffix = z2m_suffix(ent, domain, obj)  # bei Zigbee2MQTT steht die Endung fest – nur der Teil davor ist der Gerätename
            for cand in candidates if suffix is None else [obj[:len(obj) - len(suffix)]]:
                if new_slug and (obj == cand or obj.startswith(cand + "_")):
                    new_id = f"{domain}.{new_slug}{obj[len(cand):]}"
                    if new_id == ent["entity_id"]:
                        break
                    if new_id in existing:
                        skipped.append({"old": ent["entity_id"], "new": new_id, "reason": "ID existiert bereits", "device_id": it["device_id"]})
                    else:
                        existing.add(new_id)
                        changes.append({"old": ent["entity_id"], "new": new_id, "device_id": it["device_id"]})
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


async def entity_registries():
    """Entitäten-, Geräte- und Bereichs-Registry – was entity_changes braucht."""
    return await ha([{"type": "config/entity_registry/list"}, {"type": "config/device_registry/list"},
                     {"type": "config/area_registry/list"}])


def mark_stale_ids(out, entities, devices, areas):
    """Benannte Geräte, deren Entity-IDs nicht zum Gerätenamen passen – z. B. noch der Name vom Anlernen über Matter,
    oft mit dem Bereich davor (light.wohnzimmer_s2_wzel03 statt light.s2_wzel_lsp03). Je Gerät landen die IDs, die
    „Entity-IDs angleichen“ ändern würde, unter "stale_ids"; die, deren neue ID es schon gibt (doppelte Entität, meist eine
    Altlast vom früheren Namen), unter "dup_ids" – Angleichen kann sie nicht auflösen."""
    named = [d for d in out if not d["is_new"]]
    items = [{"device_id": d["id"], "name": d["name"], "old_name": d["name"], "orig_name": d["orig_name"]} for d in named]
    changes, skipped, _ = entity_changes(items, entities, devices, areas)
    by_dev = {}
    for key, rows in (("stale_ids", changes), ("dup_ids", skipped)):
        for c in rows:
            by_dev.setdefault((c["device_id"], key), []).append({"old": c["old"], "new": c["new"]})
    for d in named:
        for key in ("stale_ids", "dup_ids"):
            d[key] = sorted(by_dev.get((d["id"], key), []), key=lambda c: c["old"])


# ---------- Doppelte Entitäten (alte ID neben der schon vorhandenen neuen) ----------
REMOVABLE = ("verwaist", "deaktiviert")


def entity_status(ent, state):
    """aktiv | verwaist (die Integration liefert die Entität nicht mehr; HA hält nur den letzten Zustand) | deaktiviert |
    ohne Zustand (z. B. Integration nicht geladen)."""
    if ent.get("disabled_by"):
        return "deaktiviert"
    if state is None:
        return "ohne Zustand"
    return "verwaist" if state.get("attributes", {}).get("restored") else "aktiv"


async def entity_statuses():
    entities, states = await ha([{"type": "config/entity_registry/list"}, {"type": "get_states"}])
    by_id = {st["entity_id"]: st for st in states}
    return {e["entity_id"]: {"status": entity_status(e, by_id.get(e["entity_id"])), "device_id": e.get("device_id") or "",
                             "name": (by_id.get(e["entity_id"]) or {}).get("attributes", {}).get("friendly_name", "")} for e in entities}


async def entity_info(request):
    """Zustand der Entitäten doppelter Paare und wo sie verwendet werden (Automationen, Skripte, Szenen, Dashboards)."""
    ids = [i for i in (await request.json()).get("entity_ids", []) if isinstance(i, str) and ENTITY_REF_RE.fullmatch(i)][:200]
    status = await entity_statuses()
    usages, unreadable, _ = await collect_usages({"update_references": True}, {i: i for i in ids}) if ids else ([], 0, [])
    return web.json_response({"entities": {i: status.get(i) for i in ids}, "usages": usages, "unreadable": unreadable})


async def dedupe_entities(request):
    """Löst doppelte Entitäten auf – am Ende gibt es nur noch die neue ID, und Verweise auf die alte zeigen auf sie.
    remove_old: die alte (verwaiste/deaktivierte) Entität entfernen. replace_new: die verwaiste/deaktivierte Entität unter der
    neuen ID entfernen und die alte (aktive) dorthin umbenennen. Aktive Entitäten werden nie entfernt. Vorher wird gesichert."""
    body = await request.json()
    pairs = [p for p in body.get("pairs", []) if isinstance(p, dict) and p.get("action") in ("remove_old", "replace_new")]
    if not pairs:
        raise web.HTTPBadRequest(text="Nichts zu tun")
    status = await entity_statuses()
    await safe_backup("vor-entfernen")
    done, errors, mapping = [], [], {}
    for p in pairs:
        old, new, action = p.get("old"), p.get("new"), p["action"]
        st_old, st_new = (status.get(old) or {}).get("status"), (status.get(new) or {}).get("status")
        if action == "remove_old" and st_old in REMOVABLE and st_new:
            ok, res = await ha_try({"type": "config/entity_registry/remove", "entity_id": old})
        elif action == "replace_new" and st_new in REMOVABLE and st_old:
            ok, res = await ha_try({"type": "config/entity_registry/remove", "entity_id": new})
            if ok:
                ok, res = await ha_try({"type": "config/entity_registry/update", "entity_id": old, "new_entity_id": new})
        else:
            errors.append({"device": old or "?", "error": f"Nicht möglich: {old} ist {st_old or 'nicht vorhanden'}, {new} ist {st_new or 'nicht vorhanden'} – "
                                                         "entfernt werden nur verwaiste oder deaktivierte Entitäten"})
            continue
        if ok:
            mapping[old] = new
            done.append({"old": old, "new": new, "action": action})
        else:
            errors.append({"device": old, "error": res})
    changed = []
    if mapping:
        log_renames([{"old": o, "new": n} for o, n in mapping.items()])
        changed, _, _, ref_errors = await replace_references({"update_references": True, "update_yaml": body.get("update_yaml"),
                                                              "update_nodered": body.get("update_nodered")}, mapping)
        errors += ref_errors
    return web.json_response({"done": done, "errors": errors, "updated_references": changed})


def ekey(ent):
    """Bleibt beim Umbenennen gleich (auch wenn Z2M die Entität löscht und neu anlegt): Typ + Plattform + eindeutige ID.
    Der Typ gehört dazu: Zigbee2MQTT legt für eine einstellbare Eigenschaft (z. B. device_mode) eine Auswahl und einen
    Sensor mit derselben unique_id an – ohne Typ würden die beiden verwechselt."""
    return ent["entity_id"].partition(".")[0], ent.get("platform"), ent.get("unique_id")


async def entity_ids_by_key():
    return {ekey(e): e["entity_id"] for e in (await ha([{"type": "config/entity_registry/list"}]))[0]}


async def wait_z2m_entities(keys, before, timeout):
    """Zigbee2MQTT benennt mit „Entity-ID aktualisieren“ die Entity-IDs selbst um – in HA über Löschen, Neuanlegen und
    Umbenennen. Wartet, bis alle betroffenen Entitäten wieder da sind, eine neue ID haben und der Stand sich nicht mehr
    ändert (oder die Zeit um ist). Liefert den letzten Stand {Schlüssel: Entity-ID}."""
    deadline, last = time.monotonic() + timeout, None
    while True:
        await asyncio.sleep(1.5)
        current = await entity_ids_by_key()
        snap = {k: current.get(k) for k in keys}
        if (all(v and v != before[k] for k, v in snap.items()) and snap == last) or time.monotonic() >= deadline:
            return current
        last = snap


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


async def replace_references(body, mapping):
    """Ersetzt alte Entity-IDs in Automationen/Skripten/Szenen/Dashboards, YAML-Dateien und Node-RED-Flows (je nach Optionen).
    Vorher wird jede geänderte Konfiguration unter /data/backups gesichert. Liefert (geändert, nicht lesbar, Hinweise, Fehler)."""
    changed_refs, errors = [], []
    configs, unreadable = await scan_configs() if body.get("update_references") else ([], 0)
    notes = []
    if body.get("update_yaml") or body.get("update_nodered"):
        files, notes = scan_files(body.get("update_yaml"), body.get("update_nodered"),
                                  skip_ui_yaml=bool(body.get("update_references")))
        configs += files
    if not mapping:
        return changed_refs, unreadable, notes, errors
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
    return changed_refs, unreadable, notes, errors


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


# ---------- Verweise auf fehlende Entitäten (z. B. Karten nach einer Umbenennung) ----------
# Entity-ID im Text; davor kein Punkt/Schrägstrich (Hostnamen, Pfade, states.light.x), dahinter kein weiterer Punkt
ENTITY_REF_RE = re.compile(r"(?<![\w./:-])([a-z_][a-z0-9_]*)\.([a-z0-9_]+)(?![\w.])")
RENAME_LOG_KEEP = 5000


def rename_log_file():
    return backup_root() / "entity-id-verlauf.json"


def log_renames(renamed):
    """Merkt sich jede Änderung einer Entity-ID (alt → neu) dauerhaft neben den Sicherungen – so findet „Verweise prüfen“
    auch später noch das Ziel von Karten und Automationen, die auf eine alte ID zeigen."""
    if not renamed:
        return
    path = rename_log_file()
    try:
        entries = json.loads(path.read_text())
    except (OSError, ValueError):
        entries = []
    stamp = iso_now()
    entries = (entries if isinstance(entries, list) else []) + [{"old": c["old"], "new": c["new"], "at": stamp} for c in renamed]
    try:
        write_json(path, entries[-RENAME_LOG_KEEP:])
    except OSError as err:
        log.warning("Verlauf der Entity-IDs nicht schreibbar: %r", err)


def renamed_to(missing, known):
    """Heutige Entity-ID zu alten IDs laut Verlauf (auch über mehrere Umbenennungen hinweg)."""
    try:
        entries = json.loads(rename_log_file().read_text())
    except (OSError, ValueError):
        return {}
    step = {e["old"]: e["new"] for e in entries if isinstance(e, dict) and e.get("old") and e.get("new")}  # spätere gewinnen
    out = {}
    for old in missing:
        cur, seen = old, set()
        while cur not in known and cur in step and cur not in seen:
            seen.add(cur)
            cur = step[cur]
        if cur != old and cur in known:
            out[old] = cur
    return out


async def known_entities():
    """Alle Entity-IDs in Home Assistant (Registry und Zustände – auch YAML-Entitäten ohne unique_id) und die Zustände."""
    states, entities = await ha([{"type": "get_states"}, {"type": "config/entity_registry/list"}])
    return {st["entity_id"] for st in states} | {e["entity_id"] for e in entities}, states


async def broken_references():
    """Automationen, Skripte, Szenen und Dashboards (über die Oberfläche gepflegt), die Entitäten nennen, die es in
    Home Assistant nicht gibt. Aktionen wie light.turn_on zählen nicht. Mit Vorschlägen aus dem Verlauf der Entity-IDs
    und den vorhandenen Entitäten der betroffenen Domänen zur Auswahl."""
    known, states = await known_entities()
    services = (await ha([{"type": "get_services"}]))[0]
    domains = {k.partition(".")[0] for k in known}
    actions = {f"{d}.{a}" for d, acts in services.items() for a in acts}
    items, unreadable = await scan_configs()
    found = []
    for it in items:
        missing = sorted({m.group(0) for m in ENTITY_REF_RE.finditer(item_text(it))
                          if m.group(1) in domains and m.group(0) not in known and m.group(0) not in actions})
        if missing:
            found.append({**{k: it[k] for k in ("kind", "id", "title")}, "entities": missing})
    missing = sorted({e for f in found for e in f["entities"]})
    names = {st["entity_id"]: st["attributes"].get("friendly_name", "") for st in states}
    wanted = {m.partition(".")[0] for m in missing}
    choices = {d: [{"id": k, "name": names.get(k, "")} for k in sorted(known) if k.partition(".")[0] == d] for d in wanted}
    return {"items": found, "missing": missing, "suggestions": renamed_to(missing, known), "choices": choices,
            "scanned": len(items), "unreadable": unreadable}


async def check_references(request):
    return web.json_response(await broken_references())


async def repair_references(request):
    """Ersetzt Verweise auf fehlende Entitäten durch die gewählten (vorhandenen) Entity-IDs – nur Text-Ersatz der IDs,
    alles andere an Karten und Automationen bleibt; vorher gesichert. Danach wird erneut geprüft."""
    known, _ = await known_entities()
    mapping = {old: new for old, new in ((await request.json()).get("mapping") or {}).items()
               if isinstance(old, str) and ENTITY_REF_RE.fullmatch(old) and old not in known and new in known}
    if not mapping:
        raise web.HTTPBadRequest(text="Keine gültige Zuordnung – das Ziel muss eine vorhandene Entität sein")
    changed, _, _, errors = await replace_references({"update_references": True}, mapping)
    return web.json_response({"updated_references": changed, "errors": errors, **await broken_references()})


async def remove_from_scenes(request):
    """Entfernt Entitäten, die es nicht mehr gibt, aus Szenen (über die Oberfläche gepflegt) – z. B. Schalter eines Geräts, das
    jetzt über eine andere Integration eingebunden ist. Nur die Einträge unter entities/metadata verschwinden, der Rest der Szene
    bleibt; vorhandene Entitäten werden nie entfernt. Vorher gesichert, danach erneut geprüft."""
    known, _ = await known_entities()
    ids = {i for i in (await request.json()).get("entity_ids", []) if isinstance(i, str) and ENTITY_REF_RE.fullmatch(i) and i not in known}
    if not ids:
        raise web.HTTPBadRequest(text="Keine fehlende Entität angegeben")
    items, _ = await scan_configs()
    backup = DATA / "backups" / time.strftime("%Y%m%d-%H%M%S")
    changed, errors = [], []
    async with ClientSession(headers={"Authorization": f"Bearer {TOKEN}"}) as http:
        for it in items:
            cfg = it["config"]
            hit = [i for i in ids if any(i in (cfg.get(k) or {}) for k in ("entities", "metadata"))] if it["kind"] == "scene" else []
            if not hit:
                continue
            backup.mkdir(parents=True, exist_ok=True)
            (backup / f"scene__{slugify(str(it['id'])) or 'default'}.bak").write_text(item_text(it))
            new_cfg = {k: ({e: v2 for e, v2 in v.items() if e not in ids} if k in ("entities", "metadata") and isinstance(v, dict) else v) for k, v in cfg.items()}
            async with http.post(f"{CORE_API}/{it['path']}", json=new_cfg) as r:
                ok, res = r.status == 200, await r.text()
            if ok:
                changed.append({"kind": "scene", "title": it["title"], "entities": sorted(hit)})
            else:
                errors.append({"device": f"Szene {it['title']}", "error": res})
    return web.json_response({"updated_references": changed, "errors": errors, **await broken_references()})


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
    changes, skipped, usages, unreadable, notes, info, unhandled = [], [], [], 0, [], [], []
    if body.get("rename_entities") and items:
        entities, devices, areas = await entity_registries()
        changes, skipped, info = entity_changes(items, entities, devices, areas)
        if changes:
            mapping = {c["old"]: c["new"] for c in changes}
            usages, unreadable, notes = await collect_usages(body, mapping)
            if not body.get("update_references"):  # ohne Haken: warnen, was danach ins Leere zeigt
                unhandled, _, _ = await collect_usages({"update_references": True}, mapping)
    targets = await resolve_areas(body, items)
    area_changes = [{"device": it["name"], "from": it.get("current_area") or "", "to": targets[it["device_id"]]["name"],
                     "create": targets[it["device_id"]]["create"]} for it in items if it["device_id"] in targets]
    return web.json_response({"entities": changes, "skipped": skipped, "usages": usages, "unhandled": unhandled,
                              "unreadable": unreadable, "notes": notes, "areas": area_changes, "entity_info": info})


def use_z2m(body):
    """Ob in Zigbee2MQTT umbenannt werden soll (ältere Clients: gekoppelt an „Entity-IDs mitziehen“)."""
    return bool(body.get("rename_z2m", body.get("rename_entities")))


async def adopt_z2m_names(items, targets, timeout=15):
    """Zieht Home Assistant nach einer Umbenennung in Zigbee2MQTT sauber nach. Z2M meldet das Gerät per Discovery
    neu an (mit „Entity-ID aktualisieren“ sogar über Löschen und Neuanlegen), daher erst darauf warten. Danach:
    ein eigener HA-Name (name_by_user) würde den neuen Z2M-Namen verdecken und wird entfernt – HA folgt dann Z2M;
    ist Z2Ms Anmeldung ausgeblieben, wird der neue Name direkt in HA gesetzt. Der Bereich kommt zuletzt, damit
    er beim Neuanlegen nicht verloren geht. Liefert Fehler."""
    by_ieee = {it["ieee"].lower(): it for it in items}
    deadline = time.monotonic() + timeout
    while True:
        found = {}
        for d in (await ha([{"type": "config/device_registry/list"}]))[0]:
            src = device_source(d)
            if src and src[0] == "z2m" and src[1].lower() in by_ieee:
                found[src[1].lower()] = d
        if all(found.get(k, {}).get("name") == it["name"] for k, it in by_ieee.items()) or time.monotonic() >= deadline:
            break
        await asyncio.sleep(1)
    errors = []
    for key, it in by_ieee.items():
        dev = found.get(key)
        if not dev:
            errors.append({"device": it["name"], "error": "Nach der Umbenennung in Zigbee2MQTT nicht mehr in Home Assistant gefunden – Name/Bereich dort prüfen"})
            continue
        cmd = {"type": "config/device_registry/update", "device_id": dev["id"]}
        if dev.get("name") == it["name"]:
            if dev.get("name_by_user"):
                cmd["name_by_user"] = None
        elif dev.get("name_by_user") != it["name"]:
            cmd["name_by_user"] = it["name"]
        tgt = targets.get(it["device_id"])
        if tgt and tgt["id"] and dev.get("area_id") != tgt["id"]:
            cmd["area_id"] = tgt["id"]
        if len(cmd) > 2:
            ok, res = await ha_try(cmd)
            if not ok:
                errors.append({"device": it["name"], "error": res})
    return errors


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
    z2m_items = [it for it in items if it.get("source") == "z2m" and it.get("ieee")] if use_z2m(opts) and not opts.get("skip_names") else []
    if z2m_items:  # Stand in Zigbee2MQTT selbst (<base>/bridge/devices)
        known = await z2m_devices()
        off = [f"{it['name']} (in Z2M: {known[k]['name'] if k in known else 'nicht gefunden'})"
               for it in z2m_items if known.get(k := it["ieee"].lower(), {}).get("name") != it["name"]]
        if not known:
            checks.append(check("Zigbee2MQTT", "warn", "Geräteliste von Zigbee2MQTT (bridge/devices) nicht lesbar – Namen in Z2M nicht geprüft"))
        else:
            checks.append(check("Zigbee2MQTT", "fail" if off else "ok",
                                f"Noch nicht übernommen: {', '.join(off)}" if off else f"{len(z2m_items)} Gerät(e) heißen auch in Zigbee2MQTT wie geplant"))
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
            checks.append({**check("Verweise", "fail", "Alte Entity-IDs kommen noch vor in: " + usage_text(usages)), "fix": True})
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
        usages, _, _ = await collect_usages({"update_references": True}, {c["old"]: c["new"] for c in renamed})
        if usages:
            checks.append({**check("Verweise", "warn", "Nicht angepasst (Haken aus) – diese zeigen jetzt ins Leere: " + usage_text(usages)), "fix": True})
        else:
            checks.append(check("Verweise", "ok", "Keine alten Entity-IDs in Automationen, Skripten, Szenen und Dashboards (YAML/Node-RED nicht geprüft)"))
    return checks


KIND_NAMES = {"automation": "Automation", "script": "Skript", "scene": "Szene", "dashboard": "Dashboard", "yaml": "YAML", "nodered": "Node-RED"}


def usage_text(usages):
    return "; ".join(f"{KIND_NAMES.get(u['kind'], u['kind'])} „{u['title']}“ ({', '.join(u['entities'])})" for u in usages)


async def fix_references(request):
    """„Alte IDs jetzt ersetzen“ nach der Prüfung: ersetzt die übriggebliebenen alten Entity-IDs und prüft erneut."""
    body = await request.json()
    renamed = [c for c in body.get("renamed", []) if c.get("old") and c.get("new")]
    opts = {**body, "update_references": True}
    changed, _, _, errors = await replace_references(opts, {c["old"]: c["new"] for c in renamed})
    checks = await verify_changes(parse_request(body), renamed, {**opts, "skip_names": True}, wait=False)
    return web.json_response({"updated_references": changed, "errors": errors, "checks": checks})


async def assign_area(request):
    """Ordnet Geräte nur einem Bereich (Raum) zu – ohne sie umzubenennen."""
    body = await request.json()
    body["set_area"] = True
    items = parse_request(body)
    if not items:
        raise web.HTTPBadRequest(text="Keine Geräte angegeben")
    await safe_backup("vor-raum")
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


# ---------- Löschen ----------
async def delete_targets(items):
    """Entity-IDs je Gerät und die Geräte, die über ein Gerät angebunden sind (via_device: ZHA-Koordinator, Matter-Bridge)."""
    devices, entities = await ha([{"type": "config/device_registry/list"}, {"type": "config/entity_registry/list"}])
    ids = {it["device_id"] for it in items}
    ents, children = {}, {}
    for e in entities:
        if e.get("device_id") in ids:
            ents.setdefault(e["device_id"], []).append(e["entity_id"])
    for d in devices:
        if d.get("via_device_id") in ids:
            children.setdefault(d["via_device_id"], []).append(d.get("name_by_user") or d.get("name") or d["id"])
    return ents, children


def is_coordinator(it, children):
    """ZHA hängt alle Geräte an den Koordinator (via_device) – den darf das Löschen nie treffen."""
    return it.get("source") == "zha" and bool(children.get(it["device_id"]))


async def plan_delete(request):
    """Vorschau zum Löschen: Entitäten je Gerät, angebundene Geräte und Automationen/Skripte/Szenen/Dashboards, die die Entitäten nutzen."""
    items = parse_request(await request.json())
    ents, children = await delete_targets(items)
    ids = [e for it in items for e in ents.get(it["device_id"], [])]
    usages, unreadable, _ = await collect_usages({"update_references": True}, {e: e for e in ids}) if ids else ([], 0, [])
    return web.json_response({"devices": [{"device_id": it["device_id"], "name": it["name"], "entities": ents.get(it["device_id"], []),
                                           "children": children.get(it["device_id"], []), "blocked": is_coordinator(it, children)}
                                          for it in items],
                              "usages": usages, "unreadable": unreadable})


async def remove_in_bridge(it, owners, force):
    """Entfernt ein Gerät in Zigbee2MQTT bzw. ZHA (Abmelden aus dem Zigbee-Netz); Matter erledigt Home Assistant beim Löschen
    des Geräts selbst. Liefert (ok, Fehler, erzwungen)."""
    if it.get("source") == "z2m" and it.get("ieee"):
        owner = owners.get(it["ieee"].lower())
        if owners and not owner:
            return True, None, False  # in keiner Z2M-Instanz (mehr) vorhanden: nur noch Home Assistant aufräumen
        base = owner["base"] if owner else safe_topic(it.get("base_topic"))
        forced = False
        result = await z2m_request(base, "device/remove", {"id": it["ieee"], "force": False}, timeout=30)
        if result.get("status") not in ("ok", "unknown") and force:
            # Gerät bestätigt das Abmelden nicht (z. B. schlafender Batterie-Sensor): nur aus der Datenbank von Z2M entfernen
            forced = True
            result = await z2m_request(base, "device/remove", {"id": it["ieee"], "force": True}, timeout=15)
        if result.get("status") not in ("ok", "unknown"):
            known = await z2m_devices()  # Antwort verpasst, Gerät aber schon weg?
            if known and it["ieee"].lower() not in known:
                return True, None, forced
        failure = await z2m_failure(base, result)
        return failure is None, failure, forced
    if it.get("source") == "zha" and it.get("ieee"):
        ok, res = await ha_try({"type": "call_service", "domain": "zha", "service": "remove", "service_data": {"ieee": it["ieee"]}})
        return ok, None if ok else f"ZHA: {res}", False
    return True, None, False


async def remove_in_ha(items, timeout=20):
    """Zigbee2MQTT und ZHA melden entfernte Geräte in HA selbst ab – darauf kurz warten. Was dann noch da ist (bei Matter immer),
    wird über seine Integration gelöscht (Matter: HA entfernt den Knoten dabei aus seinem Matter-Netz); Entitäten, die danach noch
    an einem gelöschten Gerät hängen, werden entfernt. Liefert Fehler."""
    ids = {it["device_id"] for it in items}
    wait = {it["device_id"] for it in items if it.get("source") in ("z2m", "zha")}
    deadline = time.monotonic() + (timeout if wait else 0)
    while True:
        present = {d["id"]: d for d in (await ha([{"type": "config/device_registry/list"}]))[0] if d["id"] in ids}
        if not wait & present.keys() or time.monotonic() >= deadline:
            break
        await asyncio.sleep(1.5)
    failed = {}
    for dev in present.values():
        for entry in dev.get("config_entries") or []:
            ok, res = await ha_try({"type": "config/device_registry/remove_config_entry", "device_id": dev["id"], "config_entry_id": entry})
            if not ok:
                failed[dev["id"]] = res
    devices, entities = await ha([{"type": "config/device_registry/list"}, {"type": "config/entity_registry/list"}])
    still = {d["id"] for d in devices}
    names = {it["device_id"]: it["name"] for it in items}
    # ein Fehler zählt nur, wenn das Gerät noch da ist (mit dem letzten Eintrag verschwindet es samt der übrigen)
    errors = [{"device": names[i], "device_id": i, "error": f"Home Assistant: {res}"} for i, res in failed.items() if i in still]
    for ent in entities:
        if ent.get("device_id") in ids - still:
            ok, res = await ha_try({"type": "config/entity_registry/remove", "entity_id": ent["entity_id"]})
            if not ok:
                errors.append({"device": ent["entity_id"], "error": res})
    return errors


async def verify_delete(items, forced=()):
    """Prüft nach dem Löschen, ob Geräte und Entitäten aus Home Assistant und die Geräte aus Zigbee2MQTT verschwunden sind.
    Liefert (Prüfpunkte, IDs der gelöschten Geräte)."""
    devices, entities = await ha([{"type": "config/device_registry/list"}, {"type": "config/entity_registry/list"}])
    present = {d["id"] for d in devices}
    gone = [it["device_id"] for it in items if it["device_id"] not in present]
    still = [it["name"] for it in items if it["device_id"] in present]
    left = [e["entity_id"] for e in entities if e.get("device_id") in set(gone)]
    checks = [check("Home Assistant", "fail" if still else "ok",
                    f"Noch vorhanden: {', '.join(still)}" if still else f"{len(items)} Gerät(e) aus Home Assistant gelöscht")]
    if left:
        checks.append(check("Entitäten", "fail", f"Noch vorhanden: {', '.join(left)}"))
    z2m = [it for it in items if it.get("source") == "z2m" and it.get("ieee")]
    if z2m:
        known = await z2m_devices()
        off = [it["name"] for it in z2m if it["ieee"].lower() in known]
        if not known:
            checks.append(check("Zigbee2MQTT", "warn", "Geräteliste von Zigbee2MQTT (bridge/devices) nicht lesbar – dort nicht geprüft"))
        else:
            checks.append(check("Zigbee2MQTT", "fail" if off else "ok",
                                f"Noch in Zigbee2MQTT: {', '.join(off)}" if off else f"{len(z2m)} Gerät(e) aus Zigbee2MQTT entfernt"))
    if forced:
        checks.append(check("Ohne Abmelden entfernt", "warn", f"{', '.join(forced)} hat das Abmelden nicht bestätigt und wurde nur aus Zigbee2MQTT "
                                                              "entfernt. Vor dem erneuten Anlernen zurücksetzen, sonst meldet es sich womöglich von selbst wieder."))
    if any(it.get("source") == "matter" for it in items):
        checks.append(check("Matter", "info", "Aus dem Matter-Netz von Home Assistant entfernt. Ist das Gerät zusätzlich in Apple Home, "
                                              "Google Home o. ä. eingebunden, dort separat entfernen."))
    return checks, gone


async def delete_devices(request):
    """Löscht Geräte restlos: erst in Zigbee2MQTT/ZHA (Abmelden aus dem Netz), dann in Home Assistant samt Entitäten.
    Bleibt die Bridge erfolglos, bleibt das Gerät auch in HA (sonst käme es von dort wieder). Vorher wird gesichert."""
    body = await request.json()
    items = parse_request(body)
    if not items:
        raise web.HTTPBadRequest(text="Keine Geräte angegeben")
    pid = body.get("progress_id")
    prog_start(pid, len(items) + 3)
    prog(pid, "Sichere den aktuellen Stand …", 0)
    await safe_backup("vor-loeschen")
    _, children = await delete_targets(items)
    owners = await z2m_devices() if any(it.get("source") == "z2m" for it in items) else {}
    errors, removed, forced = [], [], []
    for n, it in enumerate(items, 1):
        prog(pid, f"Entferne ({n}/{len(items)}): {it['name']}", 0)
        if is_coordinator(it, children):
            errors.append({"device": it["name"], "device_id": it["device_id"], "error": "ZHA-Koordinator – wird nicht gelöscht"})
            continue
        ok, failure, was_forced = await remove_in_bridge(it, owners, bool(body.get("force")))
        if ok:
            removed.append(it)
            if was_forced:
                forced.append(it["name"])
        else:
            errors.append({"device": it["name"], "device_id": it["device_id"], "error": failure})
        prog(pid, f"Entfernt ({n}/{len(items)}): {it['name']}")
    if removed:
        prog(pid, "Lösche in Home Assistant …")
        errors += await remove_in_ha(removed)
    prog(pid, "Prüfe das Ergebnis …")
    checks, gone = await verify_delete(items, forced)
    prog_end(pid)
    return web.json_response({"ok": not errors, "checks": checks, "errors": errors, "deleted": gone, "forced": forced})


async def verify_delete_request(request):
    body = await request.json()
    checks, gone = await verify_delete(parse_request(body), body.get("forced") or [])
    return web.json_response({"checks": checks, "deleted": gone})


async def apply(request):
    body = await request.json()
    items = parse_request(body)
    if not items:
        raise web.HTTPBadRequest(text="Keine Geräte angegeben")
    z2m_mode = bool(body.get("rename_entities"))  # Entity-IDs in Home Assistant anpassen
    z2m_on = use_z2m(body)                          # Gerät in Zigbee2MQTT umbenennen
    ids_only = bool(body.get("entities_only"))      # „Entity-IDs angleichen“: Gerätenamen bleiben, nur die IDs folgen ihnen
    if ids_only:
        body.update(set_area=False, skip_names=True)  # weder Bereich noch Namen anfassen oder prüfen
    errors, done = [], []
    pid = body.get("progress_id")
    prog_start(pid, len(items) * 2 + 4)
    prog(pid, "Sichere den aktuellen Stand …", 0)
    await safe_backup("vor-umbenennen")
    prog(pid, "Lese Entitäten …", 0)
    entities, devices, areas = await entity_registries() if z2m_mode else ([], [], [])
    changes, skipped, _info = entity_changes(items, entities, devices, areas) if z2m_mode else ([], [], [])
    before = {ekey(e): e["entity_id"] for e in entities}
    key_of = {e["entity_id"]: ekey(e) for e in entities}
    batch = {it["device_id"] for it in items}
    mine = {ekey(e) for e in entities if e.get("device_id") in batch}  # alle Entitäten der umbenannten Geräte
    targets = await resolve_areas(body, items)
    await create_missing_areas(targets, errors)
    for it in items:
        tgt = targets.get(it["device_id"])
        if tgt and tgt["id"]:
            it["area_id"] = tgt["id"]

    failed_ids = set()
    owners = {}
    in_z2m = []  # in Zigbee2MQTT umbenannt: Name und Bereich in HA werden danach nachgezogen
    z2m_sent = set()  # Geräte, deren Umbenennung an Z2M ging – nur dort benennt Z2M die Entity-IDs selbst um
    if z2m_on and not ids_only and any(i.get("source") == "z2m" for i in items):
        prog(pid, "Suche die Zigbee2MQTT-Instanz der Geräte …", 0)
        owners = await z2m_devices()
    for n, it in enumerate(items, 1):
        prog(pid, f"Benenne um ({n}/{len(items)}): {it['name']}", 0)
        if ids_only:
            done.append(it["device_id"])
            continue
        if z2m_on and it.get("source") == "z2m" and it.get("ieee"):
            # In Zigbee2MQTT umbenennen und Z2Ms Antwort abwarten; die HA-Entity-IDs ändern wir selbst, damit wir sie kennen
            owner = owners.get(it["ieee"].lower())
            base = owner["base"] if owner else safe_topic(it.get("base_topic"))  # die Instanz, in der das Gerät wirklich steckt
            if owner and owner["name"] == it["name"]:
                result = {"status": "ok"}  # heißt in Z2M schon so (Z2M meldete sonst „already in use“): nur HA nachziehen
            else:
                result = await z2m_request(base, "device/rename", {"from": it["ieee"], "to": it["name"], "homeassistant_rename": z2m_mode})
                z2m_sent.add(it["device_id"])
            if result.get("status") == "timeout":  # keine Antwort: prüfen, ob Z2M den neuen Namen trotzdem schon führt
                now = (await z2m_devices()).get(it["ieee"].lower())
                if now and now["name"] == it["name"]:
                    result = {"status": "ok"}
            failure = await z2m_failure(base, result)
            if failure and owner is None and owners:
                failure += f" Das Gerät {it['ieee']} wurde in keiner gefundenen Zigbee2MQTT-Instanz gelistet."
            ok, res = (failure is None), failure
            if ok:
                in_z2m.append(it)
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
    if in_z2m:
        prog(pid, "Warte, bis Home Assistant die neuen Namen aus Zigbee2MQTT übernimmt …", 0)
        errors += await adopt_z2m_names(in_z2m, targets)

    z2m_ok = z2m_sent & set(done)
    ids_by_entity = {e["entity_id"]: e.get("device_id") for e in entities}
    changes = [c for c in changes if ids_by_entity.get(c["old"]) not in failed_ids]  # nichts ändern, wenn Z2M nicht umbenannt hat
    # Z2M benennt mit homeassistant_rename die Entity-IDs selbst um (Löschen, Neuanlegen, Umbenennen in HA) – und nicht
    # immer genau so wie vorhergesagt. Deshalb abwarten, bis es fertig ist, und nur Übriggebliebenes selbst umbenennen.
    current = before
    z2m_keys = {key_of[c["old"]] for c in changes if ids_by_entity.get(c["old"]) in z2m_ok}
    if z2m_keys:
        prog(pid, "Warte, bis Zigbee2MQTT die Entity-IDs in Home Assistant umbenannt hat …", 0)
        current = await wait_z2m_entities(z2m_keys, before, timeout=min(120, 15 + 2 * len(z2m_ok)))
    for ch in changes:
        prog(pid, f"Entity-ID: {ch['old']}")
        now = current.get(key_of[ch["old"]])
        if now and now != ch["old"]:
            continue  # hat Zigbee2MQTT schon umbenannt
        ok, res = await ha_try({"type": "config/entity_registry/update",
                                "entity_id": now or ch["old"], "new_entity_id": ch["new"]})
        if not ok:
            errors.append({"device": ch["old"], "error": res})
    # Maßgeblich für Verweise und Prüfung ist, was HA jetzt wirklich hat – alt → neu über die eindeutige ID der Entität
    renamed = []
    if z2m_mode and mine:
        after = await entity_ids_by_key()
        renamed = sorted(({"old": before[k], "new": after[k]} for k in mine if k in after and after[k] != before[k]), key=lambda c: c["old"])
        log_renames(renamed)
    # geplant, aber nicht umbenannt (weder von Z2M noch hier): nie „alles wurde angepasst“ melden
    done_old = {c["old"] for c in renamed}
    missed = [c for c in changes if c["old"] not in done_old]

    changed_refs, unreadable, notes = [], 0, []
    prog(pid, "Suche Verweise …", 0)
    if renamed and (body.get("update_references") or body.get("update_yaml") or body.get("update_nodered")):
        changed_refs, unreadable, notes, ref_errors = await replace_references(body, {c["old"]: c["new"] for c in renamed})
        errors += ref_errors
    prog(pid, "Prüfe das Ergebnis …", 0)
    checks = await verify_changes([i for i in items if i["device_id"] not in failed_ids], renamed, body) if not body.get("skip_verify") else []
    if missed and not body.get("skip_verify"):
        checks = [c for c in checks if not (c["name"] == "Entity-IDs" and c["status"] == "info")]
        checks.insert(0, check("Entity-IDs", "fail", "Nicht umbenannt: " + ", ".join(f"{c['old']} → {c['new']}" for c in missed)))
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
                sources = [s[0] for d in res if (s := device_source(d))]
                out["zigbee_devices"] = sum(1 for s in sources if s != "matter")
                out["matter_devices"] = sources.count("matter")
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
    log.info("Start: Token=%s, Zigbee-Geräte=%s, Matter-Geräte=%s, Schritte=%s", result["supervisor_token"],
             result.get("zigbee_devices"), result.get("matter_devices"), result["steps"])


def make_app():
    app = web.Application(middlewares=[errors])
    app.on_startup.append(selftest)
    app.on_startup.append(backup_loop)
    app.on_startup.append(netmap_listener)
    app.on_cleanup.append(stop_backup_loop)
    app.on_cleanup.append(stop_netmap_listener)
    app.add_routes([
        web.get("/", index),
        web.get("/zigbee-tree.js", tree_js),
        web.get("/api/networkmap", get_networkmap),
        web.post("/api/networkmap", start_networkmap),
        web.get("/api/state", get_state),
        web.get("/api/diag", diag),
        web.put("/api/store", put_store),
        web.post("/api/permit_join", permit_join),
        web.get("/api/permit_state", permit_state),
        web.post("/api/plan", plan),
        web.post("/api/apply", apply),
        web.post("/api/verify", verify),
        web.post("/api/fix_references", fix_references),
        web.get("/api/references", check_references),
        web.post("/api/references/repair", repair_references),
        web.post("/api/references/remove_from_scenes", remove_from_scenes),
        web.post("/api/entities/info", entity_info),
        web.post("/api/entities/dedupe", dedupe_entities),
        web.get("/api/progress", progress),
        web.get("/api/z2m_bases", z2m_bases),
        web.post("/api/assign_area", assign_area),
        web.post("/api/delete/plan", plan_delete),
        web.post("/api/delete", delete_devices),
        web.post("/api/delete/verify", verify_delete_request),
        web.get("/api/z2m_uis", z2m_uis),
        web.get("/api/backups", list_backups),
        web.post("/api/backups", create_backup),
        web.post("/api/backups/restore", restore_backup),
        web.get("/api/backups/{name}", get_backup),
    ])
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    web.run_app(make_app(), host="0.0.0.0", port=int(os.environ.get("PORT", 8099)))
