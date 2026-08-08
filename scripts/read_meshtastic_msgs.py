"""Read Meshtastic messages from the connected radio."""
import meshtastic
import meshtastic.serial_interface
import time
import json

iface = meshtastic.serial_interface.SerialInterface()
time.sleep(2)

# Get self info
node = iface.getNode("!da634030")
print("=== Self node ===")
print(node.showInfo())

time.sleep(1)

# Try showInfo on pix
print("\n=== Remote node ===")
pix = iface.getNode("!33676294")
print(pix.showInfo())

print("\n=== Metadata ===")
print(node.getMetadata())

iface.close()
