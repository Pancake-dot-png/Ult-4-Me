import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import cv2 as cv
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
from color_watch import ColorWatch, green_coverage
from config import Config
from vision import Vision
from test_fix_bundle import Screen


class ColorWatchTests(unittest.TestCase):
    def reference(self):
        # Exact rectangle bounded by the user's red outline in the 1440p crop.
        return cv.imread(str(ROOT / 'templates/overshield_reference.png'))[6:30,6:347]

    def test_recorded_maximum_at_both_resolutions(self):
        full = Config().detectables['Overshield']['full_coverage']
        for scale in (1, .75):
            raw = self.reference()
            raw = cv.resize(raw, (round(raw.shape[1]*scale),round(raw.shape[0]*scale)))
            for gain in (.65,1,1.15):
                w = ColorWatch()
                frame = np.clip(raw.astype(float)*gain,0,255).astype(np.uint8)
                self.assertEqual(w.update(frame, full, 100)[1], 0)
                self.assertEqual(w.update(frame, full, 100.1)[1], 0)
                strength = w.update(frame, full, 100.2)[1]
                self.assertGreater(strength,.94,(scale,gain,strength))
                self.assertLessEqual(strength,1)

    def test_green_fraction_scales_and_caps(self):
        for fraction, expected in [(0,0),(.1,.125),(.4,.5),(.8,1),(1,1)]:
            frame = np.full((22,102,3),200,np.uint8)
            frame[1:-1,1:1+round(fraction*100)] = (55,217,0)
            w=ColorWatch();w.update(frame,.8,100);w.update(frame,.8,100.1)
            self.assertAlmostEqual(w.update(frame,.8,100.2)[1],expected)

    def test_low_menu_noise_and_brief_green_flashes_never_activate(self):
        w = ColorWatch()
        frame = np.zeros((22,102,3),np.uint8)
        frame[1:-1,1:8] = (55,217,0)
        for i in range(100):
            self.assertEqual(w.update(frame,1,100+i*.1)[1],0)
        frame[1:-1,1:-1] = (55,217,0)
        self.assertEqual(w.update(frame,1,110)[1],0)
        self.assertEqual(w.update(frame,1,110.1)[1],0)
        frame[:]=0
        self.assertEqual(w.update(frame,1,110.2)[1],0)

    def test_separate_start_and_stop_levels(self):
        w = ColorWatch()
        def frame(fraction):
            image = np.zeros((22,102,3),np.uint8)
            image[1:-1,1:1+fraction] = (55,217,0)
            return image
        for t in (100,100.1,100.2):
            self.assertEqual(w.update(frame(10),1,t)[1],0)
        for t in (100.3,100.4,100.5): w.update(frame(20),1,t)
        self.assertGreater(w.update(frame(10),1,100.6)[1],0)
        self.assertEqual(w.update(frame(7),1,100.7)[1],0)
        for t in (100.8,100.9,101):
            self.assertEqual(w.update(frame(10),1,t)[1],0)

    def test_non_green_noise_floor_and_zero_release(self):
        w=ColorWatch()
        for bgr in [(200,200,200),(0,0,255),(0,255,255),(255,0,0),(0,0,0)]:
            frame=np.full((24,341,3),bgr,np.uint8)
            self.assertEqual(w.update(frame,.7,100)[1],0)
        frame=np.full((24,341,3),(55,217,0),np.uint8)
        w.update(frame,.7,100.1);w.update(frame,.7,100.2)
        self.assertEqual(w.update(frame,.7,100.3)[1],1)
        self.assertEqual(w.update(np.zeros_like(frame),.7,100.4)[1],0)
        frame[:]=0;frame[4,4]=(55,217,0)
        self.assertEqual(w.update(frame,.7,100.5)[1],0)

    def test_smoothing_and_pause_confirmation(self):
        frame=np.full((24,341,3),(55,217,0),np.uint8)
        w=ColorWatch();w.update(frame,1,100);w.update(frame,1,100.1);w.update(frame,1,100.2)
        frame[:,170:]=0
        value=w.update(frame,1,100.3)[1]
        self.assertGreater(value,.5);self.assertLess(value,1)
        self.assertEqual(w.update(frame,1,102)[1],0)

    def test_live_scoring_missing_capture_and_disabled_zone(self):
        cfg=Config();cfg.detectables={'Overshield':cfg.detectables['Overshield']}
        cfg.detectables['Overshield'].pop('hud_guard',None)
        cfg.settings.update(ignore_spectate=False,decay=0)
        screen=Screen(1440);v=Vision(cfg,ROOT/'templates',capture=screen)
        r=v._region_state['Health Watch']['scaled'];ref=self.reference()
        screen.image[r['y']:r['y']+r['h'],r['x']:r['x']+r['w'],:3]=ref
        for now,expected in [(100,0),(100.11,0),(100.22,100)]:
            with patch('vision.time.time',return_value=now),patch('vision.time.monotonic',return_value=now):v.update()
            self.assertAlmostEqual(v.get_score(),expected,places=5)
        with patch.object(v,'_crop_frame',return_value=None),patch('vision.time.time',return_value=100.33):v.update()
        self.assertEqual(v.get_score(),0)
        cfg.settings['disabled_zones']=['Health Watch'];v._setup_detectables()
        with patch('vision.time.time',return_value=100.44):v.update()
        self.assertEqual(v.get_score(),0)


if __name__ == '__main__':unittest.main()
