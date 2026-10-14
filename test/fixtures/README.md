# Test-Daten für den Reiter „Netzwerk“

Networkmaps im raw-Format von Zigbee2MQTT (`<base>/bridge/response/networkmap`, `data.value`) bzw. so, wie sie ein
HA-Sensor mit `json_attributes_template: "{{ value_json.data.value | tojson }}"` als Attribute hat.

- `real-instanz1.json` – echter Scan (25 Geräte, 8 Router), anonymisiert: IEEE-Adressen und Namen ersetzt,
  Routing-Tabellen (`routes`) entfernt. LQI, relationship, depth, Typen, Modelle, Netzwerkadressen und lastSeen sind echt.

Jede `*.json` hier wird von `test/zigbee-tree.test.mjs` automatisch auf die Grundregeln des Baums geprüft
(jedes Gerät genau einmal, Parent ist Router/Koordinator und Nachbar, Pfadwert = schwächste Verbindung).

Weiteren echten Scan hinzufügen:

1. In Home Assistant **Entwicklerwerkzeuge → Template**:
   `{{ states.sensor.zigbee2mqtt_networkmap_2.attributes | tojson }}` – Ergebnis als `scan.json` speichern.
2. `python3 scripts/anonymize_networkmap.py scan.json test/fixtures/real-instanz2.json`
3. `node --test test/zigbee-tree.test.mjs`
