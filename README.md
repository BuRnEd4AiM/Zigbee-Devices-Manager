# Zigbee Devices Manager

[![Demo herunterladen](https://img.shields.io/badge/%E2%AC%87%EF%B8%8F-Demo%20herunterladen-0b7bd6?style=for-the-badge)](https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager/releases/download/demo/zigbee-devices-manager-demo.html)

English version: [README.en.md](README.en.md)

Home-Assistant-Add-on mit eigener Seitenleisten-Spalte („Zigbee Namen“), in der du die Namen
aller Zigbee-Geräte (ZHA und Zigbee2MQTT) und Matter-Geräte (z. B. über Thread) siehst, bearbeitest
und nach einem festen Namensschema vergibst.

## Funktionen

- Liste aller neuen und bestehenden Zigbee-Geräte, Inline-Umbenennen, Suche, Filter „Neu“; zusätzlich Filter nach Haus, Etage, Raum und Typ (mit Anzahl, „ohne Raum/Typ“ findet Lücken) – Sammelaktionen wirken nur auf die sichtbaren Geräte
- **Matter-Geräte (Thread/WLAN):** Alle Geräte der Matter-Integration stehen mit in der Liste – unter dem Gateway „Matter“, mit Node-ID statt IEEE (hinter einer Matter-Bridge zusätzlich der Endpunkt). Sie bekommen dasselbe Namensschema, Haus/Etage/Raum/Typ und laufende Nummern wie die Zigbee-Geräte; umbenannt wird in Home Assistant (`name_by_user`), samt Entity-IDs, Verweisen und Bereich. Neu ist ein Matter-Gerät, solange es in HA keinen eigenen Namen hat. Gekoppelt werden Matter-Geräte weiterhin in der Home-Assistant-App.
- **Namensschema** frei konfigurierbar, z. B. `{room}_{type}_{nr}` → `WZ_LP_01`
  - Kürzel für Räume und Gerätetypen zum Auswählen (alphabetisch nach Namen sortiert)
  - Automatisches Hochzählen je Raum+Typ, überspringt belegte Namen
  - Zähler arabisch (`01`), römisch (`III`) oder Buchstaben (`C`)
  - GROSS / klein / wie eingegeben
- **Etagen:** Token `{floor}` für Stockwerke (z. B. H0 = Erdgeschoss, H1 = 1. Etage, H2, H3 … oder S2/S3 – Kürzel frei wählbar). Etagen aus Home Assistant werden übernommen; die Etage eines Geräts ergibt sich aus Raum/HA-Bereich, lässt sich aber je Gerät oder per Mehrfachauswahl überschreiben. Beispiel: `{floor}-{room}-{type}{nr}` → `H1-wzfl-lband01`. Haus und Etage lassen sich kombinieren.
- **Raum in Home Assistant setzen:** Mit dem Haken „Raum als Bereich in HA setzen“ (Standard: an) ordnet das Add-on das Gerät beim Umbenennen dem gewählten Raum als Bereich zu. Fehlende Bereiche werden in HA angelegt; die Vorschau zeigt vorher alle Änderungen, die Prüfung danach kontrolliert die Zuordnung. Ohne Haken bleibt der Raum nur ein Namensbestandteil.
- **Nur Raum zuweisen (ohne Umbenennen):** Bei bereits benannten Geräten erscheint „Raum setzen“, sobald der gewählte Raum vom HA-Bereich abweicht; mehrere Geräte auswählen → „Raum in HA setzen“. Mit Vorschau, Anlegen fehlender Bereiche und Prüfung, der Name bleibt unverändert.
- **Mehrere Zigbee2MQTT-Instanzen:** Vor dem Umbenennen fragt das Add-on bei MQTT (`<base>/bridge/devices`) nach, in welcher Z2M-Instanz das Gerät (über seine IEEE) wirklich steckt, und schickt die Anfrage dorthin – unabhängig vom eingetragenen Gateway-Topic. Bleibt Z2Ms Antwort aus, prüft es, ob Z2M den neuen Namen schon führt.
- **Verständliche Vorschau:** Ändert sich keine Entity-ID, sagt der Dialog warum (Namen enthalten den neuen Namen schon / keine ID beginnt mit dem alten Namen / keine Entitäten) und listet die gefundenen IDs. Zusätzlich wird der gemeinsame Anfang der Entity-IDs eines Geräts als Vorbild genutzt.
- **Haus/Etage im Namen hat Vorrang:** Steht am Anfang eines Namens z. B. `S2-…`, werden Haus und Etage daraus gesetzt, auch wenn Raum oder Typ im Namen unbekannt sind. Räume aus HA-Bereichen werden nur automatisch gewählt, wenn sie zu Haus und Etage des Geräts passen – ein Bereich wie „Bad (H1)“ wird einem S2-Gerät nicht zugeordnet (Code im Raumnamen, z. B. `(H1)`, wird erkannt). Das gilt auch für Raum-Kürzel im Namen: teilen sich „Bad (H1)“ und „Bad (S2)“ das Kürzel `BAD`, wählt `S2-BAD-…` den Raum mit dem Code `(S2)`. „⟳ Aus Namen zuordnen“ verwirft früher gespeicherte, dazu nicht passende Räume.
- **Umbenennen direkt in Zigbee2MQTT, sauber in HA übernommen:** Standardmäßig benennt das Add-on Z2M-Geräte wie Z2Ms eigener Dialog um (Friendly-Name, MQTT-Topic und – mit „Entity-IDs in HA anpassen“ – die Entity-IDs, `homeassistant_rename`). Danach wartet es, bis Z2M das Gerät neu in Home Assistant angemeldet hat, und zieht HA nach: Ein alter eigener Name in HA (`name_by_user`), der den neuen Z2M-Namen verdecken würde, wird entfernt – HA zeigt dann den Namen aus Z2M (heißt das Gerät in Z2M schon so, wird nur HA nachgezogen). Der Bereich (Raum) wird erst danach gesetzt, damit er beim Neuanlegen durch Z2M nicht verloren geht. Die Prüfung zeigt zusätzlich, ob Z2M selbst den neuen Namen führt. Z2M-Geräte, die schon in Z2M benannt sind, gelten nicht mehr als „neu“. Die Haken beim Umbenennen merkt sich das Add-on.
- **Einzeln wählbare Optionen:** „In Zigbee2MQTT umbenennen“, „Entity-IDs in HA anpassen“, „Verweise in Automationen/Dashboards“, „YAML-Dateien“ und „Node-RED-Flows“ lassen sich unabhängig voneinander anklicken. Die Verweis-Optionen brauchen geänderte Entity-IDs und setzen deshalb den Haken bei „Entity-IDs“ mit; ohne ihn passiert nur, was angehakt ist.
- **Vorhandene Namen erkennen und zuordnen:** Das Add-on zerlegt bestehende Namen nach deinem Muster und deinen Kürzeln (z. B. `H1-WZFL-KON03` → Haus/Etage H1, Raum WZFL, Typ KON, Nr. 03) und wählt Haus, Etage, Raum und Typ automatisch aus – beim Start für Geräte ohne eigene Auswahl, per Klick auf „⟳ Aus Namen zuordnen“ für alle. Passt der Name schon, bleibt er samt Nummer unverändert („✓ aktuell“), neue Nummern füllen nur freie Plätze. Der Filter „Passt nicht (n)“ zeigt Namen, die das Muster nicht erkennt.
- **Zigbee2MQTT-Basis-Topic automatisch erkennen:** Das Add-on sucht per MQTT die laufenden Z2M-Instanzen (`<base>/bridge/info`) und trägt den Basis-Topic je Gateway automatisch ein (Zuordnung über die IEEE des Koordinators). Im Tab „Gateways“ zeigt „Basis-Topics erkennen“ alle gefundenen Topics; bei ausbleibender Antwort nennt die Fehlermeldung die gefundenen Topics.
- **Echter Stand:** Nach dem Umbenennen/Zuweisen liest die Liste alle Geräte neu aus Home Assistant; „↻ Neu laden“ macht das jederzeit. Was Home Assistant nicht übernommen hat, erscheint also nicht als umbenannt.
- **Fortschrittsbalken und Z2M-Rückmeldung:** Beim Umbenennen zeigt ein Balken den Stand. Bei Zigbee2MQTT wartet das Add-on auf Z2Ms Antwort (`bridge/response/device/rename`); meldet Z2M einen Fehler (z. B. Name schon vergeben) oder antwortet nicht (falscher Basis-Topic?), erscheint die Meldung direkt, und Entity-IDs/Verweise werden für dieses Gerät nicht angefasst. Gleiches beim Anlernen. Die Umbenennung nutzt dieselbe Option wie Z2Ms eigener Dialog („Home Assistant Entity-ID aktualisieren“, `homeassistant_rename`); benennt Z2M die Entity-IDs nicht selbst um, macht das Add-on es nach kurzem Warten.
- **Haus-Buchstabe + Etage (H0, H1, S2 …):** Haus = Buchstabe (H, S), Etage = Nummer (0 = EG, 1, 2, 3 …); Muster `{house}{floor}-{room}-{type}{nr}` → `H1-wzfl-lband01`, `S2-wzfl-lband01`. Im Schema-Tab setzt „H0, H1, S2 …“ diese Voreinstellung mit einem Klick. Je Gateway lässt sich ein Haus festlegen, die Etage kommt aus Raum/HA-Bereich.
- **Räume aus Home Assistant:** Alle Bereiche aus HA werden automatisch als Räume übernommen (Kürzel wird vorgeschlagen und ist editierbar), Geräte bekommen ihren HA-Bereich als Raum vorgewählt. „⟳ Bereiche aus HA“ im Schema-Tab gleicht neu ab; gelöschte Räume kommen nicht von allein zurück.
- **Haus-Präfix:** Muster mit `{house}`, z. B. `{house}-{room}-{type}{nr}` → `H1-wzfl-lband01`. Häuser, Räume und Typen mit eigenen Kürzeln (Groß-/Kleinschreibung wählbar), Standard-Haus plus Auswahl je Gerät
- Mehrfachauswahl → Raum/Typ zuweisen → „Vorschläge übernehmen“
- **Geräte restlos löschen:** Geräte anhaken → „🗑 Löschen“. Zigbee2MQTT-Geräte werden aus dem Zigbee-Netz abgemeldet und aus Z2M entfernt (`bridge/request/device/remove`), ZHA-Geräte per `zha.remove`; Matter-Geräte nimmt Home Assistant beim Löschen aus seinem Matter-Netz. Danach verschwinden Gerät und Entitäten aus HA. Die Vorschau zeigt die betroffenen Entitäten, angebundene Geräte (z. B. hinter einer Matter-Bridge) und Automationen/Dashboards, die danach ins Leere zeigen. Ausgeführt wird erst, wenn man **LÖSCHEN** eintippt. Antwortet ein Z2M-Gerät nicht (z. B. schlafender Batterie-Sensor), entfernt das Add-on es auf Wunsch erzwungen und weist darauf hin. Der ZHA-Koordinator ist geschützt; schlägt das Entfernen in der Bridge fehl, bleibt das Gerät auch in HA. Vorher wird gesichert, danach geprüft.
- **Entity-IDs angleichen:** Home Assistant setzt den Bereich vor neue Entity-IDs (`light.wohnzimmer_s2_wzel03`). Beim Umbenennen erkennt das Add-on diesen Anfang (auch einen früheren Bereich und die ID der Haupt-Entität) und macht daraus `light.s2_wzel_lsp03`. Benannte Geräte, deren Entity-IDs noch den Namen vom Anlernen tragen (häufig bei Matter), zeigt der Filter „Alte Entity-IDs“; „⚠ Entity-IDs angleichen“ in der Zeile oder als Sammelknopf benennt nur die IDs um – Name und Bereich bleiben, Verweise in Automationen/Dashboards werden auf Wunsch mit angepasst.
- **Doppelte Entitäten:** Gibt es die richtige Entity-ID schon (meist eine Altlast vom früheren Namen), zeigt der Filter „Doppelte Entitäten“ beide mit Zustand (aktiv/verwaist/deaktiviert) und Verwendung. Verwaiste oder deaktivierte Altlasten lassen sich entfernen, Verweise werden dabei auf die richtige ID umgestellt; aktive Entitäten bleiben immer.
- **Verweise prüfen:** „🔍 Verweise prüfen“ in der Geräteliste findet Automationen, Skripte, Szenen und Dashboards, die auf nicht (mehr) vorhandene Entitäten zeigen, und ersetzt die alte ID durch die gewählte Entität (mit Suchfeld nach Name/ID, Vorschlag aus dem Verlauf aller Umbenennungen, `/config/zigbee_devices_manager/entity-id-verlauf.json`). Nur die ID wird ersetzt, vorher gesichert. Gibt es eine Entität nicht mehr, lässt sie sich aus Szenen entfernen (nur dieser Eintrag). Hilfreich z. B. für Karten wie die Hue-Like-Light-Card, die schon bei einer fehlenden Entität nur einen Fehler zeigen.
- **Prüfung nach dem Umbenennen:** Das Add-on liest den Stand aus Home Assistant neu ein und zeigt ✅/⚠️/❌ für Gerätenamen (bei Z2M mit bis zu 15 s Wartezeit), Entity-IDs und verbliebene alte Verweise in Automationen, YAML und Node-RED. „Erneut prüfen“ liest erneut nach.
- **Mehrere Gateways/Häuser:** Tab „Gateways“ listet jede Zigbee2MQTT-Instanz (und ZHA, Matter). Je Gateway: Bezeichnung, MQTT-Basis-Topic und Haus (gilt automatisch für dessen Geräte). In der Geräteliste Filter nach Gateway.
- **Anlernen:** Im Tab „Gateways“ öffnet „4 Min anlernen“ das Netz (Z2M per `bridge/request/permit_join`, ZHA per `zha.permit`), „Stopp“ beendet es; Status mit Countdown.
- **Mehrere Geräte auf einmal:** Häkchen setzen → Haus/Raum/Typ zuweisen → „ausgewählte Vorschläge übernehmen“ (ohne Auswahl: alle sichtbaren)
- Geplante Geräte reservieren Namen/Nummern
- Entity-IDs mitumbenennen (Standard: an, abwählbar)
- Export als CSV/JSON, Schema-Export/-Import
- **Reiter „Netzwerk“ (Zigbee2MQTT):** das Netz als aufklappbarer Baum – wer hängt an wem, wie gut ist die Verbindung (LQI-Badges grün ≥ 150, gelb 80–149, orange 30–79, rot < 30; Grenzen einstellbar; bei unterschiedlichen Richtungen beide Werte). Router hängen am besten Weg zum Koordinator (die schwächste Verbindung auf dem Weg so stark wie möglich; bei Gleichstand weniger Sprünge), Endgeräte an ihrem Parent; je Gerät aufklappbar die anderen Router in Reichweite. Geräte ohne Verbindung unter „Nicht verbunden“. Suche, Filter „Schwache Verbindungen“ und Gerätetyp, „Alles auf/zu“, Umschalter zwischen den Instanzen, Details per Klick (Parent, Weg, alle Nachbarn mit LQI, zuletzt gesehen, „ⓘ Z2M“/„⌂ HA“). „Scan starten“ fragt Z2M nach der Netzwerkkarte (`bridge/request/networkmap`, raw) – nur auf Knopfdruck; der letzte Scan bleibt gespeichert, ein vorhandener Networkmap-Sensor in HA wird mitgenutzt. LQI 0 gilt als „kein aktueller Messwert“, wenn die Gegenrichtung einen Wert hat. Das Add-on übernimmt außerdem jede Netzwerkkarte, die Zigbee2MQTT verschickt – z. B. wenn sie in dessen Oberfläche geladen wird. **Besser verbinden:** Einen Weg vorschreiben kann man in Zigbee nicht; ein Endgerät lässt sich aber gezielt nur über einen gewählten Router neu anlernen (`permit_join` mit `device`) und hängt danach an diesem – der Reiter schlägt einen Router im gleichen Raum mit starkem Weg vor. Tests: `node --test test/zigbee-tree.test.mjs`.
- **Direkt zum Gerät springen:** In der Geräteliste öffnet „ⓘ Z2M“ die Info-Seite des Geräts in der Zigbee2MQTT-Oberfläche (MQTT-Topic, Exposes, Einstellungen), „⌂ HA“ die Geräteseite in Home Assistant (Entitäten, Bereich, MQTT-Info). Die Z2M-Oberfläche findet das Add-on selbst (Zigbee2MQTT-Add-on per Ingress oder `frontend.url` aus Z2M); bei mehreren Instanzen wählst du sie im Tab „Gateways“ unter „Z2M-Oberfläche“ aus oder trägst eine Adresse wie `http://192.168.1.10:8080` ein.
- **Automatische Sicherung:** Namensschema, Zuordnungen, geplante Geräte, Gateways und die Geräteliste aus HA werden gesichert – nach Änderungen höchstens stündlich, täglich, vor jedem Umbenennen/Raum-Zuweisen und vor jeder Wiederherstellung (unveränderte Stände nicht doppelt, die letzten 60 bleiben). Ablage: `/config/zigbee_devices_manager/backups` – übersteht eine Neuinstallation und ist in jedem HA-Backup enthalten. Fehlen die Einstellungen beim Start, holt das Add-on den letzten Stand selbst zurück. Im Tab „Export“: Liste aller Sicherungen, „Jetzt sichern“, Wiederherstellen, Download als JSON oder Geräteliste als CSV, Wiederherstellen aus einer Datei.

## Installation

Einstellungen → Add-ons → Add-on-Store → ⋮ → Repositories →
`https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager` hinzufügen, dann „Zigbee Devices Manager“ installieren.

## Demo

**[⬇️ Demo herunterladen](https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager/releases/download/demo/zigbee-devices-manager-demo.html)** (startet direkt den Download, danach im Browser öffnen) · [Ansicht auf GitHub](https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager/blob/main/demo/zigbee-devices-manager-demo.html)

`demo/zigbee-devices-manager-demo.html` ist eine eigenständige Datei (ohne Backend) – einfach
herunterladen und im Browser öffnen. Neu erzeugen mit `python3 scripts/build_demo.py`
(auch als GitHub-Action-Artefakt verfügbar).

## Hinweise

- Zigbee2MQTT-Geräte werden standardmäßig in Z2M umbenannt (per `mqtt.publish` an `<base_topic>/bridge/request/device/rename`;
  Basis-Topic je Gateway oder in den Add-on-Optionen: `z2m_base_topic`, Standard `zigbee2mqtt`); Home Assistant übernimmt den
  Namen von Z2M. ZHA-Geräte (oder Z2M ohne den Haken) werden in der Home-Assistant-Geräte-Registry umbenannt (`name_by_user`).
- **Entity-IDs mitziehen:** Zeigt vor dem Umbenennen eine Vorschau der neuen Entity-IDs.
- **Verweise anpassen** (Standard: an): Maßgeblich sind die Entity-IDs, die Home Assistant nach dem Umbenennen tatsächlich hat (auch wenn Zigbee2MQTT sie selbst umbenennt). Ist der Haken aus, warnt die Vorschau, wenn Automationen/Dashboards die alten IDs nutzen; nach dem Umbenennen ersetzt „Alte IDs jetzt ersetzen“ übriggebliebene.
  Ersetzt die alten Entity-IDs in Automationen, Skripten, Szenen und Dashboards, die über die
  Oberfläche gepflegt werden. Vorschau vorab, Sicherung der alten Konfiguration unter `/data/backups/`.
  Optional zusätzlich: **YAML-Dateien** unter `/config` (Packages, `configuration.yaml`, YAML-Dashboards …, reiner Textersatz
  mit Wortgrenzen, Kommentare bleiben erhalten) und **Node-RED-Flows** (`flows.json` im Node-RED-Add-on). Nach YAML-Änderungen
  Konfiguration prüfen/neu laden, Node-RED danach neu starten. Das Add-on bindet dafür `/config` und `/addon_configs` ein.
  Nicht geändert werden `.storage`, `custom_components`, `secrets.yaml`.
- Echtes Anlernen neuer Geräte passiert weiterhin in ZHA/Z2M; neue Geräte erscheinen hier automatisch als „neu“.
- Schema und Zuweisungen liegen in `/data/store.json` des Add-ons, eine Kopie und die Sicherungen unter `/config/zigbee_devices_manager/`. Wer bewusst neu anfangen will, löscht vor der Neuinstallation auch diesen Ordner.
- Das Add-on liest über die Supervisor-API (`hassio_api`, nur lesend) die installierten Zigbee2MQTT-Add-ons, um deren Oberfläche zu verlinken.
- Änderungen je Version: [`zigbee_devices_manager/CHANGELOG.md`](zigbee_devices_manager/CHANGELOG.md) – Home Assistant zeigt sie im Update-Dialog.

## Fehlersuche

- Zeigt die Oberfläche **„Verbindung zu Home Assistant fehlgeschlagen“**, steht darunter die Fehlermeldung; „Diagnose öffnen“ (`/api/diag`) und das Add-on-Log zeigen, welcher Schritt scheitert (Token, Geräte-Registry, Entitäten-Registry, eingebundene Ordner).
- **Demo-Daten** erscheinen nur noch, wenn die Datei lokal geöffnet wird oder kein Add-on-Server antwortet.
- Nach Code-Änderungen im Repository muss die `version` in `zigbee_devices_manager/config.yaml` steigen, sonst bietet Home Assistant kein Update an. Zu jeder neuen Version gehört ein Abschnitt `## <version>` in `zigbee_devices_manager/CHANGELOG.md` – diesen Text zeigt Home Assistant im Update-Dialog.

## Entwicklung

```
cd zigbee_devices_manager && python3 server.py   # ohne HA: UI fällt auf Demo-Modus zurück
```
