# Zigbee Devices Manager

[![Download demo](https://img.shields.io/badge/%E2%AC%87%EF%B8%8F-Download%20demo-0b7bd6?style=for-the-badge)](https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager/releases/download/demo/zigbee-devices-manager-demo.html)

Home Assistant add-on with its own sidebar panel ("Zigbee Namen") to view, edit and assign
names for all Zigbee devices (ZHA and Zigbee2MQTT) following a fixed naming scheme.
German version: [README.md](README.md)

## Features

- List of all new and existing Zigbee devices, inline rename, search, "new" filter
- **Configurable naming scheme**, e.g. `{room}_{type}_{nr}` → `WZ_LP_01`
  - Abbreviations for rooms and device types, selectable per device
  - Automatic counter per room+type that skips names already in use
  - Counter as Arabic (`01`), Roman (`III`) or letters (`C`)
  - UPPER / lower / as typed
- **Floors:** token `{floor}` for storeys (e.g. H0 = ground floor, H1 = 1st floor, H2, H3 … or S2/S3 – abbreviations are free). Floors from Home Assistant are imported; a device's floor follows its room/HA area but can be overridden per device or via multi-select. Example: `{floor}-{room}-{type}{nr}` → `H1-wzfl-lband01`. House and floor can be combined.
- **Set the room in Home Assistant:** with "Raum als Bereich in HA setzen" ticked (default: on) the add-on assigns the device to the chosen room as its area when renaming. Missing areas are created in HA; the preview lists all changes first and the verification afterwards checks the assignment. Without the tick the room is only part of the name.
- **Assign room only (no renaming):** for devices that are already named, "Raum setzen" appears when the chosen room differs from the HA area; select several devices → "Raum in HA setzen". With preview, creation of missing areas and verification; the name stays unchanged.
- **House/floor in the name takes precedence:** if a name starts with e.g. `S2-…`, house and floor are taken from it even when the room or type in the name is unknown. Rooms from HA areas are only chosen automatically when they fit the device's house and floor – an area like "Bad (H1)" is not assigned to an S2 device (a code in the room name such as `(H1)` is recognised).
- **Independent options:** "In Zigbee2MQTT umbenennen", "Entity-IDs in HA anpassen", "Verweise in Automationen/Dashboards", "YAML-Dateien" and "Node-RED-Flows" can be ticked independently. The reference options need changed entity IDs and therefore tick "Entity-IDs" as well; without it only what is ticked happens.
- **Recognise existing names and assign them:** the add-on splits existing names by your pattern and abbreviations (e.g. `H1-WZFL-KON03` → house/floor H1, room WZFL, type KON, no. 03) and selects house, floor, room and type automatically – at start for devices without their own choice, via "⟳ Aus Namen zuordnen" for all. A name that already fits stays unchanged including its number ("✓ aktuell"); new numbers only fill free slots. The "Passt nicht (n)" filter lists names the pattern does not recognise.
- **Auto-detect the Zigbee2MQTT base topic:** the add-on looks for running Z2M instances over MQTT (`<base>/bridge/info`) and fills in the base topic per gateway automatically (matched via the coordinator IEEE). "Basis-Topics erkennen" in the Gateways tab lists all topics found; when there is no reply the error message names the topics found.
- **Real state:** after renaming/assigning, the list re-reads all devices from Home Assistant; "↻ Neu laden" does it any time. Whatever Home Assistant did not accept does not show up as renamed.
- **Progress bar and Z2M feedback:** a bar shows progress while renaming. With Zigbee2MQTT the add-on waits for Z2M's reply (`bridge/response/device/rename`); if Z2M reports an error (e.g. name already in use) or does not answer (wrong base topic?), the message is shown right away and entity IDs/references of that device are left untouched. Same for pairing. Renaming uses the same option as Z2M's own dialog ("update Home Assistant entity ID", `homeassistant_rename`); if Z2M does not rename the entity IDs itself, the add-on does it after a short wait.
- **House letter + floor (H0, H1, S2 …):** house = letter (H, S), floor = number (0 = ground floor, 1, 2, 3 …); pattern `{house}{floor}-{room}-{type}{nr}` → `H1-wzfl-lband01`, `S2-wzfl-lband01`. The "H0, H1, S2 …" button in the scheme tab applies this preset in one click. A house can be set per gateway; the floor comes from the room/HA area.
- **Rooms from Home Assistant:** all HA areas are imported as rooms automatically (abbreviation suggested and editable); devices get their HA area preselected as room. "⟳ Bereiche aus HA" in the scheme tab re-syncs; deleted rooms are not re-added on their own.
- **House prefix:** patterns with `{house}`, e.g. `{house}-{room}-{type}{nr}` → `H1-wzfl-lband01`. Houses, rooms and types with their own abbreviations, a default house plus per-device choice
- Multi-select → assign room/type → "apply suggestions"
- **Verification after renaming:** the add-on re-reads Home Assistant and shows ✅/⚠️/❌ for device names (up to 15 s wait for Z2M), entity IDs and leftover old references in automations, YAML and Node-RED. "Re-check" reads again.
- **Multiple gateways/houses:** the "Gateways" tab lists every Zigbee2MQTT instance (and ZHA). Per gateway: label, MQTT base topic and house (applied to its devices automatically). Gateway filter in the device list.
- **Pairing:** "4 Min anlernen" in the "Gateways" tab opens the network (Z2M via `bridge/request/permit_join`, ZHA via `zha.permit`), "Stopp" ends it; status with countdown.
- **Rename many at once:** tick devices → assign house/room/type → "apply selected suggestions" (no selection: all visible)
- Planned devices reserve names/numbers
- Optional: rename entity IDs along with the device
- CSV/JSON export, scheme export/import

## Installation

Settings → Add-ons → Add-on Store → ⋮ → Repositories → add
`https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager`, then install "Zigbee Devices Manager".

## Demo

**[⬇️ Download the demo](https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager/releases/download/demo/zigbee-devices-manager-demo.html)** (starts the download directly, then open it in a browser) · [View on GitHub](https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager/blob/main/demo/zigbee-devices-manager-demo.html)

`demo/zigbee-devices-manager-demo.html` is a standalone file (no backend): download it and open it in
a browser. Rebuild with `python3 scripts/build_demo.py` (also available as a GitHub Actions artifact).

## Notes

- Default: rename in the Home Assistant device registry (`name_by_user`).
- **Rename entity IDs:** shows a preview of the new entity IDs first. For Zigbee2MQTT the device is also renamed in Z2M itself
  (via `mqtt.publish` to `<base_topic>/bridge/request/device/rename`; set the base topic in the add-on options: `z2m_base_topic`).
- **Update references:** replaces the old entity IDs in automations, scripts, scenes and dashboards managed via the UI.
  Preview first, old configs are backed up to `/data/backups/`. Optionally also **YAML files** under `/config` (packages, `configuration.yaml`, YAML dashboards …; plain text replacement
  with word boundaries, comments are kept) and **Node-RED flows** (`flows.json` of the Node-RED add-on). Check/reload the config
  after YAML changes and restart Node-RED afterwards. The add-on mounts `/config` and `/addon_configs` for this.
  `.storage`, `custom_components` and `secrets.yaml` are never touched.
- Pairing new devices still happens in ZHA/Z2M; they show up here as "new" automatically.
- Scheme and assignments are stored in the add-on's `/data/store.json`.
