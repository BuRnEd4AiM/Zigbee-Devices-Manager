# Zigbee Devices Manager

Nach dem Start erscheint in der Seitenleiste **„Zigbee Namen“**.

## Schnellstart

1. **Namensschema** wählen (Reiter „Namensschema“) – z. B. „H0, H1, S2 …“ für Haus-Buchstabe + Etage. Räume und Etagen aus Home Assistant werden übernommen; Räume und Typen stehen alphabetisch.
2. In der **Geräteliste** Haus, Etage, Raum und Typ zuordnen – einzeln oder für mehrere Geräte auf einmal (Filter oben grenzen die Liste ein). „⟳ Aus Namen zuordnen“ erkennt vorhandene Namen.
3. **„Vorschläge übernehmen“** – die Vorschau zeigt neue Namen, Entity-IDs und die Automationen/Dashboards, die mit angepasst werden. Danach prüft das Add-on das Ergebnis.

## Aufräumen

- **Alte Entity-IDs** – Geräte, deren Entity-IDs noch den Namen vom Anlernen tragen: „⚠ Entity-IDs angleichen“.
- **Doppelte Entitäten** – die richtige ID ist schon vergeben (Altlast vom früheren Namen): verwaiste oder deaktivierte Altlasten entfernen.
- **🔍 Verweise prüfen** – Automationen, Szenen und Dashboards mit Entitäten, die es nicht mehr gibt: per Suche ersetzen oder aus Szenen entfernen.

## Vertauschte Spots

Geräte auswählen → **„💡 Neu zuordnen“**: Die Geräte blinken nacheinander, du wählst jeweils den Namen des Platzes. Namen, Entity-IDs und Raum wechseln mit; Automationen, Szenen und Dashboards bleiben unverändert und steuern danach den richtigen Platz. „💡“ in der Zeile lässt ein einzelnes Gerät blinken.

## Optionen

| Option | Bedeutung |
|---|---|
| `z2m_base_topic` | MQTT-Basis-Topic von Zigbee2MQTT, falls nicht automatisch erkannt (Standard `zigbee2mqtt`). Je Gateway lässt er sich auch im Reiter „Gateways“ eintragen. |

## Sicherungen

Unter `/config/zigbee_devices_manager/backups` – vor jeder Änderung und täglich; Wiederherstellen im Reiter „Export“. Geänderte Automationen/Dashboards werden zusätzlich vor dem Ersetzen gesichert.

Mehr Informationen, Bilder und eine Demo im Browser: <https://github.com/BuRnEd4AiM/Zigbee-Devices-Manager>
