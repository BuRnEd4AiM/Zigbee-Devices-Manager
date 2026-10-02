# Zigbee Devices Manager

[![Demo herunterladen](https://img.shields.io/badge/%E2%AC%87%EF%B8%8F-Demo%20herunterladen-0b7bd6?style=for-the-badge)](https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager/releases/download/demo/zigbee-devices-manager-demo.html)

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
- **Räume aus Home Assistant:** Alle Bereiche aus HA werden automatisch als Räume übernommen (Kürzel wird vorgeschlagen und ist editierbar), Geräte bekommen ihren HA-Bereich als Raum vorgewählt. „⟳ Bereiche aus HA“ im Schema-Tab gleicht neu ab; gelöschte Räume kommen nicht von allein zurück.
- **Haus-Präfix:** Muster mit `{house}`, z. B. `{house}-{room}-{type}{nr}` → `H1-wzfl-lband01`. Häuser, Räume und Typen mit eigenen Kürzeln (Groß-/Kleinschreibung wählbar), Standard-Haus plus Auswahl je Gerät
- Mehrfachauswahl → Raum/Typ zuweisen → „Vorschläge übernehmen“
- **Prüfung nach dem Umbenennen:** Das Add-on liest den Stand aus Home Assistant neu ein und zeigt ✅/⚠️/❌ für Gerätenamen (bei Z2M mit bis zu 15 s Wartezeit), Entity-IDs und verbliebene alte Verweise in Automationen, YAML und Node-RED. „Erneut prüfen“ liest erneut nach.
- **Mehrere Gateways/Häuser:** Tab „Gateways“ listet jede Zigbee2MQTT-Instanz (und ZHA). Je Gateway: Bezeichnung, MQTT-Basis-Topic und Haus (gilt automatisch für dessen Geräte). In der Geräteliste Filter nach Gateway.
- **Anlernen:** Im Tab „Gateways“ öffnet „4 Min anlernen“ das Netz (Z2M per `bridge/request/permit_join`, ZHA per `zha.permit`), „Stopp“ beendet es; Status mit Countdown.
- **Mehrere Geräte auf einmal:** Häkchen setzen → Haus/Raum/Typ zuweisen → „ausgewählte Vorschläge übernehmen“ (ohne Auswahl: alle sichtbaren)
- Geplante Geräte reservieren Namen/Nummern
- Optional: Entitäts-IDs mitumbenennen
- Export als CSV/JSON, Schema-Export/-Import

## Installation

Einstellungen → Add-ons → Add-on-Store → ⋮ → Repositories →
`https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager` hinzufügen, dann „Zigbee Devices Manager“ installieren.

## Demo

**[⬇️ Demo herunterladen](https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager/releases/download/demo/zigbee-devices-manager-demo.html)** (startet direkt den Download, danach im Browser öffnen) · [Ansicht auf GitHub](https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager/blob/main/demo/zigbee-devices-manager-demo.html)

`demo/zigbee-devices-manager-demo.html` ist eine eigenständige Datei (ohne Backend) – einfach
herunterladen und im Browser öffnen. Neu erzeugen mit `python3 scripts/build_demo.py`
(auch als GitHub-Action-Artefakt verfügbar).

## Hinweise

- Standard: Umbenennen in der Home-Assistant-Geräte-Registry (`name_by_user`).
- **Entity-IDs mitziehen:** Zeigt vor dem Umbenennen eine Vorschau der neuen Entity-IDs. Bei Zigbee2MQTT wird das Gerät
  zusätzlich direkt in Z2M umbenannt (per `mqtt.publish` an `<base_topic>/bridge/request/device/rename`; Basis-Topic in den
  Add-on-Optionen: `z2m_base_topic`, Standard `zigbee2mqtt`).
- **Verweise anpassen:** Ersetzt die alten Entity-IDs in Automationen, Skripten, Szenen und Dashboards, die über die
  Oberfläche gepflegt werden. Vorschau vorab, Sicherung der alten Konfiguration unter `/data/backups/`.
  Optional zusätzlich: **YAML-Dateien** unter `/config` (Packages, `configuration.yaml`, YAML-Dashboards …, reiner Textersatz
  mit Wortgrenzen, Kommentare bleiben erhalten) und **Node-RED-Flows** (`flows.json` im Node-RED-Add-on). Nach YAML-Änderungen
  Konfiguration prüfen/neu laden, Node-RED danach neu starten. Das Add-on bindet dafür `/config` und `/addon_configs` ein.
  Nicht geändert werden `.storage`, `custom_components`, `secrets.yaml`.
- Echtes Anlernen neuer Geräte passiert weiterhin in ZHA/Z2M; neue Geräte erscheinen hier automatisch als „neu“.
- Schema und Zuweisungen liegen in `/data/store.json` des Add-ons.

## Fehlersuche

- Zeigt die Oberfläche **„Verbindung zu Home Assistant fehlgeschlagen“**, steht darunter die Fehlermeldung; „Diagnose öffnen“ (`/api/diag`) und das Add-on-Log zeigen, welcher Schritt scheitert (Token, Geräte-Registry, Entitäten-Registry, eingebundene Ordner).
- **Demo-Daten** erscheinen nur noch, wenn die Datei lokal geöffnet wird oder kein Add-on-Server antwortet.
- Nach Code-Änderungen im Repository muss die `version` in `zigbee_devices_manager/config.yaml` steigen, sonst bietet Home Assistant kein Update an.

## Entwicklung

```
cd zigbee_devices_manager && python3 server.py   # ohne HA: UI fällt auf Demo-Modus zurück
```
