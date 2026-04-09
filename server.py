"""
Depth Dedicated Server Controller
Flask web server that manages server restarts and exposes status to clients.
"""

import json
import sys
import subprocess
import sys
import threading
import time
import os
from datetime import datetime
from django import template
from django import template
from matplotlib.pyplot import grid
from waitress import serve
from flask import Flask, jsonify, request, abort, Response, send_from_directory
from functools import wraps

app = Flask(__name__)

def app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

SERVER_STARTUP_WAIT = 10
BASE_DIR = app_dir()
STATUS_FILE         = os.path.join(BASE_DIR, "status.json")
MAPS_DIR            = os.path.join(BASE_DIR, "maps")
CONFIG_FILE         = os.path.join(BASE_DIR, "config.json")

# Maps: folder name (used in command) -> display name on web dashboard
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
    existing = [p for p in DEFAULT_DEPTH_PATHS if os.path.isdir(p)]

    if not existing:
        return ""

    # Prefer non-Steam install if more than one exists
    non_steam = [p for p in existing if "steamapps" not in p.lower()]
    if non_steam:
        return non_steam[0]

    return existing[0]

@app.route("/anchor.png")
def anchor_icon():
    return send_from_directory(BASE_DIR, "anchor.png")

def load_config() -> dict:
    detected = detect_game_dir()
    default_config = {
        "base_game_dir": detected
    }

    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            return {
                "base_game_dir": data.get("base_game_dir", detected)
            }
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
        subprocess.run(["taskkill", "/f", "/im", "DepthGame.exe"], capture_output=True)
        time.sleep(2)

        lan_str = "true" if is_lan else "false"

        if allow_bots:
            cmd_map = (
                f"{map_name}?Game=DepthGame.DPGameInfo"
                f"?bIsLanMatch={lan_str}"
                f"?NumberOfHumans={num_humans}"
                f"?NumPublicConnections=6"
            )
        else:
            cmd_map = (
                f"{map_name}?Game=DepthGame.DPGameInfo"
                f"?bIsLanMatch={lan_str}"
                f"?NumberOfHumans={num_humans}"
                f"?NumPublicConnections=6"
                f"?NoBots"
            )

        if not _config["base_game_dir"] or not os.path.isdir(_config["base_game_dir"]):
          raise Exception("Game folder is not set or does not exist")

        server_exe = os.path.join(_config["base_game_dir"], r"Binaries\Win32\DepthServer.exe")
        if not os.path.isfile(server_exe):
          raise Exception(f"DepthServer.exe not found in: {_config['base_game_dir']}")
        
        write_status("starting", f"Launching server on {MAPS.get(map_name, map_name)}...")
        subprocess.Popen(
            [
                server_exe,
                cmd_map,
                "-PORT=7777",
                "-QueryPort=31000",
                "-nullrhi",
            ],
            cwd=_config["base_game_dir"],
        )

        write_status("waiting", f"Waiting {SERVER_STARTUP_WAIT}s for map load...")
        time.sleep(SERVER_STARTUP_WAIT)

        write_status("ready", f"Server ready on {MAPS.get(map_name, map_name)}")

        time.sleep(60)
        write_status("idle", "Session in progress")

    except Exception as e:
        write_status("error", str(e))


@app.route("/config")
def get_config():
    return jsonify(_config)


@app.route("/config", methods=["POST"])
def update_config():
    body = request.get_json(silent=True) or {}

    if "base_game_dir" in body:
        path = str(body["base_game_dir"]).strip()
        _config["base_game_dir"] = path
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
        "maps": [{"key": k, "display": v} for k, v in MAPS.items()],
        "current_index": _server_state["map_index"],
        "rotation_on": _server_state["rotation_on"],
        "is_lan": _server_state["is_lan"],
        "num_humans": _server_state["num_humans"],
        "allow_bots": _server_state["allow_bots"],
        "current_map": _server_state["current_map"],
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

    is_lan     = bool(body.get("is_lan", _server_state["is_lan"]))
    num_humans = int(body.get("num_humans", _server_state["num_humans"]))
    allow_bots = bool(body.get("allow_bots", _server_state["allow_bots"]))

    if not (1 <= num_humans <= 6):
        return jsonify({"error": "num_humans must be between 1 and 6"}), 400

    _server_state["is_lan"]     = is_lan
    _server_state["num_humans"] = num_humans
    _server_state["allow_bots"] = allow_bots

    thread = threading.Thread(
        target=restart_sequence,
        args=(map_name, is_lan, num_humans, allow_bots),
        daemon=True
    )
    thread.start()

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


