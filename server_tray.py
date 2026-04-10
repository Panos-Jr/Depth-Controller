"""
Depth Server Controller — Tray App
Wraps server.py's Flask app in a system tray icon.
"""

import threading
import webbrowser
import os
import sys
import time
import pystray
from PIL import Image
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from server import app, write_status, get_executable_dir
from waitress import serve

PORT        = 5000
DASHBOARD_URL = f"http://127.0.0.1:{PORT}/"

def load_icon() -> Image.Image:
    icon_path = os.path.join(get_executable_dir(), "anchor.png")
    return Image.open(icon_path)

def run_server():
    write_status("idle", "Server controller started")
    serve(app, host="0.0.0.0", port=PORT)


def open_dashboard(icon, item):
    webbrowser.open(DASHBOARD_URL)


def quit_app(icon, item):
    icon.stop()
    os._exit(0)


import subprocess

def notify(title: str, message: str):
    subprocess.Popen([
        "powershell", "-WindowStyle", "Hidden", "-Command",
        f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $template.SelectSingleNode('//text[@id=1]').InnerText = '{title}'
        $template.SelectSingleNode('//text[@id=2]').InnerText = '{message}'
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Depth Controller').Show($toast)
        """
    ])

def main():
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    time.sleep(1)
    notify("Depth Controller", "Server is ready at http://127.0.0.1:5000/.")
    
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
