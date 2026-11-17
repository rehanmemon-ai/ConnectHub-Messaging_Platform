import asyncio
import time
from collections import defaultdict, deque

from app.api.errors import ApiError


class ProcessRateLimiter:
    """Small one-process sliding-window limiter for the single-worker MVP."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        async with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(events[0] + window_seconds - now) + 1)
                raise ApiError(
                    429,
                    "rate_limited",
                    "Too many requests. Try again later.",
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(now)

    async def clear(self) -> None:
        async with self._lock:
            self._events.clear()


rate_limiter = ProcessRateLimiter()
