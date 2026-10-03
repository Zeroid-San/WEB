import re
import subprocess
import threading
import time
import tkinter as tk
from collections import deque

BG = "#0b0f14"
PANEL = "#111821"
TEXT = "#e7edf5"
MUTED = "#8290a3"
ACCENT = "#59b7ff"
GOOD = "#67e8a5"
WARN = "#ffbf69"
BAD = "#ff7777"

SAMPLE_MS = 1000
WINDOW_SIZE = 60
CHANGE_THRESHOLD = 8

def get_wifi_info():
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True,
            text=True,
            timeout=5,
            encoding="utf-8",
            errors="ignore"
        )

        output = result.stdout

        ssid = re.search(r"^\s*SSID\s*:\s*(.+)$", output, re.MULTILINE)
        signal = re.search(r"^\s*Signal\s*:\s*(\d+)%", output, re.MULTILINE)

        if not signal:
            return None, None

        return (
            ssid.group(1).strip() if ssid else "Unknown",
            int(signal.group(1))
        )

    except (OSError, subprocess.SubprocessError):
        return None, None


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Wi-Fi Human Sensing")
        self.root.geometry("950x650")
        self.root.minsize(800, 560)
        self.root.configure(bg=BG)

        self.samples = deque(maxlen=WINDOW_SIZE)
        self.running = True
        self.previous_signal = None
        self.movement_score = 0

        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=22, pady=(18, 8))

        tk.Label(
            header,
            text="Wi-Fi Human Sensing",
            font=("Segoe UI", 22, "bold"),
            bg=BG,
            fg=TEXT
        ).pack(side="left")

        self.status = tk.Label(
            header,
            text="Starting...",
            font=("Segoe UI", 10, "bold"),
            bg=BG,
            fg=MUTED
        )
        self.status.pack(side="right")

        info = tk.Frame(root, bg=BG)
        info.pack(fill="x", padx=22, pady=10)

        self.ssid_label = tk.Label(
            info,
            text="Wi-Fi: detecting...",
            font=("Segoe UI", 11),
            bg=BG,
            fg=TEXT
        )
        self.ssid_label.pack(side="left")

        self.signal_label = tk.Label(
            info,
            text="Signal: --",
            font=("Segoe UI", 11, "bold"),
            bg=BG,
            fg=ACCENT
        )
        self.signal_label.pack(side="right")

        self.canvas = tk.Canvas(
            root,
            bg=PANEL,
            highlightthickness=0
        )
        self.canvas.pack(
            fill="both",
            expand=True,
            padx=22,
            pady=10
        )

        self.state_label = tk.Label(
            root,
            text="WAITING FOR DATA",
            font=("Segoe UI", 18, "bold"),
            bg=BG,
            fg=MUTED
        )
        self.state_label.pack(pady=(4, 2))

        self.explanation = tk.Label(
            root,
            text="Large changes in Wi-Fi signal may indicate movement. This is an experiment, not a precise people-location system.",
            font=("Segoe UI", 9),
            bg=BG,
            fg=MUTED
        )
        self.explanation.pack(pady=(0, 16))

        self.update()

    def update(self):
        if not self.running:
            return

        ssid, signal = get_wifi_info()

        if signal is not None:
            self.samples.append(signal)

            self.ssid_label.configure(
                text=f"Wi-Fi: {ssid}"
            )

            self.signal_label.configure(
                text=f"Signal: {signal}%"
            )

            if self.previous_signal is not None:
                change = abs(signal - self.previous_signal)

                if change >= CHANGE_THRESHOLD:
                    self.movement_score = min(
                        100,
                        self.movement_score + change * 2
                    )
                else:
                    self.movement_score = max(
                        0,
                        self.movement_score - 5
                    )

            self.previous_signal = signal

            if self.movement_score >= 35:
                self.state_label.configure(
                    text="MOVEMENT DETECTED",
                    fg=WARN
                )
                self.status.configure(
                    text="Signal changing",
                    fg=WARN
                )
            else:
                self.state_label.configure(
                    text="STABLE",
                    fg=GOOD
                )
                self.status.configure(
                    text="Monitoring",
                    fg=GOOD
                )

            self.draw_graph()

        else:
            self.status.configure(
                text="Wi-Fi data unavailable",
                fg=BAD
            )
            self.state_label.configure(
                text="NO WI-FI DATA",
                fg=BAD
            )

        self.root.after(
            SAMPLE_MS,
            self.update
        )

    def draw_graph(self):
        self.canvas.delete("all")

        width = max(
            self.canvas.winfo_width(),
            500
        )
        height = max(
            self.canvas.winfo_height(),
            300
        )

        left = 45
        right = width - 20
        top = 25
        bottom = height - 35

        for i in range(6):
            y = top + (bottom - top) * i / 5

            self.canvas.create_line(
                left,
                y,
                right,
                y,
                fill="#263342"
            )

            value = 100 - i * 20

            self.canvas.create_text(
                left - 10,
                y,
                text=str(value),
                anchor="e",
                fill=MUTED,
                font=("Segoe UI", 8)
            )

        values = list(self.samples)

        if len(values) < 2:
            return

        points = []

        for i, value in enumerate(values):
            x = left + (right - left) * i / max(
                1,
                WINDOW_SIZE - 1
            )

            y = bottom - (bottom - top) * value / 100

            points.extend([x, y])

        self.canvas.create_line(
            *points,
            fill=ACCENT,
            width=3,
            smooth=True
        )

        self.canvas.create_text(
            left,
            top - 12,
            text="Wi-Fi signal history",
            anchor="w",
            fill=TEXT,
            font=("Segoe UI", 10, "bold")
        )

    def close(self):
        self.running = False
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()
