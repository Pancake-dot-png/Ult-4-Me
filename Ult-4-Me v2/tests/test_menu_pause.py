from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import cv2 as cv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
from config import Config
from menu_pause import MenuPause
from vision import Vision
from test_fix_bundle import Screen


class MenuPauseTests(unittest.TestCase):
    def test_back_resumes_on_first_clear_scan_but_not_unknown_capture(self):
        gate=MenuPause()
        self.assertTrue(gate.update(True,100,0))
        self.assertEqual(gate.remaining(100),0)
        self.assertTrue(gate.update(None,101))
        self.assertFalse(gate.update(False,102))

    def test_latest_matched_variant_sets_resume_delay(self):
        gate=MenuPause();gate.update(True,100,5)
        gate.update(True,101,0)
        self.assertFalse(gate.update(False,102))
        gate.update(True,103,0);gate.update(True,104,5)
        for now in (105,106,107,108,109):self.assertTrue(gate.update(False,now))
        self.assertFalse(gate.update(False,110))

    def test_switching_variants_keeps_one_shared_pause(self):
        cfg=Config(str(ROOT/'release-settings.json'));cfg.load()
        cfg.settings['ignore_spectate']=False
        screen=Screen(1440);v=Vision(cfg,ROOT/'templates',capture=screen)
        examples=v._det_state['Menu Watcher']['examples']
        r=v._region_state['Menu Watcher']['scaled']
        for step,idx in enumerate([0,1,2,3,1,0,3,2]):
            screen.image[:]=40;ex=examples[idx];h,w=ex.image.shape[:2]
            x,y=r['x']+(r['w']-w)//2,r['y']+(r['h']-h)//2
            screen.image[y:y+h,x:x+w,:3]=ex.image
            now=100+step
            with patch('vision.time.time',return_value=now),patch('vision.time.monotonic',return_value=now):v.update()
            self.assertTrue(v.menu_paused)
            self.assertIsNone(v._menu_gate.clear_since)
            self.assertEqual(v.get_score(),0)

    def test_five_uninterrupted_seconds_and_reappearance(self):
        gate = MenuPause()
        self.assertTrue(gate.update(True, 100))
        for now in (101,102,103): self.assertTrue(gate.update(False,now))
        self.assertTrue(gate.update(True,104))
        for now in (105,106,107,108,109): self.assertTrue(gate.update(False,now))
        self.assertFalse(gate.update(False,110))

    def test_unknown_and_missing_scans_restart_clear_timer(self):
        gate = MenuPause();gate.update(True,100)
        gate.update(False,101);gate.update(False,102)
        self.assertTrue(gate.update(None,103))
        gate.update(False,104)
        self.assertTrue(gate.update(False,110))
        for now in (111,112,113,114): self.assertTrue(gate.update(False,now))
        self.assertFalse(gate.update(False,115))

    def test_all_variants_pause_and_capture_only_menu(self):
        for height in (1080,1440):
            for example in range(1 + len(Config().detectables['Menu Watcher']['examples'])):
                with self.subTest(height=height,example=example):
                    cfg=Config(str(ROOT/'release-settings.json'));cfg.load()
                    cfg.settings['ignore_spectate']=False
                    screen=Screen(height);v=Vision(cfg,ROOT/'templates',capture=screen)
                    ds=v._det_state['Menu Watcher'];ex=ds['examples'][example]
                    r=v._region_state['Menu Watcher']['scaled'];h,w=ex.image.shape[:2]
                    self.assertLessEqual(h,r['h']);self.assertLessEqual(w,r['w'])
                    x,y=r['x']+(r['w']-w)//2,r['y']+(r['h']-h)//2
                    screen.image[y:y+h,x:x+w,:3]=ex.image
                    v.score_over_time=75;v._holds['old']={'points':50,'expires':999}
                    v._set_score_until=999;v._set_score_value=100
                    for now in (100,101):
                        with patch('vision.time.time',return_value=now),patch('vision.time.monotonic',return_value=now),patch.object(screen,'grab',wraps=screen.grab) as grab:
                            self.assertTrue(v.update())
                            if now==101:
                                self.assertEqual(grab.call_count,1)
                                rect=grab.call_args.args[0]
                                self.assertEqual((rect[2]-rect[0],rect[3]-rect[1]),(r['w'],r['h']))
                        self.assertTrue(v.menu_paused);self.assertEqual(v.get_score(),0)
                        self.assertFalse(v._holds);self.assertEqual(v._set_score_until,0)
                        self.assertEqual(v.min_update_period,1)
                    with patch('vision.time.time',return_value=101.2):self.assertFalse(v.update())
                    screen.image[:]=40
                    for now in range(102,108):
                        with patch('vision.time.time',return_value=now),patch('vision.time.monotonic',return_value=now):v.update()
                        self.assertEqual(v.menu_paused,now < (102 if ex.filename == "menu_back.png" else 107))
                    self.assertEqual(v.min_update_period,.1)


if __name__=='__main__':unittest.main()
