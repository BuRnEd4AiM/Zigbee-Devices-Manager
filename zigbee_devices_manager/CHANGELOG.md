# Änderungen

## 0.9.1

*14.10.2026*

- Netzwerk-Scan: Die Statuszeile zeigt live, welche Router nicht antworten (aus dem Log von Zigbee2MQTT). Jeder davon kostet ~25 s – z. B. Lampen, die am Wandschalter aus sind.
- Der Scan darf jetzt bis zu 15 Minuten dauern (vorher 5). Bleibt die Antwort aus, sagt die Meldung, ob Z2M noch scannt oder schon fertig war – und nicht mehr fälschlich „stimmt der Basis-Topic?“, wenn er stimmt.
- **Netzwerkkarte automatisch von der Bridge:** Wird die Karte in der Oberfläche von Zigbee2MQTT („Netzwerk“) oder anderswo geladen, übernimmt der Reiter sie von selbst – auch ohne eigenen Networkmap-Sensor. Beim Öffnen des Reiters wird nachgesehen, ob es eine neuere Karte gibt.
- **Besser verbinden:** Für Endgeräte schlägt der Reiter einen Router vor (gleicher Raum, starker Weg zum Koordinator) und öffnet das Anlernen 4 Minuten lang nur über diesen Router – nach dem erneuten Koppeln hängt das Gerät an ihm. Für Router gibt es Hinweise; die schwächste Stelle auf dem Weg wird benannt.
- Eine Fehlermeldung zum Scan verschwindet, sobald doch eine neuere Karte angekommen ist.

## 0.9.0

*14.10.2026*

- **Neuer Reiter „Netzwerk“:** zeigt das Zigbee-Netz jeder Zigbee2MQTT-Instanz als aufklappbaren Baum – wer hängt an wem und wie gut ist die Verbindung (LQI, farbig, beide Richtungen).
- Router hängen am besten Weg zum Koordinator (die schwächste Verbindung auf dem Weg ist so stark wie möglich), Endgeräte an ihrem Parent. Je Gerät aufklappbar: andere Router in Reichweite.
- Geräte ohne Verbindung im Scan stehen gesammelt unter „Nicht verbunden“.
- Suche, Filter „Schwache Verbindungen“ und Gerätetyp, „Alles auf/zu“, LQI-Grenzen einstellbar (Standard 30/80/150).
- Klick auf ein Gerät: Typ, IEEE, Parent, Weg zum Koordinator, alle Nachbarn mit LQI, zuletzt gesehen, „ⓘ Z2M“ und „⌂ HA“.
- „Scan starten“ fragt Zigbee2MQTT nach der Netzwerkkarte (nur auf Knopfdruck, dauert meist 10–60 s). Der letzte Scan wird gespeichert; ein vorhandener Networkmap-Sensor in HA wird mitgenutzt.
- Kopfzeile bricht auf dem Handy jetzt um, statt seitlich zu scrollen.

## 0.8.1

*14.10.2026*

- **Fix: Verweise in Dashboards und Automationen gingen beim Umbenennen über Zigbee2MQTT teilweise verloren.** Z2M löscht die Entitäten in HA, legt sie neu an und benennt sie um – nicht immer genau so wie vorhergesagt, und bei vielen Geräten dauerte das länger, als das Add-on wartete. Jetzt wartet es, bis Z2M fertig ist, und ersetzt die Verweise mit den Entity-IDs, die HA tatsächlich hat (über die eindeutige ID jeder Entität).
- Die Vorschau warnt, wenn Automationen/Dashboards die alten Entity-IDs nutzen, aber „Verweise anpassen“ aus ist – mit Haken zum direkten Mitanpassen.
- Die Prüfung nach dem Umbenennen sucht auch ohne Haken nach alten Entity-IDs; „Alte IDs jetzt ersetzen“ repariert sie mit einem Klick.

## 0.8.0

*11.10.2026*

- **Direkt zum Gerät springen:** Neue Spalte „Öffnen“ in der Geräteliste – „ⓘ Z2M“ öffnet die Info-Seite des Geräts in der Zigbee2MQTT-Oberfläche, „⌂ HA“ die Geräteseite in Home Assistant.
- Die Z2M-Oberfläche wird automatisch gefunden (Zigbee2MQTT-Add-on oder `frontend.url`); bei mehreren Instanzen im Tab „Gateways“ unter „Z2M-Oberfläche“ auswählen.
- **Automatische Sicherungen** von Namensschema, Zuordnungen, Gateways und Geräteliste unter `/config/zigbee_devices_manager/backups` (übersteht eine Neuinstallation, ist in HA-Backups enthalten). Im Tab „Export“: Liste, „Jetzt sichern“, Wiederherstellen, Download als JSON/CSV.
- Fehlen die Einstellungen beim Start, wird der letzte gesicherte Stand automatisch zurückgeholt.
- Fix: War Home Assistant beim Öffnen nicht erreichbar, konnten die gespeicherten Einstellungen durch Standardwerte überschrieben werden.
- Einstellungen werden jetzt so gespeichert, dass ein Absturz keine halbe Datei hinterlässt.
- Das Add-on braucht dafür lesenden Zugriff auf die Supervisor-API (`hassio_api`).

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
