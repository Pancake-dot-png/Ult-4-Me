"""
Standalone bridge runner.
Connect to Lovense and serve Buttplug v3 on port 12345.
"""

import asyncio
import time
from bridge import LovenseClient, ButtplugServer


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


async def main():
    print("=" * 50, flush=True)
    print("  LvnsWatch Bridge", flush=True)
    print("  Lovense + Buttplug v3", flush=True)
    print("=" * 50, flush=True)
    print(flush=True)
    print("Enter the IP from Lovense Remote > Game Mode.", flush=True)
    print("Leave blank for localhost (Lovense Connect on PC).", flush=True)
    print(flush=True)

    ip = input("Lovense IP [127.0.0.1]: ").strip() or "127.0.0.1"
    print(flush=True)

    lovense = LovenseClient.from_ip(ip, on_log=lambda msg: log(f"[Lovense] {msg}"))

    if not await lovense.connect():
        log(f"Waiting for Lovense app at {ip}...")
        while not await lovense.connect():
            await asyncio.sleep(3)

    server = ButtplugServer(lovense, on_log=lambda msg: log(f"[Server] {msg}"))
    await server.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBye!")
