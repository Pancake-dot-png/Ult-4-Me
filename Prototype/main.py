"""
LvnsWatch — main app.
Ties together vision, bridge, overlay, and config into one program.
"""

import sys
import os
import asyncio
import time
import threading
import keyboard

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

from config import Config
from vision import Vision
from overlay import Overlay
from bridge import LovenseClient, get_local_ip

PANIC_KEY = None  # set during onboarding


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def prompt_lovense_ip():
    """Ask user for Lovense IP before starting the app."""
    print("=" * 50)
    print("  LvnsWatch")
    print("  Overwatch 2 + Lovense")
    print("=" * 50)
    print()

    local_ip = get_local_ip()
    if local_ip:
        prefix = local_ip.rsplit(".", 1)[0]
        print(f"Your network: {prefix}.x")
        print("Enter the last digits of your phone's IP (Lovense Remote > Game Mode).")
        print("Leave blank for localhost (Lovense Connect on PC).")
        suffix = input(f"{prefix}. ").strip()
        ip = f"{prefix}.{suffix}" if suffix else "127.0.0.1"
    else:
        print("Could not detect your network IP.")
        ip = input("Please enter Lovense IP: ").strip()
        while not ip:
            ip = input("Please enter Lovense IP: ").strip()

    print()
    return ip


def main():
    templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")
    if not os.path.exists(templates_dir):
        print(f"Templates not found at: {templates_dir}")
        input("Press Enter to exit...")
        return

    # ── Config ──
    cfg = Config()
    cfg.load()

    # ── Lovense IP ──
    saved_ip = cfg.get("lovense_ip", "")
    if saved_ip:
        print(f"Last Lovense IP: {saved_ip}")
        use_saved = input("Use this IP? [Y/n]: ").strip().lower()
        if use_saved in ("", "y", "yes"):
            ip = saved_ip
        else:
            ip = prompt_lovense_ip()
    else:
        ip = prompt_lovense_ip()

    cfg.set("lovense_ip", ip, save=True)

    # ── Safe Word key ──
    global PANIC_KEY
    saved_panic = cfg.get("panic_key", "")
    if saved_panic:
        print(f"Safe Word: {saved_panic}")
        PANIC_KEY = saved_panic
    else:
        print("Set your Safe Word key combo. This instantly stops all devices and hides everything.")
        print("Press your key or combo (e.g. F12, Shift+`, Ctrl+Shift+X)...")
        print("Hold all keys at once, then release.")
        hotkey = keyboard.read_hotkey(suppress=False)
        PANIC_KEY = hotkey
        print(f"Safe Word set to: {PANIC_KEY}")
        cfg.set("panic_key", PANIC_KEY, save=True)
    print()

    # ── Connect Lovense (in background) ──
    lovense = LovenseClient.from_ip(ip, on_log=lambda msg: log(f"[Lovense] {msg}"))

    loop = asyncio.new_event_loop()

    def run_async_loop():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    async_thread = threading.Thread(target=run_async_loop, daemon=True)
    async_thread.start()

    # Connect to Lovense
    log(f"Connecting to Lovense at {ip}...")
    future = asyncio.run_coroutine_threadsafe(lovense.connect(), loop)
    connected = future.result(timeout=10)

    if not connected:
        log("Retrying...")
        future = asyncio.run_coroutine_threadsafe(lovense.connect(), loop)
        connected = future.result(timeout=10)

    if not connected:
        log("Could not connect to Lovense. Check IP and make sure the app is running.")
        input("Press Enter to exit...")
        return

    # ── Vision ──
    ar = cfg.get_aspect_ratio()
    log(f"Monitor: {cfg.get('monitor_number')} | Aspect: {ar['id']}")

    vision = Vision(cfg, templates_dir=templates_dir)

    # ── Overlay mode ──
    cfg.settings["show_overlay_mode"] = 2   # show when Overwatch focused
    cfg.settings["show_regions_mode"] = 2   # show on detection

    # ── Qt App ──
    app = QApplication(sys.argv)
    overlay = Overlay(cfg, vision)

    # ── Intensity mapping ──
    last_level = -1
    min_score = 0
    max_score = 100
    paused = False

    def score_to_intensity(score):
        """Map score to 0.0-1.0 intensity."""
        if max_score <= min_score:
            return 0.0
        normalized = (score - min_score) / (max_score - min_score)
        return max(0.0, min(1.0, normalized))

    # ── Panic button ──
    def toggle_panic():
        nonlocal paused, last_level
        paused = not paused
        if paused:
            # Kill everything immediately
            asyncio.run_coroutine_threadsafe(lovense.stop_all(), loop)
            vision.set_score(0)
            last_level = 0
            overlay.hide()
            log(f"!! SAFE WORD — all devices stopped, overlay hidden. Press {PANIC_KEY.upper()} to resume.")
        else:
            overlay.show()
            log("Resumed.")

    keyboard.add_hotkey(PANIC_KEY, toggle_panic, suppress=False)
    log(f"Safe Word: {PANIC_KEY.upper()} — stops everything instantly.")

    # ── Main loop ──
    def tick():
        nonlocal last_level

        if paused:
            return

        if not vision.update():
            return

        overlay.update_display()
        score = vision.get_score()

        # Log detections
        for name, ds in vision.get_det_state().items():
            if ds["count"] > 0 and name != "KillcamOrPOTG":
                det = cfg.detectables[name]
                pts = det.get("points", 0)
                log(f"  DETECTED: {name} (x{ds['count']}) +{pts}pts  Score: {score:.0f}")

        # Send to Lovense
        if not lovense.connected:
            return

        intensity = score_to_intensity(score)
        level = max(0, min(20, round(intensity * 20)))

        if level != last_level:
            for tid, toy in lovense.toys.items():
                for func in toy["functions"]:
                    asyncio.run_coroutine_threadsafe(
                        lovense.send_action(tid, func, level), loop
                    )
            if level > 0:
                log(f"  >> Vibrate {level}/20 (score {score:.0f})")
            else:
                log(f"  >> Stop (score {score:.0f})")
            last_level = level

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(100)

    log("Running. Play Overwatch in borderless windowed mode.")
    log("Ctrl+C or close this window to stop.")
    print()

    try:
        app.exec()
    finally:
        # Stop devices on exit
        asyncio.run_coroutine_threadsafe(lovense.stop_all(), loop)
        time.sleep(0.5)
        loop.call_soon_threadsafe(loop.stop)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBye!")
