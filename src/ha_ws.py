"""Vector Home — Home Assistant WebSocket client.

Subscribes to HA events via the WebSocket API and provides
real-time state-change feedback.  Used alongside ha_bridge.py
(the REST client) for push-based updates.

Requires: pip install websockets
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Callable, Coroutine, Dict, Optional

import websockets
from websockets.asyncio.client import connect as ws_connect

# ── Configuration ─────────────────────────────────────────────────────

HA_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123")
HA_TOKEN = os.environ.get("HA_TOKEN", "")

logger = logging.getLogger("ha_ws")


# ── Helpers ───────────────────────────────────────────────────────────


def _ha_url_to_ws(ha_url: str) -> str:
    """Convert a Home Assistant HTTP URL to its WebSocket endpoint.

    ``http://host:8123`` → ``ws://host:8123/api/websocket``
    ``https://host:8123`` → ``wss://host:8123/api/websocket``
    """
    ws_url = ha_url.rstrip("/")
    ws_url = re.sub(r"^http://", "ws://", ws_url)
    ws_url = re.sub(r"^https://", "wss://", ws_url)
    if not ws_url.endswith("/api/websocket"):
        ws_url += "/api/websocket"
    return ws_url


def _extract_room(entity_id: str) -> str:
    """Derive a human-readable room name from an entity_id.

    ``light.living_room`` → ``Living Room``
    ``climate.master_bedroom`` → ``Master Bedroom``
    """
    _, _, name = entity_id.partition(".")
    return name.replace("_", " ").title()


# ── HAWebSocketClient ────────────────────────────────────────────────


class HAWebSocketClient:
    """Async WebSocket client for Home Assistant real-time events.

    Flow:
        1. ``connect()`` — opens WS and authenticates
        2. ``subscribe_events()`` — registers interest in event types
        3. ``listen()`` — streams events, invoking *callback* on each
        4. ``close()`` — graceful shutdown

    Reconnect with exponential back-off (1 s → 2 s → 4 s → … ≤ 30 s)
    is built into ``listen()``.
    """

    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
    ) -> None:
        self.url = url or HA_URL
        self.token = token or HA_TOKEN
        self._ws_url = _ha_url_to_ws(self.url)
        self._ws: websockets.asyncio.client.ClientConnection | None = None
        self._id_counter: int = 0
        self._connected: bool = False
        self._closing: bool = False
        # Back-off state
        self._backoff: float = 1.0
        self._max_backoff: float = 30.0

    # ── Internal helpers ──────────────────────────────────────────

    def _next_id(self) -> int:
        self._id_counter += 1
        return self._id_counter

    async def _send(self, msg: dict) -> None:
        if self._ws is None:
            raise RuntimeError("Not connected")
        payload = json.dumps(msg)
        logger.debug("WS → %s", payload)
        await self._ws.send(payload)

    async def _recv(self) -> dict:
        if self._ws is None:
            raise RuntimeError("Not connected")
        raw = await self._ws.recv()
        msg = json.loads(raw)
        logger.debug("WS ← %s", raw[:500] if isinstance(raw, str) else raw)
        return msg

    # ── Public API ─────────────────────────────────────────────────

    async def connect(self) -> None:
        """Open a WebSocket connection and authenticate with HA."""
        if not self.token:
            raise ValueError("HA_TOKEN is empty — set the environment variable or pass token=")

        logger.info("Connecting to %s …", self._ws_url)
        self._ws = await ws_connect(self._ws_url)
        # HA always sends {"type":"auth_required"} first
        msg = await self._recv()
        if msg.get("type") != "auth_required":
            raise ConnectionError(f"Unexpected first message: {msg}")

        await self._send({"type": "auth", "access_token": self.token})
        auth_ok = await self._recv()
        if auth_ok.get("type") != "auth_ok":
            raise ConnectionError(f"Authentication failed: {auth_ok}")

        self._connected = True
        self._backoff = 1.0  # reset on successful connect
        logger.info("Authenticated with Home Assistant ✓")

    async def subscribe_events(
        self,
        event_type: str = "state_changed",
    ) -> dict:
        """Subscribe to a HA event stream.

        Returns the HA response dict (contains ``id`` matching the
        request).
        """
        msg_id = self._next_id()
        await self._send({
            "id": msg_id,
            "type": "subscribe_events",
            "event_type": event_type,
        })
        resp = await self._recv()
        # HA acknowledges with {"id": N, "type": "result", "success": true}
        if resp.get("success") is False:
            logger.error("Subscribe failed: %s", resp)
        else:
            logger.info("Subscribed to event_type=%s (id=%d)", event_type, msg_id)
        return resp

    async def listen(
        self,
        callback: Callable[[Dict[str, Any]], Coroutine] | Callable[[Dict[str, Any]], Any] | None = None,
    ) -> None:
        """Listen for HA events, invoking *callback* on each.

        If *callback* is ``None``, events are printed to stdout.

        Supports automatic reconnection with exponential back-off.
        This method runs until ``close()`` is called or an
        unrecoverable error occurs.
        """
        while not self._closing:
            try:
                if not self._connected:
                    await self.connect()
                    await self.subscribe_events("state_changed")

                assert self._ws is not None
                async for raw in self._ws:
                    msg = json.loads(raw) if isinstance(raw, str) else raw

                    if msg.get("type") == "event":
                        event_data = self._parse_event(msg)
                        if event_data is None:
                            continue
                        if callback is not None:
                            try:
                                result = callback(event_data)
                                if asyncio.iscoroutine(result):
                                    await result
                            except Exception:
                                logger.exception("Callback raised an exception")
                        else:
                            self._default_print(event_data)

                    elif msg.get("type") == "result":
                        # Acknowledgement of a subscribe — already handled
                        pass

                    elif msg.get("type") == "auth_required":
                        # Re-auth after reconnect shouldn't happen here,
                        # but handle gracefully
                        await self._send({"type": "auth", "access_token": self.token})

                    else:
                        logger.debug("Unhandled message type: %s", msg.get("type"))

            except websockets.ConnectionClosed as exc:
                logger.warning("WebSocket closed (code=%s), reconnecting in %.0fs …", exc.code, self._backoff)
                self._connected = False
                if self._closing:
                    break
                await asyncio.sleep(self._backoff)
                self._backoff = min(self._backoff * 2, self._max_backoff)

            except Exception:
                logger.exception("WebSocket error, reconnecting in %.0fs …", self._backoff)
                self._connected = False
                if self._closing:
                    break
                await asyncio.sleep(self._backoff)
                self._backoff = min(self._backoff * 2, self._max_backoff)

    # ── Event parsing ──────────────────────────────────────────────

    @staticmethod
    def _parse_event(msg: dict) -> Dict[str, Any] | None:
        """Extract a normalised event dict from a WS message."""
        event = msg.get("event")
        if not event:
            return None
        data = event.get("data", {})
        entity_id: str = data.get("entity_id", "")
        new_state = data.get("new_state") or {}
        old_state = data.get("old_state") or {}

        return {
            "event_type": event.get("event_type", ""),
            "entity_id": entity_id,
            "old_state": old_state.get("state") if isinstance(old_state, dict) else None,
            "new_state": new_state.get("state") if isinstance(new_state, dict) else None,
            "attributes": new_state.get("attributes", {}) if isinstance(new_state, dict) else {},
        }

    @staticmethod
    def _default_print(event_data: Dict[str, Any]) -> None:
        eid = event_data["entity_id"]
        old = event_data.get("old_state", "?")
        new = event_data.get("new_state", "?")
        print(f"[HA] {eid}: {old} → {new}")

    # ── Shutdown ───────────────────────────────────────────────────

    async def close(self) -> None:
        """Gracefully close the WebSocket connection."""
        self._closing = True
        self._connected = False
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        logger.info("WebSocket client closed.")


# ── Integration hook: state_change → human-readable ──────────────────


def on_state_change(
    entity_id: str,
    old_state: str | None,
    new_state: str | None,
    attributes: dict | None = None,
) -> str | None:
    """Map a HA state_changed event into a human-friendly Vector Home response.

    Returns a formatted string or ``None`` if the domain is not handled.
    """
    attributes = attributes or {}
    domain = entity_id.split(".")[0]
    room = _extract_room(entity_id)

    if domain == "light":
        state = new_state or "?"
        return f"Lights {state} in {room}"

    if domain == "climate":
        temp = attributes.get("temperature") or attributes.get("current_temperature")
        if temp is not None:
            return f"Temperature set to {temp}°C in {room}"
        return f"Climate changed in {room}"

    if domain == "lock":
        state = "locked" if new_state == "locked" else "unlocked"
        return f"Door {state}"

    if domain == "media_player":
        state = new_state or "?"
        if state == "playing":
            return f"Music playing in {room}"
        return f"Music stopped in {room}"

    if domain == "input_boolean" and "alarm" in entity_id:
        state = "on" if new_state == "on" else "off"
        return f"Alarm {state}"

    # Unhandled domain
    return None


# ── Convenience starter ───────────────────────────────────────────────


async def start_ha_ws_listener(
    callback: Callable[[Dict[str, Any]], Any] | None = None,
) -> HAWebSocketClient:
    """Create, connect, and start listening on a :class:`HAWebSocketClient`.

    If *callback* is ``None``, state changes are printed to stdout.
    Returns the client so the caller can ``await client.close()`` when
    done.
    """
    client = HAWebSocketClient()

    # Wrap the optional callback so it also runs on_state_change
    async def _wrapper(event_data: Dict[str, Any]) -> None:
        # Always produce a human-friendly message via on_state_change
        msg = on_state_change(
            event_data["entity_id"],
            event_data.get("old_state"),
            event_data.get("new_state"),
            event_data.get("attributes"),
        )
        if msg:
            logger.info("🔔 %s", msg)

        if callback is not None:
            result = callback(event_data)
            if asyncio.iscoroutine(result):
                await result

    # Run listen in the background — caller can close() when ready
    listen_task = asyncio.create_task(client.listen(callback=_wrapper))
    # Give the connection a moment to establish
    await asyncio.sleep(0.5)
    # Stash the task so it isn't garbage-collected
    client._listen_task = listen_task  # type: ignore[attr-defined]
    return client


# ── __main__ for quick testing ───────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    async def _main() -> None:
        print("=== HA WebSocket Listener (Ctrl+C to quit) ===\n")
        client = await start_ha_ws_listener()
        try:
            # Block forever (or until close)
            await client._listen_task  # type: ignore[attr-defined]
        except KeyboardInterrupt:
            print("\nShutting down …")
        finally:
            await client.close()

    asyncio.run(_main())