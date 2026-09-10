const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const source = fs.readFileSync(path.join(__dirname, '../electron_test/index.js'), 'utf8');
const handler = source.match(/function handleVisionMessage\(msg\) \{[\s\S]*?\n\}/)[0];
const overlay = source.match(/function updateOverlay\([^)]*\) \{[\s\S]*?\n\}/)[0];
for (const mode of [0, 1, 2]) {
  for (const panelOpen of [false, true]) {
    const sent = [], actions = [];
    let visible = true;
    const context = vm.createContext({
      win: {isDestroyed: () => false, webContents: {send: (...args) => sent.push(args)}},
      debugWin: panelOpen ? {isDestroyed: () => false, _loggedOnce: true, webContents: {send() {}}} : null,
      overlayWin: {isDestroyed: () => false, isVisible: () => visible,
        hide: () => {visible = false;}, showInactive: () => {visible = true;}, webContents: {send() {}}},
      config: {get: key => ({show_overlay_mode: mode, max_score: 100}[key])},
      muted: false, mutedToys: new Set(), lastLevel: -1, lastSendTime: 0,
      lovense: {connected: true, toys: {fake: {name: 'Test', functions: ['Vibrate']}},
        sendActions: (...args) => actions.push(args)},
    });
    vm.runInContext(handler + '\n' + overlay, context);
    vm.runInContext(`handleVisionMessage({type:'frame',score:65,ping:20,
      detections:{'Receive Mercy Heal':1,'Receive Immortality':1},owFocused:false})`, context);
    assert(sent.some(args => args[0] === 'score' && args[1] === 65));
    assert(sent.some(args => args[0] === 'detections'));
    assert.equal(actions[0][1][0][1], 13, 'output must work without any visible overlay/debug panel');
    if (mode !== 1) assert.equal(visible, false);
  }
}
const {Config} = require('../electron_test/src/config');
const cfg = new Config(path.join(__dirname, '../../releases/v1.3-settings.json'));
cfg.load();
for (const name of ['Receive Mercy Heal', 'Receive Mercy Boost', 'Receive Immortality']) {
  assert.equal(cfg.detectables[name].filter, undefined, 'UI must not re-save the accidental edge filter');
  assert.equal(cfg.detectables[name].threshold, .8);
}
console.log('Detection and output routing passed with overlays hidden and debug panel closed.');
const os = require('os');
const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'ult-filter-test-'));
const configPath = path.join(folder, 'config.json');
const original = JSON.stringify({detectables: {
  'Receive Mercy Heal': {filter: 'edge', threshold: .73, points: 52},
  'Receive Immortality': {filename: 'custom.png', filter: 'edge'},
  'Receive Wuyang Heal': {filter: 'edge'},
}, user_regions: {Custom: {'1920x1080': {x: 1, y: 2, w: 30, h: 40}}}});
try {
  fs.writeFileSync(configPath, original);
  const repaired = new Config(configPath);
  repaired.load();
  assert.equal(repaired.detectables['Receive Mercy Heal'].filter, undefined);
  assert.equal(repaired.detectables['Receive Mercy Heal'].threshold, .73);
  assert.equal(repaired.detectables['Receive Mercy Heal'].points, 52);
  assert.equal(repaired.detectables['Receive Immortality'].filter, 'edge');
  assert.equal(repaired.detectables['Receive Wuyang Heal'].filter, 'edge');
  assert.equal(fs.readFileSync(configPath + '.before-receive-filter-fix.bak', 'utf8'), original);
  assert.deepEqual(JSON.parse(fs.readFileSync(configPath)).user_regions, JSON.parse(original).user_regions);
  new Config(configPath).load();
  assert.equal(fs.readFileSync(configPath + '.before-receive-filter-fix.bak', 'utf8'), original);
  console.log('Saved filter repair preserves custom settings and retains the original config backup.');
} finally {
  for (const file of [configPath, configPath + '.before-receive-filter-fix.bak']) {
    if (fs.existsSync(file)) fs.unlinkSync(file);
  }
  fs.rmdirSync(folder);
}
