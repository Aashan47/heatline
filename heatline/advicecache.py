"""A short lived cache for agent answers.

The free tier allows a handful of model requests a minute and one agent answer
spends several of them, so two visitors asking the same question a minute apart
is enough to rate limit the second one. The answer would have been the same.

What makes this safe rather than a shortcut: the numbers in an answer come from
tools that read the forecast, and the forecast is published hourly. A ten minute
entry therefore cannot outlive the data it was computed from. Anything that
would change the answer, including the hour asked about, is part of the key.

A cache hit spends no quota, so it does not count against the per visitor
allowance either. The allowance exists to protect the quota, and a hit costs
none of it.
"""

from __future__ import annotations

import time
from collections import OrderedDict

# Shorter than the hourly forecast issue interval, so an entry cannot survive
# the data it was computed from.
DEFAULT_TTL_SECONDS = 600
DEFAULT_MAX_ENTRIES = 256


class AdviceCache:
    def __init__(
        self,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._items: OrderedDict[str, tuple[float, dict]] = OrderedDict()

    @staticmethod
    def key(question: str, profile: str, acclimatized: bool) -> str:
        """Whitespace and case do not change an answer, so they do not change a
        key. Everything that does change one is in it."""
        return "\x00".join(
            (" ".join(question.split()).casefold(), profile, str(acclimatized))
        )

    def get(self, key: str, now: float | None = None) -> dict | None:
        now = time.monotonic() if now is None else now
        found = self._items.get(key)
        if found is None:
            return None
        stored_at, value = found
        if now - stored_at >= self.ttl:
            del self._items[key]
            return None
        self._items.move_to_end(key)
        return value

    def put(self, key: str, value: dict, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        self._items[key] = (now, value)
        self._items.move_to_end(key)
        self._evict(now)

    def _evict(self, now: float) -> None:
        # Expired entries first, so a burst of distinct questions does not push
        # out a live entry while dead ones are still holding slots.
        for key in [k for k, (t, _) in self._items.items() if now - t >= self.ttl]:
            del self._items[key]
        while len(self._items) > self.max_entries:
            self._items.popitem(last=False)

    def __len__(self) -> int:
        return len(self._items)
