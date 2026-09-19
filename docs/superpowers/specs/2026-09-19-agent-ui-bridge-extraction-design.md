# agent-ui-bridge: extracting the generic agent UI bridge out of Chartkar

Date: 2026-09-19.

## Summary

Chartkar (repo `auto_trader`) lets MCP agents drive its running web UI: the
page registers named actions with JSON schemas, dials a WebSocket relay in the
backend, and an MCP server exposes `ui_*` tools that forward to the page. A
Chrome extension ("Tab Bridge") lets the page screenshot or focus its own tab
while backgrounded. None of that core knows anything about charts. This spec
moves the generic half into its own public repository,
`github.com/maparham/agent-ui-bridge`, checked out at
`/Users/mahmoudparham/projects/agent-ui-bridge`, and rewires Chartkar to
consume it, so any web app can get the same MCP surface by registering its
own actions.

Source of truth for the code being moved: `auto_trader/frontend/src/agent/`
(registry.ts, bridge.ts, confirm.ts, AgentConfirmHost.tsx, index.ts,
actions/tab.ts), `auto_trader/frontend/src/lib/tabBridge.ts`,
`auto_trader/backend/auto_trader/api/agent_bridge.py`, the `ui_*` tools and
browser-tab helpers in `auto_trader/backend/auto_trader/api/mcp_server.py`,
`auto_trader/backend/scripts/agent_bridge_probe.py`, and
`auto_trader/extension/`. Their tests move with them.

## Goals

- One public repo holding the frontend library, the backend library, and the
  extension, installable by a new app in a few lines each.
- Chartkar keeps working unchanged from the agent's point of view: same tool
  names, same action names, same error codes, same title gate, same
  extension behaviour. `App.tsx` is not edited (it is a foreign uncommitted
  file in the shared worktree); the import paths it uses keep resolving.
- The generic code has no Chartkar words in it: no `chart.screenshot`, no
  `epic`, no Clerk, no impersonation, no `API_BASE`.
- Hosted Chartkar builds keep working, so Chartkar depends on the package by
  git URL, not by a sibling-directory path.

## Non-goals

- Publishing to npm or PyPI. Git dependencies only.
- Changing the wire protocol, the tool names, or the extension protocol.
- Extracting Chartkar's own actions (`chart.*`, `backtest.*`, ...) or the
  direct `ta_*`/`wf_*`/`runs_*` tools. They stay in Chartkar.
- CI. Tests run locally.

## Repository layout

```
agent-ui-bridge/
  package.json            npm package "agent-ui-bridge" (root, so a git URL works)
  tsconfig.json, tsconfig.build.json, vitest.config.ts
  src/
    registry.ts           action registry (verbatim from Chartkar)
    bridge.ts             WebSocket transport, auth/url injected via options
    confirm.ts            confirm gate + a minimal Signal class
    signal.ts             Signal<T> (subscribe/set/value), copied from lib/signals.ts
    tab.ts                registerTabActions, AGENT_TAB_MARK (verbatim)
    tabBridge.ts          extension client (verbatim)
    react/AgentConfirmHost.tsx
    index.ts              re-exports (no React)
    *.test.ts             the moved vitest tests
  python/
    pyproject.toml        package "agent-ui-bridge", module agent_ui_bridge, hatchling, mcp>=2.0
    agent_ui_bridge/
      __init__.py         re-exports hub + errors + register_ui_tools + serve_tab
      hub.py              BridgeHub, _Tab, _Handle, NoTabError, TabTimeoutError, ActionFailedError (verbatim)
      ws.py               serve_tab(hub, websocket)
      tools.py            register_ui_tools(mcp, hub, options)
      browser.py          macOS/AppleScript tab control helpers
      probe.py            CLI probe (python -m agent_ui_bridge.probe)
    tests/                moved pytest files
  extension/              moved verbatim, including README.md and tests
  README.md               what it is, install for a new app, protocol, extension install
  LICENSE                 MIT, Mahan Parham
  docs/superpowers/{specs,plans}/
```

## Frontend library (`agent-ui-bridge`)

`package.json`: `"name": "agent-ui-bridge"`, `"type": "module"`, `"exports"`:
`"."` → `dist/index.js`, `"./react"` → `dist/react/AgentConfirmHost.js`,
`"./tab-bridge"` → `dist/tabBridge.js`, each with `types`. `"files": ["dist"]`.
`"scripts"`: `build` = `tsc -p tsconfig.build.json`, `prepare` = `npm run build`
(npm runs `prepare` when installing from a git URL, so `dist/` is never
committed), `test` = `vitest run`. `peerDependencies`: `react >=18` (optional,
only for `./react`). devDependencies: typescript, vitest, jsdom, @types/react.

