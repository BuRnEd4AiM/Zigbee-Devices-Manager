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
- **House prefix:** patterns with `{house}`, e.g. `{house}-{room}-{type}{nr}` → `H1-wzfl-lband01`. Houses, rooms and types with their own abbreviations, a default house plus per-device choice
- Multi-select → assign room/type → "apply suggestions"
- **Verification after renaming:** the add-on re-reads Home Assistant and shows ✅/⚠️/❌ for device names (up to 15 s wait for Z2M), entity IDs and leftover old references in automations, YAML and Node-RED. "Re-check" reads again.
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
