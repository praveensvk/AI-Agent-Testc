"""
WebSocket Connection Manager.

Manages WebSocket connections per test run for broadcasting
real-time execution updates to connected clients.
"""

import asyncio
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Each entry: (websocket, done_event)
_Entry = tuple[WebSocket, asyncio.Event]


class ConnectionManager:
    """Manages WebSocket connections grouped by test run ID."""

    def __init__(self):
        self._connections: dict[str, list[_Entry]] = {}

    async def connect(self, run_id: str, websocket: WebSocket, done_event: asyncio.Event) -> None:
        await websocket.accept()
        if run_id not in self._connections:
            self._connections[run_id] = []
        self._connections[run_id].append((websocket, done_event))
        logger.info(
            "WebSocket connected for run %s (total: %d)",
            run_id,
            len(self._connections[run_id]),
        )

    def disconnect(self, run_id: str, websocket: WebSocket) -> None:
        if run_id in self._connections:
            self._connections[run_id] = [
                (ws, ev) for ws, ev in self._connections[run_id] if ws != websocket
            ]
            if not self._connections[run_id]:
                del self._connections[run_id]
        logger.info("WebSocket disconnected for run %s", run_id)

    async def broadcast(self, run_id: str, message: dict) -> None:
        """Send a JSON message to all connected clients for a given run."""
        if run_id not in self._connections:
            return
        dead: list[WebSocket] = []
        for ws, _ev in self._connections[run_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(run_id, ws)

    def close_all(self, run_id: str) -> None:
        """Signal all handlers for a run to close by setting their done events."""
        if run_id not in self._connections:
            return
        for _ws, ev in list(self._connections[run_id]):
            ev.set()
        logger.info("Signalled close for all WebSocket connections for run %s", run_id)


# Singleton instance
manager = ConnectionManager()
