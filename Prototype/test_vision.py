"""
Vision engine test harness.
Runs detection loop and prints score + detections in real-time.
"""

import time
import os
import sys
from config import Config
from vision import Vision


def main():
    print("=" * 50)
    print("  Vision Engine Test")
    print("=" * 50)
    print()

    # Check templates exist
    templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    if not os.path.exists(templates_dir):
        print(f"Templates not found at: {templates_dir}")
        print("Make sure you're running from Prototype/ and templates/ is in the parent Underwatch/ folder.")
        input("Press Enter to exit...")
        return

    template_count = len([f for f in os.listdir(templates_dir) if f.endswith(".png")])
    print(f"Templates dir: {templates_dir} ({template_count} images)")

    cfg = Config()
    cfg.load()

    monitor = cfg.get("monitor_number", 1)
    ar = cfg.get_aspect_ratio()
    print(f"Monitor: {monitor}")
    print(f"Aspect ratio: {ar['id']} ({ar['sample_w']}x{ar['sample_h']})")
    print()
    print("Starting detection loop... (Ctrl+C to stop)")
    print("Play Overwatch in borderless windowed mode to see detections.")
    print()

    vision = Vision(cfg, templates_dir=templates_dir)

    last_print = 0
    last_score = -1

    try:
        while True:
            updated = vision.update()
            if not updated:
                time.sleep(0.001)
                continue

            score = vision.get_score()
            now = time.time()

            # Print detections when they happen
            for name, ds in vision.get_det_state().items():
                if ds["count"] > 0 and name != "KillcamOrPOTG":
                    det = cfg.detectables[name]
                    pts = det.get("points", 0)
                    ts = time.strftime("%H:%M:%S")
                    print(f"  [{ts}] DETECTED: {name} (x{ds['count']}) +{pts}pts")

            # Print score periodically or when it changes
            rounded = round(score)
            if rounded != last_score or now - last_print > 2:
                ts = time.strftime("%H:%M:%S")
                ping_ms = vision.detection_ping * 1000
                print(f"  [{ts}] Score: {rounded}  |  ping: {ping_ms:.0f}ms")
                last_score = rounded
                last_print = now

    except KeyboardInterrupt:
        print()
        print("Stopped.")


if __name__ == "__main__":
    main()
