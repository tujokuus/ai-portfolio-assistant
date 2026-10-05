"""Global rolling quota for a single-process demo, not a billing cap."""
from collections import deque
from threading import Lock
from time import monotonic


class RequestQuota:
    def __init__(self, hourly: int = 20, daily: int = 100):
        if hourly < 1 or daily < 1:
            raise ValueError("Request limits must be positive")
        self.hourly, self.daily = hourly, daily
        self.calls = deque()
        self.lock = Lock()

    def allow(self, now: float | None = None) -> bool:
        now = monotonic() if now is None else now
        with self.lock:
            while self.calls and self.calls[0] <= now - 86400:
                self.calls.popleft()
            hourly_count = sum(timestamp > now - 3600 for timestamp in self.calls)
            if len(self.calls) >= self.daily or hourly_count >= self.hourly:
                return False
            self.calls.append(now)
            return True
