const { app, BrowserWindow, ipcMain, screen, dialog, globalShortcut, nativeImage } = require('electron');
const path = require('path');
const fs = require('fs');
const { Config } = require('./src/config');
const { LovenseClient, ButtplugServer, getLocalIP } = require('./src/bridge');
const { spawn, execFile } = require('child_process');
const { promisify } = require('util');
const execFileAsync = promisify(execFile);
const readline = require('readline');

// ── Portable path helpers ──
const IS_PACKAGED = app.isPackaged;
const APP_ROOT = IS_PACKAGED ? path.dirname(app.getPath('exe')) : path.join(__dirname, '..');
const CONFIG_PATH = path.join(APP_ROOT, 'config.json');
const TEMPLATES_DIR = path.join(APP_ROOT, 'templates');
const PYTHON = path.join(APP_ROOT, '.venv', 'Scripts', 'python.exe');
const WORKER_PATH = IS_PACKAGED
  ? path.join(APP_ROOT, 'vision-worker', 'vision-worker.exe')
  : path.join(__dirname, 'src', 'vision-worker.py');
const CAPTURE_SCRIPT = IS_PACKAGED
  ? path.join(APP_ROOT, 'vision-worker', 'capture-screen.exe')
  : path.join(__dirname, 'src', 'capture-screen.py');

// ── Crash logging ──
const CRASH_LOG = path.join(APP_ROOT, 'crash.log');

function crashLog(msg) {
  const ts = new Date().toISOString();
  const line = `[${ts}] ${msg}\n`;
  fs.appendFileSync(CRASH_LOG, line);
  console.error(line.trim());
}

process.on('uncaughtException', (e) => {
  crashLog(`UNCAUGHT EXCEPTION: ${e.message}\n${e.stack}`);
});
process.on('unhandledRejection', (e) => {
  crashLog(`UNHANDLED REJECTION: ${e?.message || e}\n${e?.stack || ''}`);
});

let win = null;
let overlayWin = null;
let debugWin = null;
let config = null;
let lovense = null;
let buttplugServer = null;
let visionProcess = null;
let lastLevel = -1;
let lastSendTime = 0;
let pendingOverlayRect = null;
let muted = false;
let muteKey = null;
let mutedToys = new Set();

function log(msg) {
  const ts = new Date().toLocaleTimeString('en-US', { hour12: false });
  console.log(`[${ts}] ${msg}`);
  if (win && !win.isDestroyed()) {
    win.webContents.send('log', msg);
  }
}

const BOUNDS_PATH = path.join(APP_ROOT, 'window-bounds.json');

function loadWindowBounds() {
  try {
    if (fs.existsSync(BOUNDS_PATH)) return JSON.parse(fs.readFileSync(BOUNDS_PATH, 'utf-8'));
  } catch {}
  return null;
}

function saveWindowBounds() {
  if (!win || win.isDestroyed()) return;
  try {
    const bounds = win.getBounds();
    fs.writeFileSync(BOUNDS_PATH, JSON.stringify(bounds));
    crashLog(`Window bounds saved: ${JSON.stringify(bounds)}`);
  } catch (e) {
    crashLog(`Failed to save bounds: ${e.message}`);
  }
}

function createWindow() {
  const saved = loadWindowBounds();
  win = new BrowserWindow({
    width: saved?.width || 1200,
    height: saved?.height || 680,
    x: saved?.x,
    y: saved?.y,
    frame: false,
    resizable: true,
    minWidth: 1100,
    minHeight: 650,
    backgroundColor: '#07030d',
    icon: path.join(__dirname, 'pancake.ico'),
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    },
  });

  win.loadFile(path.join(__dirname, 'app.html'));

  win.on('move', () => saveWindowBounds());
  win.on('resize', () => saveWindowBounds());
  win.on('close', () => saveWindowBounds());
  win.on('closed', () => {
    win = null;
    stopVision();
    try { if (overlayWin && !overlayWin.isDestroyed()) { overlayWin.destroy(); overlayWin = null; } } catch {}
    try { if (debugWin && !debugWin.isDestroyed()) { debugWin.destroy(); debugWin = null; } } catch {}
    if (lovense) { try { lovense.stopAll(); } catch {} }
    app.quit();
  });
}

// ── IPC handlers ──

