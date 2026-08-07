#!/usr/bin/env python3
"""Check channel config on both T-Decks via serial."""
import meshtastic.serial_interface

print("=== jutx (Pi 5 T-Deck, /dev/ttyUSB0) ===")
iface = meshtastic.serial_interface.SerialInterface("/dev/ttyUSB0")
ni = iface.getMyNodeInfo()
nid = ni["user"]["id"]
name = ni["user"]["longName"]
print(f"Node: {name} ({nid})")
lc = iface.localNode.localConfig.lora
print(f"Region: {lc.region}")
print(f"Modem preset: {lc.modem_preset}")
print(f"Channel num: {lc.channel_num}")
print(f"Frequency offset: {lc.frequency_offset}")
print(f"Hop limit: {lc.hop_limit}")
print(f"TX power: {lc.tx_power}")

for i, ch in enumerate(iface.localNode.channels):
    if ch.role:
        psk_short = ch.settings.psk.hex()[:16]
        print(f"Channel {i}: role={ch.role}, psk={psk_short}..., name='{ch.settings.name}'")

# Check nodeDB for jupx
print()
print("=== jupx from jutx nodeDB ===")
for node_id, node in iface.nodes.items():
    uname = node.get("user", {}).get("longName", "")
    if "jupx" in uname.lower():
        print(f"Found jupx: {node_id}")
        print(f"  Long name: {node.get('user', {}).get('longName')}")
        print(f"  Short name: {node.get('user', {}).get('shortName')}")
        dm = node.get("deviceMetrics", {})
        print(f"  Battery: {dm.get('batteryLevel', '?')}%")
        print(f"  Channel util: {dm.get('channelUtilization', '?')}%")
        print(f"  Air util TX: {dm.get('airUtilTx', '?')}%")
        # Look for lastHeard
        lh = node.get("lastHeard", 0)
        print(f"  Last heard: {lh}")
        # Hop count / snr
        snr = node.get("snr", "?")
        hops = node.get("hopsAway", "?")
        print(f"  SNR: {snr}  Hops: {hops}")
        break
else:
    print("jupx NOT found in nodeDB of jutx")

# Remote query jupx
print()
print("=== Remote admin query to jupx (!e0f4764c) ===")
try:
    ni2 = iface.getNode("!e0f4764c", requestAll=True)
    print(f"Got response from: {ni2.get('user', {}).get('longName', 'unknown')}")
    lc2 = ni2.get("localConfig", {}).get("lora", {})
    if lc2:
        print(f"  Region: {lc2.get('region')}")
        print(f"  Modem preset: {lc2.get('modemPreset')}")
        print(f"  Channel num: {lc2.get('channelNum')}")
        print(f"  Frequency offset: {lc2.get('frequencyOffset')}")
        print(f"  Hop limit: {lc2.get('hopLimit')}")
except Exception as e:
    print(f"Remote query failed: {e}")

iface.close()
