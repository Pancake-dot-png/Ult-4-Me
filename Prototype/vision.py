"""
Vision engine — screen capture, template matching, and scoring.

Captures Overwatch screen regions, runs template matching against
known game events, and calculates a score that drives device intensity.

Ported from Underwatch-Ultimate's computer_vision.py.
Core detection logic unchanged — refactored to use Config class
and keep mutable state out of config data.
"""

import os
import time
import mss
import numpy as np
import cv2 as cv

from config import Config, REGIONS, ASPECT_RATIOS
from detection_stability import DetectionStability


class Vision:
    def __init__(self, config: Config, templates_dir="templates"):
        self.config = config
        self.templates_dir = templates_dir

        # Timing
        self.last_update = 0
        self.min_update_period = 0.1  # 100ms = 10 FPS max
        self._stability = DetectionStability()
        self._matched_keys = set()
        self.detection_ping = 0       # smoothed processing time

        # Score
        self.score_over_time = 0
        self.score_instant = 0

        # Type 3 (set score) hold timer
        self._set_score_until = 0
        self._set_score_value = 0

        # Type 4 (hold) — tracks active holds: name -> { points, expires }
        self._holds = {}

        # Zone activity tracking — last match time per region
        self._zone_last_match = {}  # region_name -> timestamp
        self._frame_count = 0

        # Suppression hold — persists between scan gaps
        self._suppression_until = 0

        # Low-priority zones — checked every 3rd frame if idle
        self._low_priority_zones = {"Constructs", "Overtime", "Capture Progress", "POTG", "Kill Cam"}

        # Debug: stores confidence values per detectable
        self.debug_confidence = {}

        # Cached mss instance for screen capture
        self._sct = mss.mss()

        # Frame state (not in config)
        self._frame = None
        self._frame_offset = (0, 0)
        self._detection_rect = {}
        self._scale = 1

        # Per-region runtime state: scaled rects and match results
        self._region_state = {}   # region_name -> {"scaled": {x,y,w,h}, "matches": []}

        # Per-detectable runtime state: loaded templates and match counts
        self._det_state = {}      # det_name -> {"template": ndarray, "original": ndarray, "count": int}

        self.resolution_changed = False
        self._detect_resolution()

    # ── Public API ───────────────────────────────────────────────────────

    def update(self):
        """Run one detection frame. Returns True if a frame was processed."""
        t0 = time.time()
        if t0 - self.last_update < self.min_update_period:
            return False
        delta_time = min(1, t0 - self.last_update)
        self.last_update = t0

        self.resolution_changed = self._detect_resolution()
        self._frame_count += 1

        # Reset per-frame state
        self.score_instant = 0
        self.debug_confidence.clear()
        self._matched_keys.clear()
        for rs in self._region_state.values():
            rs["matches"] = []
        for ds in self._det_state.values():
            ds["count"] = 0

        self._update_detections()

        # Reduce assists by eliminations to avoid double-counting
        if self.config.get("ignore_redundant_assists"):
            elim_count = self._det_state.get("Elimination", {}).get("count", 0)
            assist_state = self._det_state.get("Assist")
            if assist_state:
                assist_state["count"] = max(0, assist_state["count"] - elim_count)

        # Calculate score — type 3 (set score) wins over everything
        set_score_active = False
        set_score_value = 0
        set_score_duration = 0
        frame_delta_points = 0
        for name, det in self.config.detectables.items():
            if name == "KillcamOrPOTG":
                continue
            if "points" not in det:
                continue

            count = self._det_state.get(name, {}).get("count", 0)
            points = det["points"]
            det_type = det.get("type", 0)

            if det_type == 3:
                if count > 0:
                    set_score_active = True
                    set_score_value = points
                    set_score_duration = det.get("duration", 0)
            elif det_type == 4:
                if count > 0:
                    self._holds[name] = {"points": points, "expires": time.time() + det.get("duration", 2)}
            elif det_type == 0:
                self.score_instant += count * points
            elif det_type == 1:
                frame_delta_points += count * points
            elif det_type == 2:
                duration = det.get("duration", 1)
                frame_delta_points += count * points / max(duration, 0.1)

        # Add hold points (type 4) — active holds contribute to instant score
        now = time.time()
        expired = [k for k, v in self._holds.items() if now >= v["expires"]]
        for k in expired:
            del self._holds[k]
        for hold in self._holds.values():
            self.score_instant += hold["points"]

        if set_score_active:
            self._set_score_value = set_score_value
            self._set_score_until = now + set_score_duration
            self.score_over_time = set_score_value
            self.score_instant = 0
        elif now < self._set_score_until:
            # Still in hold period
            self.score_over_time = self._set_score_value
            self.score_instant = 0
        else:
            self.score_over_time += delta_time * frame_delta_points
            self.score_over_time -= delta_time * self.config.get("decay", 100) / 60
            self.score_over_time = max(0, self.score_over_time)

        # Smooth detection timing
        t1 = time.time()
        a = 0.1
        self.detection_ping = (1 - a) * self.detection_ping + a * (t1 - t0)
        return True

    def get_score(self):
        return self.score_over_time + self.score_instant

    def set_score(self, value):
        self.score_over_time = value

    def get_detection_rect(self):
        return self._detection_rect

    def get_region_state(self):
        """Return region state for overlay rendering."""
        return self._region_state

    def get_det_state(self):
        """Return detectable state for overlay/debug."""
        return self._det_state

    # ── Resolution detection ─────────────────────────────────────────────

    def _detect_resolution(self):
        monitor_number = self.config.get("monitor_number", 1)
        monitor_rect = dict(self._sct.monitors[monitor_number])

        ar = self.config.get_aspect_ratio()
        sample_w = ar["sample_w"]
        sample_h = ar["sample_h"]

        game_rect = monitor_rect
        scale = 1
        monitor_ar = monitor_rect["width"] / monitor_rect["height"]

        if monitor_ar >= sample_w / sample_h:
            scale = monitor_rect["height"] / sample_h
            desired_w = int(sample_w * scale)
            black_bar = int((monitor_rect["width"] - desired_w) / 2)
            game_rect["width"] = desired_w
            game_rect["left"] += black_bar
        else:
            scale = monitor_rect["width"] / sample_w
            desired_h = int(sample_h * scale)
            black_bar = int((monitor_rect["height"] - desired_h) / 2)
            game_rect["height"] = desired_h
            game_rect["top"] += black_bar

        if self._detection_rect == game_rect:
            return False

        self._detection_rect = game_rect
        self._scale = scale
        self._setup_detectables()
        return True

    # ── Setup ────────────────────────────────────────────────────────────

    def _setup_detectables(self):
        """Load and scale all templates, compute scaled region rects."""
        self._stability = DetectionStability()
        ar = self.config.get_aspect_ratio()
        res_key = f"{ar['sample_w']}x{ar['sample_h']}"

        # Scale all regions — auto-offset when resolution key missing
        base_w = 1920
        base_h = 1080
        x_offset = (ar["sample_w"] - base_w) // 2  # horizontal shift for wider aspect ratios

        # Load disabled zones from config
        self._disabled_zones = set(self.config.get("disabled_zones") or [])

        self._region_state.clear()
        for region_name, region_data in REGIONS.items():
            if region_name in self._disabled_zones:
                continue
            rect = region_data.get(res_key)
            if rect is None:
                rect = region_data.get("1920x1080")
                if rect and x_offset != 0:
                    # Auto-offset: shift x by the aspect ratio difference
                    rect = dict(rect)
                    rect["x"] = rect["x"] + x_offset
                if rect is None:
                    rect = {"x": 0, "y": 0, "w": 100, "h": 100}
            self._region_state[region_name] = {
                "scaled": self._scale_rect(rect),
                "matches": [],
                "max_matches": region_data.get("MaxMatches", 1),
            }

        # Load and scale all templates, apply filters
        self._det_state.clear()
        for name, det in self.config.detectables.items():
            filename = det.get("filename")
            if not filename:
                continue

            path = os.path.join(os.path.abspath(self.templates_dir), filename)
            # Load with IMREAD_UNCHANGED to preserve alpha channel
            raw = cv.imread(path, cv.IMREAD_UNCHANGED)
            if raw is None:
                print(f"Warning: template not found: {path}")
                continue

            original = raw[:, :, :3] if raw.shape[2] == 4 else raw

            # Scale template to current resolution
            template_scaling = ar.get("template_scaling", 1)
            h = int(original.shape[0] * self._scale * template_scaling)
            w = int(original.shape[1] * self._scale * template_scaling)
            scaled = cv.resize(original, (w, h))

            # Apply filter to template
            filter_name = det.get("filter")
            if filter_name:
                filter_fn = self._get_filter(filter_name)
                if filter_fn:
                    scaled = filter_fn(scaled)

            self._det_state[name] = {
                "template": scaled,
                "original": original,
                "count": 0,
            }

    # ── Detection loop ───────────────────────────────────────────────────

    def _should_check_zone(self, zone_name):
        """Skip idle/low-priority zones on some frames to save time."""
        if self._stability.pending_in_region(zone_name):
            return True
        now = time.time()
        last_match = self._zone_last_match.get(zone_name, 0)
        idle_seconds = now - last_match

        # Low-priority zones: check every 3rd frame
        if zone_name in self._low_priority_zones:
            if idle_seconds > 5 and self._frame_count % 3 != 0:
                return False

        # All zones: if idle >10s, check every 2nd frame
        if idle_seconds > 10 and self._frame_count % 2 != 0:
            return False

        return True

    def _update_detections(self):
        # Filter zones to check this frame
        active_regions = [r for r in self._region_state if self._should_check_zone(r)]
        # Always include core zones, suppression zones checked every 3rd frame
        potg_region = self.config.detectables.get("KillcamOrPOTG", {}).get("region") or "KillcamOrPOTG"
        killcam_region = self.config.detectables.get("KillCam", {}).get("region") or None
        check_suppression = self._frame_count % 3 == 0
        # Always include Prompt and Popup1
        for r in ["Prompt", "Popup1"]:
            if r in self._region_state and r not in active_regions:
                active_regions.append(r)
        # Include suppression zones only on scan frames
        if check_suppression:
            for r in [potg_region, killcam_region]:
                if r and r in self._region_state and r not in active_regions:
                    active_regions.append(r)

        self._grab_frame(active_regions)

        # POTG/Killcam suppression
        potg_region = self.config.detectables.get("KillcamOrPOTG", {}).get("region") or "KillcamOrPOTG"
        killcam_region = self.config.detectables.get("KillCam", {}).get("region") or None

        if self.config.get("ignore_spectate"):
            now = time.time()

            # Check suppression zones every 3rd frame
            if check_suppression:
                if potg_region in self._region_state:
                    self._match_region(potg_region, ["KillcamOrPOTG"])
                if killcam_region and killcam_region in self._region_state and "KillCam" in self._det_state:
                    self._match_region(killcam_region, ["KillCam"])

                potg_active = self._det_state.get("KillcamOrPOTG", {}).get("count", 0) > 0
                killcam_active = self._det_state.get("KillCam", {}).get("count", 0) > 0

                if potg_active or killcam_active:
                    self._suppression_until = now + 2  # hold for 2s between scans

            # Suppression active — still check for Died (type 3) so its hold period activates
            if now < self._suppression_until:
                self.score_over_time = 0
                self.score_instant = 0
                # Check popup regions for type 3 (set score) detectables like Died
                type3_dets = [n for n, d in self.config.detectables.items()
                              if d.get("region") == "Popup" and d.get("type") == 3]
                if type3_dets:
                    self._match_region("Popup1", type3_dets)
                return

        # CC prompts
        prompt_dets = [n for n, d in self.config.detectables.items() if d.get("region") == "Prompt"]
        self._match_region("Prompt", prompt_dets)

        # Kill feed popups — cascade: only check 2 if 1 is active, 3 if 2 is active
        popup_dets = [n for n, d in self.config.detectables.items() if d.get("region") == "Popup"]
        now = time.time()
        popup_window = 4  # seconds kill feed entries stay visible

        self._match_region("Popup1", popup_dets)
        p1_active = len(self._region_state.get("Popup1", {}).get("matches", [])) > 0
        p1_recent = (now - self._zone_last_match.get("Popup1", 0)) < popup_window

        if p1_active or p1_recent:
            self._match_region("Popup2", popup_dets)
            p2_active = len(self._region_state.get("Popup2", {}).get("matches", [])) > 0
            p2_recent = (now - self._zone_last_match.get("Popup2", 0)) < popup_window

            if p2_active or p2_recent:
                self._match_region("Popup3", popup_dets)

        # Hero-specific (region name matches detectable name)
        for name, det in self.config.detectables.items():
            region = det.get("region") or ""
            if region.startswith("Give "):
                self._match_region(region, [name])

        # Received heals
        heal_dets = [n for n, d in self.config.detectables.items() if d.get("region") == "Receive Heal"]
        self._match_region("Receive Heal", heal_dets)

        # Received status effects
        status_dets = [n for n, d in self.config.detectables.items() if d.get("region") == "Receive Status Effect"]
        self._match_region("Receive Status Effect", status_dets)

        # Custom zones — anything not handled above
        handled_regions = {"KillcamOrPOTG", "POTG", "Kill Cam", "Prompt", "Popup", "Give Mercy Heal", "Give Mercy Boost",
                          "Give Harmony Orb", "Give Discord Orb", "Receive Heal", "Receive Status Effect"}
        for name, det in self.config.detectables.items():
            region = det.get("region") or ""
            if region and region not in handled_regions and region in self._region_state:
                self._match_region(region, [name])

    # ── Frame capture ────────────────────────────────────────────────────

    def _grab_frame(self, region_names):
        """Capture screen area that encompasses all named regions."""
        top = self._detection_rect["height"]
        left = self._detection_rect["width"]
        bottom = 0
        right = 0

        for name in region_names:
            rs = self._region_state.get(name)
            if not rs:
                continue
            rect = rs["scaled"]
            top = min(top, rect["y"])
            bottom = max(bottom, rect["y"] + rect["h"])
            left = min(left, rect["x"])
            right = max(right, rect["x"] + rect["w"])

        self._frame_offset = (top, left)

        abs_top = top + self._detection_rect["top"]
        abs_bottom = bottom + self._detection_rect["top"]
        abs_left = left + self._detection_rect["left"]
        abs_right = right + self._detection_rect["left"]

        self._frame = np.array(self._sct.grab((abs_left, abs_top, abs_right, abs_bottom)))[:, :, :3]

    def _crop_frame(self, rect):
        """Crop current frame to a region rect."""
        if self._frame is None:
            return None
        top = rect["y"] - self._frame_offset[0]
        bottom = rect["y"] + rect["h"] - self._frame_offset[0]
        left = rect["x"] - self._frame_offset[1]
        right = rect["x"] + rect["w"] - self._frame_offset[1]
        if min(top, left) < 0 or bottom > self._frame.shape[0] or right > self._frame.shape[1]:
            return None
        return self._frame[top:bottom, left:right].copy()

    # ── Template matching ────────────────────────────────────────────────

    def _match_region(self, region_name, det_names):
        """Match a list of detectables against a screen region."""
        rs = self._region_state.get(region_name)
        if not rs:
            return

        # Filter out zero-point detectables (except type 3/4 and suppression detectables)
        suppression = {"KillcamOrPOTG", "KillCam"}
        det_names = [n for n in det_names
                     if (self.config.detectables.get(n, {}).get("points", 0) != 0
                         or self.config.detectables.get(n, {}).get("type") in (3, 4)
                         or n in suppression)
                     and n in self._det_state]
        if not det_names:
            return

        crop = self._crop_frame(rs["scaled"])
        if crop is None or crop.size == 0:
            for name in det_names:
                self._stability.states.pop((region_name, name), None)
            return

        # Pre-compute filtered versions (one per unique filter)
        filtered_crops = {}
        for name in det_names:
            filter_name = self.config.detectables[name].get("filter")
            if filter_name and filter_name not in filtered_crops:
                filter_fn = self._get_filter(filter_name)
                if filter_fn:
                    filtered_crops[filter_name] = filter_fn(crop.copy())

        now = time.monotonic()
        candidates = []
        for name in det_names:
            key = (region_name, name)
            if key in self._matched_keys:
                continue
            self._matched_keys.add(key)

            ds = self._det_state[name]
            det = self.config.detectables[name]
            template = ds["template"]

            # Pick filtered or raw crop
            filter_name = det.get("filter")
            selected_crop = filtered_crops.get(filter_name, crop)

            # For prompt detectables, center-crop to template width to reduce false positives
            if det.get("region") == "Prompt":
                tw = template.shape[1]
                cw = selected_crop.shape[1]
                left = max(int((cw - tw) / 2) - 3, 0)
                right = min(left + tw + 6, cw)
                selected_crop = selected_crop[:, left:right, :]

            # Size check
            if template.shape[0] > selected_crop.shape[0] or template.shape[1] > selected_crop.shape[1]:
                self._stability.states.pop(key, None)
                continue

            # Match
            result = cv.matchTemplate(selected_crop, template, cv.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv.minMaxLoc(result)

            # Store confidence for debugging
            self.debug_confidence[name] = max(self.debug_confidence.get(name, 0), round(max_val, 3))

            matched = bool(np.isfinite(max_val) and max_val > det.get("threshold", 0.8))
            if self._stability.update(key, matched, now):
                candidates.append((matched, max_val, name))

        # Evaluate all candidates so release grace cannot block confirmation of
        # another event. Fresh matches take priority over held ones.
        available = max(0, rs["max_matches"] - len(rs["matches"]))
        for _, _, name in sorted(candidates, reverse=True)[:available]:
            self._det_state[name]["count"] += 1
            rs["matches"].append(name)
            self._zone_last_match[region_name] = time.time()

    # ── Image filters ────────────────────────────────────────────────────

    def _get_filter(self, name):
        filters = {
            "sobel": self._filter_sobel,
            "popup": self._filter_popup,
            "prompt": self._filter_prompt,
            "edge": self._filter_edge,
        }
        return filters.get(name)

    def _filter_sobel(self, frame):
        return cv.Sobel(frame, ddepth=cv.CV_8U, dx=0, dy=1, ksize=3)

    def _filter_popup(self, frame):
        gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        right = gray.shape[1]
        left = max(0, right - 50)
        mean = cv.mean(gray[:, left:right])
        sat = 50
        value = 130
        mask = cv.inRange(gray, int(mean[0] - sat), int(0.5 * mean[0] + value))
        frame[mask == 0] = [255, 255, 255]
        frame[mask == 255] = [0, 0, 0]
        return frame

    def _filter_prompt(self, frame):
        hsv = cv.cvtColor(frame, cv.COLOR_BGR2HSV)
        h, s, v = cv.split(hsv)
        mean_v = cv.mean(v)[0]
        t = 200
        if mean_v > t:
            v = s
        v = cv.Canny(v, t, 0)
        v = cv.dilate(v, np.ones((3, 3), np.uint8), iterations=1)
        return cv.merge((v, v, v))

    def _filter_edge(self, frame):
        """Edge detection filter — strips color, matches shapes only.
        Robust against OW2 color/lighting changes."""
        if frame is None or frame.size == 0:
            return frame
        gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        edges = cv.Canny(gray, 80, 160)
        edges = cv.dilate(edges, np.ones((2, 2), np.uint8), iterations=1)
        return cv.merge((edges, edges, edges))

    # ── Utilities ────────────────────────────────────────────────────────

    def _scale_rect(self, rect):
        return {
            "x": int(rect["x"] * self._scale),
            "y": int(rect["y"] * self._scale),
            "w": int(rect["w"] * self._scale),
            "h": int(rect["h"] * self._scale),
        }