// Lovense connection
ipcMain.handle('get-local-ip', () => getLocalIP());

ipcMain.handle('connect-lovense', async (_, ip) => {
  lovense = LovenseClient.fromIP(ip, { onLog: msg => log(`[Lovense] ${msg}`) });
  lovense.onReconnect = () => {
    log('[Lovense] Auto-reconnected');
    win?.webContents.send('lovense-status', true, lovense.toys);
  };
  lovense.onDisconnect = () => {
    log('[Lovense] Connection lost, will auto-retry...');
    win?.webContents.send('lovense-status', false);
  };
  const connected = await lovense.connect();
  if (!connected) {
    // Retry once
    const retry = await lovense.connect();
    if (!retry) return { ok: false, error: 'Could not connect. Check IP and Lovense app.' };
  }
  config.set('lovense_ip', ip);

  // Start Buttplug server for backward compat (only once)
  if (buttplugServer) {
    buttplugServer.stop();
  }
  buttplugServer = new ButtplugServer(lovense, { onLog: msg => log(`[Server] ${msg}`) });
  try {
    buttplugServer.start();
  } catch (e) {
    log(`Buttplug server: ${e.message}`);
  }

  return { ok: true, toys: lovense.toys };
});

ipcMain.handle('get-toys', () => lovense?.toys || {});

ipcMain.handle('send-action', async (_, toyId, action, level) => {
  if (lovense) await lovense.sendAction(toyId, action, level);
});

ipcMain.handle('send-actions', async (_, toyId, actionLevels) => {
  if (lovense) await lovense.sendActions(toyId, actionLevels);
});

ipcMain.handle('stop-all', async () => {
  if (lovense) await lovense.stopAll();
  lastLevel = -1;
});

ipcMain.handle('disconnect-lovense', async () => {
  if (lovense) {
    await lovense.stopAll();
    lovense.disconnect();
    lovense = null;
  }
  if (buttplugServer) {
    buttplugServer.stop();
    buttplugServer = null;
  }
  lastLevel = -1;
  log('Lovense disconnected');
});

ipcMain.handle('reset-score', () => {
  if (visionProcess) {
    visionProcess.stdin.write('reset\n');
  }
  lastLevel = -1;
  if (lovense) lovense.stopAll();
});

// Config
ipcMain.handle('get-config', () => ({ settings: config.settings, detectables: config.detectables }));
// Imported pixels keep their original dimensions and alpha. Calibration is explicit.
async function importTemplate() {
  const result = await dialog.showOpenDialog({title: 'Choose a template at its base resolution',
    filters: [{name: 'Images', extensions: ['png', 'jpg', 'bmp']}], properties: ['openFile']});
  if (result.canceled) return null;
  const image = nativeImage.createFromPath(result.filePaths[0]);
  if (image.isEmpty()) throw new Error('Cannot read image');
  const size = image.getSize();
  if (size.width > 2048 || size.height > 2048) throw new Error('Crop the template to at most 2048 × 2048 pixels first.');
  const filename = `template-${require('crypto').randomUUID()}.png`;
  fs.writeFileSync(path.join(TEMPLATES_DIR, filename), image.toPNG());
  return filename;
}
ipcMain.handle('pick-template', importTemplate);

ipcMain.handle('add-detectable', (_, name, fields) => {
  config.detectables[name] = fields;
  config.save();
  log(`Added detectable: ${name}`);
});

ipcMain.handle('delete-detectable', (_, name) => {
  delete config.detectables[name];
  config.save();
  log(`Deleted detectable: ${name}`);
});

ipcMain.handle('set-detectable', (_, name, field, value) => {
  if (config.detectables[name]) {
    if (field === 'duration') value = Math.max(0.1, value);
    config.detectables[name][field] = value;
    config.save();
  }
});
ipcMain.handle('set-config', (_, key, value) => {
  config.set(key, value);
  // Push settings to overlay
  if (overlayWin && !overlayWin.isDestroyed()) {
    if (key === 'show_overlay_mode') {
      if (value === 0) overlayWin.hide();
      else overlayWin.show();
    }
    if (key === 'show_regions_mode' || key === 'show_overlay_mode') {
      overlayWin.webContents.send('overlay-settings', config.settings);
    }
    if (key === 'theme_family' || key === 'theme_tint') {
      overlayWin.webContents.send('overlay-theme', {
        family: config.get('theme_family') || 'cyberpunk',
        accent: getThemeAccent(),
        accent2: getThemeAccent2(),
      });
    }
  }
});

