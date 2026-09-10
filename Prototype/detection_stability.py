"""Per-event confirmation and brief release grace, using monotonic scan time."""
from dataclasses import dataclass


@dataclass
class State:
    hits: int = 0
    active: bool = False
    last_hit: float = -1e9
    last_scan: float = -1e9


class DetectionStability:
    def __init__(self, confirm_scans=2, release_seconds=0.2):
        self.confirm_scans = confirm_scans
        self.release_seconds = release_seconds
        self.states = {}

    def update(self, key, matched, now):
        state = self.states.setdefault(key, State())
        if now - state.last_scan > 0.5:
            state.hits = 0
            state.active = False
        if matched:
            state.hits = min(self.confirm_scans, state.hits + 1)
            state.active = state.active or state.hits >= self.confirm_scans
            state.last_hit = now
        else:
            state.hits = 0
            state.active = state.active and now - state.last_hit < self.release_seconds - 1e-9
        state.last_scan = now
        return state.active

    def pending_in_region(self, region):
        return any(key[0] == region and (state.hits or state.active)
                   for key, state in self.states.items())
