"""
App configuration.

Defaults are defined here. User settings are saved to / loaded from config.json.
Regions, filenames, and thresholds are internal — only user-tweakable fields
(points, type, decay, monitor, lovense_ip, etc.) are persisted.
"""

import json
import os
from copy import deepcopy

CONFIG_FILE = "config.json"

# ── Aspect ratios ────────────────────────────────────────────────────────────

ASPECT_RATIOS = {
    0: {"id": "16:9",  "sample_w": 1920, "sample_h": 1080},
    1: {"id": "21:9",  "sample_w": 2560, "sample_h": 1080},
    2: {"id": "16:10", "sample_w": 1680, "sample_h": 1050, "template_scaling": 1680 / 1920},
}

# ── Screen regions (per resolution) ─────────────────────────────────────────
# These define where on screen to look for each detection type.
# Not user-configurable — tied to Overwatch UI layout.

REGIONS = {
    "Menu Watcher": {'1920x1080': {'x': 17, 'y': 27, 'w': 96, 'h': 38}},
    "Health Watch": {'1920x1080': {'x': 166, 'y': 931, 'w': 256, 'h': 18}},
    "Ultimate": {"1920x1080": {"x": 936, "y": 905, "w": 50, "h": 49}},
    "Popup1": {
        "1920x1080": {"x": 750, "y": 750, "w": 210, "h": 30},
        "2560x1080": {"x": 1070, "y": 750, "w": 210, "h": 30},
        "1680x1050": {"x": 655, "y": 656, "w": 185, "h": 27},
    },
    # Note: user_regions from config.json will merge into/override these
    "Popup2": {
        "1920x1080": {"x": 750, "y": 785, "w": 210, "h": 30},
        "2560x1080": {"x": 1070, "y": 785, "w": 210, "h": 30},
        "1680x1050": {"x": 655, "y": 686, "w": 185, "h": 27},
    },
    "Popup3": {
        "1920x1080": {"x": 750, "y": 820, "w": 210, "h": 30},
        "2560x1080": {"x": 1070, "y": 820, "w": 210, "h": 30},
        "1680x1050": {"x": 655, "y": 716, "w": 185, "h": 27},
    },
    "Give Harmony Orb": {
        "1920x1080": {"x": 725, "y": 945, "w": 50, "h": 50},
        "2560x1080": {"x": 1045, "y": 945, "w": 50, "h": 50},
        "1680x1050": {"x": 635, "y": 932, "w": 45, "h": 45},
    },
    "Give Discord Orb": {
        "1920x1080": {"x": 1145, "y": 945, "w": 50, "h": 50},
        "2560x1080": {"x": 1465, "y": 945, "w": 50, "h": 50},
        "1680x1050": {"x": 1000, "y": 932, "w": 45, "h": 45},
    },
    "Give Healing": {
        "1920x1080": {"x": 790, "y": 655, "w": 68, "h": 68},
        "2560x1080": {"x": 1110, "y": 655, "w": 68, "h": 68},
        "1680x1050": {"x": 690, "y": 625, "w": 60, "h": 60},
    },
    "Give Boost": {
        "1920x1080": {"x": 1062, "y": 655, "w": 68, "h": 68},
        "2560x1080": {"x": 1382, "y": 655, "w": 68, "h": 68},
        "1680x1050": {"x": 930, "y": 625, "w": 60, "h": 60},
    },
    "Receive Heal": {
        "MaxMatches": 2,
        "1920x1080": {"x": 440, "y": 740, "w": 210, "h": 100},
        "2560x1080": {"x": 440, "y": 740, "w": 210, "h": 100},
        "1680x1050": {"x": 385, "y": 750, "w": 200, "h": 90},
    },
    "Receive Status Effect": {
        "MaxMatches": 3,
        "1920x1080": {"x": 160, "y": 840, "w": 140, "h": 55},
        "2560x1080": {"x": 160, "y": 840, "w": 140, "h": 55},
        "1680x1050": {"x": 144, "y": 848, "w": 120, "h": 36},
    },
    "Prompt": {
        "1920x1080": {"x": 810, "y": 228, "w": 300, "h": 58},
        "2560x1080": {"x": 1130, "y": 228, "w": 300, "h": 58},
        "1680x1050": {"x": 707, "y": 200, "w": 265, "h": 52},
    },
    "Overtime": {
        "1920x1080": {"x": 900, "y": 35, "w": 123, "h": 39},
    },
    "POTG": {
        "1920x1080": {"x": 210, "y": 28, "w": 94, "h": 50},
        "2560x1080": {"x": 210, "y": 28, "w": 94, "h": 50},
    },
    "Kill Cam": {
        "1920x1080": {"x": 1628, "y": 40, "w": 158, "h": 47},
        "2560x1080": {"x": 2268, "y": 40, "w": 158, "h": 47},
    },
    "Anti Healing": {
        "1920x1080": {"x": 164, "y": 896, "w": 51, "h": 30},
    },
}