// Vision (Python child process)
ipcMain.handle('is-vision-running', () => visionProcess !== null);

ipcMain.handle('start-vision', async () => {
  if (visionProcess) return { ok: false, error: 'Already running' };

  // Use the Prototype config (snake_case keys match Python Config class)
  const configPath = CONFIG_PATH;
  const templatesDir = TEMPLATES_DIR;

  try {
    visionProcess = IS_PACKAGED
      ? spawn(WORKER_PATH, [configPath, templatesDir], { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true })
      : spawn(PYTHON, [WORKER_PATH, configPath, templatesDir], { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });

    // Read JSON lines from stdout
    const child = visionProcess;
    child.on('error', e => { log(`Vision failed: ${e.message}`); if (visionProcess === child) visionProcess = null; });
    const rl = readline.createInterface({ input: visionProcess.stdout });
    rl.on('line', (line) => {
      try {
        const msg = JSON.parse(line);
        handleVisionMessage(msg);
      } catch {}
    });

    // Log stderr
    visionProcess.stderr.on('data', (data) => {
      const text = data.toString().trim();
      if (text) crashLog(`Vision stderr: ${text}`);
    });

    visionProcess.on('exit', (code) => {
      log(`Vision process exited (code ${code})`);
      if (visionProcess === child) visionProcess = null;
    });

    // Don't create overlay yet — wait for vision to send the rect
    log('Vision engine started (Python)');
    return { ok: true };
  } catch (e) {
    crashLog(`Vision start error: ${e.message}`);
    return { ok: false, error: e.message };
  }
});

ipcMain.handle('stop-vision', () => {
  stopVision();
  log('Vision engine stopped');
});

