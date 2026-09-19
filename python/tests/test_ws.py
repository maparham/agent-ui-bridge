"""serve_tab pumps frames and always unregisters the tab."""
import asyncio

import pytest

from agent_ui_bridge.hub import BridgeHub
from agent_ui_bridge.ws import serve_tab

_CLOSED = object()


class FakeSocket:
    """Duck-typed websocket: frames pushed with `push` are read by serve_tab;
    `close` makes the next read raise like a dropped client."""

    def __init__(self):
        self.inbound: asyncio.Queue = asyncio.Queue()
        self.sent = []

    async def send_json(self, frame):
        self.sent.append(frame)

    async def receive_json(self):
        frame = await self.inbound.get()
        if frame is _CLOSED:
            raise ConnectionError("client went away")
        return frame

    def push(self, frame):
        self.inbound.put_nowait(frame)

    def close(self):
        self.inbound.put_nowait(_CLOSED)


@pytest.mark.anyio
async def test_serve_tab_relays_a_reply_then_unregisters():
    hub = BridgeHub()
    sock = FakeSocket()
    sock.close()
    with pytest.raises(ConnectionError):
        await serve_tab(hub, sock)
    assert hub.sessions() == []


@pytest.mark.anyio
async def test_serve_tab_feeds_replies_into_the_hub():
    hub = BridgeHub()
    sock = FakeSocket()
    served = asyncio.ensure_future(serve_tab(hub, sock))
    await asyncio.sleep(0)
    assert len(hub.sessions()) == 1
    sid = hub.sessions()[0]["id"]
    req = asyncio.ensure_future(hub.request("manifest", {}, session_id=sid, timeout=2))
    while not sock.sent:
        await asyncio.sleep(0)
    sock.push({"id": sock.sent[-1]["id"], "ok": True, "result": [{"name": "a"}]})
    assert await req == [{"name": "a"}]
    sock.close()
    with pytest.raises(ConnectionError):
        await served
    assert hub.sessions() == []
