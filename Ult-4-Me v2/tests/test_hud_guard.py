from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import cv2 as cv

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'engine'))
from config import Config
from vision import Vision
from test_fix_bundle import Screen


class HudGuardTests(unittest.TestCase):
    def setup_scene(self,height=1440):
        cfg=Config(str(ROOT/'release-settings.json'));cfg.load()
        cfg.detectables={name:cfg.detectables[name] for name in ['HUD Present','Overshield','Anti-Healing']}
        cfg.settings.update(ignore_spectate=False,decay=0)
        screen=Screen(height);v=Vision(cfg,ROOT/'templates',capture=screen)
        return cfg,screen,v

    def insert(self,screen,v,name):
        ex=v._det_state[name]['examples'][0]
        r=v._region_state[v.config.detectables[name]['region']]['scaled']
        h,w=ex.image.shape[:2];x,y=r['x']+(r['w']-w)//2,r['y']+(r['h']-h)//2
        screen.image[y:y+h,x:x+w,:3]=ex.image

    def green(self,screen,v):
        r=v._region_state['Health Watch']['scaled']
        screen.image[r['y']:r['y']+r['h'],r['x']:r['x']+r['w'],:3]=(55,217,0)

    def tick(self,v,now):
        with patch('vision.time.time',return_value=now),patch('vision.time.monotonic',return_value=now):
            v.update()

    def test_green_without_hud_never_scores_or_highlights(self):
        cfg,screen,v=self.setup_scene();self.green(screen,v)
        for i in range(10):self.tick(v,100+i*.11)
        self.assertEqual(v.get_score(),0)
        self.assertFalse(v._region_state['Health Watch']['matches'])
        self.assertFalse(v._region_state['Anti Healing']['matches'])

    def test_plus_is_passive_and_enables_overshield(self):
        for height in (1080,1440):
            cfg,screen,v=self.setup_scene(height);self.insert(screen,v,'HUD Present')
            for i in range(5):self.tick(v,100+i*.11)
            self.assertTrue(v._hud_present['HUD Present'])
            self.assertEqual(v.get_score(),0)
            self.assertEqual(v._det_state['HUD Present']['count'],0)
            self.assertFalse(v._region_state['Anti Healing']['matches'])
            self.assertFalse(v.match_details['HUD Present']['active'])
            self.green(screen,v)
            for i in range(4):self.tick(v,101+i*.11)
            self.assertEqual(v._det_state['Overshield']['count'],1)
            self.assertAlmostEqual(v.get_score(),100)
            # Losing the HUD immediately gates off green scenery.
            r=v._region_state['Anti Healing']['scaled']
            screen.image[r['y']:r['y']+r['h'],r['x']:r['x']+r['w']]=40
            self.tick(v,101.5)
            self.assertEqual(v.get_score(),0)
            self.assertFalse(v._region_state['Health Watch']['matches'])

    def test_actual_antiheal_still_scores_and_also_confirms_hud(self):
        cfg,screen,v=self.setup_scene();self.insert(screen,v,'Anti-Healing');self.green(screen,v)
        for i in range(5):self.tick(v,100+i*.11)
        self.assertTrue(v._hud_present['HUD Present'])
        self.assertEqual(v._det_state['HUD Present']['count'],0)
        self.assertEqual(v._det_state['Anti-Healing']['count'],1)
        self.assertEqual(v._region_state['Anti Healing']['matches'],['Anti-Healing'])
        self.assertAlmostEqual(v.get_score(),100+cfg.detectables['Anti-Healing']['points'])

    def test_missing_or_disabled_guard_fails_closed(self):
        for disable in (False,True):
            cfg,screen,v=self.setup_scene();self.green(screen,v)
            if disable:cfg.settings['disabled_zones']=['Anti Healing']
            else:del cfg.detectables['HUD Present']
            v._setup_detectables()
            for i in range(5):self.tick(v,100+i*.11)
            self.assertEqual(v.get_score(),0)


if __name__=='__main__':unittest.main()
