# Änderungen

## 0.7.0

*10.10.2026*

- **Umbenennen direkt in Zigbee2MQTT ist jetzt Standard:** „In Zigbee2MQTT umbenennen“ und „Entity-IDs in HA anpassen“ sind von Anfang an angehakt – wie in Z2Ms eigenem Dialog („Home Assistant Entity-ID aktualisieren“).
- **Home Assistant übernimmt den neuen Namen sauber:** Das Add-on wartet, bis Z2M das Gerät neu in HA angemeldet hat. Ein alter eigener Name in HA, der den Z2M-Namen verdeckt hätte, wird entfernt. Der Raum wird erst danach gesetzt und geht nicht mehr verloren.
- Heißt ein Gerät in Z2M schon so, meldet Z2M nicht mehr „already in use“ – es wird nur HA angepasst.
- Die Prüfung nach dem Umbenennen zeigt zusätzlich, ob Zigbee2MQTT selbst den neuen Namen führt.
- In Z2M bereits benannte Geräte gelten nicht mehr als „neu“.
- Die Haken beim Umbenennen werden gemerkt.
- Fix: Enter beim Umbenennen in der Liste schloss die Vorschau sofort wieder.

## 0.6.4

*02.10.2026*

- Mehrere Zigbee2MQTT-Instanzen: Das Add-on findet über `bridge/devices` heraus, in welcher Instanz ein Gerät steckt, und schickt die Umbenennung dorthin.
- Bleibt Z2Ms Antwort aus, wird geprüft, ob Z2M den neuen Namen schon führt.
- Die Vorschau erklärt, warum sich keine Entity-ID ändert.

## 0.6.3

*02.10.2026*

- Raum-Kürzel im Namen beachten Haus und Etage: `S2-BAD-…` wählt „Bad (S2)“, nicht „Bad (H1)“.
- „⟳ Aus Namen zuordnen“ verwirft früher gespeicherte, nicht passende Räume.

## 0.6.2

*02.10.2026*

- Haus und Etage aus dem Namen haben Vorrang (auch wenn Raum oder Typ unbekannt sind).
- Räume aus HA-Bereichen werden nur automatisch gewählt, wenn sie zu Haus und Etage passen.

## 0.6.1

*02.10.2026*

- Optionen einzeln anklickbar: „In Zigbee2MQTT umbenennen“ ist getrennt von Entity-IDs und Verweisen.

## 0.6.0

*02.10.2026*

- Vorhandene Namen werden nach Muster und Kürzeln erkannt; Haus, Etage, Raum und Typ werden automatisch ausgewählt.
- Neuer Button „⟳ Aus Namen zuordnen“, Anzeige „✓ aktuell“ und Filter „Passt nicht“.

## 0.5.4

*02.10.2026*

- Zigbee2MQTT-Basis-Topics werden per MQTT erkannt und je Gateway eingetragen („Basis-Topics erkennen“).
- Fehlermeldungen nennen die gefundenen Basis-Topics.

## 0.5.3

*02.10.2026*

- Nach dem Umbenennen oder Zuweisen wird die Liste neu aus Home Assistant geladen; neuer Button „↻ Neu laden“.
- Umbenennen in Z2M nutzt dieselbe Option wie Z2Ms Dialog (`homeassistant_rename`); Entity-IDs passt das Add-on nur noch an, wenn Z2M es nicht selbst tut.

## 0.5.2

*02.10.2026*

- Das Add-on wartet auf Z2Ms Antwort; Fehler und ausbleibende Antworten werden direkt angezeigt.
- Fortschrittsbalken beim Umbenennen.
- Basis-Topic aus der Add-on-Option `z2m_base_topic`.

## 0.5.1

*02.10.2026*

- Raum in Home Assistant zuweisen, ohne umzubenennen („Raum setzen“, „Raum in HA setzen“).

## 0.5.0

*02.10.2026*

- Raum als Bereich in Home Assistant setzen (optional, mit Vorschau und Prüfung); fehlende Bereiche werden angelegt.
- Fix: Die Oberfläche lud in 0.4.1 wegen eines Skriptfehlers nicht.

## 0.4.1

*02.10.2026*

- Haus-Buchstabe + Etagennummer (H0, H1, S2 …) als neue Standardwerte, Voreinstellung per Klick.

## 0.4.0

*02.10.2026*

- Etagen: Token `{floor}`, Etagen aus Home Assistant, Auswahl je Gerät und per Mehrfachauswahl.

## 0.3.1

*02.10.2026*

- Die Geräteliste füllt die Seite aus, kein horizontales Scrollen mehr.
- Haus-Auswahl immer sichtbar; Button, um `{house}` im Muster zu aktivieren.

## 0.3.0

*02.10.2026*

- Räume werden aus den Home-Assistant-Bereichen übernommen und vorgewählt.

## 0.2.2

*02.10.2026*

- Fix: Add-on startet wieder zuverlässig.

## 0.2.1

*02.10.2026*

- Fix: Verbindung zu Home Assistant (Zugangs-Token) wird zuverlässig hergestellt.

## 0.2.0

*02.10.2026*

- Verbindungsfehler werden angezeigt statt Demo-Daten; Diagnose-Seite und Log-Einträge.
- Prüfung nach dem Umbenennen: Gerätenamen, Entity-IDs und verbliebene Verweise.
- Mehrere Gateways, Anlernen neuer Geräte, Übernehmen nur für ausgewählte Geräte.

## 0.1.0

*02.10.2026*

- Erste Version: Namensschema mit Kürzeln und automatischem Hochzählen, Demo.
- Umbenennen direkt in Zigbee2MQTT inklusive Entity-IDs.
- Verweise in Automationen, Skripten, Szenen, Dashboards, YAML-Dateien und Node-RED-Flows anpassen.
- Haus-Präfix im Namensschema.
