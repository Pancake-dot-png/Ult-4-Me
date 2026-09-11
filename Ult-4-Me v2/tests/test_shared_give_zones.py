import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import cv2 as cv
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
from config import Config, migrate_shared_zones
from detector import load_examples, match_examples
from vision import Vision
from test_fix_bundle import Screen


class SharedGiveTests(unittest.TestCase):
    def test_zone_migration_preserves_tuning_and_disabled_state(self):
        data = {'user_regions': {'Give Mercy Heal': {'1920x1080': {'x': 123}},
                                 'Give Healing': {'2560x1080': {'x': 456}}},
                'detectables': {'Custom': {'region': 'Give Mercy Heal', 'points': 17}},
                'disabled_zones': ['Give Mercy Heal', 'Unrelated']}
        migrate_shared_zones(data)
        self.assertEqual(data['user_regions']['Give Healing'],
                         {'1920x1080': {'x': 123}, '2560x1080': {'x': 456}})
        self.assertEqual(data['detectables']['Custom'], {'region': 'Give Healing', 'points': 17})
        self.assertEqual(data['disabled_zones'], ['Give Healing', 'Unrelated'])
        before = json.dumps(data); migrate_shared_zones(data)
        self.assertEqual(json.dumps(data), before)

    def test_shared_zone_selects_correct_hero_without_stacking(self):
        for height in (1080, 1440):
            cfg = Config(str(ROOT / 'release-settings.json')); cfg.load()
            cfg.settings['ignore_spectate'] = False
            names = ['Give Mercy Heal', 'Give Mercy Boost', 'Give Lucio Heal', 'Give Lucio Boost']
            cfg.detectables = {n: cfg.detectables[n] for n in names}
            screen = Screen(height)
            v = Vision(cfg, ROOT / 'templates', capture=screen)
            for name in names:
                with self.subTest(height=height, event=name):
                    screen.image[:] = 55
                    det = cfg.detectables[name]
                    r = v._region_state[det['region']]['scaled']
                    ex = v._det_state[name]['examples'][0]
                    h, w = ex.image.shape[:2]
                    x, y = r['x'] + (r['w']-w)//2, r['y'] + (r['h']-h)//2
                    screen.image[y:y+h,x:x+w,:3] = ex.image
                    v._presence.state.clear(); v.last_update = 0
                    for now in (100, 100.11):
                        with patch('vision.time.time', return_value=now), patch('vision.time.monotonic', return_value=now):
                            v.update()
                    self.assertEqual([n for n, ds in v._det_state.items() if ds['count']], [name])

    def test_zero_accepts_positive_and_rejects_recorded_eight(self):
        cfg = Config(); det = cfg.detectables['Ultimate']
        for scale in (1, 4/3):
            examples = load_examples(ROOT / 'templates', det, scale)
            for filename, positive in [(ROOT/'templates/ultimate_zero.png', True),
                                       (ROOT/'tests/fixtures/ultimate-eight.png', False)]:
                raw = cv.imread(str(filename))
                raw = cv.resize(raw, (round(raw.shape[1]*scale*.75), round(raw.shape[0]*scale*.75)))
                for gain in (.8, 1, 1.15):
                    image = np.full((round(49*scale), round(50*scale), 3), 55, np.uint8)
                    h,w = raw.shape[:2]; y,x = (image.shape[0]-h)//2,(image.shape[1]-w)//2
                    image[y:y+h,x:x+w] = np.clip(raw.astype(float)*gain,0,255).astype(np.uint8)
                    result = match_examples(image, examples)
                    self.assertEqual(result.confidence >= det['threshold'], positive, (scale,gain,result.confidence))


if __name__ == '__main__': unittest.main()
