"""
api/websocket_manager.py
─────────────────────────
Manages all active WebSocket connections for real-time alert push.
"""

import json
import logging
from typing import Any, Dict, List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Broadcast new alerts to all connected dashboard clients."""

    def __init__(self):
        self._connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)
        logger.info(f"WS client connected. Total: {len(self._connections)}")

    def disconnect(self, ws: WebSocket):
        if ws in self._connections:
            self._connections.remove(ws)
        logger.info(f"WS client disconnected. Remaining: {len(self._connections)}")

    async def broadcast(self, event: str, data: Dict[str, Any]):
        """Send a message to all connected clients."""
        payload = json.dumps({"event": event, "data": data}, default=str)
        dead = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_new_alert(self, alert_data: Dict[str, Any]):
        await self.broadcast("new_alert", alert_data)

    async def broadcast_alert_update(self, alert_data: Dict[str, Any]):
        await self.broadcast("alert_updated", alert_data)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Singleton shared across all route handlers
ws_manager = WebSocketManager()
