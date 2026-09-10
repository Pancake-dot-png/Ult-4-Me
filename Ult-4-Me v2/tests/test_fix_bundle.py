"""V1.3 fixes exercised through V2's own matcher and worker."""
import importlib.util
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import cv2 as cv
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
from config import Config
from detector import Presence, Match
from vision import Vision


class Screen:
    def __init__(self, height):
        self.monitors = [None, dict(left=0, top=0, width=height * 16 // 9, height=height)]
        self.image = np.full((height, height * 16 // 9, 4), 40, np.uint8)

    def grab(self, rect):
        x, y, right, bottom = rect
        return self.image[y:bottom, x:right].copy()


class FixBundleTests(unittest.TestCase):
    def test_stability_defaults_and_explicit_opt_out(self):
        p = Presence()
        self.assertEqual([p.update('heal', score, .9, now) for score, now in
                          [(.95, 1), (.95, 1.1), (.1, 1.2), (.1, 1.3)]],
                         [False, True, True, False])
        self.assertTrue(p.update('fast', .95, .9, 1, 1, 0))
        self.assertFalse(p.update('fast', .1, .9, 1.01, 1, 0))
        self.assertFalse(p.update('heal', .95, .9, 2))

    def test_fresh_match_wins_over_higher_confidence_held_match(self):
        cfg = Config('unused.json')
        cfg.detectables = {n: dict(region='Zone', points=10, threshold=t)
                           for n, t in [('Old', .95), ('New', .5)]}
        with patch.object(Vision, '_detect_resolution', return_value=False):
            v = Vision(cfg, capture=object())
        v._region_state = {'Zone': dict(scaled=dict(x=0,y=0,w=30,h=30), matches=[], max_matches=1)}
        v._frame = np.zeros((30,30,3), np.uint8)
        v._det_state = {n: {'examples':[Mock(mode='legacy')], 'count':0} for n in cfg.detectables}
        for now, scores, expected in [(1,[.99,.1],[]),(1.1,[.99,.6],['Old']),(1.2,[.9,.6],['New'])]:
            v._matched_keys.clear(); v._region_state['Zone']['matches'] = []
            with patch('vision.time.monotonic', return_value=now), patch('vision.match_examples',
                    side_effect=[Match(confidence=s, mode='legacy', filename='test.png') for s in scores]):
                v._match_region('Zone', list(cfg.detectables))
                v._match_region('Zone', list(cfg.detectables))
            self.assertEqual(v._region_state['Zone']['matches'], expected)

    def test_worker_stops_on_owner_disconnect(self):
        spec = importlib.util.spec_from_file_location('v2_worker_test', ROOT/'app/src/vision-worker.py')
        worker = importlib.util.module_from_spec(spec); spec.loader.exec_module(worker)
        fake = Mock(template_errors={})
        fake.get_det_state.return_value = {}
        fake.get_region_state.return_value = {}
        fake.get_detection_rect.return_value = {}
        fake.update.return_value = False
        fake.min_update_period = .1; fake.last_update = 0
        with patch.object(worker, 'Vision', return_value=fake), patch.object(worker, 'emit'), \
             patch.object(sys, 'argv', ['worker', 'unused.json']), patch.object(sys, 'stdin', io.StringIO('')):
            worker.main()

    def test_polling_capped_at_ten_scans_per_second(self):
        with patch.object(Vision, '_detect_resolution', return_value=False):
            v = Vision(Config('unused.json'), capture=object())
        with patch.object(v, '_update_detections') as detect, patch.object(v, '_detect_resolution', return_value=False):
            for now in np.arange(100,101,.001):
                with patch('vision.time.time', return_value=float(now)): v.update()
        self.assertLessEqual(detect.call_count, 10)
        self.assertGreaterEqual(detect.call_count, 9)

    def test_shipped_templates_through_v2_capture_and_confirmation(self):
        base = Path(os.environ.get('ULT_V2_TEST_PACKAGE', ROOT))
        for height in (1080,1440):
            config_path = base/'config.json'
            if not config_path.exists(): config_path = base/'release-settings.json'
            cfg = Config(config_path); cfg.load()
            screen = Screen(height)
            v = Vision(cfg, base/'templates', capture=screen)
            self.assertFalse(v.template_errors)
            for name, det in cfg.detectables.items():
                with self.subTest(height=height, event=name):
                    if name == 'KillcamOrPOTG' and det.get('region') == 'Anti Healing':
                        self.skipTest('POTG assignment retained at user request')
                    region = 'Popup1' if det.get('region') == 'Popup' else det.get('region')
                    self.assertIn(region, v._region_state)
                    ds = v._det_state[name]; ex = ds['examples'][0]
                    r = v._region_state[region]['scaled']; h,w = ex.image.shape[:2]
                    self.assertLessEqual(w,r['w']); self.assertLessEqual(h,r['h'])
                    if ex.mode == 'legacy':
                        raw = cv.imread(str(base/'templates'/det['filename']))
                        raw = cv.resize(raw,(w,h))
                    else:
                        raw = ex.image
                    screen.image[:] = 40
                    x,y = r['x']+(r['w']-w)//2,r['y']+(r['h']-h)//2
                    screen.image[y:y+h,x:x+w,:3] = raw
                    v._presence.state.clear(); v._zone_last_match.clear()
                    v._suppression_until = 0; v.last_update = 0
                    counts=[]
                    for frame in range(4):
                        now=100+frame*.11
                        with patch('vision.time.time',return_value=now), patch('vision.time.monotonic',return_value=now): v.update()
                        counts.append(ds['count'])
                    self.assertEqual(counts[0],0)
                    self.assertTrue(any(counts[1:]), (name,v.debug_confidence.get(name)))


if __name__ == '__main__': unittest.main()