# ── Detectables ──────────────────────────────────────────────────────────────
# Each entry defines a game event to detect.
# Internal fields (filename, threshold, region, filter) are not saved.
# User fields (points, type, duration) are saved to config.json.
#
# Types:
#   0 = Momentary   — points added only while actively detected
#   1 = Per-second   — accumulates points/sec while detected
#   2 = Over duration — adds (points/duration) per second for 'duration' seconds

DETECTABLES = {
    "HUD Present": {'filename': 'hud_health_reference.png', 'template_crop': [17, 10, 33, 29], 'template_height': 1440, 'region': 'Anti Healing', 'threshold': 0.9, 'match_mode': 'legacy', 'points': 0, 'type': 8, 'hud_alternate': 'Anti-Healing'},
    "Menu Watcher": {'filename': 'menu_home.png', 'menu_resume_delays': {'menu_back.png': 0}, 'examples': ['menu_back.png', 'menu_home_gray.png', 'menu_back_arrow.png'], 'template_height': 1440, 'match_mode': 'legacy', 'threshold': 0.9, 'region': 'Menu Watcher', 'points': 0, 'type': 7},
    "Overshield": {'filename': 'overshield_reference.png', 'hud_guard': 'HUD Present', 'region': 'Health Watch', 'points': 100, 'type': 6, 'full_coverage': 0.6954947707160096},
    "Give Lucio Heal": {"filename": "lucio_heal.png", "template_height": 1440, "threshold": 0.9, "region": "Give Healing", "points": 10, "type": 0},
    "Give Lucio Boost": {"filename": "lucio_boost.png", "template_height": 1440, "threshold": 0.9, "region": "Give Boost", "points": 10, "type": 0},
    "Ultimate": {"filename": "ultimate_zero.png", "template_height": 1440, "threshold": 0.95, "region": "Ultimate", "points": 0, "type": 5, "duration": 8, "cooldown": 20, "confirm_frames": 2, "release_ms": 200},
    # Killcam / Play of the Game (no points, used to suppress scoring)
    "KillcamOrPOTG": {
        "filename": "play_of_the_game.png",
        "threshold": 0.7,
        "region": "POTG",
    },
    "KillCam": {
        "filename": "respawning.png",
        "threshold": 0.7,
        "region": "Kill Cam",
    },
    # Kill feed popups
    "Elimination": {
        "filename": "elimination.png", "threshold": 0.8,
        "region": "Popup",
        "points": 25, "type": 2, "duration": 2.5,
    },
    "Assist": {
        "filename": "assist.png", "threshold": 0.8,
        "region": "Popup",
        "points": 20, "type": 2, "duration": 2.5,
    },
    "Saved": {
        "filename": "saved.png", "threshold": 0.8,
        "region": "Popup",
        "points": 30, "type": 2, "duration": 2.5,
    },
    "Died": {
        "filename": "died - Copy.png", "threshold": 0.8,
        "region": "Popup",
        "points": 0, "type": 3, "duration": 8,
    },
    # Center-screen CC prompts
    "Detected":     {"filename": "prompt_detected.png",  "threshold": 0.5, "region": "Prompt", "filter": "prompt", "points": 100, "type": 0},
    "Life Gripped":  {"filename": "prompt_gripped.png",   "threshold": 0.5, "region": "Prompt", "filter": "prompt", "points": 100, "type": 0},
    "Hacked":        {"filename": "prompt_hacked.png",    "threshold": 0.5, "region": "Prompt", "filter": "prompt", "points": 100, "type": 0},
    "Hindered":      {"filename": "prompt_hindered.png",  "threshold": 0.5, "region": "Prompt", "filter": "prompt", "points": 100, "type": 0},
    "Reviving":      {"filename": "prompt_reviving.png",  "threshold": 0.5, "region": "Prompt", "filter": "prompt", "points": 100, "type": 0},
    "Pinned":        {"filename": "prompt_pinned.png",    "threshold": 0.5, "region": "Prompt", "filter": "prompt", "points": 100, "type": 0},
    "Revealed":      {"filename": "prompt_revealed.png",  "threshold": 0.5, "region": "Prompt", "filter": "prompt", "points": 100, "type": 0},
    "Sleep":         {"filename": "prompt_sleep.png",     "threshold": 0.5, "region": "Prompt", "filter": "prompt", "points": 100, "type": 0},
    "Stuck":         {"filename": "prompt_stuck.png",     "threshold": 0.5, "region": "Prompt", "filter": "prompt", "points": 100, "type": 0},
    "Stunned":       {"filename": "prompt_stunned.png",   "threshold": 0.5, "region": "Prompt", "filter": "prompt", "points": 100, "type": 0},
    "Trapped":       {"filename": "prompt_trapped.png",   "threshold": 0.5, "region": "Prompt", "filter": "prompt", "points": 100, "type": 0},
    "Grappled":      {"filename": "prompt_grappled.png", "threshold": 0.5, "region": "Prompt", "filter": "prompt", "points": 10,  "type": 0},
    # Received buffs/debuffs (left side HUD) — edge filter for robustness against UI changes
    "Receive Zen Heal":     {"filename": "receive_zen_heal.png", "match_mode": "masked", "v2_threshold": 0.85, "template_height": 1080,    "threshold": 0.8, "region": "Receive Heal",          "points": 10,  "type": 0},
    "Receive Mercy Heal":   {"filename": "receive_mercy_heal.png",  "threshold": 0.8, "region": "Receive Heal",          "points": 15,  "type": 0},
    "Receive Mercy Boost":  {"filename": "receive_mercy_boost.png", "threshold": 0.8, "region": "Receive Heal",          "points": 25,  "type": 0},
    "Receive Hack":         {"filename": "receive_hack_icon.png",   "threshold": 0.8, "region": "Receive Status Effect", "points": 100, "type": 0},
    "Receive Discord Orb":  {"filename": "receive_discord.png",     "threshold": 0.8, "region": "Receive Status Effect", "points": -20, "type": 1},
    "Receive Anti-Heal":    {"filename": "receive_purple_pot.png",  "threshold": 0.8, "region": "Receive Status Effect", "points": -50, "type": 0},
    "Receive Heal Boost":   {"filename": "receive_yellow_pot.png",  "threshold": 0.8, "region": "Receive Status Effect", "points": 20,  "type": 0},
    "Receive Immortality":  {"filename": "receive_immortality.png", "threshold": 0.8, "region": "Receive Status Effect", "points": 20,  "type": 0},
    # Hero-specific (playing as that hero) — NO filter, match raw frame
    "Give Mercy Heal":   {"filename": "apply_mercy_heal.png",  "threshold": 0.7, "region": "Give Healing",   "points": 10, "type": 0},
    "Give Mercy Boost":  {"filename": "apply_mercy_boost.png", "threshold": 0.7, "region": "Give Boost",  "points": 10, "type": 0},
    "Give Harmony Orb":  {"filename": "apply_harmony.png",     "threshold": 0.9, "region": "Give Harmony Orb",  "points": 10, "type": 0},
    "Give Discord Orb":  {"filename": "apply_discord.png",     "threshold": 0.9, "region": "Give Discord Orb",  "points": 20, "type": 0},
    # Hero abilities in kill feed — uses popup filter like Elimination
    "Earth Shatter":     {"filename": "earthshatter.png",     "threshold": 0.7, "region": "Popup", "points": 50, "type": 0},
    "Sleep Dart":        {"filename": "sleep_dart.png",      "threshold": 0.7, "region": "Popup", "points": 50, "type": 0},
    "Throwing Big Rock": {"filename": "throw_big_rock.png",  "threshold": 0.8, "region": "Popup", "points": 15, "type": 2},
    "Deployed Pylon":    {"filename": "deployed_pylon.png",  "threshold": 0.7, "region": "Constructs", "points": 30, "type": 0},
    "Deployed Tree":     {"filename": "deployed_tree.png",   "threshold": 0.7, "region": "Constructs", "points": 30, "type": 0},
    # Received heals
    "Receive Wuyang Heal": {"filename": "receive_wuyang_healing.png", "threshold": 0.8, "region": "Receive Heal", "points": 10, "type": 0},
    "Receive Wuyang Initial": {"filename": "receive_wuyang_initial_healing.png", "threshold": 0.8, "region": "Popup", "points": 20, "type": 0},
    # Anti-healing (separate zone from Receive Status Effect)
    "Anti-Healing":      {"filename": "anti-healing.png",    "threshold": 0.8, "region": "Anti Healing", "points": -50, "type": 0},
    # Game state
    "Overtime":          {"filename": "overtime.png",        "threshold": 0.3, "region": "Overtime", "points": 30, "type": 0},
}

