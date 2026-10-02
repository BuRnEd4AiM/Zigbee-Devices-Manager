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
- Multi-select → assign room/type → "apply suggestions"
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
- **Zigbee2MQTT:** with "rename entity IDs / in Z2M" ticked, the device is renamed in Z2M itself (friendly name,
  MQTT topic and HA entity IDs) via `mqtt.publish` to `<base_topic>/bridge/request/device/rename`. Set the base topic
  in the add-on options (`z2m_base_topic`, default `zigbee2mqtt`). The result is not reported back; check the first devices in Z2M.
- Automations/dashboards using old entity IDs are not updated.
- Pairing new devices still happens in ZHA/Z2M; they show up here as "new" automatically.
- Scheme and assignments are stored in the add-on's `/data/store.json`.