ipcMain.handle('restart-vision', async () => {
  stopVision(true); // keep overlay
  await new Promise(r => setTimeout(r, 500)); // let old process exit
  // Re-read config and start new worker
  const configPath = CONFIG_PATH;
  const templatesDir = TEMPLATES_DIR;
  try {
    visionProcess = IS_PACKAGED
      ? spawn(WORKER_PATH, [configPath, templatesDir], { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true })
      : spawn(PYTHON, [WORKER_PATH, configPath, templatesDir], { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
    const child = visionProcess;
    child.on('error', e => { log(`Vision failed: ${e.message}`); if (visionProcess === child) visionProcess = null; });
    const rl = readline.createInterface({ input: visionProcess.stdout });
    rl.on('line', (line) => {
      try { handleVisionMessage(JSON.parse(line)); } catch {}
    });
    visionProcess.stderr.on('data', (data) => {
      const text = data.toString().trim();
      if (text) crashLog(`Vision stderr: ${text}`);
    });
    visionProcess.on('exit', (code) => {
      log(`Vision process exited (code ${code})`);
      if (visionProcess === child) visionProcess = null;
    });
    log('Vision restarted');
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message };
  }
});

function stopVision(keepOverlay = false) {
  if (visionProcess) {
    visionProcess.kill();
    visionProcess = null;
  }
  if (!keepOverlay && overlayWin && !overlayWin.isDestroyed()) {
    overlayWin.close();
    overlayWin = null;
  }
}

function handleVisionMessage(msg) {
  if (msg.type === 'ready') {
    log(`Vision ready: monitor ${msg.monitor}, ${msg.aspect}`);
    if (msg.rect) {
      crashLog(`Vision rect received: ${msg.rect.left},${msg.rect.top} ${msg.rect.width}x${msg.rect.height}`);
      // If overlay already exists, refresh everything
      if (overlayWin && !overlayWin.isDestroyed()) {
        overlayWin.webContents.send('overlay-settings', config.settings);
        overlayWin.webContents.send('overlay-theme', {
          family: config.get('theme_family') || 'cyberpunk',
          accent: getThemeAccent(),
          accent2: getThemeAccent2(),
        });
        if (msg.regions) overlayWin.webContents.send('regions', msg.regions);
        return;
      }
      // Create overlay at the exact game rect
      overlayWin = new BrowserWindow({
        x: msg.rect.left,
        y: msg.rect.top,
        width: msg.rect.width,
        height: msg.rect.height,
        frame: false,
        transparent: true,
        alwaysOnTop: true,
        skipTaskbar: true,
        hasShadow: false,
        webPreferences: { nodeIntegration: true, contextIsolation: false },
      });
      overlayWin.setFocusable(false);
      overlayWin.setIgnoreMouseEvents(true);
      overlayWin.setAlwaysOnTop(true, 'screen-saver');
      overlayWin.loadFile(path.join(__dirname, 'overlay.html'));
      const savedRegions = msg.regions;
      overlayWin.webContents.on('did-finish-load', () => {
        overlayWin.webContents.send('overlay-settings', config.settings);
        overlayWin.webContents.send('overlay-theme', {
          family: config.get('theme_family') || 'cyberpunk',
          accent: getThemeAccent(),
          accent2: getThemeAccent2(),
        });
        if (savedRegions) overlayWin.webContents.send('regions', savedRegions);
        overlayWin.showInactive();
      });
      overlayWin.on('closed', () => { overlayWin = null; });
      log(`Overlay created at ${msg.rect.width}x${msg.rect.height} at ${msg.rect.left},${msg.rect.top}`);
    }
    return;
  }
  if (msg.type === 'info') {
    log(`Vision: ${msg.message}`);
    return;
  }
  if (msg.type === 'error') {
    log(`Vision error: ${msg.message}`);
    return;
  }
  if (msg.type === 'frame') {
    const { score, ping, detections } = msg;

    // Send to UI
    if (Object.keys(detections).length > 0) {
      win?.webContents.send('detections', detections, score);
    }
    if (win && !win.isDestroyed()) {
      win.webContents.send('score', score, ping);
    }
    updateOverlay(score, ping, detections, msg.owFocused !== false, msg.matchedRegions || []);

    // Forward full confidence data to debug panel
    if (debugWin && !debugWin.isDestroyed()) {
      const confKeys = Object.keys(msg.confidence || {});
      if (confKeys.length > 0 && !debugWin._loggedOnce) {
        debugWin._loggedOnce = true;
        console.log(`[Debug] First confidence frame: ${confKeys.length} keys — ${confKeys.slice(0, 5).join(', ')}...`);
      }
      debugWin.webContents.send('debug-frame', {
        confidence: msg.confidence || {},
        details: msg.details || {},
        templateErrors: msg.templateErrors || {},
        ping: ping,
        score: score,
        detections: detections,
        matchedRegions: msg.matchedRegions || [],
      });
    }

    // Drive Lovense
    if (!lovense?.connected) return;
    if (muted) return;
    const minScore = config.get('min_score') || 0;
    const maxScore = config.get('max_score') || 100;
    const normalized = Math.max(0, Math.min(1, (score - minScore) / (maxScore - minScore || 1)));
    const level = Math.max(0, Math.min(20, Math.round(normalized * 20)));

    const now = Date.now();
    if (level !== lastLevel || (level > 0 && now - lastSendTime > 3000)) {
      const maSettings = config.get('multi_actuator') || {};
      for (const [tid, toy] of Object.entries(lovense.toys)) {
        if (mutedToys.has(tid)) continue;
        const rawKey = toy.name.replace(/\s*\d+$/, '');
        const maKey = rawKey.charAt(0).toUpperCase() + rawKey.slice(1).toLowerCase();
        const ma = maSettings[maKey];
        const actionLevels = [];
        for (const func of toy.functions) {
          let funcLevel = level;
          if (func !== 'Vibrate') {
            if (!ma || !ma.enabled) {
              funcLevel = 0;
            } else {
              const activationScore = ma.threshold ?? 25;
              const maxLvl = ma.max_level ?? 20;
              funcLevel = score >= activationScore
                ? Math.max(0, Math.min(maxLvl, Math.round(normalized * maxLvl)))
                : 0;
            }
          }
          actionLevels.push([func, funcLevel]);
        }
        lovense.sendActions(tid, actionLevels);
      }
      lastLevel = level;
      lastSendTime = now;
    }
  }
}

// Zone editor
ipcMain.handle('get-zones', () => {
  const { REGIONS, ASPECT_RATIOS } = require('./src/config');
  const ar = ASPECT_RATIOS[config.get('aspect_ratio_index') || 0];
  // Merge hardcoded regions with user regions from config
  const configPath = CONFIG_PATH;
  let userRegions = {};
  try {
    const cfg = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    userRegions = cfg.user_regions || {};
  } catch {}
  const merged = { ...REGIONS, ...userRegions };
  let disabledZones = [];
  try {
    const cfg2 = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    disabledZones = cfg2.disabled_zones || [];
  } catch {}
  return { regions: merged, baseW: ar.sampleW, baseH: ar.sampleH, disabledZones };
});

ipcMain.handle('save-zones', (_, updatedZones, disabledZones) => {
  // Save user zones to config.json so vision engine can read them
  const configPath = CONFIG_PATH;
  const cfg = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
  // Merge zones — only update the current resolution key, preserve others
  const ar = config.getAspectRatio();
  const resKey = `${ar.sampleW}x${ar.sampleH}`;
  if (!cfg.user_regions) cfg.user_regions = {};
  for (const [name, rect] of Object.entries(updatedZones)) {
    if (!cfg.user_regions[name]) cfg.user_regions[name] = {};
    cfg.user_regions[name][resKey] = rect;
  }
  // Remove zones that were deleted (not in updatedZones)
  for (const name of Object.keys(cfg.user_regions)) {
    if (!(name in updatedZones)) {
      delete cfg.user_regions[name][resKey];
      if (Object.keys(cfg.user_regions[name]).length === 0) delete cfg.user_regions[name];
    }
  }
  cfg.disabled_zones = disabledZones || [];
  fs.writeFileSync(configPath, JSON.stringify(cfg, null, 4));
  config.load(); // reload
  log('Zones saved to config');
  return true;
});

ipcMain.handle('rename-zone', (_, oldName, newName) => {
  // Update all detectables that reference the old zone name
  let changed = false;
  for (const [detName, det] of Object.entries(config.detectables)) {
    if (det.region === oldName) {
      det.region = newName;
      changed = true;
    }
  }
  if (changed) config.save();
  return true;
});

ipcMain.handle('capture-game-screen', async () => {
  const configPath = CONFIG_PATH;
  const outPath = path.join(APP_ROOT, 'capture_temp.png');
  try {
    const command = IS_PACKAGED ? CAPTURE_SCRIPT : PYTHON;
    const args = IS_PACKAGED ? [configPath, outPath] : [CAPTURE_SCRIPT, configPath, outPath];
    const { stdout } = await execFileAsync(command, args, {timeout: 10000, windowsHide: true});
    const result = stdout.trim();
    const size = JSON.parse(result);
    const imgData = fs.readFileSync(outPath);
    const dataUrl = 'data:image/png;base64,' + imgData.toString('base64');
    return { dataUrl, width: size.w, height: size.h };
  } catch (e) {
    crashLog(`Capture failed: ${e.message}`);
    return null;
  }
});

ipcMain.handle('open-zone-editor', () => {
  const editorWin = new BrowserWindow({
    width: 1400,
    height: 900,
    frame: true,
    title: 'Zone Editor',
    icon: path.join(__dirname, 'pancake.ico'),
    webPreferences: { nodeIntegration: true, contextIsolation: false },
  });
  editorWin.loadFile(path.join(__dirname, 'zone-editor.html'));
});

ipcMain.handle('set-debug-threshold', (_, name, value, field = 'threshold') => {
  if (!['threshold', 'v2_threshold'].includes(field) || !Number.isFinite(value) || value < 0 || value > 1) throw new Error('Invalid threshold');
  if (config && config.detectables[name]) {
    config.detectables[name][field] = value;
    config.save();
    // Forward to running Python worker for live update
    if (visionProcess && visionProcess.stdin.writable) {
      visionProcess.stdin.write(JSON.stringify({ cmd: 'set_threshold', name, value, field }) + '\n');
    }
    log(`Threshold ${name} -> ${value}`);
  }
});

ipcMain.handle('get-debug-config', () => {
  return {
    detectables: config ? config.detectables : {},
    templatesDir: TEMPLATES_DIR,
  };
});

ipcMain.handle('open-debug-panel', () => {
  if (debugWin && !debugWin.isDestroyed()) {
    debugWin.focus();
    return;
  }
  debugWin = new BrowserWindow({
    width: 900,
    height: 700,
    frame: true,
    title: 'Debug — Template Confidence',
    icon: path.join(__dirname, 'pancake.ico'),
    webPreferences: { nodeIntegration: true, contextIsolation: false },
  });
  debugWin.loadFile(path.join(__dirname, 'debug.html'));
  debugWin.on('closed', () => { debugWin = null; });
});

// Monitor info
ipcMain.handle('get-monitor-count', () => {
  const displays = screen.getAllDisplays();
  return displays.map((d, i) => `Monitor ${i + 1} (${d.size.width}x${d.size.height})`);
});

// Window controls
ipcMain.on('win-minimize', (e) => {
  BrowserWindow.fromWebContents(e.sender)?.minimize();
});
ipcMain.on('win-close', (e) => {
  BrowserWindow.fromWebContents(e.sender)?.close();
});

// Overlay
ipcMain.handle('start-overlay', () => {
  createOverlay();
  return true;
});

ipcMain.handle('stop-overlay', () => {
  if (overlayWin && !overlayWin.isDestroyed()) {
    overlayWin.close();
    overlayWin = null;
  }
  return true;
});

// ── Overlay window ──

function createOverlay() {
  const displays_dbg = screen.getAllDisplays();
  const monNum_dbg = config.get('monitor_number') || 1;
  crashLog(`createOverlay: ${displays_dbg.length} displays, using #${monNum_dbg}, bounds=${JSON.stringify(displays_dbg[monNum_dbg-1]?.bounds)}`);
  if (overlayWin && !overlayWin.isDestroyed()) { crashLog('overlay already exists'); return; }

  const displays = screen.getAllDisplays();
  const monNum = config.get('monitor_number') || 1;
  const display = displays[monNum - 1] || displays[0];
  const rect = { left: display.bounds.x, top: display.bounds.y, width: display.bounds.width, height: display.bounds.height };

  overlayWin = new BrowserWindow({
    x: rect.left,
    y: rect.top,
    width: rect.width,
    height: rect.height,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    focusable: false,
    hasShadow: false,
    resizable: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    },
  });

  overlayWin.setIgnoreMouseEvents(true);
  overlayWin.loadFile(path.join(__dirname, 'overlay.html'));
  overlayWin.webContents.on('did-finish-load', () => {
    overlayWin.webContents.send('overlay-settings', config.settings);
    applyOverlayRect();
  });
  overlayWin.on('closed', () => { overlayWin = null; });
  log(`Overlay started (${rect.width}x${rect.height} at ${rect.left},${rect.top})`);
}

