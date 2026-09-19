"""Serve one connected tab: register it with the hub, pump frames, unregister.

The caller does auth and `accept()` first, then hands the socket over. Only
`send_json` and `receive_json` are used, so any object with those two coroutine
methods works; nothing here imports a web framework.
"""
from __future__ import annotations

from typing import Any

from .hub import BridgeHub


async def serve_tab(hub: BridgeHub, websocket: Any) -> None:
    """Pump frames between one accepted websocket and the hub until it drops.

    Frames FROM the tab are replies and handle events; frames TO the tab are
    invoke/manifest/abort requests sent by `hub.request`. The disconnect
    exception is deliberately not caught: the caller's route decides what a
    disconnect means, and `finally` guarantees the tab is unregistered either
    way.
    """
    sid = hub.register(websocket.send_json)
    try:
        while True:
            hub.on_frame(sid, await websocket.receive_json())
    finally:
        hub.unregister(sid)
