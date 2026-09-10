import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import cv2 as cv
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from detector import load_examples, match_examples, Presence
from config import Config
from vision import Vision


class DetectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.rng = np.random.default_rng(71)

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, name, image):
        cv.imencode('.png', image)[1].tofile(self.root / name)

    def test_alpha_ignores_invisible_pixels_and_holes(self):
        raw = self.rng.integers(0, 255, (24, 24, 4), dtype=np.uint8)
        raw[:, :, 3] = 0
        raw[4:20, 4:20, 3] = 255
        raw[8:16, 8:16, 3] = 0
        self.save('ring.png', raw)
        crop = self.rng.integers(0, 255, (48, 48, 3), dtype=np.uint8)
        visible = raw[:, :, 3] > 0
        crop[12:36, 10:34][visible] = raw[:, :, :3][visible]
        examples = load_examples(self.root, {'filename': 'ring.png'}, 1)
        result = match_examples(crop, examples)
        self.assertGreater(result.confidence, .999)
        self.assertEqual(result.location, (10, 12))
        self.assertEqual(result.mode, 'masked')

    def test_hidden_rgb_does_not_bleed_when_scaled(self):
        a = np.zeros((20, 20, 4), np.uint8)
        a[5:15, 5:15] = [40, 120, 230, 255]
        a[8:12, 8:12, :3] = [210, 30, 40]
        b = a.copy(); b[b[:, :, 3] == 0, :3] = 255
        self.save('a.png', a); self.save('b.png', b)
        aa = load_examples(self.root, {'filename':'a.png'}, 1.3)[0]
        bb = load_examples(self.root, {'filename':'b.png'}, 1.3)[0]
        np.testing.assert_array_equal(aa.image[aa.mask > 0], bb.image[bb.mask > 0])

    def test_masked_solid_color_requires_structural_detail(self):
        raw = np.zeros((24, 24, 4), np.uint8)
        raw[4:20, 4:20] = [255, 255, 255, 255]
        self.save('white.png', raw)
        with self.assertRaisesRegex(ValueError, 'visible contrast'):
            load_examples(self.root, {'filename':'white.png'},1)

    def test_masked_structure_rejects_flat_and_low_contrast_backgrounds(self):
        raw = self.rng.integers(20, 220, (24, 24, 4), dtype=np.uint8)
        raw[:, :, 3] = 255
        raw[:3, :, 3] = 0
        self.save('detail.png', raw)
        examples = load_examples(self.root, {'filename':'detail.png'}, 1)
        for value in (0, 64, 128, 192, 255):
            result = match_examples(np.full((48, 60, 3), value, np.uint8), examples)
            self.assertEqual(result.confidence, 0)
        low_contrast = self.rng.integers(127, 130, (48, 60, 3), dtype=np.uint8)
        self.assertEqual(match_examples(low_contrast, examples).confidence, 0)

    def test_masked_structure_tolerates_brightness_and_ignores_alpha_holes(self):
        raw = self.rng.integers(30, 180, (24, 24, 4), dtype=np.uint8)
        raw[:, :, 3] = self.rng.choice([0, 64, 128, 255], (24, 24))
        self.save('detail.png', raw)
        examples = load_examples(self.root, {'filename':'detail.png'}, 1)
        changed = np.rint(raw[:, :, :3].astype(float) * 1.15 + 20).astype(np.uint8)
        changed[raw[:, :, 3] == 0] = 255
        scene = np.zeros((48, 60, 3), np.uint8)
        scene[9:33, 11:35] = changed
        result = match_examples(scene, examples)
        self.assertGreater(result.confidence, .999)
        self.assertEqual(result.location, (11, 9))
        shuffled = changed.reshape(-1, 3).copy()
        self.rng.shuffle(shuffled)
        self.assertLess(match_examples(shuffled.reshape(24, 24, 3), examples).confidence, .25)

    def test_mercy_recorded_crops_and_negative_scenery(self):
        fixtures = Path(__file__).parent / 'fixtures' / 'mercy'
        examples = {kind: load_examples(fixtures, {'filename':f'{kind}.png'}, 4/3)
                    for kind in ('heal', 'boost')}
        for image_name, correct in [('heal-source.png', 'heal'), ('boost-source.png', 'boost'),
                                    ('live-heal.png', 'heal')]:
            scene = cv.imread(str(fixtures / image_name))
            wrong = 'boost' if correct == 'heal' else 'heal'
            self.assertGreater(match_examples(scene, examples[correct]).confidence, .9)
            self.assertLess(match_examples(scene, examples[wrong]).confidence, .6)
        negative = cv.imread(str(fixtures / 'scenery.png'))
        for group in examples.values():
            self.assertLess(match_examples(negative, group).confidence, .6)
            noise = self.rng.integers(0, 256, (133, 280, 3), dtype=np.uint8)
            self.assertLess(match_examples(noise, group).confidence, .2)

    def test_shape_recognizes_silhouette_and_rejects_blank(self):
        raw = np.zeros((32, 32, 4), np.uint8)
        cv.circle(raw, (16, 16), 10, (220, 220, 220, 255), -1)
        self.save('circle.png', raw)
        examples = load_examples(self.root, {'filename':'circle.png','match_mode':'shape'},1)
        crop = np.zeros((60, 60, 3), np.uint8)
        cv.circle(crop, (30,30),10,(255,150,20),-1)
        self.assertGreater(match_examples(crop,examples).confidence, .9)
        self.assertEqual(match_examples(np.zeros_like(crop),examples).confidence, 0)

    def test_alternate_example_and_size_search(self):
        a = self.rng.integers(0,255,(20,20,3),np.uint8)
        b = self.rng.integers(0,255,(20,20,3),np.uint8)
        self.save('a.png',a); self.save('b.png',b)
        crop = np.zeros((50,50,3),np.uint8)
        crop[10:32,12:34] = cv.resize(b,(22,22))
        examples = load_examples(self.root, {'filename':'a.png','examples':['b.png'],'scale_tolerance':.1},1)
        result = match_examples(crop,examples)
        self.assertEqual(result.filename,'b.png')
        self.assertGreater(result.confidence,.99)

    def test_bad_templates_and_paths_are_rejected(self):
        self.save('empty.png',np.zeros((20,20,4),np.uint8))
        for name in ['empty.png','../outside.png','missing.png']:
            with self.assertRaises((ValueError,OSError)):
                load_examples(self.root,{'filename':name},1)

    def test_temporal_confirmation_release_and_reset(self):
        p = Presence()
        self.assertFalse(p.update('heal',.95,.9,1,2,150))
        self.assertTrue(p.update('heal',.95,.9,1.1,2,150))
        self.assertTrue(p.update('heal',.2,.9,1.2,2,150))
        self.assertFalse(p.update('heal',.2,.9,1.3,2,150))
        self.assertFalse(p.update('heal',.95,.9,2,2,150))

    def test_config_instances_do_not_leak_custom_regions(self):
        path = self.root/'config.json'
        path.write_text(json.dumps({'user_regions':{'Custom':{'1920x1080':{'x':1,'y':2,'w':30,'h':40}}}}))
        a=Config(str(path));a.load();a.save()
        b=Config(str(self.root/'none.json'));b.load()
        self.assertIn('Custom',a.regions)
        self.assertNotIn('Custom',b.regions)
        self.assertIn('Custom',json.loads(path.read_text())['user_regions'])

    def test_existing_scoring_types_receive_detection_counts(self):
        # Simulate detection input to the inherited scoring loop without capture.
        for kind, points, expected in [(0,20,20),(1,20,2),(2,20,1),(3,40,40),(4,30,30)]:
            cfg=Config(str(self.root/'none.json'));cfg.detectables={'Event':{'points':points,'type':kind,'duration':2}}
            cfg.settings['decay']=0
            with patch.object(Vision,'_detect_resolution',return_value=False):
                v=Vision(cfg,capture=object())
                v._det_state={'Event':{'count':0}}
                v.last_update=10
                def detection(): v._det_state['Event']['count']=1
                with patch.object(v,'_update_detections',side_effect=detection),patch('vision.time.time',return_value=10.1001):
                    v.update()
                self.assertAlmostEqual(v.get_score(),expected,places=2)


if __name__=='__main__': unittest.main()