function applyOverlayRect() {
  if (!pendingOverlayRect || !overlayWin || overlayWin.isDestroyed()) return;
  if (overlayWin.webContents.isLoading()) return;
  const { rect, regions } = pendingOverlayRect;
  overlayWin.setBounds({ x: rect.left, y: rect.top, width: rect.width, height: rect.height });
  if (regions) overlayWin.webContents.send('regions', regions);
  overlayWin.webContents.send('overlay-settings', config.settings);
  overlayWin.show();
  log(`Overlay: ${rect.width}x${rect.height} at ${rect.left},${rect.top}`);
  pendingOverlayRect = null;
}

// Theme accent lookup
const THEME_COLORS = {
  cyberpunk: { pink: ['#ff1f8f','#00f0ff'], blue: ['#1f7fff','#ff1f8f'], green: ['#1fd97a','#ffe53a'], blood: ['#dc1432','#d8d0cc'] },
  plush: { blush: ['#ff7ab8','#c9aaf0'], cotton: ['#7abdff','#e8a8c8'], lilac: ['#b07aff','#ffaae0'], butter: ['#efd442','#965f37'] },
  industrial: { trail: ['#c45a2c','#8a3a1a'], summit: ['#2d6b4f','#1a4a34'], graphite: ['#4a4a4e','#2a2a2e'], alpine: ['#3a5a7a','#2a4060'] },
};
function getThemeAccent() {
  const f = config.get('theme_family') || 'cyberpunk';
  const t = config.get('theme_tint') || 'pink';
  return THEME_COLORS[f]?.[t]?.[0] || '#ff1f8f';
}
function getThemeAccent2() {
  const f = config.get('theme_family') || 'cyberpunk';
  const t = config.get('theme_tint') || 'pink';
  return THEME_COLORS[f]?.[t]?.[1] || '#00f0ff';
}

