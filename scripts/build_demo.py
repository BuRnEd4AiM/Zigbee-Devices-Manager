#!/usr/bin/env python3
"""Erzeugt die eigenständige Demo (eine HTML-Datei) aus der Add-on-Oberfläche."""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
src = (root / "zigbee_devices_manager/web/index.html").read_text()
marker = "<script>\n// ---------- Konfiguration"
assert marker in src
demo = src.replace(marker, "<script>window.ZDM_DEMO = true;</script>\n" + marker, 1)
out = root / "demo/zigbee-devices-manager-demo.html"
out.parent.mkdir(exist_ok=True)
out.write_text(demo)
print("geschrieben:", out)
