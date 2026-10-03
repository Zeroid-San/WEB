import concurrent.futures
import ipaddress
import platform
import re
import socket
import subprocess
import threading
import tkinter as tk
from tkinter import ttk

PING_TIMEOUT_MS = 250
MAX_WORKERS = 64
REFRESH_MS = 15000
BG = "#0b0f14"
PANEL = "#111821"
TEXT = "#e7edf5"
MUTED = "#8290a3"
ACCENT = "#59b7ff"
GOOD = "#67e8a5"
GRID = "#263342"

def get_gateway():
    if platform.system().lower() != "windows":
        return None
    try:
        result = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=5, encoding="utf-8", errors="ignore")
        gateways = re.findall(r"Default Gateway[^:]*:\s*([0-9.]+)", result.stdout, re.I)
        return next((g for g in gateways if g and g != "0.0.0.0"), None)
    except (OSError, subprocess.SubprocessError):
        return None

def get_local_ip(gateway):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if gateway:
            sock.connect((gateway, 80))
        else:
            sock.connect(("1.1.1.1", 80))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()

def ping(ip):
    command = ["ping", "-n", "1", "-w", str(PING_TIMEOUT_MS), str(ip)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=2, encoding="utf-8", errors="ignore")
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
        result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=5, encoding="utf-8", errors="ignore")
        pattern = re.compile(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:-]{17})")
        for ip, mac in pattern.findall(result.stdout):
            devices[ip] = mac.replace("-", ":").upper()
    except (OSError, subprocess.SubprocessError):
        pass
    return devices

def scan_lan(network):
    hosts = list(network.hosts())
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(ping, hosts))
    arp = get_arp_table()
    devices = []
    for result in results:
        if result:
            ip, latency = result
            devices.append({"ip": ip, "mac": arp.get(ip, "Unknown"), "latency": latency})
    return sorted(devices, key=lambda d: ipaddress.ip_address(d["ip"]))

def stable_angle(value):
    total = sum((index + 1) * ord(char) for index, char in enumerate(value))
    return (total * 137) % 360

