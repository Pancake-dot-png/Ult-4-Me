/**
 * App configuration.
 * Defaults defined here. User settings saved to / loaded from config.json.
 */

const fs = require('fs');
const path = require('path');

const ASPECT_RATIOS = {
  0: { id: '16:9',  sampleW: 1920, sampleH: 1080 },
  1: { id: '21:9',  sampleW: 2560, sampleH: 1080 },
  2: { id: '16:10', sampleW: 1680, sampleH: 1050, templateScaling: 1680 / 1920 },
};

const REGIONS = {
  "Menu Watcher": {"1920x1080": {"x": 17, "y": 27, "w": 96, "h": 38}},
  "Health Watch": {"1920x1080": {"x": 166, "y": 931, "w": 256, "h": 18}},
  Ultimate: { '1920x1080': { x: 936, y: 905, w: 50, h: 49 } },
  Popup1: {
    '1920x1080': { x: 750, y: 750, w: 210, h: 30 },
    '2560x1080': { x: 1070, y: 750, w: 210, h: 30 },
    '1680x1050': { x: 655, y: 656, w: 185, h: 27 },
  },
  Popup2: {
    '1920x1080': { x: 750, y: 785, w: 210, h: 30 },
    '2560x1080': { x: 1070, y: 785, w: 210, h: 30 },
    '1680x1050': { x: 655, y: 686, w: 185, h: 27 },
  },
  Popup3: {
    '1920x1080': { x: 750, y: 820, w: 210, h: 30 },
    '2560x1080': { x: 1070, y: 820, w: 210, h: 30 },
    '1680x1050': { x: 655, y: 716, w: 185, h: 27 },
  },
  'Give Harmony Orb': {
    '1920x1080': { x: 725, y: 945, w: 50, h: 50 },
    '2560x1080': { x: 1045, y: 945, w: 50, h: 50 },
    '1680x1050': { x: 635, y: 932, w: 45, h: 45 },
  },
  'Give Discord Orb': {
    '1920x1080': { x: 1145, y: 945, w: 50, h: 50 },
    '2560x1080': { x: 1465, y: 945, w: 50, h: 50 },
    '1680x1050': { x: 1000, y: 932, w: 45, h: 45 },
  },
  'Give Healing': {
    '1920x1080': { x: 790, y: 655, w: 68, h: 68 },
    '2560x1080': { x: 1110, y: 655, w: 68, h: 68 },
    '1680x1050': { x: 690, y: 625, w: 60, h: 60 },
  },
  'Give Boost': {
    '1920x1080': { x: 1062, y: 655, w: 68, h: 68 },
    '2560x1080': { x: 1382, y: 655, w: 68, h: 68 },
    '1680x1050': { x: 930, y: 625, w: 60, h: 60 },
  },
  'Receive Heal': {
    maxMatches: 2,
    '1920x1080': { x: 440, y: 740, w: 210, h: 100 },
    '2560x1080': { x: 440, y: 740, w: 210, h: 100 },
    '1680x1050': { x: 385, y: 750, w: 200, h: 90 },
  },
  'Receive Status Effect': {
    maxMatches: 3,
    '1920x1080': { x: 160, y: 840, w: 140, h: 55 },
    '2560x1080': { x: 160, y: 840, w: 140, h: 55 },
    '1680x1050': { x: 144, y: 848, w: 120, h: 36 },
  },
  Prompt: {
    '1920x1080': { x: 810, y: 228, w: 300, h: 58 },
    '2560x1080': { x: 1130, y: 228, w: 300, h: 58 },
    '1680x1050': { x: 707, y: 200, w: 265, h: 52 },
  },
  Overtime: {
    '1920x1080': { x: 900, y: 35, w: 123, h: 39 },
  },
  POTG: {
    '1920x1080': { x: 210, y: 28, w: 94, h: 50 },
    '2560x1080': { x: 210, y: 28, w: 94, h: 50 },
  },
  'Kill Cam': {
    '1920x1080': { x: 1628, y: 40, w: 158, h: 47 },
    '2560x1080': { x: 2268, y: 40, w: 158, h: 47 },
  },
  'Anti Healing': {
    '1920x1080': { x: 164, y: 896, w: 51, h: 30 },
  },
};

