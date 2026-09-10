import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, Mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config
from detection_stability import DetectionStability
from vision import Vision


class StabilityTests(unittest.TestCase):
    def test_confirmation_and_release_at_200ms(self):
        p = DetectionStability()
        results = [p.update(('zone', 'heal'), hit, now)
                   for hit, now in [(True, 1), (True, 1.1), (False, 1.2), (False, 1.3)]]
        self.assertEqual(results, [False, True, True, False])

    def test_single_frame_spikes_never_activate(self):
        p = DetectionStability()
        for i in range(12):
            self.assertFalse(p.update(('zone', 'heal'), i % 2 == 0, i / 10))

    def test_recovery_during_release_and_pause_reset(self):
        p = DetectionStability()
        for hit, now in [(True, 1), (True, 1.1), (False, 1.2), (True, 1.25)]:
            active = p.update(('zone', 'heal'), hit, now)
        self.assertTrue(active)
        self.assertFalse(p.update(('zone', 'heal'), True, 2))

    def test_events_and_regions_have_independent_confirmation(self):
        p = DetectionStability()
        self.assertFalse(p.update(('one', 'heal'), True, 1))
        self.assertFalse(p.update(('two', 'heal'), True, 1.1))
        self.assertFalse(p.update(('one', 'boost'), True, 1.1))
        self.assertTrue(p.update(('one', 'heal'), True, 1.1))

    def make_vision(self, events=('Heal', 'Boost')):
        cfg = Config('unused-test-config.json')
        cfg.detectables = {n: {'filename':'test.png', 'region':'Zone', 'points':50,
                               'type':0, 'threshold':.8} for n in events}
        with patch('vision.mss.mss', return_value=object()), patch.object(Vision, '_detect_resolution', return_value=False):
            v = Vision(cfg)
        v._frame = np.zeros((30, 40, 3), np.uint8)
        v._region_state = {'Zone': {'scaled': {'x':0,'y':0,'w':40,'h':30}, 'matches':[], 'max_matches':1}}
        v._det_state = {n: {'template':np.zeros((8,8,3), np.uint8),'count':0} for n in events}
        return v

    def scan(self, v, scores, now, duplicate=False):
        v._matched_keys.clear()
        v._region_state['Zone']['matches'] = []
        for state in v._det_state.values(): state['count'] = 0
        with patch('vision.time.monotonic', return_value=now), patch('vision.cv.matchTemplate',
                side_effect=[np.array([[s]], np.float32) for s in scores]) as match:
            v._match_region('Zone', list(v.config.detectables))
            if duplicate: v._match_region('Zone', list(v.config.detectables))
            self.assertEqual(match.call_count, len(scores))
        return v._region_state['Zone']['matches']

    def test_duplicate_scan_does_not_confirm_twice(self):
        v = self.make_vision(('Heal',))
        self.assertEqual(self.scan(v, [.95], 1, True), [])
        self.assertEqual(self.scan(v, [.95], 1.1, True), ['Heal'])
        self.assertEqual(v._det_state['Heal']['count'], 1)

    def test_release_keeps_momentary_output_then_expires(self):
        v = self.make_vision(('Heal',))
        self.assertEqual(self.scan(v, [.95], 1), [])
        self.assertEqual(self.scan(v, [.95], 1.1), ['Heal'])
        self.assertEqual(self.scan(v, [.2], 1.2), ['Heal'])
        self.assertEqual(self.scan(v, [.2], 1.3), [])

    def test_capacity_does_not_starve_another_event(self):
        v = self.make_vision()
        self.scan(v, [.95,.1], 1)
        self.assertEqual(self.scan(v, [.95,.9], 1.1), ['Heal'])
        self.assertEqual(self.scan(v, [.1,.9], 1.2), ['Boost'])

    def test_candidate_wakes_idle_zone_for_confirmation(self):
        v = self.make_vision(('Heal',))
        v._frame_count = 1
        self.scan(v, [.95], 1)
        self.assertTrue(v._should_check_zone('Zone'))

    def test_polling_remains_capped_at_ten_per_second(self):
        v = self.make_vision(('Heal',))
        with patch.object(v, '_detect_resolution', return_value=False), patch.object(v, '_update_detections') as update:
            for now in np.arange(100, 101, .001):
                with patch('vision.time.time', return_value=float(now)): v.update()
        self.assertLessEqual(update.call_count, 10)
        self.assertGreaterEqual(update.call_count, 9)

    def test_worker_stops_when_parent_stdin_closes(self):
        path = Path(__file__).resolve().parents[1] / 'electron_test/src/vision-worker.py'
        spec = importlib.util.spec_from_file_location('stability_worker_test', path)
        worker = importlib.util.module_from_spec(spec); spec.loader.exec_module(worker)
        fake = Mock()
        fake.get_det_state.return_value = {}
        fake.get_region_state.return_value = {}
        fake.get_detection_rect.return_value = {}
        fake.update.return_value = False
        fake.min_update_period = .1
        fake.last_update = 0
        with patch.object(worker, 'Vision', return_value=fake), patch.object(worker, 'emit'), \
             patch.object(sys, 'argv', ['vision-worker', 'unused-test-config.json']), \
             patch.object(sys, 'stdin', io.StringIO('')):
            worker.main()


if __name__ == '__main__': unittest.main()
