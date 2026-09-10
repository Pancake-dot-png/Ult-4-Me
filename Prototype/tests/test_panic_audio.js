const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const {EventEmitter} = require('events');
const source = fs.readFileSync(path.join(__dirname, '../electron_test/index.js'), 'utf8');
const fn = source.match(/function toggleMute\(\) \{[\s\S]*?\n\}/)[0];
const contents = new EventEmitter();
let audioMuted = false;
let url = 'file:///app.html';
contents.setAudioMuted = value => { audioMuted = value; };
contents.getURL = () => url;
const win = {
  webContents: contents, isDestroyed: () => false,
  setTitle() {}, setResizable() {}, setMaximizable() {}, removeAllListeners() {},
  loadURL(next) { assert.equal(audioMuted, true, 'must mute before panic navigation'); url = next; },
  loadFile() { assert.equal(audioMuted, true, 'outgoing panic page must stay muted'); },
};
const context = vm.createContext({win, muted: false, visionProcess: {}, lovense: null,
  overlayWin: null, config: {get: () => ''}, DEFAULT_PANIC_URL: 'https://example.com/'});
vm.runInContext(fn, context);
vm.runInContext('toggleMute()', context);
assert.equal(audioMuted, true);
contents.emit('dom-ready');
assert.equal(audioMuted, true, 'panic remains muted after load');
vm.runInContext('toggleMute()', context);
assert.equal(audioMuted, true, 'return navigation stays muted until app loads');
url = 'file:///app.html'; contents.emit('dom-ready');
assert.equal(audioMuted, false);
// Re-enter panic before a pending return finishes: stale callbacks cannot unmute it.
vm.runInContext('toggleMute(); toggleMute(); toggleMute()', context);
contents.emit('dom-ready');
assert.equal(audioMuted, true);
console.log('Panic audio: muted before navigation, stays silent, safely restores on return.');
