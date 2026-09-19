"""The ui_* MCP tools: a thin, app-agnostic layer over a BridgeHub.

`register_ui_tools(mcp, hub, ...)` registers ten tools on a given MCPServer.
Everything app-specific is an option: the screenshot action's name and doc, the
app's display name, how to resolve the app's URL, and whether this deployment
is hosted (hosted refuses browser tab control outright).
"""
from __future__ import annotations

import inspect
from typing import Any, Callable, Mapping

from mcp.types import ImageContent, TextContent

from . import browser
from .hub import ActionFailedError, NoTabError, TabTimeoutError

TITLE_ACTION = "tab.title.set"

# Tool descriptions. The MCP SDK cleandocs a function's docstring but registers
# an explicit `description=` verbatim, so `_add` runs inspect.cleandoc on these
# to reproduce what the original docstrings produced. Agents read this text:
# treat it as an API.
_DOC_SESSIONS = """List connected UI tabs (most recently active first)."""

_DOC_ACTIONS = """The manifest: every UI action with its name, kind, and JSON schema."""

_DOC_SET_TITLE = """Name the browser tab you are about to drive. REQUIRED before ui_invoke,
    ui_read_state or ui_screenshot work on a session. Keep it short and
    specific ('Orders review', 'Weekly report export'); the tab
    prefixes a robot mark so the owner can tell agent tabs from their own."""

_DOC_INVOKE = """Invoke a UI action. Fast actions return the result; long-running ones
    (exports, batch jobs) and confirm-kind ones (which wait on a human
    approving a dialog) return {"handle": ...} - poll with ui_wait. A rejected
    confirm surfaces as ui_wait status "error" with "REJECTED: ...".
    Refused with UNTITLED_TAB until ui_set_title has named the tab."""

_DOC_WAIT = """Wait for a long-running invocation. Returns {status, progress, result?, error?};
    status "running" after timeout means keep polling."""

_DOC_READ_STATE = """Shorthand for invoking a read-kind action by name (e.g. settings.get).

    `readOnly` is enforced by the tab: a key naming a write- or confirm-kind
    action is refused with NOT_READ_ACTION instead of being executed.
    Refused with UNTITLED_TAB until ui_set_title has named the tab."""

_DOC_SCREENSHOT = """Screenshot of the connected tab, as an image the client renders
    natively. Refused with UNTITLED_TAB until ui_set_title has named the tab."""


def _friendly(e: Exception) -> Exception:
    """Hub exceptions as one actionable line the MCP SDK turns into a tool error."""
    if isinstance(e, ActionFailedError):
        detail = f"{e.code}: {e}"
        if e.expected_schema:
            detail += f" (expected schema: {e.expected_schema})"
        return RuntimeError(detail)
    return RuntimeError(str(e))


