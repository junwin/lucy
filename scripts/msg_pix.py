#!/usr/bin/env python3
"""Just send a text message to pix and list what we know."""
import meshtastic.serial_interface

iface = meshtastic.serial_interface.SerialInterface("/dev/ttyUSB0")

# List what we know about pix from nodeDB
print("=== pix from nodeDB ===")
for nid, node in iface.nodes.items():
    uname = node.get("user", {}).get("longName", "?")
    if "pix" in uname.lower():
        print(f"Node ID: {nid}")
        print(f"Long name: {uname}")
        print(f"Short name: {node.get('user', {}).get('shortName', '?')}")
        print(f"SNR: {node.get('snr', '?')}")
        print(f"Hops: {node.get('hopsAway', '?')}")
        dm = node.get("deviceMetrics", {})
        print(f"Battery: {dm.get('batteryLevel', '?')}%")
        print(f"Voltage: {dm.get('voltage', '?')}V")
        print(f"Channel util: {dm.get('channelUtilization', '?')}%")

# Send text message
print("\nSending message to pix...")
iface.sendText("Hello from Pi 5 jutx - Peace here. Are you the Pi 4 T-Deck?", 
               destinationId="!33676294", wantAck=True)
print("Message sent!")

iface.close()