@app.route("/")
def dashboard():
    maps_json         = json.dumps([{"key": k, "display": v} for k, v in MAPS.items()])
    map_keys_json     = json.dumps(MAP_KEYS)
    server_state_json = json.dumps(_server_state)
    startup_wait_json = json.dumps(SERVER_STARTUP_WAIT)
    config_json = json.dumps(_config)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<link rel="icon" type="image/png" href="/favicon.ico">
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Depth Server Controller</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #080c10;
      --surface: #0f1923;
      --surface2: #162030;
      --border: #1e3a4a;
      --accent: #00c8ff;
      --accent2: #ff6b35;
      --text: #d0e8f0;
      --muted: #4a7a90;
      --ready: #06d6a0;
      --warn: #ffd23f;
      --danger: #ef476f;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      background: var(--bg);
      background-image:
        radial-gradient(ellipse at 20% 50%, rgba(0,100,150,0.08) 0%, transparent 60%),
        radial-gradient(ellipse at 80% 20%, rgba(0,50,100,0.06) 0%, transparent 50%);
      color: var(--text);
      font-family: 'Rajdhani', sans-serif;
      min-height: 100vh;
      padding: 1rem;
      -webkit-tap-highlight-color: transparent;
    }}

    header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 1.25rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid var(--border);
      flex-wrap: wrap;
    }}

    header h1 {{
      font-size: 1.6rem;
      font-weight: 700;
      letter-spacing: .2em;
      text-transform: uppercase;
      color: var(--accent);
      text-shadow: 0 0 20px rgba(0,200,255,0.3);
    }}

    .status-pill {{
      font-family: 'Share Tech Mono', monospace;
      font-size: .85rem;
      padding: .3rem .9rem;
      border-radius: 2px;
      text-transform: uppercase;
      letter-spacing: .1em;
      border: 1px solid currentColor;
    }}

    .grid {{
      display: grid;
      grid-template-columns: 1fr 320px;
      gap: 1.5rem;
    }}

    @media (max-width: 900px) {{
      .grid {{
        grid-template-columns: 1fr;
      }}
    }}

    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 1.5rem;
    }}

    .card-title {{
      font-size: .7rem;
      font-weight: 600;
      letter-spacing: .15em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 1.2rem;
      padding-bottom: .6rem;
      border-bottom: 1px solid var(--border);
    }}

    .map-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
      gap: .75rem;
    }}

    .map-card {{
      background: var(--surface2);
      border: 2px solid var(--border);
      border-radius: 3px;
      cursor: pointer;
      overflow: hidden;
      transition: border-color .15s, transform .15s, opacity .15s;
      position: relative;
      touch-action: manipulation;
      user-select: none;
    }}

    .map-card:hover {{
      border-color: var(--accent);
      transform: translateY(-2px);
    }}

    .map-card.selected {{
      border-color: var(--accent);
      box-shadow: 0 0 16px rgba(0,200,255,0.2);
    }}

    .map-card.current-map {{
      border-color: var(--ready);
      box-shadow: 0 0 16px rgba(6,214,160,0.2);
    }}

    .map-card img {{
      width: 100%;
      aspect-ratio: 16/9;
      object-fit: cover;
      display: block;
      background: #0a1520;
    }}

    .map-card .map-label {{
      padding: .4rem .5rem;
      font-size: .8rem;
      font-weight: 600;
      letter-spacing: .05em;
      text-align: center;
      background: var(--surface2);
    }}

    .map-card .current-badge {{
      position: absolute;
      top: 4px;
      right: 4px;
      background: var(--ready);
      color: #000;
      font-size: .6rem;
      font-weight: 700;
      padding: 2px 5px;
      border-radius: 2px;
      letter-spacing: .05em;
      display: none;
    }}

    .map-card.current-map .current-badge {{
      display: block;
    }}

    .panel {{
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }}

    .state-display {{
      font-family: 'Share Tech Mono', monospace;
      font-size: 2rem;
      font-weight: 400;
      text-transform: uppercase;
      letter-spacing: .05em;
      margin-bottom: .5rem;
    }}

    .state-msg {{
      font-size: .9rem;
      color: var(--muted);
      line-height: 1.5;
    }}

    .state-time {{
      font-size: .7rem;
      color: #1e3a4a;
      margin-top: .4rem;
      font-family: 'Share Tech Mono', monospace;
    }}

    .option-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: .75rem 0;
      border-bottom: 1px solid var(--border);
      gap: 1rem;
    }}

    .option-row:last-child {{
      border-bottom: none;
    }}

    .option-row-stack {{
      align-items: flex-start;
      flex-direction: column;
      gap: .65rem;
    }}

    .option-label {{
      font-size: .95rem;
      font-weight: 600;
    }}

    .option-sub {{
      font-size: .75rem;
      color: var(--muted);
    }}

    .select-control {{
      width: 100%;
      background: var(--surface2);
      border: 1px solid var(--border);
      color: var(--text);
      padding: .7rem .8rem;
      border-radius: 3px;
      font-family: 'Rajdhani', sans-serif;
      font-size: 1rem;
      font-weight: 600;
      outline: none;
    }}

    .select-control:focus {{
      border-color: var(--accent);
      box-shadow: 0 0 0 2px rgba(0,200,255,0.15);
    }}

    .toggle {{
      position: relative;
      width: 44px;
      height: 24px;
      flex-shrink: 0;
    }}

    .toggle input {{
      opacity: 0;
      width: 0;
      height: 0;
    }}

    .toggle-track {{
      position: absolute;
      inset: 0;
      background: var(--border);
      border-radius: 24px;
      cursor: pointer;
      transition: background .2s;
    }}

    .toggle input:checked + .toggle-track {{
      background: var(--accent);
    }}

    .toggle-track::after {{
      content: '';
      position: absolute;
      top: 3px;
      left: 3px;
      width: 18px;
      height: 18px;
      background: white;
      border-radius: 50%;
      transition: transform .2s;
    }}

    .toggle input:checked + .toggle-track::after {{
      transform: translateX(20px);
    }}

    .next-map-row {{
      display: flex;
      align-items: center;
      gap: .6rem;
      padding: .6rem .75rem;
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: 3px;
      font-size: .85rem;
      margin-top: .75rem;
      transition: opacity .2s;
    }}

    .next-map-row.hidden {{
      opacity: 0;
      pointer-events: none;
      height: 0;
      margin-top: 0;
      padding-top: 0;
      padding-bottom: 0;
      border: none;
      overflow: hidden;
    }}

    .text-control {{
      width: 100%;
      background: var(--surface2);
      border: 1px solid var(--border);
      color: var(--text);
      padding: .7rem .8rem;
      border-radius: 3px;
      font-family: 'Rajdhani', sans-serif;
      font-size: 1rem;
      font-weight: 600;
      outline: none;
    }}

    .text-control:focus {{
      border-color: var(--accent);
      box-shadow: 0 0 0 2px rgba(0,200,255,0.15);
    }}

    .path-row {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: .6rem;
      width: 100%;
    }}

    .btn-secondary {{
      padding: .7rem 1rem;
      min-height: 46px;
      background: transparent;
      border: 1px solid var(--accent);
      color: var(--accent);
      font-family: 'Rajdhani', sans-serif;
      font-size: .95rem;
      font-weight: 700;
      letter-spacing: .08em;
      text-transform: uppercase;
      border-radius: 3px;
      cursor: pointer;
      transition: background .2s, color .2s, box-shadow .2s;
      white-space: nowrap;
    }}

    .btn-secondary:hover {{
      background: var(--accent);
      color: #000;
      box-shadow: 0 0 16px rgba(0,200,255,0.25);
    }}

    .next-arrow {{
      color: var(--accent);
      font-family: 'Share Tech Mono', monospace;
    }}

    .btn-restart {{
      width: 100%;
      padding: 1rem;
      min-height: 56px;
      background: transparent;
      border: 2px solid var(--accent);
      color: var(--accent);
      font-family: 'Rajdhani', sans-serif;
      font-size: 1.05rem;
      font-weight: 700;
      letter-spacing: .15em;
      text-transform: uppercase;
      border-radius: 3px;
      cursor: pointer;
      transition: background .2s, color .2s, box-shadow .2s;
      position: relative;
      overflow: hidden;
      touch-action: manipulation;
    }}

    .btn-restart:hover:not(:disabled) {{
      background: var(--accent);
      color: #000;
      box-shadow: 0 0 24px rgba(0,200,255,0.4);
    }}

    .btn-restart:disabled {{
      border-color: var(--border);
      color: var(--muted);
      cursor: not-allowed;
    }}

    .progress-wrap {{
      height: 3px;
      background: var(--border);
      border-radius: 2px;
      overflow: hidden;
      margin-top: .75rem;
    }}

    .progress-bar {{
      height: 100%;
      width: 0%;
      background: var(--accent);
      transition: width .5s linear;
    }}

    @media (max-width: 700px) {{
      body {{
        padding: .75rem;
      }}

      .path-row {{
        grid-template-columns: 1fr;
      }}

      header h1 {{
        font-size: 1.2rem;
        letter-spacing: .12em;
      }}

      .card {{
        padding: 1rem;
      }}

      .state-display {{
        font-size: 1.5rem;
      }}

      .map-grid {{
        grid-template-columns: repeat(2, 1fr);
        gap: .65rem;
      }}

      .map-card .map-label {{
        font-size: .78rem;
        padding: .5rem .4rem;
      }}

      .option-row {{
        gap: .8rem;
      }}

      .status-pill {{
        font-size: .78rem;
      }}
    }}
  </style>
