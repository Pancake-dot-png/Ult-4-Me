import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
from timed_bonus import TimedBonus
from config import Config
from detector import load_examples, Presence
from vision import Vision


class TimedBonusTests(unittest.TestCase):
    def test_score_reset_clears_instant_and_pending_bonuses(self):
        with patch.object(Vision, '_detect_resolution', return_value=False):
            v=Vision(Config(),capture=object())
        v.score_over_time=50;v.score_instant=75
        v._holds['hold']={'points':50,'expires':999}
        v._timed_bonuses['Ultimate']=TimedBonus()
        v._set_score_until=999;v._set_score_value=100
        v.set_score(0)
        self.assertEqual(v.get_score(),0)
        self.assertFalse(v._holds);self.assertFalse(v._timed_bonuses)
        self.assertEqual(v._set_score_until,0)

    def test_lingering_zero_never_extends_or_restarts(self):
        b = TimedBonus()
        for now, expected in [(100, 75), (107.9, 75), (108, 0), (121, 0), (160, 0)]:
            self.assertEqual(b.update(True, now, 75, 8, 20), expected)

    def test_cooldown_rejects_an_edge_without_delayed_activation(self):
        b = TimedBonus()
        b.update(True, 100, 75, 8, 20)
        b.update(False, 109, 75, 8, 20)
        self.assertEqual(b.update(True, 110, 75, 8, 20), 0)
        self.assertEqual(b.update(True, 121, 75, 8, 20), 0)
        b.update(False, 122, 75, 8, 20)
        self.assertEqual(b.update(True, 123, 75, 8, 20), 75)

    def test_missing_observations_do_not_rearm(self):
        b = TimedBonus()
        b.update(True, 100, 75, 8, 20)
        self.assertEqual(b.update(None, 105, 75, 8, 20), 75)
        self.assertEqual(b.update(None, 130, 75, 8, 20), 0)
        self.assertEqual(b.update(True, 131, 75, 8, 20), 0)

    def test_short_cooldown_does_not_stack_or_extend_bonus(self):
        b = TimedBonus()
        b.update(True, 100, 75, 8, 0)
        b.update(False, 101, 75, 8, 0)
        b.update(True, 102, 75, 8, 0)
        self.assertEqual(b.update(True, 108, 75, 8, 0), 0)

    def test_scoring_confirmation_and_release_integration(self):
        cfg = Config(); cfg.detectables = {
            'Ultimate': {'points': 75, 'type': 5, 'duration': 8, 'cooldown': 20},
            'Other': {'points': 10, 'type': 0}}
        cfg.settings['decay'] = 0
        with patch.object(Vision, '_detect_resolution', return_value=False):
            v = Vision(cfg, capture=object())
        v._det_state = {'Ultimate': {'count': 0}, 'Other': {'count': 0}}
        p = Presence()
        for now, score, expected in [(100, 1, 10), (100.11, 1, 85),
                                     (100.22, 0, 85), (100.33, 1, 85),
                                     (108.2, 1, 10), (130, 1, 10),
                                     (130.11, 0, 10), (130.33, 0, 10),
                                     (130.44, 1, 10), (130.55, 1, 85)]:
            def detect():
                active = p.update('Ultimate', score, .9, now, 2, 200)
                v.match_details['Ultimate'] = {'active': active, 'matched': score >= .9}
                v._det_state['Ultimate']['count'] = int(active)
                v._det_state['Other']['count'] = 1
            with patch.object(v, '_detect_resolution', return_value=False), \
                 patch.object(v, '_update_detections', side_effect=detect), \
                 patch('vision.time.time', return_value=now), \
                 patch('vision.time.monotonic', return_value=now):
                v.update()
            self.assertEqual(v.get_score(), expected, now)

    def test_template_scale_and_saved_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg = Config(str(Path(folder) / 'config.json'))
            cfg.detectables['Ultimate']['cooldown'] = 27
            cfg.save()
            restored = Config(cfg.path); restored.load()
            det = restored.detectables['Ultimate']
            self.assertEqual(det['cooldown'], 27)
            self.assertEqual(det['template_height'], 1440)
            import cv2 as cv
            raw = cv.imread(str(ROOT / 'templates/ultimate_zero.png'))
            for scale in (1, 4/3):
                ex = load_examples(ROOT / 'templates', det, scale)[0]
                self.assertEqual(ex.image.shape[:2], tuple(round(n * scale * .75) for n in raw.shape[:2]))


if __name__ == '__main__':
    unittest.main()
