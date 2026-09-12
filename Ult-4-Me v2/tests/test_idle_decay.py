from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from config import Config
from vision import Vision


class IdleDecayTests(unittest.TestCase):
    def make_vision(self, detectables=None):
        cfg = Config()
        cfg.settings['decay'] = 60
        cfg.detectables = detectables or {}
        with patch.object(Vision, '_detect_resolution', return_value=False):
            v = Vision(cfg, capture=object())
        v.score_over_time = 100
        v._last_score_addition = 100
        v._det_state = {name: {'count': 0} for name in cfg.detectables}
        return v

    def tick(self, v, now, counts=None, elapsed=.5, details=None):
        v.last_update = now - elapsed
        def detect():
            v.match_details.update(details or {})
            for name, count in (counts or {}).items():
                v._det_state[name]['count'] = count
        with patch.object(v, '_detect_resolution', return_value=False), \
             patch.object(v, '_update_detections', side_effect=detect), \
             patch('vision.time.time', return_value=now), \
             patch('vision.time.monotonic', return_value=now):
            self.assertTrue(v.update())

    def test_ramps_and_caps_actual_decay(self):
        for age, multiplier in [(0, 1), (3, 1), (4, 1.5), (5, 2), (6.5, 3), (8, 4), (60, 4)]:
            v = self.make_vision()
            self.tick(v, 100 + age)
            self.assertAlmostEqual(v.score_over_time, 100 - .5 * multiplier)

    def test_only_positive_accumulated_inputs_restart_timer(self):
        for kind in [1, 2]:
            v = self.make_vision({'event': {'type': kind, 'points': 10, 'duration': 1}})
            self.tick(v, 110, {'event': 1})
            self.assertEqual(v._last_score_addition, 110)
            self.assertAlmostEqual(v.score_over_time, 104.5)
            self.tick(v, 112)
            self.assertAlmostEqual(v.score_over_time, 104)
        for points in [-10, 0]:
            v = self.make_vision({'event': {'type': 1, 'points': points}})
            self.tick(v, 110, {'event': 1})
            self.assertEqual(v._last_score_addition, 100)

    def test_momentary_overshield_and_holds_are_not_decayed(self):
        v = self.make_vision({'heal': {'type': 0, 'points': 10},
                              'shield': {'type': 6, 'points': 100},
                              'hold': {'type': 4, 'points': 20, 'duration': 2}})
        self.tick(v, 110, {'heal': 1, 'shield': 1, 'hold': 1}, details={'shield': {'strength': .5}})
        self.assertEqual(v._last_score_addition, 100)
        self.assertEqual(v.score_over_time, 98)
        self.assertEqual(v.score_instant, 80)

    def test_reset_and_set_score_hold_restart_idle_period(self):
        v = self.make_vision({'set': {'type': 3, 'points': 50, 'duration': 2}})
        self.tick(v, 110, {'set': 1})
        self.tick(v, 111)
        self.assertEqual(v.score_over_time, 50)
        self.tick(v, 112.1)
        self.assertEqual(v.score_over_time, 49.5)
        v.set_score(100)
        self.tick(v, 130)
        self.assertEqual(v.score_over_time, 99.5)
        v._clear_gameplay_state()
        self.assertIsNone(v._last_score_addition)
        self.assertEqual(v.get_score(), 0)

    def test_zero_decay_and_zero_score_floor(self):
        v = self.make_vision()
        v.config.settings['decay'] = 0
        self.tick(v, 160)
        self.assertEqual(v.score_over_time, 100)
        v.config.settings['decay'] = 60
        v.score_over_time = 1
        self.tick(v, 161)
        self.assertEqual(v.score_over_time, 0)


if __name__ == '__main__':
    unittest.main()
