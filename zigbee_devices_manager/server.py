"""Backend des Zigbee Devices Manager (Home Assistant Add-on, Ingress)."""
import json
import os
import re
import unicodedata
from pathlib import Path

from aiohttp import ClientSession, web

DATA = Path(os.environ.get("DATA_DIR", "/data"))
WEB = Path(__file__).parent / "web"
TOKEN = os.environ.get("SUPERVISOR_TOKEN")
WS_URL = os.environ.get("HA_WS_URL", "ws://supervisor/core/websocket")
STORE_FILE = DATA / "store.json"


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


def zigbee_ieee(device):
    """Gibt die IEEE-Adresse zurück, wenn es ein ZHA- oder Zigbee2MQTT-Gerät ist."""
    for domain, ident in device.get("identifiers", []):
        if domain == "zha":
            return ident
        if domain == "mqtt" and ident.startswith("zigbee2mqtt_"):
            return ident.removeprefix("zigbee2mqtt_")
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
        ieee = zigbee_ieee(d)
        if not ieee:
            continue
        out.append({
            "id": d["id"],
            "name": d.get("name_by_user") or d.get("name") or ieee,
            "orig_name": d.get("name") or "",
            "is_new": not d.get("name_by_user"),
            "manufacturer": d.get("manufacturer") or "",
            "model": d.get("model") or "",
            "ieee": ieee,
            "area": area_names.get(d.get("area_id"), ""),
        })
    return web.json_response({"devices": out, "store": load_store()})


async def put_store(request):
    DATA.mkdir(parents=True, exist_ok=True)
    STORE_FILE.write_text(json.dumps(await request.json(), indent=2, ensure_ascii=False))
    return web.json_response({"ok": True})


async def rename(request):
    body = await request.json()
    device_id, name = body["device_id"], body["name"].strip()
    if not name:
        raise web.HTTPBadRequest(text="Name darf nicht leer sein")
    commands = [{"type": "config/device_registry/update", "device_id": device_id, "name_by_user": name}]
    renamed = []
    if body.get("rename_entities") and body.get("old_name"):
        old_slug, new_slug = slugify(body["old_name"]), slugify(name)
        entities = (await ha([{"type": "config/entity_registry/list"}]))[0]
        for ent in entities:
            domain, _, obj = ent["entity_id"].partition(".")
            if ent.get("device_id") == device_id and old_slug and obj.startswith(old_slug):
                new_id = f"{domain}.{new_slug}{obj[len(old_slug):]}"
                commands.append({"type": "config/entity_registry/update",
                                 "entity_id": ent["entity_id"], "new_entity_id": new_id})
                renamed.append(new_id)
    await ha(commands)
    return web.json_response({"ok": True, "renamed_entities": renamed})


async def index(request):
    return web.FileResponse(WEB / "index.html")


def make_app():
    app = web.Application()
    app.add_routes([
        web.get("/", index),
        web.get("/api/state", get_state),
        web.put("/api/store", put_store),
        web.post("/api/rename", rename),
    ])
    return app


if __name__ == "__main__":
    web.run_app(make_app(), host="0.0.0.0", port=int(os.environ.get("PORT", 8099)))