</head>
<body>

<header>
  <h1><img src="/anchor.png" style="height:2rem;vertical-align:middle;margin-right:.6rem;">Depth Controller</h1>
  <span class="status-pill" id="header-pill">—</span>
</header>

<div class="grid">
  <!-- Map picker -->
  <div class="card">
    <div class="card-title">Select Map</div>
    <div class="map-grid" id="map-grid"></div>
  </div>

  <!-- Right panel -->
  <div class="panel">
    <!-- Server state -->
    <div class="card">
      <div class="card-title">Server Status</div>
      <div class="state-display" id="state-text">—</div>
      <div class="state-msg" id="state-msg"></div>
      <div class="state-time" id="state-time"></div>
      <div class="progress-wrap">
        <div class="progress-bar" id="progress-bar"></div>
      </div>
    </div>

    <!-- Options -->
    <div class="card">
      <div class="card-title">Options</div>

      <div class="option-row option-row-stack">
        <div>
          <div class="option-label">Game Folder</div>
          <div class="option-sub">Select the location of your Depth installation</div>
        </div>

        <div class="path-row">
          <input type="text" id="opt-game-dir" class="text-control" placeholder="Select Depth folder...">
          <button type="button" class="btn-secondary" id="btn-browse-folder">Browse</button>
        </div>
      </div>

      <div class="option-row option-row-stack">
        <div>
          <div class="option-label">Human Players</div>
          <div class="option-sub">Choose 1 to 6 human slots</div>
        </div>
        <select id="opt-humans" class="select-control">
          <option value="1">1</option>
          <option value="2">2</option>
          <option value="3">3</option>
          <option value="4">4</option>
          <option value="5">5</option>
          <option value="6">6</option>
        </select>
      </div>

      <div class="option-row">
        <div>
          <div class="option-label">Allow Bots</div>
          <div class="option-sub">Disable to launch with ?NoBots</div>
        </div>
        <label class="toggle">
          <input type="checkbox" id="opt-bots">
          <div class="toggle-track"></div>
        </label>
      </div>

      <div class="option-row">
        <div>
          <div class="option-label">LAN Match</div>
          <div class="option-sub">Restricts to local network</div>
        </div>
        <label class="toggle">
          <input type="checkbox" id="opt-lan">
          <div class="toggle-track"></div>
        </label>
      </div>

      <div class="option-row">
        <div>
          <div class="option-label">Map Rotation</div>
          <div class="option-sub">Auto-advance map each restart</div>
        </div>
        <label class="toggle">
          <input type="checkbox" id="opt-rotation">
          <div class="toggle-track"></div>
        </label>
      </div>

      <div class="next-map-row hidden" id="next-map-row">
        <span class="next-arrow">NEXT →</span>
        <span id="next-map-label">—</span>
      </div>
    </div>

    <!-- Restart -->
    <div class="card">
      <button class="btn-restart" id="btn-restart" onclick="doRestart()">
        ↺  Restart Server
      </button>
    </div>
  </div>
