"""
Capture a specific detection region from the game screen and save it.
Use this to grab template images directly from the live HUD.

Usage:
    python capture_region.py "Receive Heal"
    python capture_region.py "Receive Status Effect"
    python capture_region.py "Popup1"

The captured region is saved to templates/capture_<region>.png at full resolution
AND a 1080p-base version at templates/capture_<region>_1080.png.

Steps:
  1. Open Overwatch, get into a game/practice range
  2. Trigger the event you want (e.g. have Mercy heal you)
  3. While the indicator is visible, run this script
  4. Crop the icon from the captured region image
  5. Save it as the template name (e.g. receive_mercy_heal.png)
"""
import sys
import os
import json
import time
import mss
import numpy as np
from PIL import Image

# Load config
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
cfg = json.load(open(config_path))

mon_num = cfg.get('monitor_number', 1)
ar_idx = cfg.get('aspect_ratio_index', 0)
ratios = {0: (1920, 1080), 1: (2560, 1080), 2: (1680, 1050)}
sw, sh = ratios.get(ar_idx, (1920, 1080))

# Regions from config (user_regions override defaults)
REGIONS = {
    "Popup1":  {"1920x1080": {"x": 750, "y": 750, "w": 210, "h": 30}},
    "Popup2":  {"1920x1080": {"x": 750, "y": 785, "w": 210, "h": 30}},
    "Popup3":  {"1920x1080": {"x": 750, "y": 820, "w": 210, "h": 30}},
    "Give Harmony Orb": {"1920x1080": {"x": 725, "y": 945, "w": 50, "h": 50}},
    "Give Discord Orb": {"1920x1080": {"x": 1145, "y": 945, "w": 50, "h": 50}},
    "Give Mercy Heal":  {"1920x1080": {"x": 790, "y": 655, "w": 68, "h": 68}},
    "Give Mercy Boost": {"1920x1080": {"x": 1062, "y": 655, "w": 68, "h": 68}},
    "Receive Heal":     {"1920x1080": {"x": 440, "y": 740, "w": 210, "h": 100}},
    "Receive Status Effect": {"1920x1080": {"x": 160, "y": 840, "w": 140, "h": 55}},
    "Prompt":           {"1920x1080": {"x": 810, "y": 228, "w": 300, "h": 58}},
    "Overtime":         {"1920x1080": {"x": 900, "y": 35, "w": 123, "h": 39}},
    "Constructs":       {"1920x1080": {"x": 445, "y": 910, "w": 174, "h": 74}},
    "Anti Healing":     {"1920x1080": {"x": 164, "y": 896, "w": 51, "h": 30}},
}

# Merge user regions from config
for name, data in cfg.get('user_regions', {}).items():
    if name in REGIONS:
        REGIONS[name].update(data)
    else:
        REGIONS[name] = data

region_name = sys.argv[1] if len(sys.argv) > 1 else "Receive Heal"

if region_name not in REGIONS:
    print(f"Unknown region: {region_name}")
    print(f"Available: {', '.join(sorted(REGIONS.keys()))}")
    sys.exit(1)

res_key = f"{sw}x{sh}"
region = REGIONS[region_name].get(res_key) or REGIONS[region_name].get("1920x1080")
if not region:
    print(f"No region data for {res_key}")
    sys.exit(1)

# Calculate game rect and scale
with mss.mss() as sct:
    m = dict(sct.monitors[mon_num])

mar = m['width'] / m['height']
game_rect = dict(m)
if mar >= sw / sh:
    scale = m['height'] / sh
    dw = int(sw * scale)
    bb = int((m['width'] - dw) / 2)
    game_rect['width'] = dw
    game_rect['left'] += bb
else:
    scale = m['width'] / sw
    dh = int(sh * scale)
    bb = int((m['height'] - dh) / 2)
    game_rect['height'] = dh
    game_rect['top'] += bb

# Scale region to current resolution
sx = int(region["x"] * scale)
sy = int(region["y"] * scale)
sw_r = int(region["w"] * scale)
sh_r = int(region["h"] * scale)

# Capture with some padding for context
pad = int(50 * scale)
abs_left = game_rect['left'] + max(0, sx - pad)
abs_top = game_rect['top'] + max(0, sy - pad)
abs_right = game_rect['left'] + min(game_rect['width'], sx + sw_r + pad)
abs_bottom = game_rect['top'] + min(game_rect['height'], sy + sh_r + pad)

print(f"Region: {region_name}")
print(f"Monitor: {m['width']}x{m['height']}, scale: {scale:.3f}")
print(f"Capturing area: {abs_right - abs_left}x{abs_bottom - abs_top} at ({abs_left},{abs_top})")
print()

# Countdown
for i in range(3, 0, -1):
    print(f"  Capturing in {i}...")
    time.sleep(1)

with mss.mss() as sct:
    frame = np.array(sct.grab((abs_left, abs_top, abs_right, abs_bottom)))[:, :, :3]

templates_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'templates')
safe_name = region_name.replace(' ', '_').lower()

# Save full-res capture
full_path = os.path.join(templates_dir, f'capture_{safe_name}.png')
Image.fromarray(frame[:, :, ::-1]).save(full_path)
print(f"Full-res saved: {full_path} ({frame.shape[1]}x{frame.shape[0]})")

# Save 1080p-base version (downscaled)
if scale > 1.05:
    h, w = frame.shape[:2]
    base = Image.fromarray(frame[:, :, ::-1]).resize((int(w / scale), int(h / scale)), Image.LANCZOS)
    base_path = os.path.join(templates_dir, f'capture_{safe_name}_1080.png')
    base.save(base_path)
    print(f"1080p base saved: {base_path} ({base.width}x{base.height})")

print()
print("Next steps:")
print(f"  1. Open capture_{safe_name}.png in an image editor")
print(f"  2. Crop just the icon you want")
print(f"  3. Save it as the template name (e.g. receive_mercy_heal.png)")
print(f"  4. If you cropped from the full-res version, downscale by {scale:.3f}x")
print(f"     Or crop from the _1080 version and it's already at base resolution")
