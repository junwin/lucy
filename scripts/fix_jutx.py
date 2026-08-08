#!/usr/bin/env python3
"""Fix jutx region to ANZ (Australia/New Zealand)."""
import meshtastic.serial_interface
import time

iface = meshtastic.serial_interface.SerialInterface("/dev/ttyUSB0")
node = iface.localNode

ni = iface.getMyNodeInfo()
print(f"Node: {ni['user']['longName']} ({ni['user']['id']})")
print(f"Region: {node.localConfig.lora.region}")

# Set region to ANZ (5)
print("\nSetting region to ANZ (5)...")
node.localConfig.lora.region = 5

# begin + commit
print("Begin settings transaction...")
node.beginSettingsTransaction()
print("Commit...")
node.commitSettingsTransaction()

time.sleep(2)

# Verify
print(f"\nRegion after commit: {node.localConfig.lora.region}")

# Set name
print("\nSetting owner name to KD9YXQ_jutx...")
node.setOwner(long_name="KD9YXQ_jutx", short_name="jutx")

time.sleep(2)
ni = iface.getMyNodeInfo()
print(f"Done! Node: {ni['user']['longName']} ({ni['user']['id']})")
print(f"Region: {node.localConfig.lora.region}")

iface.close()
