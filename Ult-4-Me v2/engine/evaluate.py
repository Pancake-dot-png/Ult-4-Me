"""Offline matching of cropped HUD images; never creates capture or device clients."""
from dataclasses import asdict
import time
import cv2 as cv
import numpy as np
from detector import load_examples, match_examples


def analyze(payload):
    from vision import Vision
    det = payload['detectable']
    image = cv.imdecode(np.fromfile(payload['image'], dtype=np.uint8), cv.IMREAD_COLOR)
    if image is None or max(image.shape[:2]) > 2048:
        raise ValueError('Choose a cropped HUD image no larger than 2048 pixels per side')
    filters = Vision.__new__(Vision)
    fn = filters._get_filter(det.get('filter'))
    started = time.perf_counter()
    examples = load_examples(payload['templates'], det, float(payload.get('scale', 1)), fn)
    result = match_examples(image, examples, fn, float(det.get('edge_tolerance', 2)))
    threshold = det.get('threshold', .8) if result.mode == 'legacy' else det.get('v2_threshold', .9)
    return {**asdict(result), 'threshold': threshold, 'matched': result.confidence >= threshold,
            'milliseconds': round((time.perf_counter() - started) * 1000, 2)}
