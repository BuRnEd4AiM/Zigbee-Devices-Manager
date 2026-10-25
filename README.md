<p align="center">
  <img src="zigbee_devices_manager/logo.png" alt="Zigbee Devices Manager" width="128">
</p>

<h1 align="center">Zigbee Devices Manager</h1>

<p align="center">
  Home-Assistant-Add-on, das Zigbee- und Matter-Geräte nach einem festen Namensschema benennt –<br>
  samt Entity-IDs, Räumen, Automationen, Szenen und Dashboards.
</p>

<p align="center">
  <a href="zigbee_devices_manager/CHANGELOG.md"><img alt="Version" src="https://img.shields.io/badge/dynamic/yaml?url=https%3A%2F%2Fraw.githubusercontent.com%2FBuRnEd4AiM%2FZigbee-Devices-Manager%2Fmain%2Fzigbee_devices_manager%2Fconfig.yaml&query=%24.version&label=Version&color=0b7bd6"></a>
  <a href="https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager/releases"><img alt="Releases" src="https://img.shields.io/badge/Releases-alle%20Versionen-555"></a>
  <a href="https://burned4aim.github.io/Zigbee-Devices-Manager/"><img alt="Demo im Browser" src="https://img.shields.io/badge/Demo-im%20Browser%20%C3%B6ffnen-1a8f4c"></a>
  <a href="https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager/actions/workflows/tests.yml"><img alt="Tests" src="https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager/actions/workflows/tests.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="Lizenz" src="https://img.shields.io/github/license/BuRnEd4AiM/Zigbee-Devices-Manager?label=Lizenz"></a>
  <img alt="Home Assistant Add-on" src="https://img.shields.io/badge/Home%20Assistant-Add--on-41bdf5?logo=homeassistant&logoColor=white">
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FBuRnEd4AiM%2FZigbee-Devices-Manager"><img alt="Repository zu Home Assistant hinzufügen" src="https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg"></a>
</p>

<p align="center"><b>Deutsch</b> · <a href="README.en.md">English</a></p>

![Geräteliste mit Filtern und Namensvorschlägen](docs/screenshots/geraete.png)

## Was es kann

- 🏷️ **Namensschema statt Wildwuchs** – z. B. `{house}{floor}-{room}-{type}{nr}` → `S2-WZEL-LSP03`, mit Kürzeln, automatischem Hochzählen und freien Nummern.
- 🔗 **Alles zieht mit** – Gerätename in Zigbee2MQTT bzw. Home Assistant, Entity-IDs, Raum als HA-Bereich und Verweise in Automationen, Skripten, Szenen, Dashboards, YAML und Node-RED. Vorher Vorschau, danach Prüfung.
- 📡 **Zigbee2MQTT, ZHA und Matter** in einer Liste – auch mehrere Zigbee2MQTT-Instanzen und mehrere Häuser.
- 💡 **Vertauschte Spots neu zuordnen** – Lampen blinken nacheinander, du wählst den richtigen Platz; Namen und Entity-IDs tauschen, ohne dass ein Spot aus der Decke muss.
- 🔍 **Aufräumen** – alte Entity-IDs angleichen, doppelte Entitäten auflösen, kaputte Verweise finden und reparieren (z. B. Karten, die nur noch einen Fehler zeigen).
- 🕸️ **Netzwerk-Ansicht** – das Zigbee-Netz als Baum mit Verbindungsqualität.
- 🛟 **Sicher** – automatische Sicherungen, Wiederherstellen per Klick, Prüfung nach jeder Änderung.

## Bilder

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/umbenennen.png" alt="Umbenennen mit Vorschau"><br><sub><b>Umbenennen mit Vorschau</b> – neue Entity-IDs und die Automationen/Dashboards, die mit angepasst werden.</sub></td>
    <td width="50%"><img src="docs/screenshots/neu-zuordnen.png" alt="Spots neu zuordnen"><br><sub><b>💡 Neu zuordnen</b> – das Gerät blinkt, du wählst den Namen des Platzes.</sub></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/verweise.png" alt="Verweise prüfen"><br><sub><b>🔍 Verweise prüfen</b> – fehlende Entitäten finden, per Suche ersetzen oder aus Szenen entfernen.</sub></td>
    <td><img src="docs/screenshots/netzwerk.png" alt="Netzwerk"><br><sub><b>Netzwerk</b> – wer hängt an wem, wie gut ist die Verbindung, wo ist die schwächste Stelle.</sub></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/namensschema.png" alt="Namensschema"><br><sub><b>Namensschema</b> – Muster, Häuser, Etagen, Räume und Typen mit Kürzeln.</sub></td>
    <td><img src="docs/screenshots/geraete-dunkel.png" alt="Dunkles Design"><br><sub><b>Dunkles Design</b> – folgt automatisch der Einstellung des Geräts.</sub></td>
  </tr>
