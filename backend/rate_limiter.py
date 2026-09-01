"""Simple in-memory rate limiter + daily quota counter."""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from threading import Lock

from database import rpc

_lock = Lock()
_buckets: dict[str, deque] = defaultdict(deque)

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


async def daily_count() -> int:
    """Return today's durable send count from Postgres."""
    value = await rpc("get_daily_email_count")
    return int(value or 0)


async def reserve_daily_send(limit: int | None = None) -> bool:
    """Atomically reserve one daily send slot across all Vercel instances."""
    if limit is None:
        limit = int(os.environ.get("DAILY_EMAIL_LIMIT", "200"))
    return bool(await rpc("reserve_daily_email", {"p_limit": limit}))


async def release_daily_send() -> None:
    """Return a reserved slot after the provider rejects a send."""
    await rpc("release_daily_email")
