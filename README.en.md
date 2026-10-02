# Zigbee Devices Manager

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

`demo/zigbee-devices-manager-demo.html` is a standalone file (no backend): download it and open it in
a browser. Rebuild with `python3 scripts/build_demo.py` (also available as a GitHub Actions artifact).

## Notes

- Renaming happens in the Home Assistant device registry (`name_by_user`). With Zigbee2MQTT the
  friendly name inside Z2M stays unchanged.
- Pairing new devices still happens in ZHA/Z2M; they show up here as "new" automatically.
- Scheme and assignments are stored in the add-on's `/data/store.json`.
