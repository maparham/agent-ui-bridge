"""Browser tab control MCP tools (ui_focus_tab / ui_open_tab / ui_close_tab).

The AppleScript layer is faked: tests monkeypatch agent_ui_bridge.browser._osascript
and assert on the parsed results and the guards, not on real Chrome.
"""
import pytest
from mcp.server import MCPServer

from agent_ui_bridge import browser
from agent_ui_bridge.hub import ActionFailedError, NoTabError
from agent_ui_bridge.tools import register_ui_tools

URL = "http://localhost:5173"


def fake_osascript(*replies):
    calls = []

    async def run(script: str) -> str:
        calls.append(script)
        return replies[min(len(calls) - 1, len(replies) - 1)]

    run.calls = calls
    return run


class _Hub:
    def __init__(self, result=None, exc=None):
        self.result, self.exc, self.calls = result, exc, []

    async def request(self, kind, payload, session_id=None):
        self.calls.append((kind, payload))
        if self.exc:
            raise self.exc
        return self.result


class _State:
    """Per-test knobs the registered closures read at call time."""

    def __init__(self):
        self.url = URL
        self.hosted = False


@pytest.fixture()
def state():
    return _State()


@pytest.fixture()
def ui(state):
    def build(hub=None):
        return register_ui_tools(
            MCPServer("test-tabs"), hub if hub is not None else _Hub(exc=NoTabError()),
            app_name="app",
            frontend_url=lambda: state.url,
            hosted=lambda: state.hosted,
        )

    return build


@pytest.fixture(autouse=True)
def _macos(monkeypatch):
    monkeypatch.setattr(browser, "_IS_MACOS", True)


@pytest.mark.anyio
async def test_focus_tab_found(monkeypatch, ui):
    monkeypatch.setattr(browser, "_osascript", fake_osascript(f"FOCUSED:{URL}/"))
    assert await ui()["ui_focus_tab"]() == {"focused": f"{URL}/"}


@pytest.mark.anyio
async def test_focus_tab_missing_points_at_open(monkeypatch, ui):
    monkeypatch.setattr(browser, "_osascript", fake_osascript("NONE"))
    with pytest.raises(RuntimeError, match="ui_open_tab"):
        await ui()["ui_focus_tab"]()


@pytest.mark.anyio
async def test_open_tab_is_idempotent_when_tab_exists(monkeypatch, ui):
    run = fake_osascript(f"FOCUSED:{URL}/")
    monkeypatch.setattr(browser, "_osascript", run)
    assert await ui()["ui_open_tab"]() == {"focused": f"{URL}/"}
    assert len(run.calls) == 1  # never reached the open script


@pytest.mark.anyio
async def test_open_tab_opens_when_missing(monkeypatch, ui):
    run = fake_osascript("NONE", "OPENED")
    monkeypatch.setattr(browser, "_osascript", run)
    assert await ui()["ui_open_tab"]() == {"opened": URL}
    assert len(run.calls) == 2


@pytest.mark.anyio
async def test_close_tab_single(monkeypatch, ui):
    monkeypatch.setattr(browser, "_osascript", fake_osascript("CLOSED"))
    assert await ui()["ui_close_tab"]() == {"closed": URL}


@pytest.mark.anyio
async def test_close_tab_refuses_zero_and_many(monkeypatch, ui):
    monkeypatch.setattr(browser, "_osascript", fake_osascript("NONE"))
    with pytest.raises(RuntimeError, match="no app tab"):
        await ui()["ui_close_tab"]()
    monkeypatch.setattr(browser, "_osascript", fake_osascript("MANY:3"))
    with pytest.raises(RuntimeError, match="3"):
        await ui()["ui_close_tab"]()


@pytest.mark.anyio
async def test_requires_macos(monkeypatch, ui):
    # ui_open_tab/ui_close_tab hit the macOS guard directly, so this exercises
    # ITS "needs macOS" message, distinct from ui_focus_tab's own off-macOS
    # messages below.
    monkeypatch.setattr(browser, "_IS_MACOS", False)
    with pytest.raises(RuntimeError, match="needs macOS"):
        await ui()["ui_close_tab"]()


@pytest.mark.anyio
async def test_refused_in_hosted_mode(state, ui):
    # A connected tab that would happily answer tab.focus must still be
    # refused: the hosted guard has to run BEFORE the extension path, not
    # only before the AppleScript fallback.
    state.hosted = True
    with pytest.raises(RuntimeError, match="local"):
        await ui(_Hub(result={"focused": True}))["ui_focus_tab"]()


@pytest.mark.anyio
async def test_rejects_unsafe_app_url(monkeypatch, state, ui):
    state.url = 'http://x" & do shell script "echo pwn'
    monkeypatch.setattr(browser, "_osascript", fake_osascript("NONE"))
    with pytest.raises(RuntimeError, match="not a plain URL"):
        await ui()["ui_focus_tab"]()


@pytest.mark.anyio
async def test_focus_tab_needs_a_configured_url(monkeypatch):
    monkeypatch.setattr(browser, "_osascript", fake_osascript("NONE"))
    tools = register_ui_tools(MCPServer("test-nourl"), _Hub(exc=NoTabError()), app_name="app")
    with pytest.raises(RuntimeError, match="not configured"):
        await tools["ui_focus_tab"]()


@pytest.mark.anyio
async def test_focus_tab_prefers_the_extension(monkeypatch, ui):
    hub = _Hub(result={"focused": True})
    run = fake_osascript("FOCUSED:should-not-run")
    monkeypatch.setattr(browser, "_osascript", run)
    assert await ui(hub)["ui_focus_tab"]() == {"focused": "extension"}
    assert hub.calls == [("invoke", {"action": "tab.focus", "args": {}})]
    assert run.calls == []


@pytest.mark.anyio
async def test_focus_tab_falls_back_to_applescript_without_extension(monkeypatch, ui):
    monkeypatch.setattr(browser, "_osascript", fake_osascript(f"FOCUSED:{URL}/"))
    hub = _Hub(exc=ActionFailedError("NO_EXTENSION", "not installed"))
    assert await ui(hub)["ui_focus_tab"]() == {"focused": f"{URL}/"}


@pytest.mark.anyio
async def test_focus_tab_falls_back_to_applescript_with_no_tab(monkeypatch, ui):
    monkeypatch.setattr(browser, "_osascript", fake_osascript("NONE"))
    with pytest.raises(RuntimeError, match="ui_open_tab"):
        await ui(_Hub(exc=NoTabError()))["ui_focus_tab"]()


@pytest.mark.anyio
async def test_focus_tab_off_macos_without_extension_names_it(monkeypatch, ui):
    monkeypatch.setattr(browser, "_IS_MACOS", False)
    hub = _Hub(exc=ActionFailedError("NO_EXTENSION", "not installed"))
    with pytest.raises(RuntimeError, match="Tab Bridge extension"):
        await ui(hub)["ui_focus_tab"]()


@pytest.mark.anyio
async def test_focus_tab_off_macos_no_tab_names_ui_session(monkeypatch, ui):
    # No connected tab at all is not an extension problem, so off macOS this
    # must not blame the Tab Bridge extension either (distinct wording from
    # the NO_EXTENSION case above).
    monkeypatch.setattr(browser, "_IS_MACOS", False)
    with pytest.raises(RuntimeError, match="no UI session connected") as excinfo:
        await ui(_Hub(exc=NoTabError()))["ui_focus_tab"]()
    assert "Tab Bridge extension" not in str(excinfo.value)