def stable_ring(value, count):
    if count <= 1:
        return 1
    total = sum(ord(char) for char in value)
    return total % min(4, count) + 1

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Wi-Fi Device Map")
        self.root.geometry("1180x760")
        self.root.minsize(950, 650)
        self.root.configure(bg=BG)
        self.devices = []
        self.scanning = False
        self.after_id = None

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=30, borderwidth=0)
        style.configure("Treeview.Heading", background="#17212d", foreground=TEXT, relief="flat")
        style.map("Treeview", background=[("selected", "#1d4260")], foreground=[("selected", "white")])

        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=22, pady=(18, 8))
        tk.Label(header, text="Wi-Fi Device Map", font=("Segoe UI", 22, "bold"), bg=BG, fg=TEXT).pack(side="left")
        self.status = tk.Label(header, text="Ready", font=("Segoe UI", 10), bg=BG, fg=MUTED)
        self.status.pack(side="left", padx=16)

        self.refresh_button = tk.Button(header, text="Scan Now", command=self.start_scan, bg=ACCENT, fg="#071019", activebackground="#8bd2ff", relief="flat", font=("Segoe UI", 10, "bold"), padx=18, pady=9, cursor="hand2")
        self.refresh_button.pack(side="right")

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=10)

        map_frame = tk.Frame(body, bg=PANEL)
        map_frame.pack(side="left", fill="both", expand=True)

        self.canvas = tk.Canvas(map_frame, bg=PANEL, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=12, pady=12)
        self.canvas.bind("<Configure>", lambda event: self.draw_map())

        side = tk.Frame(body, bg=BG, width=330)
        side.pack(side="right", fill="y", padx=(14, 0))
        side.pack_propagate(False)

        tk.Label(side, text="Detected devices", font=("Segoe UI", 15, "bold"), bg=BG, fg=TEXT).pack(anchor="w", pady=(4, 8))
        self.count_label = tk.Label(side, text="0 devices", font=("Segoe UI", 10), bg=BG, fg=MUTED)
        self.count_label.pack(anchor="w", pady=(0, 8))

        tree_frame = tk.Frame(side, bg=PANEL)
        tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_frame, columns=("ip", "latency"), show="headings")
        self.tree.heading("ip", text="IP")
        self.tree.heading("latency", text="Latency")
        self.tree.column("ip", width=170)
        self.tree.column("latency", width=90)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.select_device)

        footer = tk.Frame(root, bg=BG)
        footer.pack(fill="x", padx=22, pady=(4, 16))
        tk.Label(footer, text="Router is centered. Device positions are visual estimates only; IP/MAC/ping cannot determine physical direction or exact feet.", font=("Segoe UI", 9), bg=BG, fg=MUTED).pack(side="left")
        self.detail = tk.Label(footer, text="", font=("Segoe UI", 9), bg=BG, fg=TEXT)
        self.detail.pack(side="right")

        self.start_scan()

    def start_scan(self):
        if self.scanning:
            return
        self.scanning = True
        self.refresh_button.configure(state="disabled", text="Scanning...")
        self.status.configure(text="Scanning local network...")
        threading.Thread(target=self.scan_worker, daemon=True).start()

    def scan_worker(self):
        gateway = get_gateway()
        local_ip = get_local_ip(gateway)
        devices = []
        error = None
        if local_ip:
            network = ipaddress.ip_network(f"{local_ip}/24", strict=False)
            devices = scan_lan(network)
        else:
            error = "Could not determine local IP"
        self.root.after(0, lambda: self.finish_scan(gateway, local_ip, devices, error))

    def finish_scan(self, gateway, local_ip, devices, error):
        self.scanning = False
        self.refresh_button.configure(state="normal", text="Scan Now")
        if error:
            self.status.configure(text=error, fg="#ff8d8d")
            return
        self.devices = devices
        self.status.configure(text=f"Gateway {gateway or 'unknown'}  •  Local IP {local_ip}  •  {len(devices)} responding devices", fg=GOOD)
        self.count_label.configure(text=f"{len(devices)} responding devices")
        for item in self.tree.get_children():
            self.tree.delete(item)
        for device in devices:
            latency = f"{device['latency']:.1f} ms" if device["latency"] is not None else "—"
            self.tree.insert("", "end", iid=device["ip"], values=(device["ip"], latency))
        self.draw_map()
        self.after_id = self.root.after(REFRESH_MS, self.start_scan)

    def draw_map(self):
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 500)
        height = max(self.canvas.winfo_height(), 500)
        cx = width / 2
        cy = height / 2
        radius = min(width, height) * 0.38
        rings = [(0.25, "25 ft"), (0.5, "50 ft"), (0.75, "75 ft"), (1.0, "100 ft")]

        for fraction, label in rings:
            r = radius * fraction
            self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline=GRID, width=1)
            self.canvas.create_text(cx + 8, cy - r + 10, text=label, anchor="w", fill=MUTED, font=("Segoe UI", 8))

        self.canvas.create_line(cx-radius, cy, cx+radius, cy, fill=GRID)
        self.canvas.create_line(cx, cy-radius, cx, cy+radius, fill=GRID)

        self.canvas.create_oval(cx-24, cy-24, cx+24, cy+24, fill=ACCENT, outline="")
        self.canvas.create_text(cx, cy, text="R", fill="#06101a", font=("Segoe UI", 13, "bold"))
        self.canvas.create_text(cx, cy+40, text="ROUTER", fill=TEXT, font=("Segoe UI", 10, "bold"))

        count = len(self.devices)
        for index, device in enumerate(self.devices):
            key = device["ip"] + device["mac"]
            ring_index = stable_ring(key, count)
            fraction = [0.25, 0.5, 0.75, 0.92][ring_index - 1]
            angle = stable_angle(key) * 3.1415926535 / 180
            r = radius * fraction
            x = cx + r * __import__("math").cos(angle)
            y = cy + r * __import__("math").sin(angle)
            node = 7
            self.canvas.create_line(cx, cy, x, y, fill="#1b2a39", dash=(2, 5))
            self.canvas.create_oval(x-node, y-node, x+node, y+node, fill=GOOD, outline="")
            self.canvas.create_text(x+12, y, text=device["ip"], anchor="w", fill=TEXT, font=("Segoe UI", 9))
            self.canvas.create_text(x+12, y+16, text=device["mac"], anchor="w", fill=MUTED, font=("Segoe UI", 7))

    def select_device(self, event=None):
        selected = self.tree.selection()
        if not selected:
            return
        ip = selected[0]
        device = next((d for d in self.devices if d["ip"] == ip), None)
        if device:
            latency = f"{device['latency']:.1f} ms" if device["latency"] is not None else "Unknown"
            self.detail.configure(text=f"{ip}  •  {device['mac']}  •  {latency}")

    def close(self):
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()
