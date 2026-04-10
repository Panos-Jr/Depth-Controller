"""
Depth Dedicated Server Controller
Flask web server that manages server restarts and exposes status to clients.
"""

import json
import sys
import subprocess
import threading
import time
import os
from datetime import datetime
from waitress import serve
import sys
from flask import Flask, jsonify, request, Response, send_from_directory

def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS # type: ignore
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_executable_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

EXE_DIR         = get_executable_dir()
STATUS_FILE     = os.path.join(EXE_DIR, "status.json")
CONFIG_FILE     = os.path.join(EXE_DIR, "config.json")

STATIC_DIR      = get_resource_path("static")
TEMPLATES_DIR   = get_resource_path("templates")
MAPS_DIR        = get_resource_path("maps")
ANCHOR_ICON_DIR = get_resource_path("")

app = Flask(__name__, 
            static_folder=STATIC_DIR, 
            template_folder=TEMPLATES_DIR)

SERVER_STARTUP_WAIT = 10

MAPS = {
    "Antiguo":    "Antiguo",
    "Arctic":     "Snowfall",
    "Cove":       "Cove",
    "Crash":      "Breach",
    "Crude":      "Crude",
    "DevilsHead": "Devil's Head",
    "Facility":   "Ohm Base",
    "Fractured":  "Fractured",
    "Galleon":    "Galleon",
    "Hillside":   "Hillside",
    "Olmec":      "Olmec",
    "Stash":      "Stash",
    "Station":    "Station",
    "Temple":     "Temple",
    "Wreck":      "Wreck",
}
MAP_KEYS = list(MAPS.keys())

_lock = threading.Lock()
_server_state = {
    "map_index":   0,
    "rotation_on": False,
    "current_map": "Crude",
    "is_lan":      False,
    "num_humans":  2,
    "allow_bots":  True,
}

DEFAULT_DEPTH_PATHS = [
    r"D:\Games\Depth",
    r"C:\Games\Depth",
    r"C:\Program Files (x86)\Steam\steamapps\common\Depth",
]

def detect_game_dir() -> str:
    existing  = [p for p in DEFAULT_DEPTH_PATHS if os.path.isdir(p)]
    if not existing:
        return ""
    non_steam = [p for p in existing if "steamapps" not in p.lower()]
    return non_steam[0] if non_steam else existing[0]

def load_config() -> dict:
    detected       = detect_game_dir()
    default_config = {"base_game_dir": detected}
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            return {"base_game_dir": data.get("base_game_dir", detected)}
    except FileNotFoundError:
        save_config(default_config)
        return default_config
    except Exception:
        return default_config

def save_config(data: dict):
    with _lock:
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)

_config = load_config()

def write_status(state: str, message: str = ""):
    payload = {
        "state":       state,
        "message":     message,
        "current_map": _server_state["current_map"],
        "updated_at":  datetime.utcnow().isoformat() + "Z",
    }
    with _lock:
        with open(STATUS_FILE, "w") as f:
            json.dump(payload, f)
    print(f"[status] {state} — {message}")
    return payload

def read_status() -> dict:
    try:
        with _lock:
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
    except FileNotFoundError:
        return write_status("idle", "Server controller started")

def restart_sequence(map_name: str, is_lan: bool, num_humans: int, allow_bots: bool):
    try:
        _server_state["current_map"] = map_name
        write_status("stopping", "Killing server and game processes...")
        subprocess.run(["taskkill", "/f", "/im", "DepthServer.exe"], capture_output=True)
        subprocess.run(["taskkill", "/f", "/im", "DepthGame.exe"],   capture_output=True)
        time.sleep(2)

        lan_str = "true" if is_lan else "false"
        cmd_map = (
            f"{map_name}?Game=DepthGame.DPGameInfo"
            f"?bIsLanMatch={lan_str}"
            f"?NumberOfHumans={num_humans}"
            f"?NumPublicConnections=6"
        )
        if not allow_bots:
            cmd_map += "?NoBots"

        if not _config["base_game_dir"] or not os.path.isdir(_config["base_game_dir"]):
            raise Exception("Game folder is not set or does not exist")

        server_exe = os.path.join(_config["base_game_dir"], r"Binaries\Win32\DepthServer.exe")
        if not os.path.isfile(server_exe):
            raise Exception(f"DepthServer.exe not found in: {_config['base_game_dir']}")

        write_status("starting", f"Launching server on {MAPS.get(map_name, map_name)}...")
        subprocess.Popen(
            [server_exe, cmd_map, "-PORT=7777", "-QueryPort=31000", "-nullrhi"],
            cwd=_config["base_game_dir"],
        )

        write_status("waiting", f"Waiting {SERVER_STARTUP_WAIT}s for map load...")
        time.sleep(SERVER_STARTUP_WAIT)
        write_status("ready", f"Server ready on {MAPS.get(map_name, map_name)}")
        time.sleep(60)
        write_status("idle", "Session in progress")

    except Exception as e:
        write_status("error", str(e))