Public API (from `.`):

```ts
// registry.ts, unchanged
export type { ActionKind, ParamProperty, ParamSchema, ActionContext, AgentAction, ActionManifestEntry };
export { ActionError, registerAction, getAction, listActions, validateArgs, invokeAction, clearRegistryForTest };
// bridge.ts
export interface BridgeOptions {
  url: string;                                   // full ws(s) URL, e.g. ws://localhost:8000/ws/agent-ui
  token?: () => string | null | Promise<string | null>;  // appended as ?token=
  decorateUrl?: (url: string) => string;         // last hook before dialing
}
export function startAgentBridge(opts: BridgeOptions): () => void;
export function handleFrame(frame: InboundFrame, send: (f: object) => void): Promise<void>;
export type { InboundFrame };
// confirm.ts + signal.ts
export { Signal, agentConfirmSignal, requestAgentConfirm, resolveAgentConfirm };
export type { AgentConfirmState };
// tab.ts
export { registerTabActions, AGENT_TAB_MARK };
```

`./react`: `AgentConfirmHost({ className = "agent-confirm", backdropClassName =
"agent-confirm-backdrop" })`. Ships no CSS. Chartkar passes `modal` and
`modal-backdrop`.

`./tab-bridge`: `TabBridgeError`, `TabBridgeHello`, `ScreenshotArgs`,
`ScreenshotResult`, `probeTabBridge`, `tabBridgeScreenshot`, `tabBridgeFocus`,
`invalidateTabBridge`, `resetTabBridgeForTest` (verbatim).

Behavioural change in `bridge.ts` only: the three Chartkar imports
(`API_BASE`, `getAuthToken`/`hasTokenGetter`, `withImpersonation`) become the
options above. Reconnect/backoff, frame handling, handle events: unchanged.

## Backend library (`agent_ui_bridge`)

- `hub.py`: `agent_bridge.py` verbatim minus the module-level `HUB`
  singleton (the app owns its hub instance).
- `ws.py`: `async def serve_tab(hub: BridgeHub, websocket) -> None`: the
  accept-free loop `sid = hub.register(websocket.send_json)`, then
  `hub.on_frame(sid, await websocket.receive_json())` until disconnect,
  `finally: hub.unregister(sid)`. The caller does auth and `accept()`.
- `tools.py`: `register_ui_tools(mcp, hub, *, screenshot_action: str =
  "page.screenshot", frontend_url: Callable[[], str] | None = None, hosted:
  Callable[[], bool] = lambda: False) -> None`. Registers, on the given
  `MCPServer`, exactly the tools Chartkar has today with the same names,
  docstrings, signatures and error strings: `ui_sessions`, `ui_actions`,
  `ui_set_title`, `ui_invoke`, `ui_wait`, `ui_read_state`, `ui_screenshot`,
  `ui_open_tab`, `ui_focus_tab`, `ui_close_tab`. `TITLE_ACTION`,
  `_require_titled`, `_friendly` move here. `ui_screenshot` invokes
  `screenshot_action` and builds its text line from `res["caption"]` when
  present, otherwise `"screenshot"`, then appends ` via {res.get("via","?")}`.
  `frontend_url` is required by the three browser-tab tools (they raise
  `RuntimeError("browser tab control is not configured")` without it);
  `hosted()` true makes them refuse exactly as `_require_not_hosted` does today.
- `browser.py`: `_osascript`, the three AppleScript builders,
  `_require_local_macos`, moved verbatim.
- `probe.py`: `scripts/agent_bridge_probe.py` moved; default URL
  `http://localhost:8000/mcp`, overridable with `--url`.
- Dependency: `mcp>=2.0` only. `serve_tab` is duck-typed over the websocket.

## Extension

`extension/` moves verbatim (all nine files). README gains one line saying
which repo it lives in. The install path in Chartkar docs changes to this
repo.

## Chartkar rewiring (repo `auto_trader`)

Dependencies:
- `frontend/package.json`: `"agent-ui-bridge": "github:maparham/agent-ui-bridge"`.
- `backend/pyproject.toml`: `"agent-ui-bridge"` in dependencies and
  `[tool.uv.sources] agent-ui-bridge = { git = "https://github.com/maparham/agent-ui-bridge", subdirectory = "python" }`.