const DETECTABLES = {
  "HUD Present": {"filename": "hud_health_reference.png", "template_crop": [17, 10, 33, 29], "template_height": 1440, "region": "Anti Healing", "threshold": 0.9, "match_mode": "legacy", "points": 0, "type": 8, "hud_alternate": "Anti-Healing"},
  "Menu Watcher": {"filename": "menu_home.png", "menu_resume_delays": {"menu_back.png": 0}, "examples": ["menu_back.png", "menu_home_gray.png", "menu_back_arrow.png"], "template_height": 1440, "match_mode": "legacy", "threshold": 0.9, "region": "Menu Watcher", "points": 0, "type": 7},
  Overshield: {"filename": "overshield_reference.png", "hud_guard": "HUD Present", "region": "Health Watch", "points": 100, "type": 6, "full_coverage": 0.6954947707160096},
  'Give Lucio Heal': { filename: 'lucio_heal.png', template_height: 1440, threshold: 0.9, region: 'Give Healing', points: 10, type: 0 },
  'Give Lucio Boost': { filename: 'lucio_boost.png', template_height: 1440, threshold: 0.9, region: 'Give Boost', points: 10, type: 0 },
  Ultimate: { filename: 'ultimate_zero.png', template_height: 1440, threshold: 0.95, region: 'Ultimate', points: 0, type: 5, duration: 8, cooldown: 20, confirm_frames: 2, release_ms: 200 },
  KillcamOrPOTG: { filename: 'play_of_the_game.png', threshold: 0.7, region: 'POTG' },
  KillCam:       { filename: 'respawning.png', threshold: 0.7, region: 'Kill Cam' },
  Elimination:   { filename: 'elimination.png', threshold: 0.8, region: 'Popup', points: 25, type: 2, duration: 2.5 },
  Assist:        { filename: 'assist.png', threshold: 0.8, region: 'Popup', points: 20, type: 2, duration: 2.5 },
  Saved:         { filename: 'saved.png', threshold: 0.8, region: 'Popup', points: 30, type: 2, duration: 2.5 },
  Died:          { filename: 'died - Copy.png', threshold: 0.8, region: 'Popup', points: 0, type: 3, duration: 8 },
  Detected:      { filename: 'prompt_detected.png', threshold: 0.5, region: 'Prompt', filter: 'prompt', points: 100, type: 0 },
  'Life Gripped': { filename: 'prompt_gripped.png', threshold: 0.5, region: 'Prompt', filter: 'prompt', points: 100, type: 0 },
  Hacked:        { filename: 'prompt_hacked.png', threshold: 0.5, region: 'Prompt', filter: 'prompt', points: 100, type: 0 },
  Hindered:      { filename: 'prompt_hindered.png', threshold: 0.5, region: 'Prompt', filter: 'prompt', points: 100, type: 0 },
  Reviving:      { filename: 'prompt_reviving.png', threshold: 0.5, region: 'Prompt', filter: 'prompt', points: 100, type: 0 },
  Pinned:        { filename: 'prompt_pinned.png', threshold: 0.5, region: 'Prompt', filter: 'prompt', points: 100, type: 0 },
  Revealed:      { filename: 'prompt_revealed.png', threshold: 0.5, region: 'Prompt', filter: 'prompt', points: 100, type: 0 },
  Sleep:         { filename: 'prompt_sleep.png', threshold: 0.5, region: 'Prompt', filter: 'prompt', points: 100, type: 0 },
  Stuck:         { filename: 'prompt_stuck.png', threshold: 0.5, region: 'Prompt', filter: 'prompt', points: 100, type: 0 },
  Stunned:       { filename: 'prompt_stunned.png', threshold: 0.5, region: 'Prompt', filter: 'prompt', points: 100, type: 0 },
  Trapped:       { filename: 'prompt_trapped.png', threshold: 0.5, region: 'Prompt', filter: 'prompt', points: 100, type: 0 },
  Grappled:      { filename: 'prompt_grappled.png', threshold: 0.5, region: 'Prompt', filter: 'prompt', points: 10, type: 0 },
  'Receive Zen Heal':    { filename: 'receive_zen_heal.png', threshold: 0.8, region: 'Receive Heal', points: 10, type: 0 },
  'Receive Mercy Heal':  { filename: 'receive_mercy_heal.png', threshold: 0.8, region: 'Receive Heal', points: 15, type: 0 },
  'Receive Mercy Boost': { filename: 'receive_mercy_boost.png', threshold: 0.8, region: 'Receive Heal', points: 25, type: 0 },
  'Receive Hack':        { filename: 'receive_hack_icon.png', threshold: 0.8, region: 'Receive Status Effect', points: 100, type: 0 },
  'Receive Discord Orb': { filename: 'receive_discord.png', threshold: 0.8, region: 'Receive Status Effect', points: -20, type: 1 },
  'Receive Anti-Heal':   { filename: 'receive_purple_pot.png', threshold: 0.8, region: 'Receive Status Effect', points: -50, type: 0 },
  'Receive Heal Boost':  { filename: 'receive_yellow_pot.png', threshold: 0.8, region: 'Receive Status Effect', points: 20, type: 0 },
  'Receive Immortality': { filename: 'receive_immortality.png', threshold: 0.8, region: 'Receive Status Effect', points: 20, type: 0 },
  'Give Mercy Heal':     { filename: 'apply_mercy_heal.png', threshold: 0.7, region: 'Give Healing', points: 10, type: 0 },
  'Give Mercy Boost':    { filename: 'apply_mercy_boost.png', threshold: 0.7, region: 'Give Boost', points: 10, type: 0 },
  'Give Harmony Orb':    { filename: 'apply_harmony.png', threshold: 0.9, region: 'Give Harmony Orb', points: 10, type: 0 },
  'Give Discord Orb':    { filename: 'apply_discord.png', threshold: 0.9, region: 'Give Discord Orb', points: 20, type: 0 },
  'Earth Shatter':       { filename: 'earthshatter.png', threshold: 0.7, region: 'Popup', points: 50, type: 0 },
  'Sleep Dart':          { filename: 'sleep_dart.png', threshold: 0.7, region: 'Popup', points: 50, type: 0 },
  'Throwing Big Rock':   { filename: 'throw_big_rock.png', threshold: 0.8, region: 'Popup', points: 15, type: 2 },
  'Deployed Pylon':      { filename: 'deployed_pylon.png', threshold: 0.7, region: 'Constructs', points: 30, type: 0 },
  'Deployed Tree':       { filename: 'deployed_tree.png', threshold: 0.7, region: 'Constructs', points: 30, type: 0 },
  'Receive Wuyang Heal': { filename: 'receive_wuyang_healing.png', threshold: 0.8, region: 'Receive Heal', points: 10, type: 0 },
  'Receive Wuyang Initial': { filename: 'receive_wuyang_initial_healing.png', threshold: 0.8, region: 'Popup', points: 20, type: 0 },
  'Anti-Healing':        { filename: 'anti-healing.png', threshold: 0.8, region: 'Anti Healing', points: -50, type: 0 },
  'Overtime':            { filename: 'overtime.png', threshold: 0.3, region: 'Overtime', points: 30, type: 0 },
};