@app.route("/anchor.png")
def anchor_icon():
    return send_from_directory(ANCHOR_ICON_DIR, "anchor.png")

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)

@app.route("/maps/<map_name>/<filename>")
def map_image(map_name, filename):
    return send_from_directory(os.path.join(MAPS_DIR, map_name), filename)

@app.route("/config")
def get_config():
    return jsonify(_config)

@app.route("/config", methods=["POST"])
def update_config():
    body = request.get_json(silent=True) or {}
    if "base_game_dir" in body:
        _config["base_game_dir"] = str(body["base_game_dir"]).strip()
        save_config(_config)
    return jsonify({"ok": True, **_config})

@app.route("/browse-folder", methods=["POST"])
def browse_folder():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.askdirectory(
        title="Select your Depth game folder",
        initialdir=_config.get("base_game_dir") or "C:\\"
    )
    root.destroy()
    if selected:
        _config["base_game_dir"] = selected
        save_config(_config)
        return jsonify({"ok": True, "base_game_dir": selected})
    return jsonify({"ok": False, "base_game_dir": _config.get("base_game_dir", "")})

@app.route("/status")
def status():
    return jsonify(read_status())

@app.route("/maps")
def maps():
    return jsonify({
        "maps":          [{"key": k, "display": v} for k, v in MAPS.items()],
        "current_index": _server_state["map_index"],
        "rotation_on":   _server_state["rotation_on"],
        "is_lan":        _server_state["is_lan"],
        "num_humans":    _server_state["num_humans"],
        "allow_bots":    _server_state["allow_bots"],
        "current_map":   _server_state["current_map"],
    })

@app.route("/restart", methods=["POST"])
def restart():
    current = read_status()
    if current["state"] in ("stopping", "starting", "waiting"):
        return jsonify({"error": "Restart already in progress", "state": current["state"]}), 409
    body = request.get_json(silent=True) or {}
    if _server_state["rotation_on"]:
        _server_state["map_index"] = (_server_state["map_index"] + 1) % len(MAP_KEYS)
        map_name = MAP_KEYS[_server_state["map_index"]]
    else:
        map_name = body.get("map", _server_state["current_map"])
        if map_name not in MAPS:
            return jsonify({"error": f"Unknown map: {map_name}"}), 400

    is_lan     = bool(body.get("is_lan",     _server_state["is_lan"]))
    num_humans = int(body.get("num_humans",  _server_state["num_humans"]))
    allow_bots = bool(body.get("allow_bots", _server_state["allow_bots"]))
    if not (1 <= num_humans <= 6):
        return jsonify({"error": "num_humans must be between 1 and 6"}), 400

    _server_state["is_lan"]     = is_lan
    _server_state["num_humans"] = num_humans
    _server_state["allow_bots"] = allow_bots

    threading.Thread(
        target=restart_sequence,
        args=(map_name, is_lan, num_humans, allow_bots),
        daemon=True,
    ).start()
    return jsonify({"ok": True, "map": map_name})

@app.route("/settings", methods=["POST"])
def settings():
    body = request.get_json(silent=True) or {}
    if "rotation_on" in body:
        _server_state["rotation_on"] = bool(body["rotation_on"])
    if "map_index" in body:
        idx = int(body["map_index"])
        if 0 <= idx < len(MAP_KEYS):
            _server_state["map_index"] = idx
    if "is_lan" in body:
        _server_state["is_lan"] = bool(body["is_lan"])
    if "num_humans" in body:
        val = int(body["num_humans"])
        if 1 <= val <= 6:
            _server_state["num_humans"] = val
    if "allow_bots" in body:
        _server_state["allow_bots"] = bool(body["allow_bots"])
    return jsonify({"ok": True, **_server_state})

def _load_template() -> str:
    path = os.path.join(TEMPLATES_DIR, "dashboard.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

@app.route("/")
def dashboard():
    inline_data = (
        "<script>\n"
        f"const MAPS         = {json.dumps([{'key': k, 'display': v} for k, v in MAPS.items()])};\n"
        f"const MAP_KEYS     = {json.dumps(MAP_KEYS)};\n"
        f"const SERVER_STATE = {json.dumps(_server_state)};\n"
        f"const STARTUP_WAIT = {json.dumps(SERVER_STARTUP_WAIT)};\n"
        f"const CONFIG       = {json.dumps(_config)};\n"
        "</script>"
    )
    html = _load_template().replace("__INLINE_DATA__", inline_data)
    return Response(html, mimetype="text/html")

if __name__ == "__main__":
    write_status("idle", "Server controller started")
    serve(app, host="0.0.0.0", port=5000)
