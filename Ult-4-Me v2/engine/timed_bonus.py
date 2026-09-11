"""One-shot additive bonuses, independent of how long an icon remains visible."""


class TimedBonus:
    def __init__(self):
        self.armed = True
        self.expires = 0
        self.ready_at = 0
        self.points = 0

    def update(self, present, now, points, duration, cooldown):
        # None means no valid observation (disabled zone, suppression, capture
        # failure). It must never be mistaken for the icon disappearing.
        if present is False:
            self.armed = True
        elif present is True and self.armed:
            self.armed = False
            if now >= self.ready_at and now >= self.expires:
                self.points = points
                self.expires = now + max(0.1, duration)
                self.ready_at = now + max(0, cooldown)
        return self.points if now < self.expires else 0
