const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const source = fs.readFileSync(path.join(__dirname, '../app/index.js'), 'utf8');
const handler = source.match(/function handleVisionMessage\(msg\) \{[\s\S]*?\n\}/)[0];
for (const muted of [false, true]) {
  let stops = 0, actions = 0;
  const context = vm.createContext({
    win: null, debugWin: null, updateOverlay() {}, muted,
    mutedToys: new Set(['toy']), lastLevel: 20, lastSendTime: 0,
    config: {get: k => ({min_score: -100, max_score: 100}[k])},
    lovense: {connected: true, stopAll() { stops++; },
      toys: {toy: {name: 'Nora', functions: ['Vibrate', 'Rotate']}},
      sendActions() { actions++; }},
  });
  vm.runInContext(handler, context);
  vm.runInContext("handleVisionMessage({type:'frame',score:0,ping:1,detections:{},menuPaused:true})", context);
  assert.equal(stops, 1);
  assert.equal(actions, 0);
}
console.log('Menu pause bypasses score minimums and stops all outputs, including muted toys.');
