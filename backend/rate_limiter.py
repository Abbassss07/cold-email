"""Simple in-memory rate limiter + daily quota counter."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from datetime import datetime, timezone

_lock = Lock()
_buckets: dict[str, deque] = defaultdict(deque)

# daily counters
_daily: dict[str, int] = {}
_daily_date: str = ""


def allow(key: str, max_calls: int, window_seconds: int) -> bool:
    now = time.time()
    with _lock:
        q = _buckets[key]
        while q and q[0] <= now - window_seconds:
            q.popleft()
        if len(q) >= max_calls:
            return False
        q.append(now)
        return True


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def daily_count(key: str = "sent") -> int:
    global _daily_date
    with _lock:
        today = _today()
        if today != _daily_date:
            _daily.clear()
            _daily_date = today
        return _daily.get(key, 0)


def daily_increment(key: str = "sent", by: int = 1) -> int:
    global _daily_date
    with _lock:
        today = _today()
        if today != _daily_date:
            _daily.clear()
            _daily_date = today
        _daily[key] = _daily.get(key, 0) + by
        return _daily[key]
