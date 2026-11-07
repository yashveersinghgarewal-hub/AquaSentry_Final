#!/usr/bin/env python3
"""
AquaSentry Desktop — runs the AquaSentry server and opens the dashboard in its own window.

    python desktop_app.py              # desktop window (needs: pip install pywebview)
    python desktop_app.py --browser    # use your normal web browser instead of a window
    python desktop_app.py --server-only --port 8000
    python desktop_app.py --lan        # also accept the ESP32 / other devices on your Wi-Fi (port 8000)

How it works:
  1. Starts the FastAPI backend (AquaSentry_Platform/app/main.py) on 127.0.0.1 in a background thread.
  2. Waits until /api/health answers.
  3. Opens http://127.0.0.1:<port>/ in a native window (pywebview uses Microsoft Edge WebView2 on Windows).
Closing the window stops the server.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

FROZEN = getattr(sys, "frozen", False)  # True inside a PyInstaller .exe
BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
PLATFORM_DIR = BUNDLE_DIR if FROZEN else os.path.join(BUNDLE_DIR, "AquaSentry_Platform")


def data_dir() -> str:
    """Where the database lives. Next to the code when run from source; in the user's app-data folder for the .exe."""
    if not FROZEN:
        return PLATFORM_DIR
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    path = os.path.join(base, "AquaSentry")
    os.makedirs(path, exist_ok=True)
    seed = os.path.join(BUNDLE_DIR, "aquasentry.db")
    target = os.path.join(path, "aquasentry.db")
    if os.path.exists(seed) and not os.path.exists(target):
        shutil.copy2(seed, target)
    return path


def free_port(preferred: int) -> int:
    for port in [preferred] + list(range(preferred + 1, preferred + 50)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found between %d and %d" % (preferred, preferred + 49))


def start_server(port: int, host: str = "127.0.0.1"):
    os.chdir(data_dir())  # the database URL is relative: sqlite:///./aquasentry.db
    os.environ.setdefault("AQUASENTRY_FRONTEND_DIR", os.path.join(PLATFORM_DIR, "frontend"))
    sys.path.insert(0, PLATFORM_DIR)
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(PLATFORM_DIR, ".env"))
    except ImportError:
        pass

    import uvicorn
    from app.main import app  # imported directly so PyInstaller can find every dependency

    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server, thread


def lan_ip() -> str:
    """This PC's address on the local network (what the ESP32 should use)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))   # no packet is sent; this just picks the outgoing interface
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def wait_until_up(url: str, seconds: float = 30.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=1.5) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def main():
    ap = argparse.ArgumentParser(description="AquaSentry desktop app")
    ap.add_argument("--port", type=int, default=None, help="Preferred port (default 8765, or 8000 with --lan)")
    ap.add_argument("--lan", action="store_true",
                    help="Listen on your Wi-Fi network too, so the ESP32 can send readings (allow it in Windows Firewall)")
    ap.add_argument("--browser", action="store_true", help="Open in the default web browser instead of a window")
    ap.add_argument("--server-only", action="store_true", help="Only run the server (for testing)")
    args = ap.parse_args()

    port = free_port(args.port or (8000 if args.lan else 8765))
    url = f"http://127.0.0.1:{port}"
    host = "0.0.0.0" if args.lan else "127.0.0.1"
    print(f"[AquaSentry] Starting server on {url} ...")
    server, thread = start_server(port, host)
    if args.lan:
        print(f"[AquaSentry] Network mode: put this in Firmware/esp32_firmware/esp32_firmware.ino -> BACKEND_API_URL:")
        print(f"             http://{lan_ip()}:{port}/api/readings")
        print("             If Windows Firewall asks, allow Python on Private networks.")
    if not wait_until_up(url):
        print("[AquaSentry] The server did not start. Run 'pip install -r requirements.txt' and try again.")
        sys.exit(1)
    print("[AquaSentry] Server is running.")

    if args.server_only:
        try:
            while thread.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
    elif args.browser:
        webbrowser.open(url + "/")
        print("[AquaSentry] Opened in your browser. Press Ctrl+C here to stop.")
        try:
            while thread.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
    else:
        try:
            import webview  # pywebview
        except ImportError:
            print("[AquaSentry] pywebview is not installed, opening your browser instead.")
            print("            For a desktop window run: pip install pywebview")
            webbrowser.open(url + "/")
            try:
                while thread.is_alive():
                    time.sleep(0.5)
            except KeyboardInterrupt:
                pass
        else:
            webview.create_window("AquaSentry — Water Safety Monitor", url + "/", width=1320, height=880, min_size=(380, 600))
            webview.start()  # blocks until the window is closed

    print("[AquaSentry] Stopping server...")
    server.should_exit = True
    thread.join(timeout=5)


if __name__ == "__main__":
    main()