</div>

<script>
const MAPS         = {maps_json};
const MAP_KEYS     = {map_keys_json};
const SERVER_STATE = {server_state_json};
const STARTUP_WAIT = {startup_wait_json};
const CONFIG       = {config_json};

const STATE_COLOURS = {{
  idle:     '#4a9eff',
  stopping: '#ff6b35',
  starting: '#ffd23f',
  waiting:  '#ffd23f',
  ready:    '#06d6a0',
  error:    '#ef476f',
  unknown:  '#888',
}};

let selectedMap   = null;
let rotationOn    = SERVER_STATE.rotation_on ?? false;
let rotationIndex = SERVER_STATE.map_index ?? 0;
let currentMap    = SERVER_STATE.current_map ?? null;

// Build map grid
function buildGrid() {{
  const grid = document.getElementById('map-grid');
  MAPS.forEach(m => {{
    const card = document.createElement('div');
    card.className = 'map-card';
    card.dataset.key = m.key;
    card.innerHTML = `
      <img src="/maps/${{m.key}}/preview.jpg"
           onerror="this.style.background='#0a1520';this.style.height='80px'"
           alt="${{m.display}}">
      <div class="current-badge">LIVE</div>
      <div class="map-label">${{m.display}}</div>`;
    card.onclick = () => selectMap(m.key);
    grid.appendChild(card);
  }});
}}

