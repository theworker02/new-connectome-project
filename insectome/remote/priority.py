"""Priority fetch queue for camera-aware streaming."""

from __future__ import annotations

import heapq
import itertools
import threading
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(order=True)
class FetchJob:
    priority: int
    seq: int
    kind: str = field(compare=False)
    key: str = field(compare=False)
    fn: Callable[[], Any] = field(compare=False)
    cancelled: bool = field(default=False, compare=False)


class PriorityFetcher:
    """P0 selected neuron … P5 background warmth. Cancel obsolete keys on camera move."""

    def __init__(self) -> None:
        self._q: list[FetchJob] = []
        self._seq = itertools.count()
        self._lock = threading.Lock()
        self._inflight: dict[str, FetchJob] = {}

    def submit(self, priority: int, kind: str, key: str, fn: Callable[[], Any]) -> None:
        with self._lock:
            old = self._inflight.get(key)
            if old is not None:
                old.cancelled = True
            job = FetchJob(priority=priority, seq=next(self._seq), kind=kind, key=key, fn=fn)
            self._inflight[key] = job
            heapq.heappush(self._q, job)

    def cancel_prefix(self, prefix: str) -> int:
        n = 0
        with self._lock:
            for job in list(self._inflight.values()):
                if job.key.startswith(prefix):
                    job.cancelled = True
                    n += 1
        return n

    def pop(self) -> FetchJob | None:
        with self._lock:
            while self._q:
                job = heapq.heappop(self._q)
                if job.cancelled:
                    self._inflight.pop(job.key, None)
                    continue
                return job
        return None

    def run_one(self) -> Any:
        job = self.pop()
        if job is None:
            return None
        try:
            if job.cancelled:
                return None
            return job.fn()
        finally:
            with self._lock:
                self._inflight.pop(job.key, None)

    def status(self) -> dict:
        with self._lock:
            return {
                "queued": len(self._q),
                "inflight": len(self._inflight),
                "keys": list(self._inflight.keys())[:20],
            }
