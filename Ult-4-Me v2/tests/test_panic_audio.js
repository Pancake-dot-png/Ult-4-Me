const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const {EventEmitter} = require('events');
const source = fs.readFileSync(path.join(__dirname, '../app/index.js'), 'utf8');
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
const commands = [];
const context = vm.createContext({path, __dirname: path.resolve(__dirname, "../app"), win, muted: false,
  visionProcess: {stdin: {writable: true, write: command => commands.push(command)}}, lovense: null,
  overlayWin: null, config: {get: () => ''}, DEFAULT_PANIC_URL: 'https://example.com/'});
vm.runInContext(fn, context);
vm.runInContext('toggleMute()', context);
assert.equal(audioMuted, true);
assert.deepEqual(commands, ['reset\n'], 'panic activation must reset the engine score');
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

const {installPanicAudio} = require('../app/src/panic-audio');
const guarded = new EventEmitter();
let panic = true, guardedMuted = false, injected = 0;
guarded.isDestroyed = () => false;
guarded.setAudioMuted = value => { guardedMuted = value; };
guarded.executeJavaScript = async () => { injected++; };
installPanicAudio(guarded, () => panic);
for (const event of ['did-start-navigation', 'did-navigate', 'dom-ready', 'media-started-playing']) {
  guardedMuted = false;
  guarded.emit(event);
  assert.equal(guardedMuted, true, `${event} must reassert silence`);
}
assert.equal(injected, 2);
panic = false; guardedMuted = false;
guarded.emit('dom-ready');
assert.equal(guardedMuted, false);
assert.equal(injected, 2);
console.log('Panic mute is reapplied on navigation and autoplay, without affecting the normal app.');