async function saveGameDir(path) {{
  await fetch('/config', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ base_game_dir: path }})
  }});
}}

async function browseGameFolder() {{
  const btn = document.getElementById('btn-browse-folder');
  btn.disabled = true;
  btn.textContent = 'Opening...';

  try {{
    const r = await fetch('/browse-folder', {{
      method: 'POST'
    }});

    const d = await r.json();
    if (d.base_game_dir !== undefined) {{
      document.getElementById('opt-game-dir').value = d.base_game_dir || '';
    }}
  }} catch (e) {{
    console.error('Folder picker failed', e);
  }} finally {{
    btn.disabled = false;
    btn.textContent = 'Browse';
  }}
}}

function selectMap(key, save = true) {{
  if (rotationOn) return;

  selectedMap = key;
  rotationIndex = MAP_KEYS.indexOf(key);

  document.querySelectorAll('.map-card').forEach(c => {{
    c.classList.toggle('selected', c.dataset.key === key);
  }});

  updateNextMap();

  if (save) {{
    fetch('/settings', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ map_index: rotationIndex }})
    }});
  }}
}}

function setCurrentMap(key) {{
  currentMap = key;
  document.querySelectorAll('.map-card').forEach(c => {{
    c.classList.toggle('current-map', c.dataset.key === key);
  }});
}}

function updateNextMap() {{
  const row = document.getElementById('next-map-row');
  const lbl = document.getElementById('next-map-label');

  if (!rotationOn) {{
    row.classList.add('hidden');
    return;
  }}

  row.classList.remove('hidden');

  const nextIdx = (rotationIndex + 1) % MAP_KEYS.length;
  const nextKey = MAP_KEYS[nextIdx];
  const nextDisplay = MAPS.find(m => m.key === nextKey)?.display || nextKey;
  lbl.textContent = nextDisplay;
}}

function applyRotationUI() {{
  document.querySelectorAll('.map-card').forEach(c => {{
    c.style.opacity = rotationOn ? '0.5' : '1';
    c.style.pointerEvents = rotationOn ? 'none' : '';
  }});
}}