function updateOverlay(score, ping, detections, owFocused, matchedRegions) {
  if (!overlayWin || overlayWin.isDestroyed()) return;

  const mode = config.get('show_overlay_mode') ?? 0;
  if (mode === 0) {
    if (overlayWin.isVisible()) overlayWin.hide();
    return;
  }
  if (mode === 2 && !owFocused) {
    if (overlayWin.isVisible()) overlayWin.hide();
    return;
  }
  if (!overlayWin.isVisible()) overlayWin.showInactive();

  overlayWin.webContents.send('overlay-update', { score, ping, detections, matchedRegions });
}


// ── Mute hotkey ──

const DEFAULT_PANIC_URL = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ';

function toggleMute() {
  // Only allow panic when vision is running
  if (!muted && !visionProcess) return;
  muted = !muted;
  if (muted && lovense) {
    lovense.stopAll();
    lastLevel = -1;
  }
  if (win && !win.isDestroyed()) {
    if (muted) {
      // Switch to panic screen — hide the overlay too
      if (overlayWin && !overlayWin.isDestroyed()) overlayWin.hide();
      win.setTitle('YouTube');
      win.setResizable(false);
      win.setMaximizable(false);
      // Mute before navigation: covers autoplay, redirects, ads, and audio APIs.
      win.webContents.setAudioMuted(true);
      const panicUrl = config.get('panic_url') || DEFAULT_PANIC_URL;
      win.loadURL(panicUrl);
    } else {
      // Restore the app
      win.removeAllListeners('page-title-updated');
      win.setTitle('ULT-4-ME V2');
      win.setResizable(true);
      win.setMaximizable(true);
      // Keep the outgoing panic page silent until the local app has loaded.
      win.webContents.once('dom-ready', () => {
        if (win && !win.isDestroyed() && !muted && win.webContents.getURL().startsWith('file:')) {
          win.webContents.setAudioMuted(false);
        }
      });
      win.loadFile(path.join(__dirname, 'app.html'));
      if (overlayWin && !overlayWin.isDestroyed()) overlayWin.showInactive();
    }
  }
}

