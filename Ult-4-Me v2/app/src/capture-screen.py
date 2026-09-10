"""Capture the game area and save as PNG."""
import sys, json, os
import mss
import numpy as np
from PIL import Image

config_path = sys.argv[1]
out_path = sys.argv[2]

cfg = json.load(open(config_path))
mon_num = cfg.get('monitor_number', 1)
ar_idx = cfg.get('aspect_ratio_index', 0)
ratios = {0: (1920, 1080), 1: (2560, 1080), 2: (1680, 1050)}
sw, sh = ratios.get(ar_idx, (1920, 1080))

with mss.mss() as sct:
    m = dict(sct.monitors[mon_num])

mar = m['width'] / m['height']
rect = dict(m)
if mar >= sw / sh:
    scale = m['height'] / sh
    dw = int(sw * scale)
    bb = int((m['width'] - dw) / 2)
    rect['width'] = dw
    rect['left'] += bb
else:
    scale = m['width'] / sw
    dh = int(sh * scale)
    bb = int((m['height'] - dh) / 2)
    rect['height'] = dh
    rect['top'] += bb

with mss.mss() as sct:
    frame = np.array(sct.grab(rect))[:, :, :3]

Image.fromarray(frame[:, :, ::-1]).save(out_path)
print(json.dumps({'w': rect['width'], 'h': rect['height']}))
