#!/usr/bin/env python3
"""Macht eine echte Zigbee2MQTT-Networkmap (raw) für test/fixtures/ öffentlich tauglich: IEEE-Adressen und Gerätenamen
werden ersetzt (Herstellerteil der IEEE bleibt), Routing-Tabellen entfernt; LQI, relationship, depth, Typen, Modelle,
Netzwerkadressen und lastSeen bleiben. Eingabe: Attribute des Networkmap-Sensors oder die Antwort von Z2M als JSON.

  python3 scripts/anonymize_networkmap.py scan.json test/fixtures/real-instanz2.json
"""
import json
import sys

src = json.load(open(sys.argv[1]))
data = src
for _ in range(4):  # {data: {value: …}} oder {attributes: …} auspacken
    if isinstance(data, dict) and isinstance(data.get("nodes"), list):
        break
    data = data.get("data") or data.get("value") or data.get("attributes") if isinstance(data, dict) else None
if not isinstance(data, dict) or not isinstance(data.get("nodes"), list):
    sys.exit("Keine Networkmap (nodes/links) gefunden")

ids, count = {}, {}


def anon(ieee):
    ieee = str(ieee).lower()
    if ieee == "0x0000000000000000":
        return ieee
    if ieee not in ids:
        ids[ieee] = f"{ieee[:8]}{len(ids) + 1:010x}"
    return ids[ieee]


for n in data["nodes"]:
    old = str(n.get("ieeeAddr", "")).lower()
    typ = n.get("type", "Unknown")
    if typ == "Coordinator":
        name = "Coordinator"
    elif str(n.get("friendlyName", "")).lower() == old:
        name = anon(old)  # Gerät ohne Namen trägt in Z2M seine IEEE
    else:
        count[typ] = count.get(typ, 0) + 1
        name = f"{ {'Router': 'Router', 'EndDevice': 'Endgeraet'}.get(typ, 'Geraet') }-{count[typ]:02d}"
    n["ieeeAddr"], n["friendlyName"] = anon(old), name
for link in data.get("links", []):
    for side in ("source", "target"):
        if isinstance(link.get(side), dict) and "ieeeAddr" in link[side]:
            link[side]["ieeeAddr"] = anon(link[side]["ieeeAddr"])
    for key in ("sourceIeeeAddr", "targetIeeeAddr"):
        if key in link:
            link[key] = anon(link[key])
    link["routes"] = []
json.dump({"links": data.get("links", []), "nodes": data["nodes"]}, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)
print(len(data["nodes"]), "Geräte,", len(data.get("links", [])), "Links ->", sys.argv[2])
