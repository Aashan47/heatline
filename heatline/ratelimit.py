"""Per-client rate limiting for the one endpoint that costs money.

The deterministic endpoints are free to serve and are not limited. `/advise`
spends Gemini quota, and on a public URL that quota belongs to whoever deployed
it, so it is capped per client.

Deliberately a fixed window in memory rather than anything cleverer. Cloud Run
scales to zero and can run more than one instance, so a per-instance counter is
approximate: the real ceiling is the cap times the instance count. That is
honest about what this is, and for a demo the point is to stop one visitor
draining the day's quota, not to be exact.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class RateLimiter:
    limit: int
    window_seconds: int
    max_keys: int = 4096
    _hits: dict[str, deque[float]] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def check(self, key: str, now: float | None = None) -> tuple[bool, int, int]:
        """Returns (allowed, remaining, seconds until the window frees up)."""
        now = time.time() if now is None else now
        cutoff = now - self.window_seconds
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= self.limit:
                retry = int(q[0] + self.window_seconds - now) + 1
                return False, 0, max(1, retry)
            q.append(now)
            if len(self._hits) > self.max_keys:
                self._sweep(cutoff)
            return True, self.limit - len(q), 0

    def _sweep(self, cutoff: float) -> None:
        """Drop every client whose window has fully expired.

        Pruning happens per key on access, so a client that never comes back
        keeps its timestamps for ever. A test on a long-lived instance found
        5000 keys still resident, which on Cloud Run is a slow leak rather
        than a theoretical one. Only expired entries are dropped, so this can
        never let a client over its cap.
        """
        stale = [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]
        for k in stale:
            del self._hits[k]


def client_key(headers, fallback: str | None) -> str:
    """The caller's address, as seen from behind a proxy.

    Cloud Run terminates TLS and forwards the real client in
    X-Forwarded-For, leftmost entry. Without this every request would look
    like it came from the load balancer and one visitor would exhaust the cap
    for everyone.
    """
    fwd = headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return fallback or "unknown"