const SAVE_FIELDS = new Set(['template_crop', 'hud_guard', 'hud_alternate', 'menu_resume_delays', 'full_coverage', 'cooldown', 'template_height', 'points', 'type', 'duration', 'threshold', 'filename', 'region', 'filter', "match_mode", "v2_threshold", "examples", "scale_tolerance", "confirm_frames", "release_ms", "edge_tolerance"]);

const DEFAULT_SETTINGS = {
  monitor_number: 1,
  aspect_ratio_index: 0,
  show_overlay_mode: 2,
  show_regions_mode: 0,
  ignore_spectate: true,
  ignore_redundant_assists: true,
  decay: 100,
  lovense_ip: '',
  min_score: 0,
  max_score: 100,
  max_intensity: 100,
  disabled_zones: [],
  multi_actuator: {
    Nora:    { enabled: true, threshold: 25, max_level: 20 },
    Max:     { enabled: true, threshold: 25, max_level: 20 },
    Edge:    { enabled: true, threshold: 25, max_level: 20 },
    Gravity: { enabled: true, threshold: 25, max_level: 20 },
    Dolce:   { enabled: true, threshold: 25, max_level: 20 },
    Gemini:  { enabled: true, threshold: 25, max_level: 20 },
    Vulse:   { enabled: true, threshold: 25, max_level: 20 },
  },
  theme_family: 'cyberpunk',
  theme_tint: 'pink',
  onboarding_completed: false,
  mute_key: 'Delete',
  panic_url: '',
};


