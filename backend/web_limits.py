"""Per-IP and service-wide rolling quotas for a single-process demo."""
from collections import deque
from threading import Lock
from time import monotonic


class RequestQuota:
    def __init__(self, hourly: int = 20, daily: int = 100,
                 ip_hourly: int = 5, ip_daily: int = 20):
        if min(hourly, daily, ip_hourly, ip_daily) < 1:
            raise ValueError("Request limits must be positive")
        self.hourly, self.daily = hourly, daily  # Across every visitor.
        self.ip_hourly, self.ip_daily = ip_hourly, ip_daily
        self.calls = deque()
        self.ip_calls: dict[str, deque] = {}
        self.last_ip_cleanup = 0.0
        self.lock = Lock()

    def check(self, client_ip: str, now: float | None = None) -> str | None:
        """Return None when allowed, otherwise 'ip' or 'service' for the hit limit."""
        now = monotonic() if now is None else now
        with self.lock:
            while self.calls and self.calls[0] <= now - 86400:
                self.calls.popleft()

            if now - self.last_ip_cleanup >= 300:
                expired = [ip for ip, calls in self.ip_calls.items()
                           if not calls or calls[-1] <= now - 86400]
                for ip in expired:
                    del self.ip_calls[ip]
                self.last_ip_cleanup = now

            hourly_count = sum(timestamp > now - 3600 for timestamp in self.calls)
            if len(self.calls) >= self.daily or hourly_count >= self.hourly:
                return "service"

            ip_calls = self.ip_calls.setdefault(client_ip, deque())
            while ip_calls and ip_calls[0] <= now - 86400:
                ip_calls.popleft()
            ip_hourly_count = sum(timestamp > now - 3600 for timestamp in ip_calls)
            if len(ip_calls) >= self.ip_daily or ip_hourly_count >= self.ip_hourly:
                return "ip"

            self.calls.append(now)
            ip_calls.append(now)
            return None

    def allow(self, now: float | None = None, *, client_ip: str = "unknown") -> bool:
        """Boolean compatibility helper for callers that only need allow/deny."""
        return self.check(client_ip, now) is None
