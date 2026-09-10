/**
 * Buttplug v3 WebSocket server.
 * Accepts Buttplug-speaking clients and translates to Lovense HTTP API.
 */

const { WebSocketServer } = require('ws');
const { getActuators } = require('./device-db');

class ButtplugServer {
  constructor(lovense, { onLog = () => {} } = {}) {
    this.lovense = lovense;
    this._log = onLog;
    this.clientName = null;
    this._commandCount = 0;
    this._startTime = null;
    this._actuatorMap = {};  // `${devIdx},${actIdx}` -> { toyId, action }
    this._lastLevels = {};   // `${toyId},${action}` -> level
    this._wss = null;
  }

  _buildDeviceList() {
    const devices = [];
    this._actuatorMap = {};
    let devIdx = 0;

    for (const [tid, toy] of Object.entries(this.lovense.toys)) {
      const actuatorDefs = getActuators(toy.name, toy.functions);
      const scalarCmds = [];

      actuatorDefs.forEach(([lovenseAction, bpType], actIdx) => {
        scalarCmds.push({ FeatureDescriptor: lovenseAction, ActuatorType: bpType, StepCount: 20 });
        this._actuatorMap[`${devIdx},${actIdx}`] = { toyId: tid, action: lovenseAction };
      });

      devices.push({
        DeviceIndex: devIdx,
        DeviceName: `Lovense ${toy.name}`,
        DeviceMessages: { ScalarCmd: scalarCmds, StopDeviceCmd: {} },
        DeviceMessageTimingGap: 50,
      });
      devIdx++;
    }
    return devices;
  }

  async _handleMessage(type, body, id) {
    if (type === 'RequestServerInfo') {
      this.clientName = body.ClientName || 'Unknown';
      this._log(`Handshake: ${this.clientName}`);
      return [{ ServerInfo: { Id: id, ServerName: 'LvnsWatch Bridge', MessageVersion: 3, MaxPingTime: 0 } }];
    }
    if (type === 'RequestDeviceList') {
      const devices = this._buildDeviceList();
      this._log(`DeviceList: ${devices.length} device(s)`);
      return [{ DeviceList: { Id: id, Devices: devices } }];
    }
    if (type === 'StartScanning') {
      await this.lovense.refreshToys();
      const responses = [{ Ok: { Id: id } }];
      for (const dev of this._buildDeviceList()) {
        responses.push({ DeviceAdded: { Id: 0, DeviceIndex: dev.DeviceIndex, DeviceName: dev.DeviceName, DeviceMessages: dev.DeviceMessages } });
      }
      responses.push({ ScanningFinished: { Id: 0 } });
      const online = Object.values(this.lovense.toys).filter(t => t.status === 1).length;
      this._log(`Scan: ${online} online device(s)`);
      return responses;
    }
    if (type === 'StopScanning') return [{ Ok: { Id: id } }];

    if (type === 'ScalarCmd') {
      const devIdx = body.DeviceIndex || 0;
      for (const scalar of (body.Scalars || [])) {
        const actIdx = scalar.Index || 0;
        const level = Math.max(0, Math.min(20, Math.round((scalar.Scalar || 0) * 20)));
        const mapping = this._actuatorMap[`${devIdx},${actIdx}`];
        if (!mapping) continue;
        const levelKey = `${mapping.toyId},${mapping.action}`;
        if (this._lastLevels[levelKey] === level) continue;
        await this.lovense.sendAction(mapping.toyId, mapping.action, level);
        this._lastLevels[levelKey] = level;
        this._commandCount++;
        const toyName = this.lovense.toys[mapping.toyId]?.name || '?';
        this._log(`${toyName} ${mapping.action} ${level}/20`);
      }
      return [{ Ok: { Id: id } }];
    }
    if (type === 'VibrateCmd') {
      const devIdx = body.DeviceIndex || 0;
      for (const speed of (body.Speeds || [])) {
        const level = Math.max(0, Math.min(20, Math.round((speed.Speed || 0) * 20)));
        for (const [key, mapping] of Object.entries(this._actuatorMap)) {
          if (!key.startsWith(`${devIdx},`)) continue;
          const levelKey = `${mapping.toyId},${mapping.action}`;
          if (this._lastLevels[levelKey] === level) continue;
          await this.lovense.sendAction(mapping.toyId, mapping.action, level);
          this._lastLevels[levelKey] = level;
          this._commandCount++;
        }
      }
      return [{ Ok: { Id: id } }];
    }
    if (type === 'StopDeviceCmd' || type === 'StopAllDevices') {
      if (type === 'StopDeviceCmd') {
        const devIdx = body.DeviceIndex || 0;
        for (const [key, mapping] of Object.entries(this._actuatorMap)) {
          if (key.startsWith(`${devIdx},`)) {
            await this.lovense.stopToy(mapping.toyId);
            this._lastLevels[`${mapping.toyId},${mapping.action}`] = 0;
            break;
          }
        }
      } else {
        await this.lovense.stopAll();
        this._lastLevels = {};
      }
      this._commandCount++;
      this._log('Stop');
      return [{ Ok: { Id: id } }];
    }
    if (type === 'Ping') return [{ Ok: { Id: id } }];
    return [{ Ok: { Id: id } }];
  }

  start(port = 12345) {
    this._wss = new WebSocketServer({ host: '127.0.0.1', port });
    this._log(`Buttplug server on ws://127.0.0.1:${port}`);

    this._wss.on('connection', (ws) => {
      this.clientName = null;
      this._commandCount = 0;
      this._startTime = Date.now();
      this._lastLevels = {};
      this._log('Client connected');

      ws.on('message', async (raw) => {
        let messages;
        try { messages = JSON.parse(raw); } catch { return; }

        const responses = [];
        for (const msg of messages) {
          const [type, body] = Object.entries(msg)[0];
          const id = body.Id || 0;
          try {
            const resp = await this._handleMessage(type, body, id);
            if (resp) responses.push(...resp);
          } catch (e) {
            this._log(`Error: ${e.message}`);
            responses.push({ Ok: { Id: id } });
          }
        }
        if (responses.length > 0) {
          ws.send(JSON.stringify(responses));
        }
      });

      ws.on('close', () => {
        const elapsed = ((Date.now() - this._startTime) / 1000).toFixed(0);
        this._log(`Client '${this.clientName}' disconnected (${elapsed}s, ${this._commandCount} cmds)`);
        this.lovense.stopAll();
      });
    });
  }

  stop() {
    if (this._wss) {
      this._wss.close();
      this._wss = null;
    }
  }
}

module.exports = { ButtplugServer };