</table>

## Ausprobieren

- **[▶ Demo im Browser](https://burned4aim.github.io/Zigbee-Devices-Manager/)** – läuft ohne Home Assistant mit Beispieldaten; Änderungen bleiben nur in deinem Browser.
- **[⬇️ Demo herunterladen](https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager/releases/download/demo/zigbee-devices-manager-demo.html)** – eine einzelne HTML-Datei, zum Öffnen ohne Internet.

## Installation

1. Auf den Knopf **„Add repository to my Home Assistant“** oben klicken – oder in Home Assistant: *Einstellungen → Add-ons → Add-on-Store → ⋮ → Repositories* und `https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager` hinzufügen.
2. **„Zigbee Devices Manager“** installieren und starten.
3. In der Seitenleiste erscheint **„Zigbee Namen“**.

## Schnellstart

1. **Namensschema** wählen (Reiter „Namensschema“) – z. B. „H0, H1, S2 …“ für Haus-Buchstabe + Etage. Räume und Etagen aus Home Assistant werden übernommen.
2. In der **Geräteliste** Haus, Etage, Raum und Typ zuordnen – einzeln oder für mehrere Geräte auf einmal. „⟳ Aus Namen zuordnen“ erkennt vorhandene Namen.
3. **„Vorschläge übernehmen“** – die Vorschau zeigt neue Namen, Entity-IDs und betroffene Automationen/Dashboards; danach prüft das Add-on das Ergebnis.
4. Ab und zu **„🔍 Verweise prüfen“** und die Filter **„Alte Entity-IDs“** / **„Doppelte Entitäten“** nutzen, um Reste aufzuräumen.

## Funktionen im Detail

<details>
<summary><b>Geräteliste, Filter und Namensschema</b></summary>

- Liste aller neuen und bestehenden Geräte, Inline-Umbenennen, Suche, Filter „Neu“, „Benannt“, „Passt nicht“, „Geplant“; zusätzlich Filter nach Haus, Etage, Raum und Typ (mit Anzahl, „ohne Raum/Typ“ findet Lücken). Sammelaktionen wirken nur auf die sichtbaren Geräte.
- **Namensschema** frei konfigurierbar, z. B. `{room}_{type}_{nr}` → `WZ_LP_01`
  - Kürzel für Räume und Gerätetypen zum Auswählen (alphabetisch nach Namen sortiert)
  - Automatisches Hochzählen je Raum+Typ, überspringt belegte Namen
  - Zähler arabisch (`01`), römisch (`III`) oder Buchstaben (`C`)
  - GROSS / klein / wie eingegeben
- **Etagen:** Token `{floor}` für Stockwerke (z. B. H0 = Erdgeschoss, H1 = 1. Etage … oder S2/S3 – Kürzel frei wählbar). Etagen aus Home Assistant werden übernommen; die Etage eines Geräts ergibt sich aus Raum/HA-Bereich, lässt sich aber je Gerät oder per Mehrfachauswahl überschreiben. Beispiel: `{floor}-{room}-{type}{nr}` → `H1-wzfl-lband01`.
- **Haus-Buchstabe + Etage (H0, H1, S2 …):** Haus = Buchstabe (H, S), Etage = Nummer (0 = EG, 1, 2, 3 …); Muster `{house}{floor}-{room}-{type}{nr}` → `H1-wzfl-lband01`, `S2-wzfl-lband01`. Im Schema-Tab setzt „H0, H1, S2 …“ diese Voreinstellung mit einem Klick. Je Gateway lässt sich ein Haus festlegen.
- **Haus-Präfix:** Muster mit `{house}`, z. B. `{house}-{room}-{type}{nr}` → `H1-wzfl-lband01`. Häuser, Räume und Typen mit eigenen Kürzeln, Standard-Haus plus Auswahl je Gerät.
- **Räume aus Home Assistant:** Alle Bereiche aus HA werden automatisch als Räume übernommen (Kürzel wird vorgeschlagen und ist editierbar), Geräte bekommen ihren HA-Bereich als Raum vorgewählt. „⟳ Bereiche aus HA“ gleicht neu ab; gelöschte Räume kommen nicht von allein zurück.
- **Vorhandene Namen erkennen:** Das Add-on zerlegt bestehende Namen nach deinem Muster und deinen Kürzeln (z. B. `H1-WZFL-KON03` → Haus/Etage H1, Raum WZFL, Typ KON, Nr. 03) und wählt Haus, Etage, Raum und Typ automatisch aus. Passt der Name schon, bleibt er samt Nummer („✓ aktuell“), neue Nummern füllen nur freie Plätze.
- **Haus/Etage im Namen hat Vorrang:** Steht am Anfang eines Namens z. B. `S2-…`, werden Haus und Etage daraus gesetzt. Räume aus HA-Bereichen werden nur gewählt, wenn sie zu Haus und Etage passen – „Bad (H1)“ wird keinem S2-Gerät zugeordnet; teilen sich „Bad (H1)“ und „Bad (S2)“ das Kürzel `BAD`, wählt `S2-BAD-…` den Raum mit `(S2)`.
- Geplante Geräte reservieren Namen/Nummern. Export als CSV/JSON, Schema-Export/-Import.
</details>

<details>
<summary><b>Umbenennen: Zigbee2MQTT, ZHA, Matter</b></summary>

- **Zigbee2MQTT:** Umbenannt wird wie mit Z2Ms eigenem Dialog (Friendly-Name, MQTT-Topic und – mit „Entity-IDs in HA anpassen“ – die Entity-IDs, `homeassistant_rename`). Das Add-on wartet auf Z2Ms Antwort, dann darauf, dass Z2M das Gerät neu in Home Assistant angemeldet hat, und zieht HA nach (alter eigener Name in HA wird entfernt, Bereich zuletzt gesetzt). Meldet Z2M einen Fehler, erscheint er direkt.
- **Mehrere Zigbee2MQTT-Instanzen:** Das Add-on fragt per MQTT (`<base>/bridge/devices`), in welcher Instanz das Gerät wirklich steckt, und erkennt die Basis-Topics selbst (`<base>/bridge/info`).
- **ZHA und Matter:** Umbenannt wird in der Geräte-Registry von Home Assistant (`name_by_user`), samt Entity-IDs, Verweisen und Bereich. Matter-Geräte stehen unter dem Gateway „Matter“ mit Node-ID statt IEEE; gekoppelt werden sie weiterhin in der Home-Assistant-App.
- **Raum in Home Assistant setzen:** Mit „Raum als Bereich in HA setzen“ (Standard: an) wird das Gerät dem gewählten Raum zugeordnet; fehlende Bereiche werden angelegt. „Raum setzen“ bzw. „Raum in HA setzen“ geht auch ohne Umbenennen.
- **Einzeln wählbare Optionen:** „In Zigbee2MQTT umbenennen“, „Entity-IDs in HA anpassen“, „Verweise in Automationen/Dashboards“ (Standard: an), „YAML-Dateien“ und „Node-RED-Flows“.
- **Prüfung nach dem Umbenennen:** ✅/⚠️/❌ für Gerätenamen (auch in Z2M), Entity-IDs und übrig gebliebene alte Verweise; „Erneut prüfen“ liest erneut nach. Bleibt eine geplante Umbenennung aus, steht das ausdrücklich da.
</details>

<details>
<summary><b>Entity-IDs und Verweise aufräumen</b></summary>

- **Entity-IDs mit Bereich davor:** Home Assistant legt neue Entity-IDs als `<Bereich>_<Gerät>_<Entität>` an (`light.wohnzimmer_s2_wzel03`). Das Add-on erkennt diesen Anfang (auch einen früheren Bereich), bei Zigbee2MQTT liest es die Endung aus der eindeutigen Kennung – Ergebnis: `light.s2_wzel_lsp03`.
- **„Alte Entity-IDs“ / „⚠ Entity-IDs angleichen“:** benannte Geräte, deren Entity-IDs noch den Namen vom Anlernen tragen; benennt nur die IDs um, Name und Bereich bleiben.
- **„Doppelte Entitäten“:** Gibt es die richtige ID schon (Altlast vom früheren Namen), zeigt der Dialog beide mit Zustand (aktiv/verwaist/deaktiviert) und Verwendung. Verwaiste oder deaktivierte Altlasten lassen sich entfernen, Verweise werden umgestellt; aktive Entitäten bleiben immer.
- **„🔍 Verweise prüfen“:** findet Automationen, Skripte, Szenen und Dashboards mit Entitäten, die es nicht mehr gibt. Ersatz per Suchfeld (Name/ID, mehrere Wörter), Vorschlag aus dem Verlauf aller Umbenennungen (`/config/zigbee_devices_manager/entity-id-verlauf.json`); gibt es eine Entität nicht mehr, lässt sie sich aus Szenen entfernen. Nur die ID wird ersetzt, vorher gesichert – hilfreich z. B. für Karten wie die Hue-Like-Light-Card, die schon bei einer fehlenden Entität nur einen Fehler zeigen.
- **Verweise anpassen:** Maßgeblich sind die Entity-IDs, die Home Assistant nach dem Umbenennen tatsächlich hat. Ersetzt werden Automationen, Skripte, Szenen und Dashboards aus der Oberfläche, optional **YAML-Dateien** unter `/config` (reiner Textersatz mit Wortgrenzen) und **Node-RED-Flows**. Nie geändert werden `.storage`, `custom_components`, `secrets.yaml`.
</details>

<details>
<summary><b>💡 Blinken und Neu zuordnen (vertauschte Spots)</b></summary>

- **„💡“ je Gerät** lässt es blinken – über den Identifizieren-Knopf (Matter, ZHA), bei Zigbee2MQTT über den Effekt „blink“ (ändert den Zustand nicht), sonst kurzes Aufblinken der Lampe.
- **„💡 Neu zuordnen“:** Geräte auswählen (z. B. per Filter Raum + Typ). Sie blinken nacheinander, je Gerät wählst du den Namen des Platzes; wählst du einen Namen, den ein anderes Gerät hat, tauschen die beiden (Tausch oder Ringtausch).
- Gerätename, Zigbee2MQTT-Name, Entity-IDs, Haus/Etage/Raum/Typ und der Bereich wechseln mit dem Namen – auch zwischen Matter und Zigbee. **Automationen, Szenen und Dashboards bleiben unverändert** und steuern danach den richtigen Platz. Hat das andere Gerät eine Entität nicht (z. B. Matter ↔ Zigbee), warnt die Vorschau.
- Über Zwischennamen, mit Vorschau, Sicherung und Prüfung; geht der erste Schritt schief, wird er zurückgenommen.
</details>

<details>
<summary><b>Gateways, Anlernen, Löschen</b></summary>

- **Tab „Gateways“:** jede Zigbee2MQTT-Instanz (und ZHA, Matter) mit Bezeichnung, MQTT-Basis-Topic und Haus. „4 Min anlernen“ öffnet das Netz (Z2M per `bridge/request/permit_join`, ZHA per `zha.permit`), mit Countdown.
- **Direkt zum Gerät:** „ⓘ Z2M“ öffnet das Gerät in der Zigbee2MQTT-Oberfläche, „⌂ HA“ die Geräteseite in Home Assistant. Die Z2M-Oberfläche findet das Add-on selbst; bei mehreren Instanzen im Tab „Gateways“ wählbar.
- **Geräte restlos löschen:** Zigbee2MQTT-Geräte werden aus dem Netz abgemeldet und aus Z2M entfernt, ZHA-Geräte per `zha.remove`, Matter-Geräte nimmt Home Assistant aus seinem Matter-Netz. Die Vorschau zeigt Entitäten, angebundene Geräte und betroffene Automationen/Dashboards; ausgeführt wird erst nach eingetipptem **LÖSCHEN**. Der ZHA-Koordinator ist geschützt.
</details>

<details>
<summary><b>Netzwerk (Zigbee2MQTT)</b></summary>

- Das Netz als aufklappbarer Baum – wer hängt an wem, wie gut ist die Verbindung (LQI grün ≥ 150, gelb 80–149, orange 30–79, rot < 30; Grenzen einstellbar; bei unterschiedlichen Richtungen beide Werte).
- Router hängen am besten Weg zum Koordinator (schwächste Verbindung so stark wie möglich), Endgeräte an ihrem Parent; Router in Reichweite aufklappbar; Geräte ohne Verbindung unter „Nicht verbunden“.
- Suche, Filter „Schwache Verbindungen“ und Gerätetyp, Umschalter zwischen Instanzen, Details per Klick (Parent, Weg, Nachbarn, zuletzt gesehen).
- „Scan starten“ fragt Z2M nach der Netzwerkkarte – nur auf Knopfdruck; jede Karte, die Zigbee2MQTT verschickt, wird automatisch übernommen. **Besser verbinden:** ein Endgerät gezielt über einen gewählten Router neu anlernen.
</details>

<details>
<summary><b>Sicherungen</b></summary>

- Namensschema, Zuordnungen, geplante Geräte, Gateways und die Geräteliste aus HA werden gesichert – nach Änderungen höchstens stündlich, täglich und vor jedem Umbenennen, Raum-Zuweisen, Tauschen, Löschen und Wiederherstellen (die letzten 60 bleiben).
- Ablage: `/config/zigbee_devices_manager/backups` – übersteht eine Neuinstallation und ist in jedem HA-Backup enthalten. Fehlen die Einstellungen beim Start, holt das Add-on den letzten Stand selbst zurück.
- Tab „Export“: Liste aller Sicherungen, „Jetzt sichern“, Wiederherstellen, Download als JSON oder Geräteliste als CSV, Wiederherstellen aus einer Datei.
</details>

## Versionen

Was sich je Version geändert hat, steht im **[Changelog](zigbee_devices_manager/CHANGELOG.md)** – Home Assistant zeigt denselben Text im Update-Dialog. Zu jeder Version gibt es außerdem ein **[Release](https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager/releases)** mit der Demo zum Herunterladen.

## Hinweise

- Echtes Anlernen neuer Geräte passiert weiterhin in ZHA/Z2M bzw. in der Home-Assistant-App (Matter); neue Geräte erscheinen hier automatisch als „neu“.
- Zigbee2MQTT-Basis-Topic je Gateway oder in den Add-on-Optionen (`z2m_base_topic`, Standard `zigbee2mqtt`).
- Schema und Zuweisungen liegen in `/data/store.json` des Add-ons, eine Kopie und die Sicherungen unter `/config/zigbee_devices_manager/`. Wer bewusst neu anfangen will, löscht vor der Neuinstallation auch diesen Ordner.
- Das Add-on bindet `/config` und `/addon_configs` ein (YAML, Node-RED) und liest über die Supervisor-API (nur lesend) die installierten Zigbee2MQTT-Add-ons, um deren Oberfläche zu verlinken.

## Fehlersuche

- Zeigt die Oberfläche **„Verbindung zu Home Assistant fehlgeschlagen“**, steht darunter die Fehlermeldung; „Diagnose öffnen“ (`/api/diag`) und das Add-on-Log zeigen, welcher Schritt scheitert.
- **Demo-Daten** erscheinen nur, wenn die Datei lokal geöffnet wird oder kein Add-on-Server antwortet.
- Kein Update angeboten? Im Add-on-Store *⋮ → Nach Updates suchen*.

## Entwicklung

```sh
cd zigbee_devices_manager && python3 server.py          # ohne HA: Oberfläche fällt auf den Demo-Modus zurück
python3 -m unittest discover -s test                    # Tests (Umbenennen, Entity-IDs, Verweise, Tauschen)
node --test test/zigbee-tree.test.mjs                   # Tests des Netzwerk-Reiters
python3 scripts/build_demo.py                           # Demo neu erzeugen
node scripts/screenshots.js                             # Bilder für diese Seite (braucht Playwright)
```

- Nach Code-Änderungen muss die `version` in `zigbee_devices_manager/config.yaml` steigen, sonst bietet Home Assistant kein Update an. Zu jeder Version gehört ein Abschnitt `## <version>` in `zigbee_devices_manager/CHANGELOG.md`; daraus entsteht beim Mergen automatisch das Release `vX.Y.Z`.
- Die Demo im Browser wird bei jedem Merge über GitHub Pages veröffentlicht (einmalig einschalten: *Settings → Pages → Source: GitHub Actions*).
