const assert = require('assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const {LovenseClient} = require('../app/src/bridge/lovense');
const {Config} = require('../app/src/config');

(async () => {
  const client = new LovenseClient({maxIntensity: 50});
  const sent = [];
  client._post = async payload => { sent.push(payload); return {code: 200}; };
  await client.sendActions('nora', [['Vibrate', 20], ['Rotate', 10]]);
  assert.equal(sent.at(-1).action, 'Vibrate:10,Rotate:5');
  await client.sendAction('domi', 'Vibrate', 10);
  assert.equal(sent.at(-1).action, 'Vibrate:5');
  await client.setMaxIntensity(25);
  assert.equal(sent.at(-2).action, 'Vibrate:5,Rotate:3');
  assert.equal(sent.at(-1).action, 'Vibrate:3');
  await client.setMaxIntensity(0);
  assert(sent.slice(-2).every(p => p.action === 'Stop'));
  await client.setMaxIntensity(100);
  assert.equal(sent.at(-2).action, 'Vibrate:20,Rotate:10');
  assert.equal(sent.at(-1).action, 'Vibrate:10');
  await client.stopToy('domi');
  await client.stopAll();
  const count = sent.length;
  await client.setMaxIntensity(50);
  assert.equal(sent.length, count, 'Changing limit must not restart panic/menu/stopped output');
  for (const limit of [0, 5, 25, 50, 75, 100]) {
    await client.setMaxIntensity(limit);
    for (const level of [0, 1, 10, 20, 100]) {
      await client.sendAction('test', 'Vibrate', level);
      const action = sent.at(-1).action;
      const actual = action === 'Stop' ? 0 : Number(action.split(':')[1]);
      assert(actual <= Math.floor(20 * limit / 100));
    }
  }
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'ult-intensity-'));
  try {
    const file = path.join(folder, 'config.json');
    const cfg = new Config(file);
    assert.equal(cfg.get('max_intensity'), 100);
    cfg.set('max_intensity', 0);
    const loaded = new Config(file); loaded.load();
    assert.equal(loaded.get('max_intensity'), 0);
  } finally {
    fs.rmSync(folder, {recursive: true, force: true});
  }
  console.log('Max intensity: all actions scaled/capped, live changes, zero, stop behavior and persistence passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
