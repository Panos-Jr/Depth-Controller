const STATE_COLOURS = {
  idle:     '#4a9eff',
  stopping: '#ff6b35',
  starting: '#ffd23f',
  waiting:  '#ffd23f',
  ready:    '#06d6a0',
  error:    '#ef476f',
  unknown:  '#888',
};

let selectedMap   = null;
let rotationOn    = SERVER_STATE.rotation_on ?? false;
let rotationIndex = SERVER_STATE.map_index ?? 0;
let currentMap    = SERVER_STATE.current_map ?? null;

function buildGrid() {
  const grid = document.getElementById('map-grid');
  MAPS.forEach(m => {
    const card = document.createElement('div');
    card.className = 'map-card';
    card.dataset.key = m.key;
    card.innerHTML = `
      <img src="/maps/${m.key}/preview.jpg"
           onerror="this.style.background='#0a1520';this.style.height='80px'"
           alt="${m.display}">
      <div class="current-badge">LIVE</div>
      <div class="map-label">${m.display}</div>`;
    card.onclick = () => selectMap(m.key);
    grid.appendChild(card);
  });
}

function selectMap(key, save = true) {
  if (rotationOn) return;

  selectedMap   = key;
  rotationIndex = MAP_KEYS.indexOf(key);

  document.querySelectorAll('.map-card').forEach(c => {
    c.classList.toggle('selected', c.dataset.key === key);
  });

  updateNextMap();

  if (save) {
    fetch('/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ map_index: rotationIndex }),
    });
  }
}

function setCurrentMap(key) {
  currentMap = key;
  document.querySelectorAll('.map-card').forEach(c => {
    c.classList.toggle('current-map', c.dataset.key === key);
  });
}

function updateNextMap() {
  const row = document.getElementById('next-map-row');
  const lbl = document.getElementById('next-map-label');

  if (!rotationOn) {
    row.classList.add('hidden');
    return;
  }

  row.classList.remove('hidden');

  const nextIdx     = (rotationIndex + 1) % MAP_KEYS.length;
  const nextKey     = MAP_KEYS[nextIdx];
  const nextDisplay = MAPS.find(m => m.key === nextKey)?.display || nextKey;
  lbl.textContent   = nextDisplay;
}

function applyRotationUI() {
  document.querySelectorAll('.map-card').forEach(c => {
    c.style.opacity       = rotationOn ? '0.5' : '1';
    c.style.pointerEvents = rotationOn ? 'none' : '';
  });
}

async function saveGameDir(path) {
  await fetch('/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ base_game_dir: path }),
  });
}

async function browseGameFolder() {
  const btn = document.getElementById('btn-browse-folder');
  btn.disabled    = true;
  btn.textContent = 'Opening...';

  try {
    const r = await fetch('/browse-folder', { method: 'POST' });
    const d = await r.json();
    if (d.base_game_dir !== undefined) {
      document.getElementById('opt-game-dir').value = d.base_game_dir || '';
    }
  } catch (e) {
    console.error('Folder picker failed', e);
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Browse';
  }
}

function applyState(data) {
  const state  = data.state || 'unknown';
  const colour = STATE_COLOURS[state] || '#888';

  document.getElementById('state-text').textContent = state.toUpperCase();
  document.getElementById('state-text').style.color = colour;
  document.getElementById('state-msg').textContent  = data.message || '';

  if (data.updated_at) {
    const dt = new Date(data.updated_at);
    document.getElementById('state-time').textContent = 'updated ' + dt.toLocaleString();
  } else {
    document.getElementById('state-time').textContent = '';
  }

  document.getElementById('header-pill').textContent = state;
  document.getElementById('header-pill').style.color = colour;

  const busy       = ['stopping', 'starting', 'waiting'].includes(state);
  const restartBtn = document.getElementById('btn-restart');
  restartBtn.disabled    = busy;
  restartBtn.textContent = busy ? 'WORKING...' : '↺  Restart Server';

  const bar = document.getElementById('progress-bar');
  if (state === 'waiting') {
    bar.style.transition = `width ${STARTUP_WAIT}s linear`;
    bar.style.width      = '100%';
  } else if (state === 'ready') {
    bar.style.transition = 'none';
    bar.style.width      = '100%';
    bar.style.background = 'var(--ready)';
  } else {
    bar.style.transition = 'none';
    bar.style.width      = '0%';
    bar.style.background = 'var(--accent)';
  }

  if (data.current_map) {
    setCurrentMap(data.current_map);
  }
}

async function poll() {
  try {
    const r = await fetch('/status');
    const d = await r.json();
    applyState(d);
  } catch (e) {
    document.getElementById('state-text').textContent = 'UNREACHABLE';
    document.getElementById('state-text').style.color = '#888';
  }
  setTimeout(poll, 3000);
}

async function doRestart() {
  const map = rotationOn ? null : (selectedMap || currentMap);
  document.getElementById('btn-restart').disabled = true;

  await fetch('/restart', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      map,
      is_lan:     document.getElementById('opt-lan').checked,
      num_humans: parseInt(document.getElementById('opt-humans').value, 10),
      allow_bots: document.getElementById('opt-bots').checked,
    }),
  });

  // Sync rotation index from server
  const r = await fetch('/maps');
  const d = await r.json();
  rotationIndex = d.current_index ?? rotationIndex;
  updateNextMap();

  setTimeout(poll, 500);
}

document.getElementById('opt-rotation').addEventListener('change', function () {
  rotationOn = this.checked;
  updateNextMap();
  applyRotationUI();
  fetch('/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rotation_on: rotationOn }),
  });
});

document.getElementById('opt-lan').addEventListener('change', function () {
  fetch('/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_lan: this.checked }),
  });
});

document.getElementById('opt-humans').addEventListener('change', function () {
  fetch('/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ num_humans: parseInt(this.value, 10) }),
  });
});

document.getElementById('opt-bots').addEventListener('change', function () {
  fetch('/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ allow_bots: this.checked }),
  });
});

document.getElementById('btn-browse-folder').addEventListener('click', browseGameFolder);

document.getElementById('opt-game-dir').addEventListener('change', function () {
  saveGameDir(this.value.trim());
});


// Init

buildGrid();

document.getElementById('opt-lan').checked      = SERVER_STATE.is_lan ?? false;
document.getElementById('opt-humans').value      = SERVER_STATE.num_humans ?? 2;
document.getElementById('opt-bots').checked      = SERVER_STATE.allow_bots ?? true;
document.getElementById('opt-rotation').checked  = rotationOn;
document.getElementById('opt-game-dir').value    = CONFIG.base_game_dir ?? '';

if (currentMap) {
  selectedMap = currentMap;
  selectMap(currentMap, false);
  setCurrentMap(currentMap);
}

updateNextMap();
applyRotationUI();
poll();
