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
- **Etagen:** Token `{floor}` für Stockwerke (z. B. H0 = Erdgeschoss, H1 = 1. Etage, H2, H3 … oder S2/S3 – Kürzel frei wählbar). Etagen aus Home Assistant werden übernommen; die Etage eines Geräts ergibt sich aus Raum/HA-Bereich, lässt sich aber je Gerät oder per Mehrfachauswahl überschreiben. Beispiel: `{floor}-{room}-{type}{nr}` → `H1-wzfl-lband01`. Haus und Etage lassen sich kombinieren.
- **Raum in Home Assistant setzen:** Mit dem Haken „Raum als Bereich in HA setzen“ (Standard: an) ordnet das Add-on das Gerät beim Umbenennen dem gewählten Raum als Bereich zu. Fehlende Bereiche werden in HA angelegt; die Vorschau zeigt vorher alle Änderungen, die Prüfung danach kontrolliert die Zuordnung. Ohne Haken bleibt der Raum nur ein Namensbestandteil.
- **Nur Raum zuweisen (ohne Umbenennen):** Bei bereits benannten Geräten erscheint „Raum setzen“, sobald der gewählte Raum vom HA-Bereich abweicht; mehrere Geräte auswählen → „Raum in HA setzen“. Mit Vorschau, Anlegen fehlender Bereiche und Prüfung, der Name bleibt unverändert.
- **Vorhandene Namen erkennen und zuordnen:** Das Add-on zerlegt bestehende Namen nach deinem Muster und deinen Kürzeln (z. B. `H1-WZFL-KON03` → Haus/Etage H1, Raum WZFL, Typ KON, Nr. 03) und wählt Haus, Etage, Raum und Typ automatisch aus – beim Start für Geräte ohne eigene Auswahl, per Klick auf „⟳ Aus Namen zuordnen“ für alle. Passt der Name schon, bleibt er samt Nummer unverändert („✓ aktuell“), neue Nummern füllen nur freie Plätze. Der Filter „Passt nicht (n)“ zeigt Namen, die das Muster nicht erkennt.
- **Zigbee2MQTT-Basis-Topic automatisch erkennen:** Das Add-on sucht per MQTT die laufenden Z2M-Instanzen (`<base>/bridge/info`) und trägt den Basis-Topic je Gateway automatisch ein (Zuordnung über die IEEE des Koordinators). Im Tab „Gateways“ zeigt „Basis-Topics erkennen“ alle gefundenen Topics; bei ausbleibender Antwort nennt die Fehlermeldung die gefundenen Topics.
- **Echter Stand:** Nach dem Umbenennen/Zuweisen liest die Liste alle Geräte neu aus Home Assistant; „↻ Neu laden“ macht das jederzeit. Was Home Assistant nicht übernommen hat, erscheint also nicht als umbenannt.
- **Fortschrittsbalken und Z2M-Rückmeldung:** Beim Umbenennen zeigt ein Balken den Stand. Bei Zigbee2MQTT wartet das Add-on auf Z2Ms Antwort (`bridge/response/device/rename`); meldet Z2M einen Fehler (z. B. Name schon vergeben) oder antwortet nicht (falscher Basis-Topic?), erscheint die Meldung direkt, und Entity-IDs/Verweise werden für dieses Gerät nicht angefasst. Gleiches beim Anlernen. Die Umbenennung nutzt dieselbe Option wie Z2Ms eigener Dialog („Home Assistant Entity-ID aktualisieren“, `homeassistant_rename`); benennt Z2M die Entity-IDs nicht selbst um, macht das Add-on es nach kurzem Warten.
- **Haus-Buchstabe + Etage (H0, H1, S2 …):** Haus = Buchstabe (H, S), Etage = Nummer (0 = EG, 1, 2, 3 …); Muster `{house}{floor}-{room}-{type}{nr}` → `H1-wzfl-lband01`, `S2-wzfl-lband01`. Im Schema-Tab setzt „H0, H1, S2 …“ diese Voreinstellung mit einem Klick. Je Gateway lässt sich ein Haus festlegen, die Etage kommt aus Raum/HA-Bereich.
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
