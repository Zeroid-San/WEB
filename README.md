# Wi-Fi Device Map

Windows 10 Python desktop app for viewing responding devices on your local network in a visual radar-style map.

## Run

1. Install Python 3.10+ from python.org and make sure Python is added to PATH.
2. Open Command Prompt in this repository folder.
3. Run:

```
python wifi_device_map.py
```

Tkinter is included with the standard Windows Python installer, so no pip packages are required.

## What it does

- Detects the local gateway and local IP automatically.
- Scans the local /24 network for devices that respond to ping.
- Reads the Windows ARP table for MAC addresses.
- Displays the router at the center of a dark radar-style interface.
- Refreshes automatically every 15 seconds.
- Shows IP address, MAC address, and ping latency.

## Important limitation

The circles and device positions are a visual map, not physical coordinates. Standard IP, MAC address, ping latency, and a normal Windows Wi-Fi scan cannot determine the real direction or exact distance of a client device.

For actual proximity estimates, the network hardware must expose suitable RSSI/ranging data, or additional hardware such as Bluetooth/UWB/multiple access points can be used.

Use this only on networks you own or are authorized to administer.
