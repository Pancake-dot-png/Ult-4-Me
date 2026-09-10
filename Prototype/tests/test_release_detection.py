"""Exercise shipped templates through capture scheduling, matching and scoring."""
from pathlib import Path
import sys
import unittest
import tempfile
import json
from unittest.mock import patch

import cv2 as cv
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config
from vision import Vision

ROOT = Path(__file__).resolve().parents[2]
EVENTS = ('Receive Mercy Heal', 'Receive Mercy Boost', 'Receive Immortality')


class Screen:
    def __init__(self, height):
        width = height * 16 // 9
        self.monitors = [None, dict(left=0, top=0, width=width, height=height)]
        self.image = np.full((height, width, 4), 40, np.uint8)

    def grab(self, rect):
        left, top, right, bottom = rect
        return self.image[top:bottom, left:right].copy()


class ReleaseDetectionTests(unittest.TestCase):
    def test_all_shipped_events_with_competing_templates(self):
        """Use the release configuration and real image matching, with every event enabled."""
        for height in (1080, 1440):
            cfg = Config(ROOT / 'releases/v1.3-settings.json')
            cfg.load()
            screen = Screen(height)
            with patch('vision.mss.mss', return_value=screen):
                v = Vision(cfg, ROOT / 'templates')
            for name, det in cfg.detectables.items():
                with self.subTest(height=height, event=name):
                    # Explicitly retained by the user: POTG is assigned to a zone
                    # narrower than its image. Do not silently repair its settings.
                    if name == 'KillcamOrPOTG' and det.get('region') == 'Anti Healing':
                        self.skipTest('User retained the existing POTG/Anti Healing assignment')
                    region = 'Popup1' if det.get('region') == 'Popup' else det.get('region')
                    self.assertIn(name, v._det_state)
                    self.assertIn(region, v._region_state)
                    ds = v._det_state[name]
                    r = v._region_state[region]['scaled']
                    h, w = ds['template'].shape[:2]
                    self.assertLessEqual(w, r['w'])
                    self.assertLessEqual(h, r['h'])
                    raw = cv.resize(ds['original'], (w, h))
                    screen.image[:] = 40
                    x, y = r['x'] + (r['w'] - w) // 2, r['y'] + (r['h'] - h) // 2
                    screen.image[y:y+h, x:x+w, :3] = raw
                    # Each case starts cold, including idle-zone scheduling.
                    v._stability.states.clear()
                    v._zone_last_match.clear()
                    v._suppression_until = 0
                    v._frame_count = 0
                    v.last_update = 0
                    counts = []
                    for frame in range(12):
                        now = 100 + frame * .11
                        with patch('vision.time.time', return_value=now), patch('vision.time.monotonic', return_value=now):
                            self.assertTrue(v.update())
                        counts.append(ds['count'])
                    self.assertTrue(any(counts), (name, v.debug_confidence.get(name)))
                    self.assertFalse({n: d['count'] for n, d in v._det_state.items()
                                      if n != name and d['count']}, 'Another template matched this isolated icon')

    def test_saved_accidental_filter_repaired_without_changing_custom_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            path.write_text(json.dumps({'detectables': {
                'Receive Mercy Heal': {'filter': 'edge', 'threshold': .73, 'points': 52},
                'Receive Immortality': {'filename': 'custom.png', 'filter': 'edge'},
                'Receive Wuyang Heal': {'filter': 'edge'},
            }}))
            cfg = Config(path)
            cfg.load()
            self.assertNotIn('filter', cfg.detectables['Receive Mercy Heal'])
            self.assertEqual(cfg.detectables['Receive Mercy Heal']['threshold'], .73)
            self.assertEqual(cfg.detectables['Receive Mercy Heal']['points'], 52)
            self.assertEqual(cfg.detectables['Receive Immortality']['filter'], 'edge')
            self.assertEqual(cfg.detectables['Receive Wuyang Heal']['filter'], 'edge')

    def test_release_matching_with_overlay_settings_and_idle_capture(self):
        for height in (1080, 1440):
            for overlay in (0, 1, 2):
                with self.subTest(height=height, overlay=overlay):
                    cfg = Config(ROOT / 'releases/v1.3-settings.json')
                    cfg.load()
                    cfg.settings.update(show_overlay_mode=overlay, show_regions_mode=overlay)
                    screen = Screen(height)
                    with patch('vision.mss.mss', return_value=screen):
                        v = Vision(cfg, ROOT / 'templates')
                    for name in EVENTS:
                        # The previous shipped worker uses raw color at 0.8.
                        self.assertIsNone(cfg.detectables[name].get('filter'))
                        self.assertEqual(cfg.detectables[name]['threshold'], .8)
                        ds = v._det_state[name]
                        raw = cv.resize(ds['original'], (ds['template'].shape[1], ds['template'].shape[0]))
                        np.testing.assert_array_equal(ds['template'], raw)
                        r = v._region_state[cfg.detectables[name]['region']]['scaled']
                        x = r['x'] + (110 * height // 1080 if name.endswith('Boost') else 5)
                        y = r['y'] + 5
                        h, w = raw.shape[:2]
                        screen.image[y:y+h, x:x+w, :3] = raw
                    for frame in range(12):
                        now = 100 + frame * .11
                        with patch('vision.time.time', return_value=now), patch('vision.time.monotonic', return_value=now):
                            self.assertTrue(v.update())
                        if frame >= 2:
                            for name in EVENTS:
                                self.assertEqual(v._det_state[name]['count'], 1, (name, frame, v.debug_confidence))
                            self.assertGreaterEqual(v.get_score(), sum(cfg.detectables[n]['points'] for n in EVENTS))
                    # Release grace must expire on a blank screen, even after idle scheduling.
                    screen.image[:] = 40
                    for frame in range(12, 24):
                        now = 100 + frame * .11
                        with patch('vision.time.time', return_value=now), patch('vision.time.monotonic', return_value=now):
                            v.update()
                    self.assertTrue(all(v._det_state[n]['count'] == 0 for n in EVENTS))


if __name__ == '__main__':
    unittest.main()
