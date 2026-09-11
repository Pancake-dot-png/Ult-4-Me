"""Menu pause timing uses only valid, once-per-second observations."""


class MenuPause:
    def __init__(self):
        self.paused = False
        self.clear_since = None
        self.last_observation = None
        self.resume_delay = 5

    def update(self, present, now, resume_delay=5):
        # Missed observations cannot count toward five seconds of clear screen.
        if self.last_observation is not None and now - self.last_observation > 1.5:
            self.clear_since = None
        self.last_observation = now
        if present is True:
            self.paused = True
            self.clear_since = None
            self.resume_delay = resume_delay
        elif present is None:
            self.clear_since = None
        elif self.paused:
            if self.resume_delay == 0:
                self.paused = False
                self.clear_since = None
            elif self.clear_since is None:
                self.clear_since = now
            elif now - self.clear_since >= self.resume_delay:
                self.paused = False
                self.clear_since = None
        return self.paused

    def remaining(self, now):
        return self.resume_delay if self.clear_since is None else max(0, self.resume_delay - (now - self.clear_since))
