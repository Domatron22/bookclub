# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""A small in-process rate limiter.

Coverbound is a single-process self-hosted app, so an in-memory window is
enough and saves a Redis dependency. The trade-off is deliberate: counters
reset on restart and are not shared between workers. If this ever runs under
`--workers N`, the effective limit becomes N times what is configured here —
which is still a bound, just a looser one.

Keys are caller-supplied. Prefer a user id over a client address: behind a
reverse proxy every request carries the proxy's IP, and `X-Forwarded-For` is
attacker-supplied unless the proxy is known to overwrite it.
"""
import threading
import time
from collections import defaultdict, deque

_hits: "defaultdict[str, deque]" = defaultdict(deque)
_lock = threading.Lock()

# Cleared opportunistically so a long-running process doesn't accumulate a
# deque per key that was used once.
_PRUNE_EVERY = 256
_calls_since_prune = 0


def check(key: str, limit: int, window_seconds: int) -> "tuple[bool, int]":
    """Record an attempt for `key`. Returns (allowed, seconds_until_retry).

    A rejected attempt is *not* recorded, so a caller hammering the endpoint
    can't extend their own lockout indefinitely.
    """
    global _calls_since_prune
    now = time.monotonic()
    cutoff = now - window_seconds

    with _lock:
        bucket = _hits[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            return False, max(1, int(bucket[0] - cutoff) + 1)

        bucket.append(now)

        _calls_since_prune += 1
        if _calls_since_prune >= _PRUNE_EVERY:
            _calls_since_prune = 0
            for k in [k for k, v in _hits.items() if not v or v[-1] <= cutoff]:
                del _hits[k]

        return True, 0


def reset() -> None:
    """Drop all counters. For tests."""
    with _lock:
        _hits.clear()