def register_ui_tools(
    mcp: Any,
    hub: Any,
    *,
    screenshot_action: str = "page.screenshot",
    screenshot_doc: str | None = None,
    docs: Mapping[str, str] | None = None,
    title_example: str = "Orders review",
    app_name: str = "app",
    app_url_label: str = "the configured app URL",
    frontend_url: Callable[[], str] | None = None,
    hosted: Callable[[], bool] = lambda: False,
) -> dict[str, Callable[..., Any]]:
    """Register the ten ui_* tools on `mcp`, relaying through `hub`.

    Returns the registered callables keyed by tool name, so a test can drive
    them directly without an MCP transport. `docs` overrides the description
    of any tool by name (an app may want its own examples in the text agents
    read); `title_example` is the sample title quoted in the UNTITLED_TAB
    error.
    """
    tools: dict[str, Callable[..., Any]] = {}
    overrides = dict(docs or {})

    def _add(fn: Callable[..., Any], description: str) -> None:
        text = overrides.get(fn.__name__, description)
        mcp.tool(description=inspect.cleandoc(text))(fn)
        tools[fn.__name__] = fn

    # -- guards ------------------------------------------------------------
    def _require_titled(session: str | None) -> None:
        """Every driven tab must be named first. The owner juggles many tabs and
        wants agent-driven ones to be recognisable at a glance, so the gate is
        here, on the tools, not in the recipe text."""
        try:
            titled = hub.title_of(session) is not None
        except NoTabError as e:
            raise _friendly(e) from e
        if not titled:
            raise RuntimeError(
                "UNTITLED_TAB: this tab has no title yet; call ui_set_title with a "
                f"short description of what you are doing (e.g. '{title_example}') "
                "before invoking, reading or screenshotting it"
            )

    def _require_not_hosted() -> None:
        if hosted():
            raise RuntimeError("browser tab control is local-dev only (hosted mode refuses it)")

    def _require_local_macos() -> None:
        _require_not_hosted()
        if not browser._IS_MACOS:
            raise RuntimeError("browser tab control needs macOS (AppleScript drives Chrome)")

    def _app_url() -> str:
        if frontend_url is None:
            raise RuntimeError("browser tab control is not configured")
        return browser.validate_url(frontend_url().rstrip("/"))

    # -- relay tools -------------------------------------------------------
    async def ui_sessions() -> list[dict]:
        return hub.sessions()

    _add(ui_sessions, _DOC_SESSIONS)

    async def ui_actions(session: str | None = None) -> list[dict]:
        try:
            return await hub.request("manifest", {}, session_id=session)
        except (NoTabError, TabTimeoutError, ActionFailedError) as e:
            raise _friendly(e) from e

    _add(ui_actions, _DOC_ACTIONS)

    async def ui_set_title(title: str, session: str | None = None) -> dict:
        title = (title or "").strip()
        if not title:
            raise RuntimeError("title must be a non-empty string")
        try:
            sid = hub.target_id(session)
            res = await hub.request(
                "invoke", {"action": TITLE_ACTION, "args": {"title": title}}, session_id=sid
            )
        except (NoTabError, TabTimeoutError, ActionFailedError) as e:
            raise _friendly(e) from e
        shown = (res or {}).get("title") if isinstance(res, dict) else None
        hub.set_title(sid, shown or title)
        return {"session": sid, "title": shown or title}

    _add(ui_set_title, _DOC_SET_TITLE)

    async def ui_invoke(action: str, args: dict | None = None, session: str | None = None) -> object:
        if action == TITLE_ACTION:
            return await ui_set_title(str((args or {}).get("title", "")), session)
        _require_titled(session)
        try:
            return await hub.request(
                "invoke", {"action": action, "args": args or {}}, session_id=session
            )
        except (NoTabError, TabTimeoutError, ActionFailedError) as e:
            raise _friendly(e) from e

    _add(ui_invoke, _DOC_INVOKE)

    async def ui_wait(handle: str, timeout_s: float = 60.0) -> dict:
        try:
            return await hub.wait_handle(handle, timeout=timeout_s)
        except KeyError:
            raise RuntimeError(f"unknown handle: {handle} (expired or never issued)") from None

    _add(ui_wait, _DOC_WAIT)

    async def ui_read_state(key: str, session: str | None = None) -> object:
        _require_titled(session)
        try:
            return await hub.request(
                "invoke", {"action": key, "args": {}, "readOnly": True}, session_id=session
            )
        except (NoTabError, TabTimeoutError, ActionFailedError) as e:
            raise _friendly(e) from e

    _add(ui_read_state, _DOC_READ_STATE)

    async def ui_screenshot(session: str | None = None) -> list:
        _require_titled(session)
        try:
            res = await hub.request(
                "invoke",
                {"action": screenshot_action, "args": {}, "readOnly": True},
                session_id=session,
            )
        except (NoTabError, TabTimeoutError, ActionFailedError) as e:
            raise _friendly(e) from e
        caption = res.get("caption") or "screenshot"
        return [
            ImageContent(type="image", data=res["image_base64"], mimeType=res["mime"]),
            TextContent(type="text", text=f"{caption} via {res.get('via', '?')}"),
        ]

    _add(ui_screenshot, screenshot_doc or _DOC_SCREENSHOT)

    # -- browser tab control ----------------------------------------------
    async def ui_focus_tab() -> dict:
        # Checked before the HUB attempt (not just before the AppleScript
        # fallback): otherwise a hosted deployment with a connected tab and the
        # extension installed would let this tool succeed, which hosted mode
        # must never allow.
        _require_not_hosted()
        no_session_message: str | None = None
        try:
            await hub.request("invoke", {"action": "tab.focus", "args": {}})
            return {"focused": "extension"}
        except ActionFailedError as e:
            if e.code != "NO_EXTENSION":
                raise _friendly(e) from e
        except NoTabError:
            # No tab connected at all is not an extension problem; say so rather
            # than pointing at the Tab Bridge extension.
            no_session_message = "no UI session connected: open the app in a browser"
        except TabTimeoutError:
            pass
        if not browser._IS_MACOS:
            if no_session_message:
                raise RuntimeError(no_session_message)
            raise RuntimeError(
                "focusing the tab needs the Tab Bridge extension off macOS "
                "(extension/README.md); AppleScript fallback is macOS-only"
            )
        _require_local_macos()
        result = await browser._osascript(browser.focus_script(_app_url()))
        if result.startswith("FOCUSED:"):
            return {"focused": result[len("FOCUSED:"):]}
        raise RuntimeError(f"no {app_name} tab open in Chrome (ui_open_tab creates one)")

    _add(ui_focus_tab, f"""Bring the {app_name} browser tab to the front. Tries the connected tab's
    tab.focus action first (needs the Tab Bridge extension, extension/README.md,
    works on any OS), then falls back to AppleScript on macOS local dev.
    Errors if no tab is open; ui_open_tab creates one.""")

    async def ui_open_tab() -> dict:
        _require_local_macos()
        url = _app_url()
        existing = await browser._osascript(browser.focus_script(url))
        if existing.startswith("FOCUSED:"):
            return {"focused": existing[len("FOCUSED:"):]}
        await browser._osascript(browser.open_script(url))
        return {"opened": url}

    _add(ui_open_tab, f"""Open the app in Chrome (macOS local dev): focuses an existing {app_name}
    tab, else opens a new one at {app_url_label}. After opening, poll ui_sessions
    until the bridge connects (a second or two).""")

    async def ui_close_tab() -> dict:
        _require_local_macos()
        url = _app_url()
        result = await browser._osascript(browser.close_script(url))
        if result == "CLOSED":
            return {"closed": url}
        if result.startswith("MANY:"):
            raise RuntimeError(
                f"{result[len('MANY:'):]} {app_name} tabs are open; close manually or leave them"
            )
        raise RuntimeError(f"no {app_name} tab open in Chrome")

    _add(ui_close_tab, f"""Close the {app_name} browser tab (macOS local dev). Refuses when several
    matching tabs are open, so it never guesses which one to close.""")

    return tools
