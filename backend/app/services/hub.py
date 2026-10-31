"""WebSocket broadcast hub. Thread-safe: sync code (threadpool / background thread) can publish."""
import asyncio
import json
import logging
import threading

from fastapi import WebSocket

log = logging.getLogger("intelliward.hub")


class Hub:
    def __init__(self):
        self.clients: dict[WebSocket, dict] = {}
        self.loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    def bind_loop(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    async def connect(self, ws: WebSocket, user: dict):
        await ws.accept()
        with self._lock:
            self.clients[ws] = user

    def disconnect(self, ws: WebSocket):
        with self._lock:
            self.clients.pop(ws, None)

    async def _send_all(self, message: str, staff_scope: int | None):
        with self._lock:
            targets = list(self.clients.items())
        for ws, user in targets:
            # staff accounts only receive events about themselves
            if user.get("access_role") == "staff" and staff_scope is not None and user.get("staff_id") != staff_scope:
                continue
            if user.get("access_role") == "staff" and staff_scope is None:
                continue
            try:
                await ws.send_text(message)
            except Exception:
                self.disconnect(ws)

    def publish(self, event_type: str, data: dict, staff_scope: int | None = None):
        if self.loop is None:
            return
        message = json.dumps({"type": event_type, "data": data}, default=str)
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self.loop:
            self.loop.create_task(self._send_all(message, staff_scope))
        else:
            asyncio.run_coroutine_threadsafe(self._send_all(message, staff_scope), self.loop)


hub = Hub()
