const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const {LovenseClient} = require('../app/src/bridge/lovense');
const html = fs.readFileSync(path.join(__dirname, '../app/app.html'), 'utf8');
const renderer = html.slice(html.indexOf('function deviceIconKey('), html.indexOf('function updateToyMuteBtn('));

for (const status of [1, '1', 0, '0', undefined, null, 'unknown']) {
  for (const serialized of [false, true]) {
    const client = new LovenseClient();
    const payload = {domi: {name: 'Domi', status, battery: 73}};
    client._parseToys({toys: serialized ? JSON.stringify(payload) : payload});
    const online = status === 1 || status === '1';
    assert.equal(client.toys.domi.status, online ? 1 : 0);
    const nodes = Object.fromEntries(['device-list', 'device-chip', 'dev-count', 'rail-dot'].map(id =>
      [id, {innerHTML: '', textContent: '', className: '', querySelectorAll: () => []}]));
    const context = vm.createContext({document: {getElementById: id => nodes[id]}, toys: client.toys});
    vm.runInContext(renderer + '\nupdateDeviceList(toys);', context);
    assert.equal(nodes['device-chip'].textContent, online ? '1 ONLINE' : '0 ONLINE');
    assert.equal(nodes['rail-dot'].className, online ? 'pulse-dot live' : 'pulse-dot off');
    const card = nodes['device-list'].innerHTML;
    if (online) {
      assert(card.includes('73%'));
      assert(card.includes('>LIVE</button>'));
      assert(card.includes('icon_domi_pink.png'));
    } else {
      assert(card.includes('offline'));
      assert(!card.includes('>LIVE</button>'));
    }
  }
}
console.log('Device status: numeric/text online states show battery, LIVE and active icon; offline stays offline.');
