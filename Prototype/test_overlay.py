"""
Overlay test harness.
Runs vision + overlay together. You should see:
- Magenta border around the detection area
- Score and detection delay in bottom-left
- Red region boxes when detections happen (if overlay mode is set)

Press Ctrl+C in terminal to stop.
"""

import sys
import os
import asyncio
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

from config import Config
from vision import Vision
from overlay import Overlay


def main():
    print("=" * 50)
    print("  Overlay + Vision Test")
    print("=" * 50)
    print()

    templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    if not os.path.exists(templates_dir):
        print(f"Templates not found at: {templates_dir}")
        input("Press Enter to exit...")
        return

    cfg = Config()
    cfg.load()

    # Force overlay visible for testing
    cfg.settings["show_overlay_mode"] = 1    # always show
    cfg.settings["show_regions_mode"] = 2    # show on detection

    ar = cfg.get_aspect_ratio()
    print(f"Monitor: {cfg.get('monitor_number')}")
    print(f"Aspect ratio: {ar['id']}")
    print(f"Overlay: ON  |  Regions: show on detection")
    print()
    print("You should see a magenta border on your game screen.")
    print("Detections will show as red boxes. Close this window to stop.")
    print()

    app = QApplication(sys.argv)

    vision = Vision(cfg, templates_dir=templates_dir)
    overlay = Overlay(cfg, vision)

    # Run vision + overlay update on a timer (100ms = 10fps)
    def tick():
        if vision.update():
            overlay.update_display()
            score = vision.get_score()
            # Print detections to console too
            for name, ds in vision.get_det_state().items():
                if ds["count"] > 0 and name != "KillcamOrPOTG":
                    print(f"  DETECTED: {name} (x{ds['count']})  Score: {score:.0f}")

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(100)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
