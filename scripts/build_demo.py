#!/usr/bin/env python3
"""Erzeugt die eigenständige Demo (eine HTML-Datei) aus der Add-on-Oberfläche."""
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
src = (root / "zigbee_devices_manager/web/index.html").read_text()
marker = "<script>\n// ---------- Konfiguration"
assert marker in src
demo = src.replace(marker, "<script>window.ZDM_DEMO = true;</script>\n" + marker, 1)
# Netzwerk-Modul einbetten, damit die Demo eine einzelne Datei bleibt
tag = re.search(r'<script src="zigbee-tree\.js[^"]*"></script>', demo)
assert tag
tree = (root / "zigbee_devices_manager/web/zigbee-tree.js").read_text()
demo = demo[:tag.start()] + "<script>\n" + tree + "</script>" + demo[tag.end():]
out = root / "demo/zigbee-devices-manager-demo.html"
out.parent.mkdir(exist_ok=True)
out.write_text(demo)
print("geschrieben:", out)
