import concurrent.futures
import ipaddress
import platform
import re
import socket
import subprocess

ROUTER_IP = "192.168.1.1"
PING_TIMEOUT_MS = 250
MAX_WORKERS = 64

def get_local_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((ROUTER_IP, 80))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()

def get_network(local_ip):
    return ipaddress.ip_network(f"{local_ip}/24", strict=False)

def ping(ip):
    if platform.system().lower() == "windows":
        command = ["ping", "-n", "1", "-w", str(PING_TIMEOUT_MS), str(ip)]
    else:
        command = ["ping", "-c", "1", "-W", "1", str(ip)]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=2)
        if result.returncode != 0:
            return None

        match = re.search(r"time[=<]([0-9.]+)\s*ms", result.stdout, re.I)
        latency = float(match.group(1)) if match else None
        return str(ip), latency
    except (OSError, subprocess.SubprocessError):
        return None

def get_arp_table():
    devices = {}

    try:
        result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=5)
        pattern = re.compile(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:-]{17})")

        for ip, mac in pattern.findall(result.stdout):
            devices[ip] = mac.replace("-", ":").upper()
    except (OSError, subprocess.SubprocessError):
        pass

    return devices

def scan_lan(network):
    hosts = list(network.hosts())

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = executor.map(ping, hosts)

    arp = get_arp_table()
    devices = []

    for result in results:
        if result:
            ip, latency = result
            devices.append({
                "ip": ip,
                "mac": arp.get(ip, "Unknown"),
                "latency": latency
            })

    return sorted(devices, key=lambda device: ipaddress.ip_address(device["ip"]))

def scan_nearby_wifi():
    if platform.system().lower() != "windows":
        return []

    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="ignore"
        )
    except (OSError, subprocess.SubprocessError):
        return []

    networks = []
    current = None

    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()

        if line.startswith("SSID ") and ":" in line:
            name = line.split(":", 1)[1].strip()
            current = {"ssid": name, "signal": None}
            networks.append(current)

        elif current and line.lower().startswith("signal") and ":" in line:
            current["signal"] = line.split(":", 1)[1].strip()

    unique = {}
    for network in networks:
        key = network["ssid"]
        unique[key] = network

    return list(unique.values())

def main():
    print("Wi-Fi Device Scanner")
    print("=" * 60)
    print("Authorized local-network scanning only.")
    print()

    local_ip = get_local_ip()

    if not local_ip:
        print("Could not determine your local IP.")
        print(f"Check ROUTER_IP at the top of this file. Current value: {ROUTER_IP}")
        return

    network = get_network(local_ip)

    print(f"Local IP : {local_ip}")
    print(f"Subnet   : {network}")
    print()
    print("Scanning devices connected to your LAN...")
    print()

    devices = scan_lan(network)

    if devices:
        print(f"{'IP':<18}{'MAC':<20}{'Latency':<14}")
        print("-" * 52)

        for device in devices:
            latency = (
                f"{device['latency']:.1f} ms"
                if device["latency"] is not None
                else "Unknown"
            )
            print(f"{device['ip']:<18}{device['mac']:<20}{latency:<14}")

        print()
        print(f"LAN devices found: {len(devices)}")
    else:
        print("No responding LAN devices found.")

    print()
    print("Nearby Wi-Fi networks detected by this Windows PC:")
    print()

    wifi_networks = scan_nearby_wifi()

    if wifi_networks:
        print(f"{'SSID':<35}{'Signal'}")
        print("-" * 48)

        for network_info in sorted(
            wifi_networks,
            key=lambda item: item["signal"] or "",
            reverse=True
        ):
            print(f"{network_info['ssid'][:34]:<35}{network_info['signal'] or 'Unknown'}")
    else:
        print("No Wi-Fi networks were reported by Windows.")

    print()
    print("Distance note:")
    print("- LAN IP, MAC address, and ping latency do not provide physical distance.")
    print("- Windows can report signal strength for nearby Wi-Fi access points.")
    print("- That signal is for the access point, not arbitrary client devices.")
    print("- Exact distance such as 100 ft requires supported RSSI, UWB, Bluetooth, or other ranging hardware.")
    print("- A device outside your Wi-Fi network will not appear in the LAN scan.")

if __name__ == "__main__":
    main()
