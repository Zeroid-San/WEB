import ipaddress
import platform
import re
import socket
import subprocess
import concurrent.futures

ROUTER_IP = "192.168.1.1"
MAX_RANGE_FEET = 100
PING_TIMEOUT_MS = 250

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((ROUTER_IP, 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()

def get_subnet(local_ip):
    if not local_ip:
        return None
    return ipaddress.ip_network(local_ip + "/24", strict=False)

def ping(ip):
    system = platform.system().lower()
    if system == "windows":
        command = ["ping", "-n", "1", "-w", str(PING_TIMEOUT_MS), str(ip)]
    else:
        command = ["ping", "-c", "1", "-W", "1", str(ip)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            match = re.search(r"time[=<]([0-9.]+)\s*ms", result.stdout, re.I)
            latency = float(match.group(1)) if match else None
            return str(ip), latency
    except (subprocess.SubprocessError, OSError):
        pass
    return None

def get_arp_table():
    devices = {}
    try:
        result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=5)
        pattern = re.compile(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:-]{17})")
        for ip, mac in pattern.findall(result.stdout):
            devices[ip] = mac.replace("-", ":").upper()
    except (subprocess.SubprocessError, OSError):
        pass
    return devices

def main():
    print("Wi-Fi LAN Device Scanner")
    print("=" * 30)
    print(f"Configured router: {ROUTER_IP}")
    print(f"Requested range: {MAX_RANGE_FEET} ft")
    print()

    local_ip = get_local_ip()

    if not local_ip:
        print("Could not determine your local IP.")
        print("Set ROUTER_IP at the top of this file to your router's LAN address.")
        return

    network = get_subnet(local_ip)

    print(f"Your IP: {local_ip}")
    print(f"Scanning: {network}")
    print("Please wait...")
    print()

    hosts = list(network.hosts())

    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as executor:
        results = list(executor.map(ping, hosts))

    arp = get_arp_table()
    found = []

    for result in results:
        if result:
            ip, latency = result
            found.append((ip, arp.get(ip, "Unknown"), latency))

    if not found:
        print("No responding devices were found.")
        return

    print(f"{'IP':<18}{'MAC':<20}{'Latency':<12}{'Distance'}")
    print("-" * 65)

    for ip, mac, latency in sorted(found):
        latency_text = f"{latency:.1f} ms" if latency is not None else "Unknown"
        print(f"{ip:<18}{mac:<20}{latency_text:<12}Not measurable")

    print()
    print(f"Devices responding on your Wi-Fi/LAN: {len(found)}")
    print()
    print("Important:")
    print("- This scanner can find devices connected to the same LAN.")
    print("- Wi-Fi IP/MAC data does not reveal a device's physical distance.")
    print("- 100 ft cannot be enforced or measured from a router IP alone.")
    print("- A device that is nearby but not connected to your Wi-Fi will not appear.")
    print("- For real distance/proximity, the hardware must provide usable RSSI/UWB/Bluetooth data.")

if __name__ == "__main__":
    main()
