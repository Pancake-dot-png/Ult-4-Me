"""
Buttplug v3 WebSocket server.

Accepts clients (like the original Underwatch) and translates
Buttplug device commands to Lovense HTTP API calls.
Also allows our own app to call LovenseClient directly — the server
is for backward compat with any Buttplug-speaking app.
"""

import asyncio
import json
import time
import websockets
from websockets.asyncio.server import serve
from .device_db import get_actuators, KNOWN_DEVICES
from .lovense import LovenseClient


class ButtplugServer:
    def __init__(self, lovense: LovenseClient, on_log=None):
        self.lovense = lovense
        self._log = on_log or (lambda msg: None)
        self.client_name = None
        self._command_count = 0
        self._start_time = None
        # Maps (device_index, actuator_index) -> (toy_id, lovense_action)
        self._actuator_map = {}
        # Tracks last sent level per (toy_id, action) to skip duplicates
        self._last_levels = {}

    def _build_device_list(self):
        """Build Buttplug v3 device list and actuator mapping from connected toys."""
        devices = []
        self._actuator_map.clear()
        dev_idx = 0

        for tid, toy in self.lovense.toys.items():
            name = toy["name"]
            actuator_defs = get_actuators(name, toy.get("functions"))

            scalar_cmds = []
            for act_idx, (lovense_action, bp_type) in enumerate(actuator_defs):
                scalar_cmds.append({
                    "FeatureDescriptor": lovense_action,
                    "ActuatorType": bp_type,
                    "StepCount": 20,
                })
                self._actuator_map[(dev_idx, act_idx)] = (tid, lovense_action)

            devices.append({
                "DeviceIndex": dev_idx,
                "DeviceName": f"Lovense {name}",
                "DeviceMessages": {"ScalarCmd": scalar_cmds, "StopDeviceCmd": {}},
                "DeviceMessageTimingGap": 50,
            })
            dev_idx += 1

        return devices

    async def handle_client(self, ws):
        self.client_name = None
        self._command_count = 0
        self._start_time = time.time()
        self._last_levels.clear()
        self._log(f"Client connected from {ws.remote_address}")
        try:
            async for raw in ws:
                try:
                    messages = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                responses = []
                for msg in messages:
                    try:
                        msg_type, body = next(iter(msg.items()))
                        msg_id = body.get("Id", 0)
                        resp = await self._handle_message(msg_type, body, msg_id)
                        if resp:
                            responses.extend(resp)
                    except Exception as e:
                        self._log(f"Error: {e}")
                        try:
                            responses.append({"Ok": {"Id": body.get("Id", 0)}})
                        except Exception:
                            pass
                if responses:
                    await ws.send(json.dumps(responses))
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            self._log(f"Error: {e}")
        finally:
            elapsed = time.time() - self._start_time if self._start_time else 0
            self._log(f"Client '{self.client_name}' disconnected ({elapsed:.0f}s, {self._command_count} cmds)")
            try:
                await self.lovense.stop_all()
            except Exception:
                pass

    async def _handle_message(self, msg_type, body, msg_id):
        if msg_type == "RequestServerInfo":
            self.client_name = body.get("ClientName", "Unknown")
            self._log(f"Handshake: {self.client_name}")
            return [{"ServerInfo": {
                "Id": msg_id,
                "ServerName": "LvnsWatch Bridge",
                "MessageVersion": 3,
                "MaxPingTime": 0,
            }}]

        elif msg_type == "RequestDeviceList":
            devices = self._build_device_list()
            self._log(f"DeviceList: {len(devices)} device(s)")
            return [{"DeviceList": {"Id": msg_id, "Devices": devices}}]

        elif msg_type == "StartScanning":
            await self.lovense.refresh_toys()
            responses = [{"Ok": {"Id": msg_id}}]
            for dev in self._build_device_list():
                responses.append({"DeviceAdded": {
                    "Id": 0,
                    "DeviceIndex": dev["DeviceIndex"],
                    "DeviceName": dev["DeviceName"],
                    "DeviceMessages": dev["DeviceMessages"],
                }})
            responses.append({"ScanningFinished": {"Id": 0}})
            online = sum(1 for t in self.lovense.toys.values() if t["status"] == 1)
            self._log(f"Scan: {online} online device(s)")
            return responses

        elif msg_type == "StopScanning":
            return [{"Ok": {"Id": msg_id}}]

        elif msg_type == "ScalarCmd":
            dev_idx = body.get("DeviceIndex", 0)
            for scalar in body.get("Scalars", []):
                act_idx = scalar.get("Index", 0)
                value = scalar.get("Scalar", 0)
                level = max(0, min(20, round(value * 20)))

                mapping = self._actuator_map.get((dev_idx, act_idx))
                if not mapping:
                    continue

                toy_id, lovense_action = mapping
                level_key = (toy_id, lovense_action)
                if self._last_levels.get(level_key) == level:
                    continue

                await self.lovense.send_action(toy_id, lovense_action, level)
                self._last_levels[level_key] = level
                self._command_count += 1
                toy_name = self.lovense.toys.get(toy_id, {}).get("name", "?")
                self._log(f"{toy_name} {lovense_action} {level}/20")
            return [{"Ok": {"Id": msg_id}}]

        elif msg_type == "VibrateCmd":
            dev_idx = body.get("DeviceIndex", 0)
            for speed in body.get("Speeds", []):
                value = speed.get("Speed", 0)
                level = max(0, min(20, round(value * 20)))
                for (di, ai), (toy_id, lovense_action) in self._actuator_map.items():
                    if di != dev_idx:
                        continue
                    level_key = (toy_id, lovense_action)
                    if self._last_levels.get(level_key) == level:
                        continue
                    await self.lovense.send_action(toy_id, lovense_action, level)
                    self._last_levels[level_key] = level
                    self._command_count += 1
                    toy_name = self.lovense.toys.get(toy_id, {}).get("name", "?")
                    self._log(f"{toy_name} {lovense_action} {level}/20")
            return [{"Ok": {"Id": msg_id}}]

        elif msg_type in ("StopDeviceCmd", "StopAllDevices"):
            if msg_type == "StopDeviceCmd":
                dev_idx = body.get("DeviceIndex", 0)
                for (di, ai), (toy_id, lovense_action) in self._actuator_map.items():
                    if di == dev_idx:
                        await self.lovense.stop_toy(toy_id)
                        self._last_levels[(toy_id, lovense_action)] = 0
                        break
            else:
                await self.lovense.stop_all()
                self._last_levels.clear()
            self._command_count += 1
            self._log("Stop")
            return [{"Ok": {"Id": msg_id}}]

        elif msg_type == "Ping":
            return [{"Ok": {"Id": msg_id}}]

        else:
            return [{"Ok": {"Id": msg_id}}]

    async def start(self, host="127.0.0.1", port=12345):
        """Start the WebSocket server. Blocks until cancelled."""
        self._log(f"Buttplug server on ws://{host}:{port}")
        async with serve(self.handle_client, host, port):
            await asyncio.Future()
