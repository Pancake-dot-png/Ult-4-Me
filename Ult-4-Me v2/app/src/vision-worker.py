"""
Vision worker — runs as a child process of Electron.
Captures screen, runs template matching, outputs JSON lines on stdout.

Electron reads these and drives the UI + Lovense.
"""

import sys
import os
import json
import time
import threading
import select

# Add Prototype dir to path for config/vision imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'engine'))

from config import Config
from vision import Vision


def main():
    # Read config path and templates dir from argv
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    templates_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), '..', '..', '..', 'templates')

    cfg = Config(config_path)
    cfg.load()

    # Log what we loaded
    det_count = len([n for n, d in cfg.detectables.items() if d.get("points", 0) != 0])
    emit({"type": "info", "message": f"Loaded {det_count} active detectables, {len(cfg.detectables)} total"})

    emit({"type": "info", "message": f"Templates dir: {templates_dir}, config: {config_path}"})

    vision = Vision(cfg, templates_dir=templates_dir)

    for name, error in vision.template_errors.items():
        emit({"type": "error", "message": f"{name}: {error}"})
    loaded = list(vision.get_det_state().keys())
    emit({"type": "info", "message": f"Templates loaded: {len(loaded)}"})

    # Signal ready with detection rect and region positions
    det_rect = vision.get_detection_rect()
    regions = {}
    for name, rs in vision.get_region_state().items():
        regions[name] = rs["scaled"]
    emit({
        "type": "ready",
        "monitor": cfg.get("monitor_number"),
        "aspect": cfg.get_aspect_ratio()["id"],
        "rect": det_rect,
        "regions": regions,
    })

    try:
        from win32gui import GetWindowText, GetForegroundWindow
        has_win32 = True
    except ImportError:
        has_win32 = False

    stop_event = threading.Event()
    reset_event = threading.Event()
    # Listen for commands on stdin in a background thread
    def stdin_listener():
        for line in sys.stdin:
            cmd = line.strip()
            if cmd == "reset":
                reset_event.set()
            elif cmd.startswith("{"):
                try:
                    msg = json.loads(cmd)
                    if msg.get("cmd") == "set_threshold":
                        name = msg["name"]
                        value = float(msg["value"])
                        if name in cfg.detectables:
                            cfg.detectables[name][msg.get("field", "threshold")] = value
                            emit({"type": "info", "message": f"Threshold {name} -> {value}"})
                except (json.JSONDecodeError, KeyError, ValueError):
                    pass

        stop_event.set()

    threading.Thread(target=stdin_listener, daemon=True).start()

    while not stop_event.is_set():
        try:
            if reset_event.is_set():
                reset_event.clear()
                vision.set_score(0)
                emit({"type": "info", "message": "Score reset to 0"})
            updated = vision.update()
        except Exception as e:
            emit({"type": "error", "message": str(e)})
            stop_event.wait(0.5)
            continue

        if not updated:
            stop_event.wait(max(0.001, vision.min_update_period - (time.time() - vision.last_update)))
            continue

        # Check if Overwatch is focused
        ow_focused = True
        if has_win32:
            try:
                ow_focused = GetWindowText(GetForegroundWindow()) == "Overwatch"
            except:
                pass

        score = vision.get_score()

        # Collect detections
        detections = {}
        for name, ds in vision.get_det_state().items():
            if ds["count"] > 0 and name != "KillcamOrPOTG" and cfg.detectables.get(name, {}).get("type") != 7:
                detections[name] = ds["count"]

        # Collect which regions had matches
        matched_regions = []
        for rname, rs in vision.get_region_state().items():
            if rs["matches"]:
                matched_regions.append(rname)

        # Include all confidence values for debug panel
        confidence = {}
        for name, val in vision.debug_confidence.items():
            confidence[name] = val

        emit({
            "type": "frame",
            "score": round(score, 1),
            "ping": round(vision.detection_ping * 1000, 1),
            "detections": detections,
            "matchedRegions": matched_regions,
            "confidence": confidence,
            "details": vision.match_details,
            "templateErrors": vision.template_errors,
            "owFocused": ow_focused,
            "menuPaused": vision.menu_paused,
            "menuResumeSeconds": vision._menu_gate.remaining(time.monotonic()) if vision.menu_paused else 0,
        })


def emit(obj):
    """Write a JSON line to stdout for Electron to read."""
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        if "--analyze" in sys.argv:
            from evaluate import analyze
            emit(analyze(json.load(sys.stdin)))
        else:
            main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        emit({"type": "error", "message": str(e)})