# Fields that get saved to config.json (user-tweakable)
_SAVE_FIELDS = {"template_crop", "hud_guard", "hud_alternate", "menu_resume_delays", "full_coverage", "cooldown", "template_height", "points", "type", "duration", "threshold", "filename", "region", "filter", "match_mode", "v2_threshold", "examples", "scale_tolerance", "confirm_frames", "release_ms", "edge_tolerance"}

# ── Default config ───────────────────────────────────────────────────────────

DEFAULT_SETTINGS = {
    "max_intensity": 100,
    "monitor_number": 1,
    "aspect_ratio_index": 0,
    "show_overlay_mode": 0,
    "show_regions_mode": 0,
    "ignore_spectate": True,
    "ignore_redundant_assists": True,
    "decay": 100,
    "lovense_ip": "",
    "panic_key": "",
    "mute_key": "",
    "disabled_zones": [],
    "multi_actuator": {
        "Nora":    {"enabled": True, "threshold": 25, "max_level": 20},
        "Max":     {"enabled": True, "threshold": 25, "max_level": 20},
        "Edge":    {"enabled": True, "threshold": 25, "max_level": 20},
        "Gravity": {"enabled": True, "threshold": 25, "max_level": 20},
        "Dolce":   {"enabled": True, "threshold": 25, "max_level": 20},
        "Gemini":  {"enabled": True, "threshold": 25, "max_level": 20},
        "Vulse":   {"enabled": True, "threshold": 25, "max_level": 20},
    },
}