function migrateSharedZones(data) {
  const before = JSON.stringify(data);
  const names = { 'Give Mercy Heal': 'Give Healing', 'Give Mercy Boost': 'Give Boost' };
  const regions = data.user_regions || {};
  for (const [oldName, newName] of Object.entries(names)) {
    if (regions[oldName]) {
      regions[newName] = {...regions[oldName], ...regions[newName]};
      delete regions[oldName];
    }
  }
  for (const det of Object.values(data.detectables || {})) {
    if (names[det.region]) det.region = names[det.region];
  }
  if (data.disabled_zones) data.disabled_zones = [...new Set(data.disabled_zones.map(z => names[z] || z))];
  return JSON.stringify(data) !== before;
}

class Config {
  constructor(configPath) {
    this.path = configPath || path.join(process.cwd(), 'config.json');
    this.settings = JSON.parse(JSON.stringify(DEFAULT_SETTINGS));
    this.detectables = JSON.parse(JSON.stringify(DETECTABLES));
  }

  load() {
    if (!fs.existsSync(this.path)) return;
    try {
      const data = JSON.parse(fs.readFileSync(this.path, 'utf-8'));
      const migratedZones = migrateSharedZones(data);
      for (const [key, value] of Object.entries(data)) {
        if (key === 'detectables') {
          for (const [detName, detFields] of Object.entries(value)) {
            if (detName === 'Capture Progress') continue; // Retired after the in-game UI changed.
            if (this.detectables[detName]) {
              Object.assign(this.detectables[detName], detFields);
            } else {
              // Custom user-created detectable
              this.detectables[detName] = detFields;
            }
          }
        } else if (key === 'multi_actuator' && typeof value === 'object') {
          // Merge per-device settings on top of defaults
          for (const [devName, devFields] of Object.entries(value)) {
            if (this.settings.multi_actuator[devName]) {
              Object.assign(this.settings.multi_actuator[devName], devFields);
            } else {
              this.settings.multi_actuator[devName] = devFields;
            }
          }
        } else if (key in this.settings) {
          this.settings[key] = value;
        }
      }
      // Repair the accidental receive-icon filter persisted by the September 10
      // rebuild, without changing custom images, thresholds, or scoring.
      let repaired = false;
      for (const [name, defaults] of Object.entries(DETECTABLES)) {
        const det = this.detectables[name];
        if (['Receive Zen Heal', 'Receive Mercy Heal', 'Receive Mercy Boost', 'Receive Hack',
             'Receive Discord Orb', 'Receive Anti-Heal', 'Receive Heal Boost', 'Receive Immortality'].includes(name)
            && !defaults.filter && det?.filename === defaults.filename && det.filter === 'edge') {
          delete det.filter;
          repaired = true;
        }
      }
      if (migratedZones) this.save();
      if (repaired) {
        const backup = this.path + '.before-receive-filter-fix.bak';
        if (!fs.existsSync(backup)) fs.copyFileSync(this.path, backup);
        this.save();
      }
    } catch {}
  }

  save() {
    // Read existing file to preserve user_regions and other non-settings data
    let existing = {};
    try { existing = JSON.parse(fs.readFileSync(this.path, 'utf-8')); } catch {}

    const out = { ...existing, ...this.settings, detectables: {} };
    migrateSharedZones(out);
    if (out.user_regions) delete out.user_regions['Capture Progress'];
    for (const [name, det] of Object.entries(this.detectables)) {
      const userFields = {};
      for (const [k, v] of Object.entries(det)) {
        if (SAVE_FIELDS.has(k)) userFields[k] = v;
      }
      if (Object.keys(userFields).length > 0) out.detectables[name] = userFields;
    }
    fs.writeFileSync(this.path, JSON.stringify(out, null, 4));
  }

  get(key) { return this.settings[key]; }

  set(key, value) {
    this.settings[key] = value;
    this.save();
  }

  getRegion(name) {
    const region = REGIONS[name];
    if (!region) return null;
    const ar = ASPECT_RATIOS[this.settings.aspect_ratio_index];
    return region[`${ar.sampleW}x${ar.sampleH}`] || null;
  }

  getAspectRatio() {
    return ASPECT_RATIOS[this.settings.aspect_ratio_index];
  }
}

module.exports = { migrateSharedZones, Config, ASPECT_RATIOS, REGIONS, DETECTABLES, DEFAULT_SETTINGS };