// Rotation toggle
document.getElementById('opt-rotation').addEventListener('change', function() {{
  rotationOn = this.checked;
  updateNextMap();
  applyRotationUI();

  fetch('/settings', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ rotation_on: rotationOn }})
  }});
}});

// LAN toggle
document.getElementById('opt-lan').addEventListener('change', function() {{
  fetch('/settings', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ is_lan: this.checked }})
  }});
}});

// Human players
document.getElementById('opt-humans').addEventListener('change', function() {{
  fetch('/settings', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ num_humans: parseInt(this.value, 10) }})
  }});
}});

// Allow bots
document.getElementById('opt-bots').addEventListener('change', function() {{
  fetch('/settings', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ allow_bots: this.checked }})
  }});
}});

// Browse and save game folder
document.getElementById('btn-browse-folder').addEventListener('click', browseGameFolder);

document.getElementById('opt-game-dir').addEventListener('change', function() {{
  saveGameDir(this.value.trim());
}});

// State display
function applyState(data) {{
  const state = data.state || 'unknown';
  const colour = STATE_COLOURS[state] || '#888';

  document.getElementById('state-text').textContent = state.toUpperCase();
  document.getElementById('state-text').style.color = colour;
  document.getElementById('state-msg').textContent = data.message || '';

  if (data.updated_at) {{
    const dt = new Date(data.updated_at);
    document.getElementById('state-time').textContent = 'updated ' + dt.toLocaleString();
  }} else {{
    document.getElementById('state-time').textContent = '';
  }}

  document.getElementById('header-pill').textContent = state;
  document.getElementById('header-pill').style.color = colour;

  const busy = ['stopping', 'starting', 'waiting'].includes(state);
  const restartBtn = document.getElementById('btn-restart');
  restartBtn.disabled = busy;
  restartBtn.textContent = busy ? 'WORKING...' : '↺  Restart Server';

  const bar = document.getElementById('progress-bar');
  if (state === 'waiting') {{
    bar.style.transition = `width ${{STARTUP_WAIT}}s linear`;
    bar.style.width = '100%';
  }} else if (state === 'ready') {{
    bar.style.transition = 'none';
    bar.style.width = '100%';
    bar.style.background = 'var(--ready)';
  }} else {{
    bar.style.transition = 'none';
    bar.style.width = '0%';
    bar.style.background = 'var(--accent)';
  }}

  if (data.current_map) {{
    setCurrentMap(data.current_map);
  }}
}}

// Poll
async function poll() {{
  try {{
    const r = await fetch('/status');
    const d = await r.json();
    applyState(d);
  }} catch (e) {{
    document.getElementById('state-text').textContent = 'UNREACHABLE';
    document.getElementById('state-text').style.color = '#888';
  }}
  setTimeout(poll, 3000);
}}

// Restart
async function doRestart() {{
  const map = rotationOn ? null : (selectedMap || currentMap);
  document.getElementById('btn-restart').disabled = true;

  await fetch('/restart', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{
      map: map,
      is_lan: document.getElementById('opt-lan').checked,
      num_humans: parseInt(document.getElementById('opt-humans').value, 10),
      allow_bots: document.getElementById('opt-bots').checked,
    }})
  }});

  setTimeout(poll, 500);
}}

// Init
buildGrid();

document.getElementById('opt-lan').checked = SERVER_STATE.is_lan ?? false;
document.getElementById('opt-humans').value = SERVER_STATE.num_humans ?? 2;
document.getElementById('opt-bots').checked = SERVER_STATE.allow_bots ?? true;
document.getElementById('opt-rotation').checked = rotationOn;
document.getElementById('opt-game-dir').value = CONFIG.base_game_dir ?? '';

if (currentMap) {{
  selectedMap = currentMap;
  selectMap(currentMap, false);
  setCurrentMap(currentMap);
}}

updateNextMap();
applyRotationUI();
poll();
</script>
</body>
</html>"""
    return Response(html, mimetype="text/html")


@app.route("/maps/<map_name>/<filename>")
def map_image(map_name, filename):
    return send_from_directory(os.path.join(MAPS_DIR, map_name), filename)


if __name__ == "__main__":
    write_status("idle", "Server controller started")
    serve(app, host="127.0.0.1", port=5000)