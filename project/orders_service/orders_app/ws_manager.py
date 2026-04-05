"""
ConnectionManager — manages WebSocket connections for real-time order updates.

Connection model:
  - Each user connects once:  ws://host/ws/orders?token=<access_token>
  - The manager stores connections keyed by user_id
  - On any order status change, the manager broadcasts to the relevant user
  - Admins (is_superuser=True) receive ALL order events across all users

Ping/pong:
  - Server sends {"event": "ping"} every 25s
  - Client should respond with {"event": "pong"} to keep connection alive
  - Stale connections are cleaned up on send failure
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # user_id → list of WebSocket (same user can have multiple tabs)
        self._connections: dict[int, list[WebSocket]] = {}
        # superuser user_ids — receive all events
        self._superusers: set[int] = set()

    # ── Connection lifecycle ──────────────────────────────────────────────────

    async def connect(self, websocket: WebSocket, user_id: int, is_superuser: bool = False):
        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)
        if is_superuser:
            self._superusers.add(user_id)
        log.info("WS connected: user_id=%s  total_connections=%s", user_id, self.total)

    def disconnect(self, websocket: WebSocket, user_id: int):
        conns = self._connections.get(user_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self._connections.pop(user_id, None)
            self._superusers.discard(user_id)
        log.info("WS disconnected: user_id=%s  total_connections=%s", user_id, self.total)

    @property
    def total(self) -> int:
        return sum(len(v) for v in self._connections.values())

    # ── Sending ───────────────────────────────────────────────────────────────

    async def _send(self, websocket: WebSocket, data: dict):
        """Send to a single socket, return False if the socket is dead."""
        try:
            await websocket.send_text(json.dumps(data))
            return True
        except Exception:
            return False

    async def send_to_user(self, user_id: int, data: dict):
        """Send an event to all sockets belonging to a specific user."""
        dead = []
        for ws in list(self._connections.get(user_id, [])):
            if not await self._send(ws, data):
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, user_id)

    async def broadcast_to_superusers(self, data: dict):
        """Broadcast an event to all connected superusers."""
        for uid in list(self._superusers):
            await self.send_to_user(uid, data)

    async def notify_order_event(
        self,
        user_id: int,
        event: str,
        order_id: int,
        status: Optional[str] = None,
        extra: Optional[dict] = None,
    ):
        """
        Notify the order's owner + all superusers about an order event.
        This is the main method called from route handlers.
        """
        payload = {"event": event, "order_id": order_id}
        if status:
            payload["status"] = status
        if extra:
            payload.update(extra)

        await self.send_to_user(user_id, payload)
        await self.broadcast_to_superusers(payload)

    async def ping_all(self):
        """Send keep-alive pings to all connected clients."""
        ping = {"event": "ping"}
        for uid in list(self._connections.keys()):
            await self.send_to_user(uid, ping)


# ── Singleton ─────────────────────────────────────────────────────────────────
manager = ConnectionManager()


async def start_ping_loop(interval: int = 25):
    """Background task: ping all clients every `interval` seconds."""
    while True:
        await asyncio.sleep(interval)
        if manager.total > 0:
            await manager.ping_all()