function registerMuteKey(key) {
  // Unregister old key
  if (muteKey) {
    try { globalShortcut.unregister(muteKey); } catch {}
  }
  muteKey = key;
  if (key) {
    try {
      globalShortcut.register(key, toggleMute);
      log(`Mute hotkey bound: ${key}`);
    } catch (e) {
      log(`Failed to bind mute hotkey "${key}": ${e.message}`);
      muteKey = null;
    }
  }
  config.set('mute_key', key || '');
}

ipcMain.handle('toggle-toy-mute', async (_, tid) => {
  if (mutedToys.has(tid)) {
    mutedToys.delete(tid);
  } else {
    mutedToys.add(tid);
    // Stop this toy immediately
    if (lovense) {
      try { await lovense.sendAction(tid, 'Vibrate', 0); } catch {}
    }
  }
  return mutedToys.has(tid);
});

ipcMain.handle('is-toy-muted', (_, tid) => mutedToys.has(tid));

ipcMain.handle('toggle-mute', () => {
  toggleMute();
  return muted;
});

ipcMain.handle('get-mute-status', () => ({ muted, key: muteKey || '', url: config.get('panic_url') || '' }));

ipcMain.handle('set-panic-url', (_, url) => {
  config.set('panic_url', url);
});

ipcMain.handle('set-mute-key', (_, key) => {
  registerMuteKey(key);
  return { ok: true, key: muteKey || '' };
});

ipcMain.handle('suspend-mute-key', () => {
  if (muteKey) {
    try { globalShortcut.unregister(muteKey); } catch {}
  }
});

ipcMain.handle('resume-mute-key', () => {
  if (muteKey) {
    try { globalShortcut.register(muteKey, toggleMute); } catch {}
  }
});

ipcMain.on('restart-app', () => {
  stopVision();
  app.relaunch();
  app.exit(0);
});

// ── App lifecycle ──

