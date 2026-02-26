"""
BookUdecate V1.0 — Server-Sent Events Manager
===========================================
Publishes progress events from the pipeline to connected frontend clients.
Each job has its own event queue. Clients connect via GET /jobs/{id}/progress.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import AsyncIterator


class SSEManager:
    """
    In-memory pub/sub broker for Server-Sent Events.
    The pipeline PUSHES events via `publish()`.
    Frontend clients PULL events via `subscribe()`.
    """

    def __init__(self):
        # job_id → list of asyncio.Queue (one per connected client)
        self._queues: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def subscribe(self, job_id: str) -> AsyncIterator[dict]:
        """
        Async generator that yields SSE events for a specific job.
        Each connected client gets its own Queue so events are broadcast to all.
        """
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._queues[job_id].append(q)
        try:
            while True:
                event = await q.get()
                yield event
                if event.get("status") in ("completed", "failed"):
                    break  # Terminal state — close the SSE stream
        finally:
            self._queues[job_id].remove(q)

    async def publish(self, job_id: str, event: dict):
        """
        Push an event dictionary to all clients subscribed to this job.
        Event shape: { progress_percentage, current_phase, status, message }
        """
        for q in list(self._queues.get(job_id, [])):
            try:
                await q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Drop the event if client is too slow — non-blocking

    def broadcast_sync(self, job_id: str, event: dict):
        """
        Thread-safe wrapper for publishing from synchronous pipeline code.
        Uses asyncio.run_coroutine_threadsafe to push from a worker thread.
        """

        loop = _get_event_loop()
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(self.publish(job_id, event), loop)


def _get_event_loop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        return None


# Global singleton shared across the FastAPI app
sse_manager = SSEManager()
