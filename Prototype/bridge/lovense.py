"""
Lovense Connect / Remote HTTP API client.

Talks directly to the Lovense app over HTTP — no Intiface needed.
Supports both Lovense Connect (PC, port 20010) and Lovense Remote
Game Mode (phone IP, port 20010).
"""

import asyncio
import json
import socket
import urllib.request
from .device_db import get_actuators


def get_local_ip():
    """Get this machine's local network IP. Returns None if unavailable."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


class LovenseClient:
    def __init__(self, urls=None, on_log=None):
        self.urls = urls or []
        self.base_url = None
        self.toys = {}          # id -> toy dict
        self.connected = False
        self._poll_task = None
        self._log = on_log or (lambda msg: None)

    @classmethod
    def from_ip(cls, ip="127.0.0.1", **kwargs):
        """Create client from an IP address. Tries HTTP port 20010 then 30010."""
        urls = [
            f"http://{ip}:20010/command",
            f"http://{ip}:30010/command",
        ]
        return cls(urls=urls, **kwargs)

    def _post(self, payload):
        """Synchronous HTTP POST. Runs in executor for async use."""
        if not self.base_url:
            return None
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base_url, data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

    async def _post_async(self, payload):
        return await asyncio.get_event_loop().run_in_executor(None, self._post, payload)

    async def connect(self):
        """Try each URL until one responds with toys. Returns True on success."""
        for url in self.urls:
            self.base_url = url
            result = await self._post_async({"command": "GetToys"})
            if result and result.get("code") == 200:
                self.connected = True
                self._parse_toys(result.get("data", {}))
                self._log(f"Connected via {url} — {len(self.toys)} toy(s)")
                for tid, toy in self.toys.items():
                    status = "ONLINE" if toy["status"] == 1 else "offline"
                    funcs = ", ".join(toy["functions"])
                    self._log(f"  {toy['name']} (id={tid}) battery={toy['battery']}% {status} [{funcs}]")
                self._poll_task = asyncio.create_task(self._poll_loop())
                return True
        self._log("Could not connect to any Lovense app")
        self.base_url = None
        return False

    async def disconnect(self):
        if self._poll_task:
            self._poll_task.cancel()
            self._poll_task = None
        self.connected = False
        self.toys.clear()

    async def send_action(self, toy_id, action, level):
        """Send a specific action to a specific toy.
        action: 'Vibrate', 'Rotate', 'Oscillate'
        level: 0-20
        """
        level = max(0, min(20, level))
        action_str = "Stop" if level <= 0 else f"{action}:{level}"
        await self._post_async({
            "command": "Function",
            "action": action_str,
            "timeSec": 0,
            "toy": toy_id,
            "apiVer": 1,
        })

    async def stop_toy(self, toy_id):
        await self._post_async({
            "command": "Function",
            "action": "Stop",
            "timeSec": 0,
            "toy": toy_id,
            "apiVer": 1,
        })

    async def stop_all(self):
        await self._post_async({
            "command": "Function",
            "action": "Stop",
            "timeSec": 0,
            "apiVer": 1,
        })

    async def refresh_toys(self):
        result = await self._post_async({"command": "GetToys"})
        if result and result.get("code") == 200:
            self._parse_toys(result.get("data", {}))
            if not self.connected:
                self.connected = True
                self._log("Reconnected!")
        else:
            if self.connected:
                self._log("Connection lost, will retry...")
                self.connected = False

    def _parse_toys(self, data):
        toys_raw = data.get("toys", "{}")
        if isinstance(toys_raw, str):
            try:
                toys_obj = json.loads(toys_raw)
            except json.JSONDecodeError:
                return
        else:
            toys_obj = toys_raw
        self.toys.clear()
        for tid, toy in toys_obj.items():
            name = toy.get("name", "unknown")
            reported = toy.get("fullFunctionsNames", toy.get("fullFunctionNames", []))
            functions = [a[0] for a in get_actuators(name, reported)]
            self.toys[tid] = {
                "id": toy.get("id", tid),
                "name": name,
                "nickName": toy.get("nickName", ""),
                "status": toy.get("status", 0),
                "battery": toy.get("battery", 0),
                "version": toy.get("version", ""),
                "functions": functions,
            }

    async def _poll_loop(self):
        """Poll Lovense every 10s to track device state and auto-reconnect."""
        while True:
            await asyncio.sleep(10)
            try:
                await self.refresh_toys()
            except Exception:
                pass
