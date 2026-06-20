"""Process-local fan-out of :class:`ModelChange` events to subscribed states.

Django model signals fire on whatever thread runs the ORM write (often a
synchronous worker thread), while Reflex state background tasks consume changes
on the asyncio event loop. The broadcaster bridges the two: subscribers create
an :class:`asyncio.Queue` bound to their running loop, and ``publish`` schedules
delivery onto each subscriber's loop with ``call_soon_threadsafe`` so it is safe
to call from any thread.

This is an in-process transport (single worker / dev and small deployments). A
multi-process deployment should layer a real fan-out (e.g. Postgres
``LISTEN/NOTIFY`` or Redis pub/sub) that calls :meth:`publish` on each worker;
the subscriber side is unchanged.
"""

from __future__ import annotations

import asyncio
import threading
from collections import defaultdict

from reflex_django.live.change import ModelChange


class _Subscription:
    __slots__ = ("queue", "loop")

    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop) -> None:
        self.queue = queue
        self.loop = loop


class LiveBroadcaster:
    """Thread-safe registry mapping ``"app.model"`` labels to subscriber queues."""

    def __init__(self) -> None:
        self._subs: dict[str, set[_Subscription]] = defaultdict(set)
        self._queue_subs: dict[int, _Subscription] = {}
        self._lock = threading.Lock()

    def subscribe(self, model_label: str) -> asyncio.Queue:
        """Register the current task and return a queue of incoming changes.

        Must be called from within a running event loop (a Reflex background
        event handler).
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # pragma: no cover - defensive
            loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()
        sub = _Subscription(queue, loop)
        with self._lock:
            self._subs[model_label].add(sub)
            self._queue_subs[id(queue)] = sub
        return queue

    def unsubscribe(self, model_label: str, queue: asyncio.Queue) -> None:
        with self._lock:
            sub = self._queue_subs.pop(id(queue), None)
            subs = self._subs.get(model_label)
            if not subs:
                return
            if sub is not None:
                subs.discard(sub)
            else:  # pragma: no cover - defensive
                subs.difference_update({s for s in subs if s.queue is queue})
            if not subs:
                self._subs.pop(model_label, None)

    def publish(self, change: ModelChange) -> int:
        """Deliver *change* to every subscriber of its model. Returns delivered count."""
        with self._lock:
            subs = list(self._subs.get(change.model_label, ()))
        delivered = 0
        for sub in subs:
            try:
                sub.loop.call_soon_threadsafe(sub.queue.put_nowait, change)
                delivered += 1
            except RuntimeError:
                # Loop already closed; drop the dead subscription.
                self.unsubscribe(change.model_label, sub.queue)
        return delivered

    def subscriber_count(self, model_label: str) -> int:
        with self._lock:
            return len(self._subs.get(model_label, ()))

    def clear(self) -> None:
        with self._lock:
            self._subs.clear()
            self._queue_subs.clear()


_BROADCASTER = LiveBroadcaster()


def live_broadcaster() -> LiveBroadcaster:
    """Return the process-wide broadcaster singleton."""
    return _BROADCASTER


__all__ = ["LiveBroadcaster", "live_broadcaster"]
