/**
 * Lovense Connect / Remote HTTP client.
 * Talks directly to the Lovense app — no Intiface needed.
 */

const { getActuators } = require('./device-db');
const dgram = require('dgram');
const os = require('os');

function getLocalIP() {
  // Prefer Wi-Fi, then any non-virtual adapter
  const nets = os.networkInterfaces();
  const prefer = ['wi-fi', 'wifi', 'wlan', 'wireless'];
  let wifiIP = null;
  let ethernetIP = null;

  for (const [name, addrs] of Object.entries(nets)) {
    const nameLower = name.toLowerCase();
    for (const net of addrs) {
      if (net.family === 'IPv4' && !net.internal) {
        if (prefer.some(p => nameLower.includes(p))) {
          wifiIP = net.address;
        } else if (!ethernetIP) {
          ethernetIP = net.address;
        }
      }
    }
  }
  return wifiIP || ethernetIP || null;
}

class LovenseClient {
  constructor({ urls = [], onLog = () => {} } = {}) {
    this.urls = urls;
    this.baseUrl = null;
    this.toys = {};       // id -> toy object
    this.connected = false;
    this._pollTimer = null;
    this._log = onLog;
  }

  static fromIP(ip = '127.0.0.1', opts = {}) {
    return new LovenseClient({
      urls: [
        `http://${ip}:20010/command`,
        `http://${ip}:30010/command`,
      ],
      ...opts,
    });
  }

  async _post(payload) {
    if (!this.baseUrl) return null;
    try {
      const res = await fetch(this.baseUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(3000),
      });
      return await res.json();
    } catch {
      return null;
    }
  }

  async connect() {
    for (const url of this.urls) {
      this.baseUrl = url;
      const result = await this._post({ command: 'GetToys' });
      if (result && result.code === 200) {
        this.connected = true;
        this._parseToys(result.data);
        this._log(`Connected via ${url} — ${Object.keys(this.toys).length} toy(s)`);
        for (const [tid, toy] of Object.entries(this.toys)) {
          const status = toy.status === 1 ? 'ONLINE' : 'offline';
          this._log(`  ${toy.name} (id=${tid}) battery=${toy.battery}% ${status} [${toy.functions.join(', ')}] reported=[${toy.reported.join(', ')}]`);
        }
        this._startPolling();
        return true;
      }
    }
    this._log('Could not connect to any Lovense app');
    this.baseUrl = null;
    return false;
  }

  disconnect() {
    this._stopPolling();
    this.connected = false;
    this.toys = {};
  }

  async sendAction(toyId, action, level) {
    level = Math.max(0, Math.min(20, level));
    const actionStr = level <= 0 ? 'Stop' : `${action}:${level}`;
    await this._post({
      command: 'Function',
      action: actionStr,
      timeSec: 0,
      toy: toyId,
      apiVer: 1,
    });
  }

  async sendActions(toyId, actionLevels) {
    // actionLevels: array of [action, level] pairs — sent as one combined command
    const parts = [];
    for (const [action, level] of actionLevels) {
      const l = Math.max(0, Math.min(20, level));
      if (l > 0) parts.push(`${action}:${l}`);
    }
    if (parts.length === 0) {
      return this.stopToy(toyId);
    }
    await this._post({
      command: 'Function',
      action: parts.join(','),
      timeSec: 0,
      toy: toyId,
      apiVer: 1,
    });
  }

  async stopToy(toyId) {
    await this._post({ command: 'Function', action: 'Stop', timeSec: 0, toy: toyId, apiVer: 1 });
  }

  async stopAll() {
    await this._post({ command: 'Function', action: 'Stop', timeSec: 0, apiVer: 1 });
  }

  async refreshToys() {
    let result = await this._post({ command: 'GetToys' });
    // If primary URL failed, try all URLs
    if (!result || result.code !== 200) {
      for (const url of this.urls) {
        if (url === this.baseUrl) continue;
        this.baseUrl = url;
        result = await this._post({ command: 'GetToys' });
        if (result && result.code === 200) break;
      }
    }
    if (result && result.code === 200) {
      this._parseToys(result.data);
      if (!this.connected) {
        this.connected = true;
        this._log('Reconnected!');
        if (this.onReconnect) this.onReconnect();
      }
    } else if (this.connected) {
      this._log('Connection lost, retrying...');
      this.connected = false;
      if (this.onDisconnect) this.onDisconnect();
    }
  }

  _parseToys(data) {
    let toysRaw = data.toys || '{}';
    if (typeof toysRaw === 'string') {
      try { toysRaw = JSON.parse(toysRaw); } catch { return; }
    }
    this.toys = {};
    for (const [tid, toy] of Object.entries(toysRaw)) {
      const name = toy.name || 'unknown';
      const reported = toy.fullFunctionsNames || toy.fullFunctionNames || [];
      const actuators = getActuators(name, reported);
      this.toys[tid] = {
        id: toy.id || tid,
        name,
        nickName: toy.nickName || '',
        status: toy.status || 0,
        battery: toy.battery || 0,
        version: toy.version || '',
        functions: actuators.map(a => a[0]),
        reported,
      };
    }
  }

  _startPolling() {
    this._stopPolling();
    this._pollTimer = setInterval(() => this.refreshToys(), 10000);
  }

  _stopPolling() {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
  }
}

module.exports = { LovenseClient, getLocalIP };
