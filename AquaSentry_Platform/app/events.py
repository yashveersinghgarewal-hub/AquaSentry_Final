"""
Live updates for dashboards: a tiny in-process publish/subscribe hub served as Server-Sent Events.

Readings are stored in worker threads (sync FastAPI endpoints), so publish() hands each message to the
event loop with call_soon_threadsafe. Each subscriber has a bounded queue; a slow browser tab loses old
messages instead of slowing the server down.
"""
from __future__ import annotations

import asyncio
import itertools
import json
import threading
from typing import Any, Dict, Optional, Set

MAX_SUBSCRIBERS = 100
QUEUE_SIZE = 100


class EventHub:
    def __init__(self):
        self._subs: Set[asyncio.Queue] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.Lock()
        self._ids = itertools.count(1)

    def bind_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    @property
    def subscriber_count(self) -> int:
        return len(self._subs)

    def subscribe(self) -> Optional[asyncio.Queue]:
        with self._lock:
            if len(self._subs) >= MAX_SUBSCRIBERS:
                return None
            q: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
            self._subs.add(q)
            return q

    def unsubscribe(self, q: asyncio.Queue):
        with self._lock:
            self._subs.discard(q)

    @staticmethod
    def _offer(q: asyncio.Queue, msg: str):
        if q.full():
            try:
                q.get_nowait()          # drop the oldest message for a slow client
            except asyncio.QueueEmpty:
                pass
        q.put_nowait(msg)

    def publish(self, event: str, data: Dict[str, Any]):
        msg = f"id: {next(self._ids)}\nevent: {event}\ndata: {json.dumps(data, default=str)}\n\n"
        loop = self._loop
        with self._lock:
            subs = list(self._subs)
        if not subs or loop is None or loop.is_closed():
            return
        for q in subs:
            try:
                loop.call_soon_threadsafe(self._offer, q, msg)
            except RuntimeError:        # loop shutting down
                return


HUB = EventHub()
