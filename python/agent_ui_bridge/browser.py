"""Browser tab control for local macOS development, via AppleScript.

The bridge's page JS cannot raise its own tab (browsers block programmatic
focus-stealing), but a backend running on the same machine as Chrome can. This
is what lets an agent recover from a hidden tab without a human: focus, then
retry the screenshot.
"""
from __future__ import annotations

import asyncio
import re
import sys

_IS_MACOS = sys.platform == "darwin"

# Interpolated into AppleScript string literals, so it must not be able to
# close the quote. Plain URL characters only; no quotes, backslashes, spaces.
_SAFE_URL_RE = re.compile(r"^https?://[A-Za-z0-9.:\-_/]+$")


def validate_url(url: str) -> str:
    """The app URL, checked before it is interpolated into AppleScript."""
    if not _SAFE_URL_RE.match(url):
        raise RuntimeError(
            f"the app URL is not a plain URL, refusing to script Chrome with it: {url!r}"
        )
    return url


# A blocked macOS automation prompt makes osascript wait forever; the cap
# turns that into an actionable error instead of a hung MCP call.
_OSASCRIPT_TIMEOUT_S = 15.0

_AUTOMATION_HINT = (
    "grant the backend's host app (the terminal or editor that runs uvicorn) "
    "permission to control Google Chrome: approve the macOS prompt, or System "
    "Settings > Privacy & Security > Automation"
)


async def _osascript(script: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "osascript", "-e", script,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), _OSASCRIPT_TIMEOUT_S)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(
            f"osascript timed out after {_OSASCRIPT_TIMEOUT_S:.0f}s, likely a "
            f"pending automation permission dialog: {_AUTOMATION_HINT}"
        ) from None
    if proc.returncode != 0:
        raise RuntimeError(
            f"osascript failed: {err.decode().strip() or out.decode().strip()} ({_AUTOMATION_HINT})"
        )
    return out.decode().strip()


def focus_script(url: str) -> str:
    return f'''
tell application "Google Chrome"
  activate
  repeat with w in windows
    set i to 1
    repeat with t in tabs of w
      if URL of t starts with "{url}" then
        set active tab index of w to i
        try
          set minimized of w to false
        end try
        set index of w to 1
        return "FOCUSED:" & (URL of t)
      end if
      set i to i + 1
    end repeat
  end repeat
  return "NONE"
end tell'''


def open_script(url: str) -> str:
    return f'''
tell application "Google Chrome"
  activate
  if (count of windows) = 0 then
    make new window
  end if
  tell window 1 to make new tab with properties {{URL:"{url}"}}
  return "OPENED"
end tell'''


def close_script(url: str) -> str:
    return f'''
tell application "Google Chrome"
  set n to 0
  repeat with w in windows
    repeat with t in tabs of w
      if URL of t starts with "{url}" then set n to n + 1
    end repeat
  end repeat
  if n = 0 then return "NONE"
  if n > 1 then return "MANY:" & n
  repeat with w in windows
    repeat with t in tabs of w
      if URL of t starts with "{url}" then
        close t
        return "CLOSED"
      end if
    end repeat
  end repeat
end tell'''
