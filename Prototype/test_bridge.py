"""
Bridge test harness.
Connects to Lovense, then gives you a simple CLI to test device commands.
"""

import asyncio
import time
from bridge import LovenseClient, get_local_ip


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def print_help():
    print()
    print("Commands:")
    print("  0-20      Set intensity (e.g. '5' or '15')")
    print("  s         Stop all devices")
    print("  t         Show connected toys")
    print("  r         Refresh toy list")
    print("  q         Quit")
    print()


async def main():
    print("=" * 50, flush=True)
    print("  Bridge Test Harness", flush=True)
    print("=" * 50, flush=True)
    print(flush=True)

    local_ip = get_local_ip()
    if local_ip:
        prefix = local_ip.rsplit(".", 1)[0]  # e.g. "192.168.86"
        print(f"Your network: {prefix}.x", flush=True)
        print("Enter the last digits of your phone's IP (from Lovense Remote > Game Mode).", flush=True)
        print("Leave blank to try this PC (localhost).", flush=True)
        suffix = input(f"{prefix}. ").strip()
        ip = f"{prefix}.{suffix}" if suffix else "127.0.0.1"
    else:
        print("Could not detect your network IP.", flush=True)
        ip = input("Please enter full Lovense IP: ").strip()
        while not ip:
            ip = input("Please enter full Lovense IP: ").strip()
    print(flush=True)

    lovense = LovenseClient.from_ip(ip, on_log=lambda msg: log(f"[Lovense] {msg}"))

    if not await lovense.connect():
        log(f"Retrying Lovense at {ip}...")
        await asyncio.sleep(3)
        if not await lovense.connect():
            log(f"Failed to connect to Lovense at {ip}. Check the IP and make sure the app is running.")
            input("Press Enter to exit...")
            return

    print_help()

    loop = asyncio.get_event_loop()

    while True:
        try:
            cmd = await loop.run_in_executor(None, lambda: input(">> ").strip().lower())
        except (EOFError, KeyboardInterrupt):
            break

        if not cmd:
            continue

        if cmd == "q":
            break
        elif cmd == "s":
            await lovense.stop_all()
            log("Stopped all")
        elif cmd == "t":
            if not lovense.toys:
                print("  No toys connected")
            for tid, toy in lovense.toys.items():
                status = "ONLINE" if toy["status"] == 1 else "offline"
                print(f"  {toy['name']} (id={tid}) battery={toy['battery']}% {status} [{', '.join(toy['functions'])}]")
        elif cmd == "r":
            await lovense.refresh_toys()
            log(f"Refreshed — {len(lovense.toys)} toy(s)")
        elif cmd.isdigit() and 0 <= int(cmd) <= 20:
            level = int(cmd)
            for tid, toy in lovense.toys.items():
                for func in toy["functions"]:
                    await lovense.send_action(tid, func, level)
                    log(f"{toy['name']} {func} {level}/20")
        else:
            print(f"  Unknown command: {cmd}")
            print_help()

    await lovense.stop_all()
    await lovense.disconnect()
    print("Bye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBye!")