- Local iteration: `npm link` / `uv pip install -e ../../agent-ui-bridge/python`
  documented in the new repo's README.

Frontend shims (keep every path `App.tsx` imports):
- `src/agent/registry.ts`: `export * from "agent-ui-bridge"` restricted to the
  registry names (explicit named re-exports).
- `src/agent/confirm.ts`: named re-exports of the confirm API.
- `src/agent/AgentConfirmHost.tsx`: default export rendering the package
  component with `className="modal" backdropClassName="modal-backdrop"`.
- `src/agent/actions/tab.ts`: re-export `registerTabActions`, `AGENT_TAB_MARK`.
- `src/agent/index.ts`: keeps `agentBridgeEnabled()` and `initAgentBridge()`;
  the latter registers Chartkar's action modules plus `registerTabActions()`
  and calls `startAgentBridge({ url: API_BASE.replace(/^http/, "ws") + "/ws/agent-ui", token: hasTokenGetter() ? getAuthToken : undefined, decorateUrl: withImpersonation })`.
- `src/lib/tabBridge.ts`: `export * from "agent-ui-bridge/tab-bridge"`.
- `src/agent/bridge.ts` and the moved tests (`registry.test.ts`,
  `bridge.test.ts`, `confirm.test.ts`, `AgentConfirmHost.test.tsx`,
  `actions/tab.test.ts`, `lib/tabBridge.test.ts`) are deleted from Chartkar.
  `chart.test.ts` keeps `vi.mock("../../lib/tabBridge")`, which still works
  against the shim.
- `src/agent/actions/chart.ts`: `chart.screenshot` result gains
  `caption: \`${epic} ${resolution} (cell ${cellId})\``, preserving the
  existing fields.

Backend shims:
- `api/agent_bridge.py`: `from agent_ui_bridge.hub import BridgeHub, NoTabError, TabTimeoutError, ActionFailedError` and `HUB = BridgeHub()`.
- `api/routers/agent.py`: after its auth checks and `accept()`, `await serve_tab(HUB, websocket)`.
- `api/mcp_server.py`: drops the `ui_*` functions, `_require_titled`,
  `TITLE_ACTION`, `_require_not_hosted`, `_require_local_macos`,
  `_osascript`, the AppleScript builders and `_frontend_url`; calls
  `register_ui_tools(mcp, HUB, screenshot_action="chart.screenshot", frontend_url=lambda: os.environ.get("FRONTEND_URL", "http://localhost:5173"), hosted=lambda: bool(os.environ.get("CLERK_JWKS_URL")))`
  at import time. Direct tools, `_friendly` users, `mcp_http_app`,
  `mcp_session`, `configure_direct_tools` stay.
- `scripts/agent_bridge_probe.py` becomes a two-line wrapper that runs
  `agent_ui_bridge.probe.main()`.
- Tests: `test_agent_bridge_hub.py`, `test_mcp_tools.py`,
  `test_mcp_browser_tabs.py`, `test_mcp_screenshot.py` move to the package
  (imports adjusted; the screenshot test asserts the `caption` path). Chartkar
  keeps `test_mcp_direct_tools.py` and gains one small test asserting the
  Chartkar `mcp` instance lists the ten `ui_*` tools plus its direct tools.
- `CLAUDE.md`: the Tab Bridge paragraph points at the new repo for the
  extension and names the package; the probe command becomes
  `python3 -m agent_ui_bridge.probe`.
- `extension/` is deleted from Chartkar in the same commit that adds the
  dependency.

## Ordering constraint

Chartkar's git dependencies only resolve once the new repo is on GitHub.
So: build and test the new repo, push it (public repo, user-approved), then
rewire Chartkar. Chartkar changes are committed on `main`, never pushed.

## Testing

- New repo: `npm test` (vitest, jsdom) for src; `node --test extension/*.test.js`;
  `cd python && uv run pytest` for the moved backend tests.
- Chartkar: `npx vitest run src/agent src/lib/tabBridge.test.ts` (only the
  affected files, never the full suite); `cd backend && uv run pytest tests/test_mcp_direct_tools.py tests/test_mcp_registration.py`;
  `npx tsc -b` parity check; then a live check with the running backend:
  `ui_sessions`, `ui_set_title`, `ui_screenshot` reports `via extension`.

## Security

Unchanged: the hub only relays to the requesting session, the extension only
targets the requester's tab, the MCP endpoint keeps the SDK's localhost Host
allowlist, and the `ui_*` tools keep the UNTITLED_TAB gate.
