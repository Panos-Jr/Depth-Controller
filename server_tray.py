"""
Depth Server Controller — Tray App
Wraps server.py's Flask app in a system tray icon.
"""

import threading
import webbrowser
import os
import sys

import pystray
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from server import app, write_status, app_dir
from waitress import serve

PORT        = 5000
DASHBOARD_URL = f"http://127.0.0.1:{PORT}/"

def load_icon() -> Image.Image:
    icon_path = os.path.join(app_dir(), "anchor.png")
    return Image.open(icon_path)

def run_server():
    write_status("idle", "Server controller started")
    serve(app, host="127.0.0.1", port=PORT)


def open_dashboard(icon, item):
    webbrowser.open(DASHBOARD_URL)


def quit_app(icon, item):
    icon.stop()
    os._exit(0)


def main():
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    menu = pystray.Menu(
        pystray.MenuItem("Open Controller", open_dashboard, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", quit_app),
    )

    icon = pystray.Icon(
        name="DepthController",
        icon=load_icon(),
        title="Depth Server Controller",
        menu=menu,
    )

    icon.run()


if __name__ == "__main__":
    main()
