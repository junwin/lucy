#!/usr/bin/env python3
"""Wait a bit then check the nodeDB for jupx."""
import meshtastic.serial_interface
import time

print("Waiting 45 seconds for mesh re-sync...")
time.sleep(45)

iface = meshtastic.serial_interface.SerialInterface("/dev/ttyUSB0")

ni = iface.getMyNodeInfo()
print(f"Local node: {ni['user']['longName']} ({ni['user']['id']})")
lc = iface.localNode.localConfig.lora
print(f"Region: {lc.region}")

print(f"\n=== NodeDB ({len(iface.nodes)} nodes) ===")
for nid, node in iface.nodes.items():
    uname = node.get("user", {}).get("longName", "?")
    snr = node.get("snr", "?")
    hops = node.get("hopsAway", "?")
    lh = node.get("lastHeard", 0)
    print(f"  {nid}: {uname}  SNR={snr}  hops={hops}  lastHeard={lh}")

iface.close()
