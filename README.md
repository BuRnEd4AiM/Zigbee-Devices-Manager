# Zigbee Devices Manager

English version: [README.en.md](README.en.md)

Home-Assistant-Add-on mit eigener Seitenleisten-Spalte („Zigbee Namen“), in der du die Namen
aller Zigbee-Geräte (ZHA und Zigbee2MQTT) siehst, bearbeitest und nach einem festen
Namensschema vergibst.

## Funktionen

- Liste aller neuen und bestehenden Zigbee-Geräte, Inline-Umbenennen, Suche, Filter „Neu“
- **Namensschema** frei konfigurierbar, z. B. `{room}_{type}_{nr}` → `WZ_LP_01`
  - Kürzel für Räume und Gerätetypen zum Auswählen
  - Automatisches Hochzählen je Raum+Typ, überspringt belegte Namen
  - Zähler arabisch (`01`), römisch (`III`) oder Buchstaben (`C`)
  - GROSS / klein / wie eingegeben
- Mehrfachauswahl → Raum/Typ zuweisen → „Vorschläge übernehmen“
- Geplante Geräte reservieren Namen/Nummern
- Optional: Entitäts-IDs mitumbenennen
- Export als CSV/JSON, Schema-Export/-Import

## Installation

Einstellungen → Add-ons → Add-on-Store → ⋮ → Repositories →
`https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager` hinzufügen, dann „Zigbee Devices Manager“ installieren.

## Demo

**[⬇️ Demo herunterladen](https://raw.githubusercontent.com/BuRnEd4AiM/Zigbee-Devices-Manager/main/demo/zigbee-devices-manager-demo.html)** (Rechtsklick → „Link speichern unter…“, dann im Browser öffnen) · [Ansicht auf GitHub](https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager/blob/main/demo/zigbee-devices-manager-demo.html)

`demo/zigbee-devices-manager-demo.html` ist eine eigenständige Datei (ohne Backend) – einfach
herunterladen und im Browser öffnen. Neu erzeugen mit `python3 scripts/build_demo.py`
(auch als GitHub-Action-Artefakt verfügbar).

## Hinweise

- Umbenannt wird in der Home-Assistant-Geräte-Registry (`name_by_user`). Bei Zigbee2MQTT bleibt der
  Friendly-Name in Z2M unverändert.
- Echtes Anlernen neuer Geräte passiert weiterhin in ZHA/Z2M; neue Geräte erscheinen hier automatisch als „neu“.
- Schema und Zuweisungen liegen in `/data/store.json` des Add-ons.

## Entwicklung

```
cd zigbee_devices_manager && python3 server.py   # ohne HA: UI fällt auf Demo-Modus zurück
```
