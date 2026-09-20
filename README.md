# agent-ui-bridge

Let an MCP agent drive a running web app: the page registers named,
schema-validated actions, dials a WebSocket relay in your backend, and ten
`ui_*` MCP tools forward to it. A Chrome extension lets the page screenshot or
focus its own tab while backgrounded.

Nothing here knows what your app does. Actions are yours; this is the wire.

## What is in the box

| Piece | Install |
| --- | --- |
| npm package `agent-ui-bridge` (action registry, relay client, confirm gate, React modal, extension client) | `npm i github:maparham/agent-ui-bridge` |
| Python package `agent-ui-bridge` (relay hub, WebSocket pump, the `ui_*` MCP tools, a probe) | `uv add "agent-ui-bridge @ git+https://github.com/maparham/agent-ui-bridge#subdirectory=python"` |
| `extension/` Tab Bridge Chrome extension | clone this repo, then load `extension/` unpacked (it is not in the npm tarball), see `extension/README.md` |

The extension's page-side client ships in the npm package as
`agent-ui-bridge/tab-bridge` (`probeTabBridge`, `tabBridgeScreenshot`,
`tabBridgeFocus`); the React confirm modal is `agent-ui-bridge/react`.

## Frontend: register actions, start the bridge

```ts
import { registerAction, registerTabActions, restoreTabTitle, startAgentBridge } from "agent-ui-bridge";

registerAction({
  name: "cart.add",
  description: "Add a product to the cart.",
  kind: "write", // read | write | confirm
  params: {
    type: "object",
    properties: { sku: { type: "string" }, qty: { type: "number" } },
    required: ["sku"],
  },
  handler: async (args) => addToCart(String(args.sku), Number(args.qty ?? 1)),
});

registerTabActions();            // adds tab.title.set, required by ui_set_title
restoreTabTitle();               // a reloaded tab keeps its name (sessionStorage)
const stop = startAgentBridge({  // returns a stop function
  url: "ws://localhost:8000/ws/agent-ui",
  token: () => myAuthToken(),    // optional; appended as ?token=
  decorateUrl: (u) => u,         // optional last hook before dialing
});
```

A `kind: "confirm"` action executes only after a human clicks Approve. Render
the dialog once, near the root:

```tsx
import { AgentConfirmHost } from "agent-ui-bridge/react";

<AgentConfirmHost className="modal" backdropClassName="modal-backdrop" />
```

No CSS ships with it. Style your two class names plus `.modal-head`,
`.confirm-body`, `.modal-foot`, `.ghost`, `.confirm-primary` and
`.agent-confirm-warning`.

## Backend: one hub, one route, one call

```python
from agent_ui_bridge import BridgeHub, register_ui_tools, serve_tab
from mcp.server import MCPServer

HUB = BridgeHub()
mcp = MCPServer("my-app-ui")

register_ui_tools(
    mcp, HUB,
    screenshot_action="page.screenshot",   # your own read-kind action
    app_name="MyApp",                      # used in the tab-control tool text
    frontend_url=lambda: "http://localhost:5173",
    hosted=lambda: False,                  # True refuses browser tab control
)
# Optional: docs={tool_name: text} overrides any tool description agents read
# (screenshot_doc does the same for ui_screenshot); title_example is the sample
# title quoted in the UNTITLED_TAB error;
# app_url_label names the setting frontend_url comes from in error text.
# The call returns {tool_name: callable} so tests can drive the tools directly.

@app.websocket("/ws/agent-ui")
async def ws_agent_ui(websocket):
    # your own auth first
    await websocket.accept()
    try:
        await serve_tab(HUB, websocket)
    except WebSocketDisconnect:
        pass
```

The tools: `ui_sessions`, `ui_actions`, `ui_set_title`, `ui_invoke`, `ui_wait`,
`ui_read_state`, `ui_screenshot`, plus `ui_open_tab` / `ui_focus_tab` /
`ui_close_tab` (macOS local dev, AppleScript). Every driven tab must be named
with `ui_set_title` first; everything else answers `UNTITLED_TAB` until it has.

`ui_screenshot` invokes `screenshot_action` and expects
`{image_base64, mime, via, caption?}`. `caption` becomes the text line beside
the image.

## Probe

```bash
python3 -m agent_ui_bridge.probe --url http://localhost:8000/mcp
python3 -m agent_ui_bridge.probe --read-state cart.state
python3 -m agent_ui_bridge.probe --invoke cart.add --args '{"sku":"A1"}'
python3 -m agent_ui_bridge.probe --screenshot /tmp/shot.png
```

## Local development against a consumer app

```bash
cd agent-ui-bridge && npm link
cd ../your-app/frontend && npm link agent-ui-bridge
# With a linked copy, dedupe React or the confirm modal's hook throws:
# vite.config.ts -> resolve: { dedupe: ["react", "react-dom"] }

uv pip install -e ../agent-ui-bridge/python
```

## Tests

```bash
npm test                          # frontend library (vitest)
node --test extension/*.test.js   # extension
cd python && uv run pytest        # backend library
```

## License

MIT, Mahan Parham.