SHARED_ZONES = {"Give Mercy Heal": "Give Healing", "Give Mercy Boost": "Give Boost"}


def migrate_shared_zones(data):
    regions = data.get("user_regions", {})
    for old, new in SHARED_ZONES.items():
        if old in regions:
            regions[new] = {**regions.pop(old), **regions.get(new, {})}
    for det in data.get("detectables", {}).values():
        if det.get("region") in SHARED_ZONES:
            det["region"] = SHARED_ZONES[det["region"]]
    if "disabled_zones" in data:
        data["disabled_zones"] = list(dict.fromkeys(SHARED_ZONES.get(z, z) for z in data["disabled_zones"]))


class Config:
    def __init__(self, path=None):
        self.path = path or CONFIG_FILE
        self.settings = deepcopy(DEFAULT_SETTINGS)
        self.detectables = deepcopy(DETECTABLES)
        self.regions = deepcopy(REGIONS)

    def load(self):
        """Load user settings from config.json, merging on top of defaults."""
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        migrate_shared_zones(data)

        # Merge top-level settings
        for key, value in data.items():
            if key == "detectables":
                for det_name, det_fields in value.items():
                    if det_name == "Capture Progress":
                        continue  # Retired after the in-game UI changed.
                    if det_name in self.detectables:
                        for field, val in det_fields.items():
                            self.detectables[det_name][field] = val
                    else:
                        # Custom user-created detectable
                        self.detectables[det_name] = det_fields
            elif key == "user_regions":
                # Merge user regions into REGIONS — add/update resolution keys, don't replace
                for region_name, region_data in value.items():
                    if region_name == "Capture Progress":
                        continue
                    if region_name in self.regions:
                        self.regions[region_name].update(region_data)
                    else:
                        self.regions[region_name] = region_data
            elif key in self.settings:
                self.settings[key] = value

        # The September 10 rebuild accidentally persisted edge filtering for
        # the stock receive icons. The original v1.3 worker matched these raw.
        # Repair only those stock images; preserve custom images and thresholds.
        for name, default in DETECTABLES.items():
            det = self.detectables.get(name, {})
            if (name in ("Receive Zen Heal", "Receive Mercy Heal", "Receive Mercy Boost",
                         "Receive Hack", "Receive Discord Orb", "Receive Anti-Heal",
                         "Receive Heal Boost", "Receive Immortality")
                    and default.get("filter") is None
                    and det.get("filename") == default.get("filename")
                    and det.get("filter") == "edge"):
                det.pop("filter")

    def save(self):
        """Save user-tweakable settings to config.json."""
        try:
            with open(self.path, encoding="utf-8") as source:
                save_dict = json.load(source)
        except (OSError, ValueError):
            save_dict = {}
        migrate_shared_zones(save_dict)
        save_dict.get("user_regions", {}).pop("Capture Progress", None)
        save_dict.update(deepcopy(self.settings))
        save_dict["detectables"] = {}
        for name, det in self.detectables.items():
            user_fields = {k: v for k, v in det.items() if k in _SAVE_FIELDS}
            if user_fields:
                save_dict["detectables"][name] = user_fields

        with open(self.path, "w") as f:
            json.dump(save_dict, f, indent=4)

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value, save=True):
        self.settings[key] = value
        if save:
            self.save()

    def get_region(self, name):
        """Get a screen region dict for the current aspect ratio, fallback to 1920x1080."""
        region = self.regions.get(name)
        if not region:
            return None
        ar = ASPECT_RATIOS[self.settings["aspect_ratio_index"]]
        res_key = f"{ar['sample_w']}x{ar['sample_h']}"
        return region.get(res_key) or region.get("1920x1080")

    def get_aspect_ratio(self):
        return ASPECT_RATIOS[self.settings["aspect_ratio_index"]]
