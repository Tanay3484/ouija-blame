"""A small in-memory rate limit for the routes that cost CPU (a séance is up to a minute of Gemma on CPU).

Per client address, a sliding one-minute window. It is deliberately simple: one process, no storage, and
nothing about the request is kept beyond a timestamp per recent call.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(
        self,
        max_per_minute: int,
        clock: Callable[[], float] = time.monotonic,
        max_clients: int = 5000,
    ) -> None:
        self.max = max_per_minute
        self.clock = clock
        self.max_clients = max_clients
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, client: str) -> bool:
        now = self.clock()
        if len(self._hits) > self.max_clients:  # forget idle clients so memory stays bounded
            for key in [k for k, v in self._hits.items() if not v or now - v[-1] > 60]:
                del self._hits[key]
        hits = self._hits[client]
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= self.max:
            return False
        hits.append(now)
        return True


def client_of(request: Request) -> str:
    # Behind Render's proxy the real address is the first X-Forwarded-For entry.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def limit(limiter: RateLimiter):
    def dependency(request: Request) -> None:
        if not limiter.check(client_of(request)):
            raise HTTPException(
                429,
                "Too many requests. The spirits are tired. Try again in a minute, or open a séance from the gallery.",
            )

    return dependency
