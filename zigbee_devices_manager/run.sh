#!/usr/bin/with-contenv bashio
# with-contenv macht SUPERVISOR_TOKEN (Zugriff auf Home Assistant) für den Server sichtbar
bashio::log.info "Starte Zigbee Devices Manager"
exec python3 /app/server.py