app.whenReady().then(async () => {
  config = new Config(CONFIG_PATH);
  config.load();
  if (!fs.existsSync(CONFIG_PATH)) config.save();

  crashLog('App ready');

  // Register mute hotkey
  const savedKey = config.get('mute_key') || 'Delete';
  registerMuteKey(savedKey);

  if (config.get('onboarding_completed')) {
    createWindow();
  } else {
    createOnboarding();
  }
});

function createOnboarding() {
  win = new BrowserWindow({
    width: 960,
    height: 600,
    frame: false,
    resizable: false,
    backgroundColor: '#050505',
    icon: path.join(__dirname, 'pancake.ico'),
    webPreferences: { nodeIntegration: true, contextIsolation: false },
  });
  win.loadFile(path.join(__dirname, 'onboarding.html'));
  win.on('closed', () => { win = null; });
}

ipcMain.on('onboarding-done', () => {
  const oldWin = win;
  win = null;
  if (oldWin && !oldWin.isDestroyed()) {
    oldWin.removeAllListeners('closed');
    oldWin.close();
  }
  createWindow();
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
});

app.on('window-all-closed', () => {
  // Don't quit during onboarding→main transition
  if (win) return;
  stopVision();
  if (lovense) lovense.stopAll();
  app.quit();
});

// V2 authoring: no capture or hardware command is made by these handlers.
ipcMain.handle('open-detection-lab', () => {
  const lab = new BrowserWindow({width: 1120, height: 850, title: 'ULT-4-ME V2 · Detection editor',
    webPreferences: {nodeIntegration: true, contextIsolation: false}});
  lab.loadFile(path.join(__dirname, 'detection-lab.html'));
});
ipcMain.handle('lab-read-template', (_, filename) => {
  if (typeof filename !== 'string' || path.basename(filename) !== filename) throw new Error('Invalid template name');
  return nativeImage.createFromPath(path.join(TEMPLATES_DIR, filename)).toDataURL();
});
ipcMain.handle('lab-save-template', (_, dataURL) => {
  if (typeof dataURL !== 'string' || !dataURL.startsWith('data:image/png;base64,') || dataURL.length > 24000000) throw new Error('Invalid PNG');
  const image = nativeImage.createFromDataURL(dataURL);
  const size = image.getSize();
  if (image.isEmpty() || size.width > 2048 || size.height > 2048) throw new Error('Invalid template dimensions');
  const filename = `masked-${require('crypto').randomUUID()}.png`;
  fs.writeFileSync(path.join(TEMPLATES_DIR, filename), image.toPNG());
  return filename;
});
ipcMain.handle('lab-save-options', (_, name, options) => {
  if (!config.detectables[name]) throw new Error('Unknown event');
  const {validateOptions} = require('./src/detection-options');
  validateOptions(options);
  Object.assign(config.detectables[name], options);
  config.save();
  return true;
});
ipcMain.handle('lab-test', async (_, name, options) => {
  const {validateOptions} = require('./src/detection-options');
  validateOptions(options);
  if (!config.detectables[name]) throw new Error('Unknown event');
  const picked = await dialog.showOpenDialog({title: 'Choose a cropped HUD image to test',
    filters: [{name: 'Images', extensions: ['png', 'jpg', 'bmp']}], properties: ['openFile']});
  if (picked.canceled) return null;
  const payload = {image: picked.filePaths[0], templates: TEMPLATES_DIR,
    detectable: {...config.detectables[name], ...options}};
  return new Promise((resolve, reject) => {
    const child = spawn(IS_PACKAGED ? WORKER_PATH : PYTHON,
      IS_PACKAGED ? ['--analyze'] : [WORKER_PATH, '--analyze'], {windowsHide: true});
    let out = '', err = '';
    const timer = setTimeout(() => { child.kill(); reject(new Error('Image test exceeded 15 seconds')); }, 15000);
    child.on('error', e => { clearTimeout(timer); reject(e); });
    child.stdout.on('data', b => { out += b; });
    child.stderr.on('data', b => { err += b; });
    child.on('exit', code => { clearTimeout(timer); try {
      if (code) throw new Error(err || out || 'Image test failed');
      resolve(JSON.parse(out));
    } catch(e) { reject(e); } });
    child.stdin.end(JSON.stringify(payload));
  });
});
