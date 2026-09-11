// Run with node_modules/electron/dist/electron.exe. No network or device access.
const {app, BrowserWindow} = require('electron');
const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const profile = fs.mkdtempSync(path.join(__dirname, '../build/panic-audio-test-'));
app.setPath('userData', profile);
const {installPanicAudio} = require('../app/src/panic-audio');
app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');
let win;
app.whenReady().then(async () => {
  win = new BrowserWindow({show: false, webPreferences: {contextIsolation: true, sandbox: true}});
  let panic = true;
  const contents = win.webContents;
  installPanicAudio(contents, () => panic);
  contents.setAudioMuted(true);
  const page = 'data:text/html,' + encodeURIComponent('<html><body><video id="initial"></video></body></html>');
  await win.loadURL(page);
  const inspect = async () => contents.executeJavaScript(`new Promise(resolve => setTimeout(() => resolve(
    [...document.querySelectorAll('video,audio')].map(m => ({volume:m.volume,muted:m.muted,defaultMuted:m.defaultMuted}))
  ), 50))`);
  assert.equal(contents.isAudioMuted(), true);
  assert.deepEqual(await inspect(), [{volume: 0, muted: true, defaultMuted: true}]);
  await contents.executeJavaScript(`const ad = document.createElement('audio'); document.body.appendChild(ad);`);
  assert.equal((await inspect()).length, 2);
  await contents.executeJavaScript(`document.querySelectorAll('video,audio').forEach(m => {m.volume=1;m.muted=false;});`);
  for (const media of await inspect()) {
    assert.equal(media.volume, 0); assert.equal(media.muted, true);
  }
  // New document, like a redirect or player reload.
  await win.loadURL(page + '%20');
  assert.equal(contents.isAudioMuted(), true);
  assert.equal((await inspect())[0].volume, 0);
  panic = false;
  await win.loadURL(page + '%20%20');
  contents.setAudioMuted(false);
  assert.deepEqual(await inspect(), [{volume: 1, muted: false, defaultMuted: false}]);
  console.log('Real Electron: initial player, added media, volume resets and navigation remain muted; normal app restores.');
  win.destroy(); app.exit(0);
}).catch(error => {console.error(error); if (win) win.destroy(); app.exit(1);});
