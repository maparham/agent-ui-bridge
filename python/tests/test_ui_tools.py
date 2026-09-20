"""The ui_* tool functions drive BridgeHub correctly (no HTTP transport here)."""
import asyncio

import pytest
from mcp.server import MCPServer

from agent_ui_bridge.hub import BridgeHub
from agent_ui_bridge.tools import register_ui_tools


@pytest.fixture()
def hub():
    return BridgeHub()


@pytest.fixture()
def ui(hub):
    """The ten tool callables, registered on a throwaway server."""
    return register_ui_tools(
        MCPServer("test-ui"), hub,
        screenshot_action="page.screenshot",
        app_name="app",
        app_url_label="the test URL",
        frontend_url=lambda: "http://localhost:5173",
    )


def fake_tab(hub):
    sent = []

    async def send(frame):
        sent.append(frame)

    sid = hub.register(send)
    return sid, sent


def titled_tab(hub, title="✻ test"):
    sid, sent = fake_tab(hub)
    hub.set_title(sid, title)
    return sid, sent


async def reply(hub, sid, sent, **kv):
    while not sent:
        await asyncio.sleep(0)
    hub.on_frame(sid, {"id": sent[-1]["id"], **kv})


@pytest.mark.anyio
async def test_ui_sessions_empty(ui):
    assert await ui["ui_sessions"]() == []


@pytest.mark.anyio
async def test_ui_actions_relays_manifest(hub, ui):
    sid, sent = fake_tab(hub)
    task = asyncio.ensure_future(ui["ui_actions"]())
    await reply(hub, sid, sent, ok=True, result=[{"name": "thing.do"}])
    assert await task == [{"name": "thing.do"}]
    assert sent[0]["op"] == "manifest"


@pytest.mark.anyio
async def test_ui_invoke_and_wait(hub, ui):
    sid, sent = titled_tab(hub)
    task = asyncio.ensure_future(ui["ui_invoke"]("thing.run", {}))
    while not sent:
        await asyncio.sleep(0)
    rid = sent[-1]["id"]
    hub.on_frame(sid, {"id": rid, "ok": True, "handle": rid})
    assert await task == {"handle": rid}
    hub.on_frame(sid, {"handle": rid, "event": "done", "payload": {"total": 1}})
    st = await ui["ui_wait"](rid, timeout_s=1)
    assert st["status"] == "done" and st["result"] == {"total": 1}


@pytest.mark.anyio
async def test_no_tab_is_a_clear_message(ui):
    with pytest.raises(Exception, match="no UI session connected"):
        await ui["ui_invoke"]("x", {})


@pytest.mark.anyio
async def test_invalid_args_error_carries_schema(hub, ui):
    sid, sent = titled_tab(hub)
    task = asyncio.ensure_future(ui["ui_invoke"]("x", {}))
    await reply(hub, sid, sent, ok=False,
                error={"code": "INVALID_ARGS", "message": "missing name",
                       "expectedSchema": {"type": "object"}})
    with pytest.raises(Exception, match="INVALID_ARGS.*missing name"):
        await task


@pytest.mark.anyio
async def test_ui_read_state_marks_the_frame_read_only(hub, ui):
    """The tab refuses a non-read action on a readOnly frame, so ui_read_state
    can never be used to run a confirm-kind action."""
    sid, sent = titled_tab(hub)
    task = asyncio.ensure_future(ui["ui_read_state"]("thing.result"))
    await reply(hub, sid, sent, ok=True, result={"total": 1})
    assert await task == {"total": 1}
    assert sent[0]["op"] == "invoke"
    assert sent[0]["action"] == "thing.result"
    assert sent[0]["readOnly"] is True


# --- tab titles: every driven tab must be named before it is used -----------


@pytest.mark.anyio
async def test_untitled_tab_refuses_invoke_read_and_screenshot(hub, ui):
    fake_tab(hub)
    for call in (
        ui["ui_invoke"]("thing.select", {"name": "a"}),
        ui["ui_read_state"]("thing.state"),
        ui["ui_screenshot"](),
    ):
        with pytest.raises(RuntimeError, match="UNTITLED_TAB.*ui_set_title"):
            await call


@pytest.mark.anyio
async def test_ui_set_title_invokes_the_action_and_unlocks_the_tab(hub, ui):
    sid, sent = fake_tab(hub)
    task = asyncio.ensure_future(ui["ui_set_title"]("nightly review"))
    await reply(hub, sid, sent, ok=True, result={"title": "✻ nightly review"})
    assert await task == {"session": sid, "title": "✻ nightly review"}
    assert sent[0]["op"] == "invoke" and sent[0]["action"] == "tab.title.set"
    assert sent[0]["args"] == {"title": "nightly review"}
    assert (await ui["ui_sessions"]())[0]["title"] == "✻ nightly review"
    task = asyncio.ensure_future(ui["ui_invoke"]("thing.select", {"name": "a"}))
    while len(sent) < 2:
        await asyncio.sleep(0)
    hub.on_frame(sid, {"id": sent[-1]["id"], "ok": True, "result": {"ok": True}})
    assert await task == {"ok": True}


@pytest.mark.anyio
async def test_ui_set_title_rejects_blank(hub, ui):
    fake_tab(hub)
    with pytest.raises(RuntimeError, match="title"):
        await ui["ui_set_title"]("   ")


@pytest.mark.anyio
async def test_title_is_per_session(hub, ui):
    a, _ = titled_tab(hub)
    b, _ = fake_tab(hub)
    with pytest.raises(RuntimeError, match="UNTITLED_TAB"):
        await ui["ui_invoke"]("thing.select", {"name": "a"}, session=b)
    sessions = await ui["ui_sessions"]()
    assert {s["id"]: s["title"] for s in sessions} == {a: "✻ test", b: None}


@pytest.mark.anyio
async def test_ui_invoke_of_the_title_action_routes_to_set_title(hub, ui):
    """tab.title.set through ui_invoke must not hit the UNTITLED_TAB gate, or
    the tab could never be named through the generic tool."""
    sid, sent = fake_tab(hub)
    task = asyncio.ensure_future(ui["ui_invoke"]("tab.title.set", {"title": "named"}))
    await reply(hub, sid, sent, ok=True, result={"title": "✻ named"})
    assert await task == {"session": sid, "title": "✻ named"}
