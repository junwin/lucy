#!/usr/bin/env python3
"""Query pix and try to send a message."""
import meshtastic.serial_interface
import time

iface = meshtastic.serial_interface.SerialInterface("/dev/ttyUSB0")

# Try to get remote node info from pix
print("=== Querying KD9YXQ_pix (!33676294) ===")
try:
    node = iface.getNode("!33676294")
    user = node.get("user", {})
    print(f"Long name: {user.get('longName')}")
    print(f"Short name: {user.get('shortName')}")
    print(f"HW model: {user.get('hwModel')}")
    
    dm = node.get("deviceMetrics", {})
    print(f"Battery: {dm.get('batteryLevel', '?')}%")
    print(f"Voltage: {dm.get('voltage', '?')}V")
    
    snr = node.get("snr", "?")
    hops = node.get("hopsAway", "?")
    print(f"SNR: {snr}  Hops: {hops}")
    
    # Try remote admin to get config
    print("\nRequesting remote config...")
    iface.localNode.requestConfig("!33676294")
    time.sleep(5)
    
    # re-get node after config request
    node2 = iface.getNode("!33676294")
    lc = node2.get("localConfig", {}).get("lora", {})
    if lc:
        print(f"Remote region: {lc.get('region')}")
        print(f"Remote modem: {lc.get('modemPreset')}")
        print(f"Remote channel: {lc.get('channelNum')}")
except Exception as e:
    print(f"Query failed: {e}")

# Send a text message to pix
print("\nSending test message to pix...")
iface.sendText("Hello from Pi 5 jutx - Peace here. Are you the Pi 4 T-Deck (formerly jupx)?", 
               destinationId="!33676294", wantAck=True)
print("Sent!")

time.sleep(2)
iface.close()
