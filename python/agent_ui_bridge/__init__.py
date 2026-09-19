"""Relay hub and ui_* MCP tools that let an agent drive a running web UI."""
from .hub import ActionFailedError, BridgeHub, NoTabError, TabTimeoutError
from .tools import TITLE_ACTION, register_ui_tools
from .ws import serve_tab

__all__ = [
    "ActionFailedError",
    "BridgeHub",
    "NoTabError",
    "TabTimeoutError",
    "TITLE_ACTION",
    "register_ui_tools",
    "serve_tab",
]
