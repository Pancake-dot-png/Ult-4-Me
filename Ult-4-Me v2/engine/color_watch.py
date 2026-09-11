"""Small-region green coverage, normalized to a recorded full-overshield frame."""
import math
import cv2 as cv
import numpy as np

START_STRENGTH = .12
STOP_STRENGTH = .08
CONFIRM_SCANS = 3


def green_coverage(frame):
    # Ignore the one-pixel zone outline and keep calibration/capture identical.
    if frame is None or frame.ndim != 3 or min(frame.shape[:2]) < 3:
        return 0.0
    hsv = cv.cvtColor(frame[1:-1, 1:-1, :3], cv.COLOR_BGR2HSV)
    mask = cv.inRange(hsv, (55, 120, 50), (80, 255, 255))
    return cv.countNonZero(mask) / mask.size


class ColorWatch:
    def __init__(self):
        self.last_time = None
        self.strength = 0.0
        self.hits = 0

    def update(self, frame, full_coverage, now):
        if not math.isfinite(full_coverage) or not .01 <= full_coverage <= 1:
            raise ValueError('Full overshield coverage must be between 1% and 100%')
        coverage = green_coverage(frame)
        target = min(1.0, coverage / full_coverage) if coverage >= .005 else 0.0
        gap = self.last_time is None or now - self.last_time > .5
        elapsed = .1 if self.last_time is None else max(0, now - self.last_time)
        self.last_time = now
        if gap:
            self.strength = 0.0
            self.hits = 0
        # Hysteresis: small green UI details cannot start an overshield bonus.
        # Once active, allow it to decay a little further without chattering.
        minimum = STOP_STRENGTH if self.hits >= CONFIRM_SCANS else START_STRENGTH
        if target < minimum:
            self.strength = 0.0
            self.hits = 0
        else:
            self.hits += 1
            if self.hits >= CONFIRM_SCANS:
                # Confirm onset, then smooth short fluctuations (~150 ms).
                alpha = 1.0 if self.hits == CONFIRM_SCANS else 1 - math.exp(-elapsed / .15)
                self.strength += alpha * (target - self.strength)
        return coverage, self.strength
