# agent-ui-bridge Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Chartkar's generic agent UI bridge (action registry, WebSocket relay, `ui_*` MCP tools, Tab Bridge extension) into the public repo `maparham/agent-ui-bridge`, then rewire Chartkar to consume it with no change to the agent-visible surface.

**Architecture:** One repository holds three shippable pieces: an npm package (`agent-ui-bridge`, root `package.json`, TypeScript compiled to `dist/` by a `prepare` script so a git URL install works), a Python package (`python/`, hatchling, module `agent_ui_bridge`), and the Chrome extension (`extension/`). Everything Chartkar-specific is injected: the frontend bridge takes a URL, a token getter and a URL decorator as options; the backend `register_ui_tools(mcp, hub, ...)` takes the screenshot action name, the app name, the frontend URL resolver and a hosted predicate. Chartkar keeps thin shim modules at every import path `App.tsx` already uses, so `App.tsx` is never edited.

**Tech Stack:** Node 25, npm with package-lock, TypeScript ~6.0 (`moduleResolution: "bundler"`), vitest 4 + jsdom, React 19 (optional peer dep). Python >=3.12, uv + hatchling, `mcp>=2.0` (`from mcp.server import MCPServer`), pytest + anyio. Chrome MV3 extension, plain JS, `node --test`.

**Spec:** `/Users/mahmoudparham/projects/agent-ui-bridge/docs/superpowers/specs/2026-09-19-agent-ui-bridge-extraction-design.md`

## Global Constraints

- No em dashes anywhere: never `—` or `--` in prose, docs, comments or UI strings. Split the sentence instead. (Code that already contains them stays as it is when copied verbatim; do not introduce new ones.)
- No Chartkar-specific words in the package code: no `chart`, `epic`, `Clerk`, `impersonation`, `API_BASE`, `Chartkar`, `backtest`, `US100`. Everything app-specific is an injected option.
- Tool names, action names, error codes and error message strings stay identical to today, as seen by an agent driving Chartkar. The ten tools are `ui_sessions`, `ui_actions`, `ui_set_title`, `ui_invoke`, `ui_wait`, `ui_read_state`, `ui_screenshot`, `ui_open_tab`, `ui_focus_tab`, `ui_close_tab`. The `ui_*` docstrings agents read stay byte-identical for Chartkar (achieved via the `app_name` and `screenshot_doc` options).
- `frontend/src/App.tsx` is NEVER edited. Neither are `frontend/src/IndicatorSettings.tsx`, `frontend/src/indicatorSettings/DefaultsMenu*.tsx`, `frontend/src/mobile/MobileModals.tsx`, `frontend/src/App.css`, `frontend/src/lib/indicatorMeta.ts`. They are other people's uncommitted files in a shared worktree.
- Never run the full Chartkar frontend test suite. Only the named files. Never `git stash`, `git clean`, `git checkout --` or `git restore` in the Chartkar worktree.
- Every Chartkar commit stages by explicit path (`git add <path> <path>`), never `git add -A` / `git add .`. Commit to the current branch; never create a branch.
- Chartkar is NEVER pushed. The new repo is pushed exactly once at Task 5, and again at the end of Task 8 only if a later task changed a file in it.
- Chartkar commit messages end with exactly these two lines:
  ```
  Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01SoZ7wfsyG7HZxLXuC4au8p
  ```
- Repo paths: new repo `/Users/mahmoudparham/projects/agent-ui-bridge` (git init'd, branch `main`, no commits yet, only `docs/`). Chartkar `/Users/mahmoudparham/projects/auto_trader`.

## File Structure

New repo:

| Path | Responsibility |
| --- | --- |
| `package.json`, `tsconfig.json`, `tsconfig.build.json`, `vitest.config.ts`, `.gitignore`, `LICENSE` | npm package scaffolding |
| `src/registry.ts` | typed action registry (verbatim move) |
| `src/signal.ts` | `Signal<T>` (copied from Chartkar `lib/signals.ts`) |
| `src/confirm.ts` | confirm gate (verbatim except its Signal import) |
| `src/bridge.ts` | WebSocket relay client; the only behavioural change (injected options) |
| `src/tab.ts` | `registerTabActions`, `AGENT_TAB_MARK` (verbatim except import path) |
| `src/tabBridge.ts` | Tab Bridge extension client (verbatim except header comment) |
| `src/react/AgentConfirmHost.tsx` | the confirm modal, class names as props |
| `src/index.ts` | public re-exports, no React |
| `src/*.test.ts` | moved vitest tests |
| `python/pyproject.toml` | Python package metadata |
| `python/agent_ui_bridge/{__init__,hub,ws,tools,browser,probe}.py` | backend library |
| `python/tests/*.py` | moved pytest files |
| `extension/` | nine files, moved verbatim except two README lines |
| `README.md` | what it is, install, protocol |

Chartkar after rewiring: `src/agent/{registry,confirm,index}.ts`, `src/agent/AgentConfirmHost.tsx`, `src/agent/actions/tab.ts`, `src/lib/tabBridge.ts` become shims; `src/agent/bridge.ts` is deleted. `api/agent_bridge.py` becomes a hub instance; `api/mcp_server.py` keeps only the direct tools plus one `register_ui_tools(...)` call.

---

### Task 1: New repo scaffolding

**Files:**
- Create: `/Users/mahmoudparham/projects/agent-ui-bridge/package.json`
- Create: `/Users/mahmoudparham/projects/agent-ui-bridge/tsconfig.json`
- Create: `/Users/mahmoudparham/projects/agent-ui-bridge/tsconfig.build.json`
- Create: `/Users/mahmoudparham/projects/agent-ui-bridge/vitest.config.ts`
- Create: `/Users/mahmoudparham/projects/agent-ui-bridge/.gitignore`
- Create: `/Users/mahmoudparham/projects/agent-ui-bridge/LICENSE`

**Interfaces:**
- Consumes: nothing.
- Produces: an npm project named `agent-ui-bridge` whose `npm run build` emits `dist/index.js`, `dist/react/AgentConfirmHost.js`, `dist/tabBridge.js` with `.d.ts` beside each; `npm test` runs vitest over `src/**/*.test.ts(x)`.

- [ ] **Step 1: Write `package.json`**

`prepare` is what makes `"agent-ui-bridge": "github:maparham/agent-ui-bridge"` work: npm runs it after installing from a git URL, which is why `dist/` is never committed. npm installs the package's own devDependencies while running `prepare`, so `typescript` MUST be a devDependency or the git install fails with "tsc: not found".

```json
{
  "name": "agent-ui-bridge",
  "version": "0.1.0",
  "description": "Let MCP agents drive a running web UI: a typed action registry, a WebSocket relay client, and the ui_* MCP tools.",
  "license": "MIT",
  "author": "Mahan Parham",
  "repository": { "type": "git", "url": "git+https://github.com/maparham/agent-ui-bridge.git" },
  "type": "module",
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": { "types": "./dist/index.d.ts", "default": "./dist/index.js" },
    "./react": { "types": "./dist/react/AgentConfirmHost.d.ts", "default": "./dist/react/AgentConfirmHost.js" },
    "./tab-bridge": { "types": "./dist/tabBridge.d.ts", "default": "./dist/tabBridge.js" }
  },
  "files": ["dist"],
  "scripts": {
    "build": "tsc -p tsconfig.build.json",
    "prepare": "npm run build",
    "test": "vitest run",
    "typecheck": "tsc -p tsconfig.json --noEmit"
  },
  "peerDependencies": { "react": ">=18" },
  "peerDependenciesMeta": { "react": { "optional": true } },
  "devDependencies": {
    "@types/react": "^19.2.14",
    "jsdom": "^29.1.1",
    "react": "^19.2.6",
    "typescript": "~6.0.2",
    "vitest": "^4.1.9"
  }
}
```

- [ ] **Step 2: Write `tsconfig.json`** (dev + typecheck, includes tests)

```json
{
  "compilerOptions": {
    "target": "es2023",
    "lib": ["ES2023", "DOM"],
    "module": "esnext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "skipLibCheck": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force",
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "noEmit": true
  },
  "include": ["src", "vitest.config.ts"]
}
```

- [ ] **Step 3: Write `tsconfig.build.json`** (emits `dist/`, excludes tests)

```json
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "noEmit": false,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src"],
  "exclude": ["src/**/*.test.ts", "src/**/*.test.tsx"]
}
```

- [ ] **Step 4: Write `vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";

// .test.ts files are pure logic and run in the fast `node` environment; the
// DOM-touching ones (tab.test.ts, tabBridge.test.ts) declare
// `// @vitest-environment jsdom` on their first line.
export default defineConfig({
  test: {
    include: ["src/**/*.{test.ts,test.tsx}"],
    environment: "node",
  },
});
```

- [ ] **Step 5: Write `.gitignore`**

```gitignore
node_modules/
dist/
.venv/
__pycache__/
*.pyc
.pytest_cache/
.superpowers/
```

- [ ] **Step 6: Write `LICENSE`** (MIT, Mahan Parham)

```
MIT License

Copyright (c) 2026 Mahan Parham

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 7: Install and verify the toolchain runs**

```bash
cd /Users/mahmoudparham/projects/agent-ui-bridge && npm install
```
Expected: creates `package-lock.json` and `node_modules/`. `npm run build` will fail until Task 2 adds `src/`, which is expected at this point; do not run it yet.

- [ ] **Step 8: No commit yet**

The new repo has no commits; the first commit is Task 5, after the code exists and the tests are green.

---

### Task 2: Frontend library and its tests

**Files:**
- Create: `src/signal.ts`, `src/registry.ts`, `src/confirm.ts`, `src/bridge.ts`, `src/tab.ts`, `src/tabBridge.ts`, `src/react/AgentConfirmHost.tsx`, `src/index.ts`
- Create (moved tests): `src/registry.test.ts`, `src/confirm.test.ts`, `src/bridge.test.ts`, `src/tab.test.ts`, `src/tabBridge.test.ts`
- Read (sources in Chartkar): `/Users/mahmoudparham/projects/auto_trader/frontend/src/agent/{registry,confirm,bridge}.ts`, `.../agent/actions/tab.ts`, `.../agent/AgentConfirmHost.tsx`, `.../lib/tabBridge.ts`, `.../lib/signals.ts`

**Interfaces:**
- Consumes: the scaffolding from Task 1.
- Produces (importable from `"agent-ui-bridge"`):
  - types `ActionKind`, `ParamProperty`, `ParamSchema`, `ActionContext`, `AgentAction`, `ActionManifestEntry`, `AgentConfirmState`, `InboundFrame`, `BridgeOptions`
  - values `ActionError`, `registerAction`, `getAction`, `listActions`, `validateArgs`, `invokeAction`, `clearRegistryForTest`, `Signal`, `agentConfirmSignal`, `requestAgentConfirm`, `resolveAgentConfirm`, `registerTabActions`, `AGENT_TAB_MARK`, `startAgentBridge`, `handleFrame`
  - from `"agent-ui-bridge/react"`: named and default export `AgentConfirmHost({ className?, backdropClassName? })`
  - from `"agent-ui-bridge/tab-bridge"`: `TabBridgeError`, `probeTabBridge`, `tabBridgeScreenshot`, `tabBridgeFocus`, `invalidateTabBridge`, `resetTabBridgeForTest`, types `TabBridgeHello`, `ScreenshotArgs`, `ScreenshotResult`
  - `startAgentBridge(opts: BridgeOptions): () => void` where
    ```ts
    interface BridgeOptions {
      url: string;
      token?: () => string | null | Promise<string | null>;
      decorateUrl?: (url: string) => string;
    }
    ```

- [ ] **Step 1: Copy the four unchanged-logic modules**

Copy verbatim (byte for byte, comments included), then apply ONLY the import-path edit named for each:

| New file | Copy verbatim from | Edit after copying |
| --- | --- | --- |
| `src/registry.ts` | `auto_trader/frontend/src/agent/registry.ts` | none |
| `src/confirm.ts` | `auto_trader/frontend/src/agent/confirm.ts` | `import { Signal } from "../lib/signals";` becomes `import { Signal } from "./signal";` |
| `src/tab.ts` | `auto_trader/frontend/src/agent/actions/tab.ts` | `from "../registry"` becomes `from "./registry"` |
| `src/tabBridge.ts` | `auto_trader/frontend/src/lib/tabBridge.ts` | the first header-comment line `// Page-side client for the Tab Bridge Chrome extension (extension/ at the` / `// repo root). The extension lets this page screenshot or focus its own tab` becomes `// Page-side client for the Tab Bridge Chrome extension (extension/ in this` / `// repo). The extension lets this page screenshot or focus its own tab` |

```bash
cd /Users/mahmoudparham/projects/agent-ui-bridge
mkdir -p src/react
CK=/Users/mahmoudparham/projects/auto_trader/frontend/src
cp "$CK/agent/registry.ts" src/registry.ts
cp "$CK/agent/confirm.ts" src/confirm.ts
cp "$CK/agent/actions/tab.ts" src/tab.ts
cp "$CK/lib/tabBridge.ts" src/tabBridge.ts
```

- [ ] **Step 2: Write `src/signal.ts`**

The `Signal` class copied out of Chartkar's `lib/signals.ts` (which also holds Chartkar's app signals; only the class moves).

```ts
// Tiny observable: a value plus subscribers. Copied out of the host app so the
// confirm gate can publish its pending request without pulling in a framework.

type Listener<T> = (value: T) => void;

export class Signal<T> {
  private listeners = new Set<Listener<T>>();
  value: T;
  constructor(initial: T) {
    this.value = initial;
  }
  set(value: T): void {
    this.value = value;
    this.listeners.forEach((l) => l(value));
  }
  subscribe(fn: Listener<T>): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }
}
```

- [ ] **Step 3: Write `src/bridge.ts`**

`handleFrame` and the whole reconnect/backoff/drain machinery are verbatim from `auto_trader/frontend/src/agent/bridge.ts`. The ONLY changes: the three Chartkar imports are gone, `startAgentBridge` takes `BridgeOptions`, the URL is `opts.url` (no `API_BASE`), `withImpersonation(...)` becomes `decorateUrl(...)`, and the token branch uses `opts.token`. The token call is allowed to answer synchronously so a host with no auth configured dials in the same tick it does today.

```ts
// WebSocket client side of the agent UI bridge. Connects to the host app's
// relay endpoint, executes registry actions on request, and streams progress
// for long-running invocations. Frame shapes are mirrored in the Python
// package's hub.py.
import {
  ActionError, getAction, invokeAction, listActions, validateArgs,
} from "./registry";
import { requestAgentConfirm } from "./confirm";

export interface InboundFrame {
  id: string;
  op: "manifest" | "invoke" | "abort";
  action?: string;
  args?: Record<string, unknown>;
  handle?: string;
  /** ui_read_state sets this: only read-kind actions may run. */
  readOnly?: boolean;
}

export interface BridgeOptions {
  /** Full ws(s) URL of the relay, e.g. ws://localhost:8000/ws/agent-ui */
  url: string;
  /** Resolves the auth token appended as ?token=. May answer synchronously. */
  token?: () => string | null | Promise<string | null>;
  /** Last hook before dialing: rewrite the final URL (query params etc). */
  decorateUrl?: (url: string) => string;
}

// Long-running invocations in flight, keyed by handle (= the invoke frame id).
const running = new Map<string, AbortController>();

export async function handleFrame(frame: InboundFrame, send: (f: object) => void): Promise<void> {
  if (frame.op === "manifest") {
    send({ id: frame.id, ok: true, result: listActions() });
    return;
  }
  if (frame.op === "abort") {
    const ctl = frame.handle ? running.get(frame.handle) : undefined;
    ctl?.abort();
    send({ id: frame.id, ok: true, result: { aborted: Boolean(ctl) } });
    return;
  }
  // op === "invoke"
  const name = frame.action ?? "";
  const args = frame.args ?? {};
  const action = getAction(name);

  // ui_read_state must never mutate anything. Checked before validation, the
  // confirm gate, the handler, and the long-running branch, so a write action
  // named by a read-only frame is refused inline and never starts.
  if (frame.readOnly && action?.kind !== "read") {
    send({
      id: frame.id,
      ok: false,
      error: {
        code: "NOT_READ_ACTION",
        message: `${name || "action"} is not a read-kind action; use ui_invoke`,
      },
    });
    return;
  }

  const ctl = new AbortController();

  const runIt = async () => {
    // Validate args before confirm gate so malformed confirm-kind invokes fail
    // INVALID_ARGS without popping a nonsense dialog
    if (action) {
      const problem = validateArgs(action.params, args);
      if (problem) throw new ActionError("INVALID_ARGS", problem, action.params);
    }
    if (action?.kind === "confirm") {
      // confirmContext adds display-only facts the agent never sent but the user
      // must see before approving. Merged into the dialog payload only: `args`
      // itself stays exactly what was validated, so the handler is never handed
      // a key outside its schema.
      const approved = await requestAgentConfirm({
        action: name,
        description: action.description,
        args: { ...args, ...(action.confirmContext?.() ?? {}) },
        warning: action.confirmWarning?.() ?? null,
        // Abort dismisses the dialog as rejected. Without this the agent's
        // invocation could be aborted (or the socket drop) while the dialog
        // stayed open, and a later Approve would still run the handler.
        signal: ctl.signal,
      });
      if (!approved) throw new ActionError("REJECTED", "user rejected or confirm timed out");
    }
    return invokeAction(name, args, {
      progress: (payload) => send({ handle: frame.id, event: "progress", payload }),
      signal: ctl.signal,
    });
  };

  // Confirm-kind actions relay as long-running even when they are quick: the
  // dialog can sit open for up to 120s while the backend's HUB.request times
  // out at 30s. On the fast path that dropped the reply and a later Approve
  // would still execute an action the agent had already been told failed.
  // Acking a handle immediately makes the relay timeout irrelevant: the
  // outcome reaches the agent through ui_wait, whenever the user decides.
  if (action?.longRunning || action?.kind === "confirm") {
    running.set(frame.id, ctl);
    send({ id: frame.id, ok: true, handle: frame.id });
    // Fire-and-stream: completion goes out as a handle event, not a reply.
    runIt()
      .then((result) => send({ handle: frame.id, event: "done", payload: result }))
      .catch((e) => send({
        handle: frame.id, event: "error",
        payload: { message: e instanceof Error ? e.message : String(e), code: e instanceof ActionError ? e.code : undefined },
      }))
      .finally(() => running.delete(frame.id));
    return;
  }

  try {
    const result = await runIt();
    send({ id: frame.id, ok: true, result });
  } catch (e) {
    const err = e instanceof ActionError
      ? { code: e.code, message: e.message, expectedSchema: e.expectedSchema }
      : { code: "ACTION_FAILED", message: e instanceof Error ? e.message : String(e) };
    send({ id: frame.id, ok: false, error: err });
  }
}

/** Connect to the relay; auto-reconnects with backoff. Returns a stop fn. */
export function startAgentBridge(opts: BridgeOptions): () => void {
  const { url, token: getToken, decorateUrl } = opts;
  let ws: WebSocket | null = null;
  let stopped = false;
  let retryMs = 1000;
  let stabilityTimer: ReturnType<typeof setTimeout> | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  // Shared by the disconnect and stop paths: nothing in flight can outlive the
  // socket, and no timer may fire after the bridge is gone.
  const drain = () => {
    if (stabilityTimer) { clearTimeout(stabilityTimer); stabilityTimer = null; }
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
    for (const ctl of running.values()) ctl.abort();
    running.clear();
  };

  const connect = () => {
    if (stopped) return;
    const dial = (token: string | null) => {
      const dialUrl = token ? `${url}?token=${encodeURIComponent(token)}` : url;
      ws = new WebSocket(decorateUrl ? decorateUrl(dialUrl) : dialUrl);
      ws.onopen = () => {
        // Only reset retryMs after connection has been stable for 5s
        // (avoids backoff reset on handshake-then-close storms)
        stabilityTimer = setTimeout(() => {
          retryMs = 1000;
          stabilityTimer = null;
        }, 5000);
      };
      ws.onmessage = (ev) => {
        let frame: InboundFrame;
        try { frame = JSON.parse(ev.data); } catch { return; }
        void handleFrame(frame, (f) => {
          if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(f));
        });
      };
      ws.onclose = () => {
        if (stopped) return; // stop() already drained
        // Clear timers + abort in-flight invocations, then back off and retry.
        drain();
        reconnectTimer = setTimeout(connect, retryMs);
        retryMs = Math.min(retryMs * 2, 15_000);
      };
    };
    if (!getToken) {
      dial(null);
      return;
    }
    // A token getter may answer synchronously (a host with no auth configured
    // returns null on the spot): dial in the same tick then, so behaviour is
    // byte-identical to a bridge built without a getter at all. A promise is
    // awaited; a rejection (network blip, torn-down session) dials tokenless
    // rather than leaving the handle dead, and the backend refusing the socket
    // hands the retry to the existing onclose/backoff machinery.
    let answer: string | null | Promise<string | null>;
    try {
      answer = getToken();
    } catch {
      answer = null;
    }
    if (answer === null || typeof answer === "string") {
      dial(answer);
      return;
    }
    void answer.then((t) => t, () => null).then((t) => {
      if (stopped) return;
      dial(t);
    });
  };
  connect();
  // stop() sets `stopped` before closing, so onclose early-returns: drain here
  // or in-flight invocations and timers would outlive the bridge.
  return () => { stopped = true; drain(); ws?.close(); };
}
```

- [ ] **Step 4: Write `src/react/AgentConfirmHost.tsx`**

Copied from `auto_trader/frontend/src/agent/AgentConfirmHost.tsx`. The two OUTER class names become props (Chartkar passes `modal` / `modal-backdrop`); the inner class names stay exactly as they are so Chartkar renders identically. The package ships no CSS.

```tsx
// Renders the pending agent confirm request (if any) as a blocking modal.
// Approve runs the parked action handler; Reject (or timeout, handled in
// confirm.ts) refuses it. No CSS ships with this: pass the host app's own
// modal class names, and style .modal-head / .confirm-body / .modal-foot /
// .ghost / .confirm-primary / .agent-confirm-warning there too.
import { useSyncExternalStore } from "react";
import { agentConfirmSignal, resolveAgentConfirm } from "../confirm";

export interface AgentConfirmHostProps {
  className?: string;
  backdropClassName?: string;
}

export function AgentConfirmHost({
  className = "agent-confirm",
  backdropClassName = "agent-confirm-backdrop",
}: AgentConfirmHostProps) {
  const state = useSyncExternalStore(
    (cb) => agentConfirmSignal.subscribe(cb),
    () => agentConfirmSignal.value,
  );
  if (!state) return null;
  return (
    <div className={backdropClassName} onMouseDown={() => resolveAgentConfirm(false)}>
      <div className={className} onMouseDown={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span>Agent requests: {state.action}</span>
        </div>
        <div className="confirm-body">
          {/* Above the description, not buried in the args dump: this exists for
              the case where the args look completely ordinary and the danger is
              in the surrounding state. */}
          {state.warning && <p className="agent-confirm-warning">{state.warning}</p>}
          <p style={{ margin: 0 }}>{state.description}</p>
          <pre style={{ maxHeight: 200, overflow: "auto", fontSize: 12, margin: "8px 0 0 0" }}>
            {JSON.stringify(state.args, null, 2)}
          </pre>
        </div>
        <div className="modal-foot">
          <button className="ghost" onClick={() => resolveAgentConfirm(false)}>Reject</button>
          <button className="confirm-primary" onClick={() => resolveAgentConfirm(true)}>Approve</button>
        </div>
      </div>
    </div>
  );
}

export default AgentConfirmHost;
```

- [ ] **Step 5: Write `src/index.ts`**

No React import anywhere in this graph: a host that never renders the dialog must not need React installed.

```ts
// Public entry point. React lives behind the "agent-ui-bridge/react" export and
// the extension client behind "agent-ui-bridge/tab-bridge", so importing this
// module pulls in neither.
export type {
  ActionKind, ParamProperty, ParamSchema, ActionContext, AgentAction, ActionManifestEntry,
} from "./registry";
export {
  ActionError, registerAction, getAction, listActions, validateArgs, invokeAction,
  clearRegistryForTest,
} from "./registry";

export type { InboundFrame, BridgeOptions } from "./bridge";
export { startAgentBridge, handleFrame } from "./bridge";

export { Signal } from "./signal";
export type { AgentConfirmState } from "./confirm";
export { agentConfirmSignal, requestAgentConfirm, resolveAgentConfirm } from "./confirm";

export { registerTabActions, AGENT_TAB_MARK } from "./tab";
```

- [ ] **Step 6: Move the five test files**

```bash
cd /Users/mahmoudparham/projects/agent-ui-bridge
CK=/Users/mahmoudparham/projects/auto_trader/frontend/src
cp "$CK/agent/registry.test.ts" src/registry.test.ts
cp "$CK/agent/confirm.test.ts" src/confirm.test.ts
cp "$CK/agent/bridge.test.ts" src/bridge.test.ts
cp "$CK/agent/actions/tab.test.ts" src/tab.test.ts
cp "$CK/lib/tabBridge.test.ts" src/tabBridge.test.ts
```

Then apply exactly these edits and nothing else:

1. `src/registry.test.ts`: no edit (it already imports `"./registry"`).
2. `src/confirm.test.ts`: no edit (already imports `"./confirm"`).
3. `src/bridge.test.ts`: the one call site changes. Replace
   ```ts
      const stop = startAgentBridge("ws://stub/ws");
   ```
   with
   ```ts
      const stop = startAgentBridge({ url: "ws://stub/ws" });
   ```
4. `src/tab.test.ts`: change the two imports and the placeholder document title. Replace
   ```ts
   import { clearRegistryForTest, listActions, invokeAction } from "../registry";
   import { registerTabActions, AGENT_TAB_MARK } from "./tab";
   ```
   with
   ```ts
   import { clearRegistryForTest, listActions, invokeAction } from "./registry";
   import { registerTabActions, AGENT_TAB_MARK } from "./tab";
   ```
   and replace both occurrences of `document.title = "Chartkar";` with `document.title = "host app";`.
5. `src/tabBridge.test.ts`: replace the first line
   ```ts
   // frontend/src/lib/tabBridge.test.ts
   ```
   with
   ```ts
   // src/tabBridge.test.ts
   ```

- [ ] **Step 7: Run the tests**

Run: `cd /Users/mahmoudparham/projects/agent-ui-bridge && npm test`
Expected: PASS, five files. If `bridge.test.ts` fails on `vi.mock("./confirm")`, confirm `src/confirm.ts` exists at that exact path; the mock resolves relative to the test file.

- [ ] **Step 8: Run the build**

Run: `cd /Users/mahmoudparham/projects/agent-ui-bridge && npm run build`
Expected: exit 0, and `dist/index.js`, `dist/index.d.ts`, `dist/react/AgentConfirmHost.js`, `dist/tabBridge.js` all exist.

```bash
ls dist dist/react
```

- [ ] **Step 9: No commit yet** (first commit is Task 5)

---

### Task 3: Python package

**Files:**
- Create: `python/pyproject.toml`
- Create: `python/agent_ui_bridge/__init__.py`, `hub.py`, `ws.py`, `browser.py`, `tools.py`, `probe.py`
- Create (moved tests): `python/tests/test_hub.py`, `python/tests/test_ui_tools.py`, `python/tests/test_browser_tabs.py`, `python/tests/test_screenshot.py`
- Read: `auto_trader/backend/auto_trader/api/agent_bridge.py`, `.../api/mcp_server.py`, `auto_trader/backend/scripts/agent_bridge_probe.py`, `auto_trader/backend/tests/test_agent_bridge_hub.py`, `test_mcp_tools.py`, `test_mcp_browser_tabs.py`, `test_mcp_screenshot.py`

**Interfaces:**
- Consumes: nothing from Task 2 (independent language).
- Produces:
  - `agent_ui_bridge.hub`: `BridgeHub`, `NoTabError`, `TabTimeoutError`, `ActionFailedError`
  - `agent_ui_bridge.ws.serve_tab(hub: BridgeHub, websocket) -> None`
  - `agent_ui_bridge.browser`: module attributes `_IS_MACOS`, `_osascript`, `validate_url`, `focus_script`, `open_script`, `close_script`
  - `agent_ui_bridge.tools.register_ui_tools(mcp, hub, *, screenshot_action="page.screenshot", screenshot_doc=None, app_name="app", app_url_label="the configured app URL", frontend_url=None, hosted=lambda: False) -> dict[str, Callable]`
  - `agent_ui_bridge.probe.main(url, invoke, args_json, read_state, screenshot)` and `agent_ui_bridge.probe.cli() -> None`
  - `agent_ui_bridge.__init__` re-exports `BridgeHub`, `NoTabError`, `TabTimeoutError`, `ActionFailedError`, `serve_tab`, `register_ui_tools`

**Deviations from the spec, deliberate, both required to make the moved tests work:**
- `register_ui_tools` returns `dict[str, Callable]` (the registered tool callables by name) rather than `None`. The spec says `-> None`; a dict is a superset, Chartkar ignores it, and it is the only way the moved tests can call closures that no longer live at module scope.
- `_frontend_url()`'s validation message no longer names the `FRONTEND_URL` env var (the package does not read env). `browser.validate_url` raises `RuntimeError(f"the app URL is not a plain URL, refusing to script Chrome with it: {url!r}")`. That message is not agent-facing in normal operation (it only fires on a misconfigured URL), which is why it is allowed to change.

**Docstring fidelity, verified against the installed SDK:** `Tool.from_function` does `func_doc = description or fn.__doc__ or ""` with NO `inspect.cleandoc()`. So the description a client sees today is the raw docstring, four-space continuation indents and all. Every multi-line description below therefore reproduces the original docstring byte for byte, indentation included, as a module-level triple-quoted constant (the tool functions are nested inside `register_ui_tools`, so their own docstrings would carry eight-space indents; that is why descriptions are passed explicitly). `app_url_label` exists for the same reason: `ui_open_tab`'s text says "at FRONTEND_URL", which `app_name` cannot supply.

- [ ] **Step 1: Write `python/pyproject.toml`**

```toml
[project]
name = "agent-ui-bridge"
version = "0.1.0"
description = "Relay hub and ui_* MCP tools that let an agent drive a running web UI."
requires-python = ">=3.12"
license = { text = "MIT" }
authors = [{ name = "Mahan Parham" }]
dependencies = [
    "mcp>=2.0",
]

[project.scripts]
agent-ui-bridge-probe = "agent_ui_bridge.probe:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["agent_ui_bridge"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "anyio>=4",
]
```

- [ ] **Step 2: Write `python/agent_ui_bridge/hub.py`**

Copy `auto_trader/backend/auto_trader/api/agent_bridge.py` verbatim, then apply exactly two edits:
- the module docstring's second paragraph `Browser tabs connect over /ws/agent-ui (routers/agent.py) and register a send callable here. MCP tools (mcp_server.py) call ...` becomes `Browser tabs connect over the host app's WebSocket route (see ws.serve_tab) and register a send callable here. The ui_* MCP tools (tools.py) call ...`
- delete the final two lines (`HUB = BridgeHub()` and the blank line before it). The app owns its instance.

```bash
cd /Users/mahmoudparham/projects/agent-ui-bridge
mkdir -p python/agent_ui_bridge python/tests
cp /Users/mahmoudparham/projects/auto_trader/backend/auto_trader/api/agent_bridge.py python/agent_ui_bridge/hub.py
```

Verify after editing:
```bash
grep -n "^HUB" python/agent_ui_bridge/hub.py
```
Expected: no output.

- [ ] **Step 3: Write `python/agent_ui_bridge/ws.py`**

The disconnect exception is NOT caught here: the host's route already owns `except WebSocketDisconnect`, and swallowing it here would hide real errors. This function is duck-typed over the websocket (`send_json`, `receive_json`), so it never imports FastAPI.

```python
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
```

- [ ] **Step 4: Write `python/agent_ui_bridge/browser.py`**

Moved verbatim from the bottom of `mcp_server.py` (`_IS_MACOS`, `_SAFE_URL_RE`, `_OSASCRIPT_TIMEOUT_S`, `_AUTOMATION_HINT`, `_osascript`, `_focus_script`, `_open_script`, `_close_script`), with `_frontend_url()` replaced by `validate_url(url)` (the app supplies the URL) and the three script builders renamed without the leading underscore (they are the module's public surface for `tools.py`).

```python
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
```

- [ ] **Step 5: Write `python/agent_ui_bridge/tools.py`**

Three things an executor must not "clean up":
1. `from . import browser`, then `browser._osascript(...)` and `browser._IS_MACOS` at CALL time. A direct `from .browser import _osascript` would freeze the reference and break the six monkeypatching tests in `test_browser_tabs.py`.
2. Registration is `mcp.tool(description=...)(fn)`, not the `@mcp.tool()` decorator, because the description is built from `app_name` / `screenshot_doc` at call time. `MCPServer.tool` takes `(name, title, description, annotations, icons, meta, structured_output)` and returns a decorator, verified against the installed `mcp>=2.0`.
3. The docstrings of the ten tools are the agent-visible contract. With `app_name="Chartkar"` and Chartkar's `screenshot_doc`, the descriptions registered are byte-identical to today's.

```python
"""The ui_* MCP tools: a thin, app-agnostic layer over a BridgeHub.

`register_ui_tools(mcp, hub, ...)` registers ten tools on a given MCPServer.
Everything app-specific is an option: the screenshot action's name and doc, the
app's display name, how to resolve the app's URL, and whether this deployment
is hosted (hosted refuses browser tab control outright).
"""
from __future__ import annotations

from typing import Any, Callable

from mcp.types import ImageContent, TextContent

from . import browser
from .hub import ActionFailedError, NoTabError, TabTimeoutError

TITLE_ACTION = "tab.title.set"

# Tool descriptions. The MCP SDK registers `description or fn.__doc__` verbatim
# (no cleandoc), so these reproduce the original docstrings exactly, four-space
# continuation indents included. Agents read this text: treat it as an API.
_DOC_SESSIONS = """List connected UI tabs (most recently active first)."""

_DOC_ACTIONS = """The manifest: every UI action with its name, kind, and JSON schema."""

_DOC_SET_TITLE = """Name the browser tab you are about to drive. REQUIRED before ui_invoke,
    ui_read_state or ui_screenshot work on a session. Keep it short and
    specific ('US100 4H backtest', 'OIL_CRUDE trendline review'); the tab
    prefixes a robot mark so the owner can tell agent tabs from their own."""

_DOC_INVOKE = """Invoke a UI action. Fast actions return the result; long-running ones
    (backtest.run, sweep.start) and confirm-kind ones (which wait on a human
    approving a dialog) return {"handle": ...} - poll with ui_wait. A rejected
    confirm surfaces as ui_wait status "error" with "REJECTED: ...".
    Refused with UNTITLED_TAB until ui_set_title has named the tab."""

_DOC_WAIT = """Wait for a long-running invocation. Returns {status, progress, result?, error?};
    status "running" after timeout means keep polling."""

_DOC_READ_STATE = """Shorthand for invoking a read-kind action by name (e.g. backtest.result).

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
    app_name: str = "app",
    app_url_label: str = "the configured app URL",
    frontend_url: Callable[[], str] | None = None,
    hosted: Callable[[], bool] = lambda: False,
) -> dict[str, Callable[..., Any]]:
    """Register the ten ui_* tools on `mcp`, relaying through `hub`.

    Returns the registered callables keyed by tool name, so a test can drive
    them directly without an MCP transport.
    """
    tools: dict[str, Callable[..., Any]] = {}

    def _add(fn: Callable[..., Any], description: str) -> None:
        mcp.tool(description=description)(fn)
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
                "short description of what you are doing (e.g. 'US100 4H backtest') "
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
```

- [ ] **Step 6: Write `python/agent_ui_bridge/__init__.py`**

```python
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
```

- [ ] **Step 7: Write `python/agent_ui_bridge/probe.py`**

Moved from `auto_trader/backend/scripts/agent_bridge_probe.py`. `_structured`, `_blocks`, `payload`, `show`, `_screenshot` and `_follow` are verbatim. Changed: the docstring, the two hardcoded Chartkar action names become flags (`--read-state KEY` replaces the hardcoded `ui_read_state backtest.config.get`; `--run` is dropped, since it was shorthand for `--invoke backtest.run`), the screenshot default path is `screenshot.png`, and a synchronous `cli()` holds the argparse so a host repo can wrap it in two lines.

```python
"""End-to-end probe for the agent UI bridge.

Prereqs: the host app's backend running with the MCP endpoint mounted, and, for
anything beyond ui_sessions, the app open in a browser so a tab is connected.

    python3 -m agent_ui_bridge.probe
    python3 -m agent_ui_bridge.probe --read-state backtest.config.get
    python3 -m agent_ui_bridge.probe --invoke market.select --args '{"epic": "US100"}'
    python3 -m agent_ui_bridge.probe --screenshot /tmp/shot.png

With no tab connected the ui_* tools return tool errors ("no UI session
connected: open the app in a browser"); the probe prints them and carries on.

Transport: the MCP python client (mcp>=2.0) over streamable HTTP. The endpoint
has the SDK's DNS-rebinding protection, so the URL host must be localhost,
127.0.0.1 or [::1] (any other Host header gets a 421).
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
from typing import Any

from mcp.client import Client  # mcp>=2.0: dataclass client, URL string = streamable HTTP

DEFAULT_URL = "http://localhost:8000/mcp"
_MISSING = object()  # distinguishes "no structured output" from a structured None


def _structured(res: Any) -> Any:
    """The structured output, or _MISSING when the result has none."""
    sc = getattr(res, "structured_content", None)
    if sc is None:
        sc = getattr(res, "structuredContent", None)
    return _MISSING if sc is None else sc


def _blocks(res: Any) -> list[str]:
    """EVERY text block of the result. A tool returning a list arrives as one
    block per element (ui_actions: one block per action), so joining only the
    first block silently drops most of the answer."""
    return [c.text for c in (getattr(res, "content", None) or []) if hasattr(c, "text")]


def payload(res: Any) -> Any:
    """The tool's return value, whatever shape the SDK wrapped it in.

    Structured output is preferred (tools declare real return types); a lone
    "result" key is the SDK's wrapper for a non-object return and is unwrapped.
    Falls back to the text blocks: each block parsed as JSON where it is JSON,
    collapsing to the single value when there is exactly one block.
    """
    sc = _structured(res)
    if sc is not _MISSING:
        if isinstance(sc, dict) and set(sc) == {"result"}:
            return sc["result"]
        return sc
    parsed = []
    for text in _blocks(res):
        try:
            parsed.append(json.loads(text))
        except (ValueError, TypeError):
            parsed.append(text)
    if not parsed:
        return None
    return parsed[0] if len(parsed) == 1 else parsed


def show(name: str, res: Any) -> Any:
    """Print one tool result in full. Tool errors are printed, not raised.

    Nothing is truncated and no block is skipped: an under-printed manifest
    reads as a missing action.
    """
    marker = " [tool error]" if getattr(res, "is_error", False) else ""
    print(f"\n== {name}{marker} ==")
    sc = _structured(res)
    if sc is not _MISSING:
        print(json.dumps(sc, indent=2, default=str))
    else:
        for text in _blocks(res) or ["(no content)"]:
            print(text)
    return payload(res)


async def _screenshot(client: Client, path: str) -> None:
    """Call ui_screenshot, decode the image block, write it to `path`."""
    res = await client.call_tool("ui_screenshot", {})
    print(f"\n== ui_screenshot{' [tool error]' if getattr(res, 'is_error', False) else ''} ==")
    if getattr(res, "is_error", False):
        for text in _blocks(res) or ["(no content)"]:
            print(text)
        return
    content = getattr(res, "content", None) or []
    image = next((c for c in content if getattr(c, "type", None) == "image"), None)
    if image is None:
        print("(no image block in result)")
        for text in _blocks(res) or ["(no content)"]:
            print(text)
        return
    data = base64.b64decode(image.data)
    with open(path, "wb") as f:
        f.write(data)
    print(f"wrote {path} ({len(data)} bytes, {image.mimeType})")
    for text in _blocks(res):
        print(text)


async def main(
    url: str, invoke: str | None, args_json: str, read_state: str | None, screenshot: str | None
) -> None:
    print(f"connecting to {url}")
    async with Client(url) as client:
        tools = await client.list_tools()
        print("tools:", ", ".join(t.name for t in tools.tools))

        show("ui_sessions", await client.call_tool("ui_sessions", {}))
        show("ui_actions", await client.call_tool("ui_actions", {}))

        if read_state:
            show(
                f"ui_read_state {read_state}",
                await client.call_tool("ui_read_state", {"key": read_state}),
            )

        if invoke:
            res = await client.call_tool(
                "ui_invoke", {"action": invoke, "args": json.loads(args_json)}
            )
            await _follow(client, show(f"ui_invoke {invoke}", res), res)

        if screenshot:
            await _screenshot(client, screenshot)


async def _follow(client: Client, body: Any, res: Any, max_polls: int = 60) -> None:
    """Poll ui_wait when the invocation returned a long-running handle."""
    if getattr(res, "is_error", False):
        return
    handle = body.get("handle") if isinstance(body, dict) else None
    if not handle:
        print("(immediate result, no handle to poll)")
        return
    print(f"run started, handle={handle}")
    for _ in range(max_polls):
        wres = await client.call_tool("ui_wait", {"handle": handle, "timeout_s": 10})
        if getattr(wres, "is_error", False):
            show("ui_wait", wres)
            return
        st = payload(wres)
        if not isinstance(st, dict):
            show("ui_wait", wres)
            return
        print("status:", st.get("status"), "progress:", st.get("progress"))
        if st.get("status") != "running":
            print("final:", json.dumps(st, indent=2, default=str))
            return
    print(f"gave up after {max_polls} polls; handle {handle} still running")


def cli() -> None:
    """Synchronous entry point: parse argv and run the probe."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default=DEFAULT_URL, help=f"MCP endpoint (default {DEFAULT_URL})")
    ap.add_argument("--invoke", help="invoke an action by name (e.g. market.select)")
    ap.add_argument("--args", default="{}", help="JSON args for --invoke")
    ap.add_argument("--read-state", dest="read_state", help="read a read-kind action by name")
    ap.add_argument(
        "--screenshot",
        nargs="?",
        const="screenshot.png",
        default=None,
        metavar="PATH",
        help="call ui_screenshot and write the image to PATH (default screenshot.png)",
    )
    ns = ap.parse_args()
    asyncio.run(main(ns.url, ns.invoke, ns.args, ns.read_state, ns.screenshot))


if __name__ == "__main__":
    cli()
```

- [ ] **Step 8: Move `test_hub.py`**

```bash
cp /Users/mahmoudparham/projects/auto_trader/backend/tests/test_agent_bridge_hub.py \
   /Users/mahmoudparham/projects/agent-ui-bridge/python/tests/test_hub.py
```
Then the single import edit: replace
```python
from auto_trader.api.agent_bridge import (
    ActionFailedError, BridgeHub, NoTabError, TabTimeoutError,
)
```
with
```python
from agent_ui_bridge.hub import (
    ActionFailedError, BridgeHub, NoTabError, TabTimeoutError,
)
```
Nothing else in that file changes: it never touches `HUB` or `mcp_server`.

- [ ] **Step 9: Write `python/tests/test_ui_tools.py`**

This is the hub-driving half of Chartkar's `test_mcp_tools.py`. The four transport tests (`test_mcp_serves_initialize_at_exactly_slash_mcp`, `test_mcp_lists_the_ui_tools_and_survives_a_second_startup`, `test_tools_call_over_http_returns_a_result`, `test_tools_call_surfaces_the_no_tab_message_as_a_tool_error`) do NOT move: they import `auto_trader.api.app` and stay in Chartkar as `tests/test_mcp_registration.py` (Task 7). The `hub` fixture becomes a `ui` fixture that registers the tools on a throwaway MCPServer and hands back the callables.

```python
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


def titled_tab(hub, title="🤖 test"):
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
    await reply(hub, sid, sent, ok=True, result={"title": "🤖 nightly review"})
    assert await task == {"session": sid, "title": "🤖 nightly review"}
    assert sent[0]["op"] == "invoke" and sent[0]["action"] == "tab.title.set"
    assert sent[0]["args"] == {"title": "nightly review"}
    assert (await ui["ui_sessions"]())[0]["title"] == "🤖 nightly review"
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
    assert {s["id"]: s["title"] for s in sessions} == {a: "🤖 test", b: None}


@pytest.mark.anyio
async def test_ui_invoke_of_the_title_action_routes_to_set_title(hub, ui):
    """tab.title.set through ui_invoke must not hit the UNTITLED_TAB gate, or
    the tab could never be named through the generic tool."""
    sid, sent = fake_tab(hub)
    task = asyncio.ensure_future(ui["ui_invoke"]("tab.title.set", {"title": "named"}))
    await reply(hub, sid, sent, ok=True, result={"title": "🤖 named"})
    assert await task == {"session": sid, "title": "🤖 named"}
```

- [ ] **Step 10: Write `python/tests/test_screenshot.py`**

Moved from `test_mcp_screenshot.py`. The FakeHub shape is unchanged (a duck-typed object with `request` and `title_of`), it is now passed to `register_ui_tools` instead of monkeypatched onto a module, and the text-line assertion moves to the `caption` field.

```python
import base64

import pytest
from mcp.server import MCPServer

from agent_ui_bridge.hub import NoTabError
from agent_ui_bridge.tools import register_ui_tools


class FakeHub:
    def __init__(self, result=None, exc=None):
        self.result = result
        self.exc = exc
        self.calls = []

    async def request(self, kind, payload, session_id=None):
        self.calls.append((kind, payload, session_id))
        if self.exc:
            raise self.exc
        return self.result

    def title_of(self, session_id=None):
        # The title gate runs before the request; a missing tab surfaces here.
        if isinstance(self.exc, NoTabError):
            raise self.exc
        return "🤖 test"


def tools_for(hub):
    return register_ui_tools(
        MCPServer("test-shot"), hub, screenshot_action="page.screenshot", app_name="app"
    )


@pytest.mark.anyio
async def test_ui_screenshot_returns_image_block():
    png = base64.b64encode(b"\x89PNG fake").decode()
    hub = FakeHub(result={
        "caption": "US100 HOUR (cell c1)",
        "mime": "image/png", "image_base64": png, "via": "extension",
    })
    blocks = await tools_for(hub)["ui_screenshot"]()
    image = next(b for b in blocks if getattr(b, "type", "") == "image")
    text = next(b for b in blocks if getattr(b, "type", "") == "text")
    assert image.data == png
    assert image.mime_type == "image/png"
    assert text.text == "US100 HOUR (cell c1) via extension"
    # It must go through the readOnly invoke path:
    kind, payload, _ = hub.calls[0]
    assert kind == "invoke"
    assert payload == {"action": "page.screenshot", "args": {}, "readOnly": True}


@pytest.mark.anyio
async def test_ui_screenshot_without_a_caption_still_labels_the_image():
    png = base64.b64encode(b"\x89PNG fake").decode()
    hub = FakeHub(result={"mime": "image/png", "image_base64": png, "via": "canvas"})
    blocks = await tools_for(hub)["ui_screenshot"]()
    text = next(b for b in blocks if getattr(b, "type", "") == "text")
    assert text.text == "screenshot via canvas"


@pytest.mark.anyio
async def test_ui_screenshot_no_tab_is_friendly():
    hub = FakeHub(exc=NoTabError("no UI session connected"))
    with pytest.raises(RuntimeError, match="no UI session"):
        await tools_for(hub)["ui_screenshot"]()
```

- [ ] **Step 11: Write `python/tests/test_browser_tabs.py`**

Moved from `test_mcp_browser_tabs.py`. Monkeypatch targets move from `mcp_server` to the `agent_ui_bridge.browser` module (which is why `tools.py` reads them as module attributes at call time). `hosted` becomes a mutable flag instead of the `CLERK_JWKS_URL` env var, the app URL is injected instead of read from `FRONTEND_URL`, "no Chartkar tab" becomes "no app tab", and the unsafe-URL message no longer names an env var.

```python
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
```

- [ ] **Step 12: Add a `serve_tab` test**

`ws.py` is new code with no moved test, so it gets one. Create `python/tests/test_ws.py`:

```python
"""serve_tab pumps frames and always unregisters the tab."""
import asyncio

import pytest

from agent_ui_bridge.hub import BridgeHub
from agent_ui_bridge.ws import serve_tab


class FakeSocket:
    """Duck-typed websocket: replies to whatever serve_tab forwards, then drops."""

    def __init__(self, inbound):
        self.inbound = list(inbound)
        self.sent = []

    async def send_json(self, frame):
        self.sent.append(frame)

    async def receive_json(self):
        if not self.inbound:
            raise ConnectionError("client went away")
        await asyncio.sleep(0)
        return self.inbound.pop(0)


@pytest.mark.anyio
async def test_serve_tab_relays_a_reply_then_unregisters():
    hub = BridgeHub()
    sock = FakeSocket([])
    task = asyncio.ensure_future(serve_tab(hub, sock))
    await asyncio.sleep(0)
    with pytest.raises(ConnectionError):
        await task
    assert hub.sessions() == []


@pytest.mark.anyio
async def test_serve_tab_feeds_replies_into_the_hub():
    hub = BridgeHub()
    sock = FakeSocket([])
    served = asyncio.ensure_future(serve_tab(hub, sock))
    while not hub.sessions():
        await asyncio.sleep(0)
    sid = hub.sessions()[0]["id"]
    req = asyncio.ensure_future(hub.request("manifest", {}, session_id=sid))
    while not sock.sent:
        await asyncio.sleep(0)
    sock.inbound.append({"id": sock.sent[-1]["id"], "ok": True, "result": [{"name": "a"}]})
    assert await req == [{"name": "a"}]
    with pytest.raises(ConnectionError):
        await served
    assert hub.sessions() == []
```

- [ ] **Step 13: Run the Python tests**

Run: `cd /Users/mahmoudparham/projects/agent-ui-bridge/python && uv run --extra dev pytest -q`
(If `--extra dev` is rejected because the dev deps live in `[dependency-groups]`, use plain `uv run pytest -q`, which installs the default dependency group.)
Expected: PASS, five files, no failures. A `fixture 'anyio_backend' not found` error means anyio's pytest plugin is missing; confirm `anyio` is in the dev group and re-run.

- [ ] **Step 14: No commit yet** (first commit is Task 5)

---

### Task 4: Extension and repo README

**Files:**
- Create (moved verbatim): `extension/background.js`, `extension/content.js`, `extension/dispatch.js`, `extension/dispatch.test.js`, `extension/handlers.js`, `extension/handlers.test.js`, `extension/manifest.json`, `extension/test-helpers.js`
- Create (moved, two lines changed): `extension/README.md`
- Create: `README.md` (repo root)

**Interfaces:**
- Consumes: nothing.
- Produces: `extension/` installable unpacked; `node --test extension/*.test.js` green.

- [ ] **Step 1: Copy all nine extension files verbatim**

```bash
cd /Users/mahmoudparham/projects/agent-ui-bridge
cp -R /Users/mahmoudparham/projects/auto_trader/extension extension
ls extension
```
Expected: `README.md background.js content.js dispatch.js dispatch.test.js handlers.js handlers.test.js manifest.json test-helpers.js`

- [ ] **Step 2: Fix the two stale lines in `extension/README.md`**

Replace

```
It is generic. Any page that speaks the protocol below can use it. Chartkar
is the first consumer (`frontend/src/lib/tabBridge.ts`).
```

with

```
It is generic. Any page that speaks the protocol below can use it. The
page-side client in this repo (`src/tabBridge.ts`, published as
`agent-ui-bridge/tab-bridge`) is one such consumer.
```

Leave every other line of that README exactly as it is.

- [ ] **Step 3: Run the extension tests**

Run: `cd /Users/mahmoudparham/projects/agent-ui-bridge && node --test extension/*.test.js`
Expected: PASS.

- [ ] **Step 4: Write the repo `README.md`**

```markdown
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
| `extension/` Tab Bridge Chrome extension | load unpacked, see `extension/README.md` |

## Frontend: register actions, start the bridge

```ts
import { registerAction, registerTabActions, startAgentBridge } from "agent-ui-bridge";

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
```

- [ ] **Step 5: No commit yet** (Task 5 commits everything at once)

---

### Task 5: First commit and public push

**Files:**
- Modify: nothing. This task only commits and pushes `/Users/mahmoudparham/projects/agent-ui-bridge`.

**Interfaces:**
- Consumes: Tasks 1 to 4.
- Produces: `https://github.com/maparham/agent-ui-bridge` public, branch `main`, so Chartkar's git dependencies resolve. Nothing in Tasks 6 to 8 can start before this.

- [ ] **Step 1: Re-run all three test suites one last time**

```bash
cd /Users/mahmoudparham/projects/agent-ui-bridge
npm test && node --test extension/*.test.js && (cd python && uv run pytest -q)
```
Expected: all three PASS. Do not push on a red suite.

- [ ] **Step 2: Confirm nothing generated is about to be committed**

```bash
cd /Users/mahmoudparham/projects/agent-ui-bridge && git status --short | head -40
```
Expected: no `node_modules/`, no `dist/`, no `__pycache__/`, no `.venv/`. If any appear, fix `.gitignore` before continuing.

- [ ] **Step 3: Commit**

```bash
cd /Users/mahmoudparham/projects/agent-ui-bridge
git add .gitignore LICENSE README.md package.json package-lock.json \
  tsconfig.json tsconfig.build.json vitest.config.ts src python extension docs
git commit -m "$(cat <<'EOF'
feat: agent-ui-bridge, extracted from Chartkar

A generic agent UI bridge any web app can adopt: a typed action registry and
WebSocket relay client (npm "agent-ui-bridge"), a relay hub plus the ten ui_*
MCP tools (python "agent-ui-bridge"), and the Tab Bridge Chrome extension.

Everything app-specific is injected: the bridge takes a URL, a token getter
and a URL decorator; register_ui_tools takes the screenshot action, the app
name, the app URL and a hosted predicate.
EOF
)"
```

Note: this repo's commits carry no Co-Authored-By trailer. The attribution
lines in the Global Constraints apply to Chartkar commits (Tasks 6 to 8).

- [ ] **Step 4: Create the public repo and push**

```bash
cd /Users/mahmoudparham/projects/agent-ui-bridge
gh repo create maparham/agent-ui-bridge --public --source . --push
```
Expected: prints the repo URL and pushes `main`.

- [ ] **Step 5: Verify the git dependency resolves from a clean directory**

This is the gate for Tasks 6 and 7: if it fails, Chartkar's install will fail too.

```bash
cd "$(mktemp -d)" && npm init -y >/dev/null && npm i github:maparham/agent-ui-bridge && ls node_modules/agent-ui-bridge/dist
```
Expected: `dist/` exists with `index.js` and `index.d.ts`. A "tsc: not found" failure here means `typescript` is missing from `devDependencies`; fix, commit, push, retry.

---

### Task 6: Chartkar frontend rewire

**Files:**
- Modify: `/Users/mahmoudparham/projects/auto_trader/frontend/package.json` (add the dependency)
- Modify: `frontend/src/agent/registry.ts`, `frontend/src/agent/confirm.ts`, `frontend/src/agent/AgentConfirmHost.tsx`, `frontend/src/agent/actions/tab.ts`, `frontend/src/agent/index.ts`, `frontend/src/lib/tabBridge.ts` (become shims)
- Modify: `frontend/src/agent/actions/chart.ts` (add `caption` to both `chart.screenshot` return sites)
- Delete: `frontend/src/agent/bridge.ts`, `frontend/src/agent/bridge.test.ts`, `frontend/src/agent/registry.test.ts`, `frontend/src/agent/confirm.test.ts`, `frontend/src/agent/actions/tab.test.ts`, `frontend/src/lib/tabBridge.test.ts`
- Test: `npx vitest run src/agent src/lib` and `npx tsc -b`

**Interfaces:**
- Consumes: the published package from Task 5.
- Produces: every import path `App.tsx` already uses keeps resolving, with the same exported names. `chart.screenshot` results gain `caption: "<epic> <resolution> (cell <cellId>)"` on BOTH return paths, which is what the package's `ui_screenshot` reads.

Note: the spec's delete list mentions `AgentConfirmHost.test.tsx`. That file does not exist in Chartkar (`ls frontend/src/agent` shows no such test); there is nothing to delete.

- [ ] **Step 1: Add the dependency**

Edit `frontend/package.json`, adding one line to `"dependencies"` in alphabetical position (right before `"@codemirror/autocomplete"` is wrong; `agent-ui-bridge` sorts after the scoped packages and before `klinecharts`):

```json
    "@lezer/lr": "^1.4.10",
    "agent-ui-bridge": "github:maparham/agent-ui-bridge",
    "klinecharts": "10.0.0",
```

Run: `cd /Users/mahmoudparham/projects/auto_trader/frontend && npm install`
Expected: `package-lock.json` updated, `node_modules/agent-ui-bridge/dist/index.js` present.

```bash
ls /Users/mahmoudparham/projects/auto_trader/frontend/node_modules/agent-ui-bridge/dist
```

- [ ] **Step 2: Turn `src/agent/registry.ts` into a shim**

Replace the ENTIRE file with:

```ts
// The action registry lives in the agent-ui-bridge package now. This module
// stays so every existing import path (App.tsx, every actions/ module) keeps
// resolving, and so there is exactly one registry instance in the app.
export type {
  ActionKind, ParamProperty, ParamSchema, ActionContext, AgentAction, ActionManifestEntry,
} from "agent-ui-bridge";
export {
  ActionError, registerAction, getAction, listActions, validateArgs, invokeAction,
  clearRegistryForTest,
} from "agent-ui-bridge";
```

- [ ] **Step 3: Turn `src/agent/confirm.ts` into a shim**

Replace the ENTIRE file with:

```ts
// The dealing confirm gate lives in the agent-ui-bridge package now; this
// module keeps the import path the app already uses.
export type { AgentConfirmState } from "agent-ui-bridge";
export { agentConfirmSignal, requestAgentConfirm, resolveAgentConfirm } from "agent-ui-bridge";
```

- [ ] **Step 4: Turn `src/agent/AgentConfirmHost.tsx` into a shim**

Replace the ENTIRE file with:

```tsx
// The dialog itself lives in the agent-ui-bridge package; Chartkar supplies its
// own modal class names (see .modal / .modal-backdrop in App.css) so it looks
// exactly like every other modal in the app.
import { AgentConfirmHost } from "agent-ui-bridge/react";

export default function ChartkarAgentConfirmHost() {
  return <AgentConfirmHost className="modal" backdropClassName="modal-backdrop" />;
}
```

- [ ] **Step 5: Turn `src/agent/actions/tab.ts` into a shim**

Replace the ENTIRE file with:

```ts
// tab.title.set lives in the agent-ui-bridge package (it registers against the
// same registry instance, re-exported by ../registry).
export { registerTabActions, AGENT_TAB_MARK } from "agent-ui-bridge";
```

- [ ] **Step 6: Turn `src/lib/tabBridge.ts` into a shim**

Replace the ENTIRE file with:

```ts
// Page-side client for the Tab Bridge Chrome extension. The extension and this
// client both live in github.com/maparham/agent-ui-bridge now; this module
// keeps the import path (and the vi.mock target in actions/chart.test.ts).
export * from "agent-ui-bridge/tab-bridge";
```

- [ ] **Step 7: Rewrite `src/agent/index.ts`**

Only the imports and the final `startAgentBridge` call change; `agentBridgeEnabled` and the body of `initAgentBridge` are untouched. `token` is a function evaluated per dial (not `hasTokenGetter() ? getAuthToken : undefined` evaluated once), because `ClerkTokenBridge` may mount after `initAgentBridge` runs; returning `null` synchronously keeps the tokenless dev dial synchronous exactly as before.

```ts
// Entry point: registers all action modules and starts the WS bridge when the
// build enables it (VITE_AGENT_BRIDGE=1; dev builds default on). Idempotent.
import { registerTabActions, startAgentBridge } from "agent-ui-bridge";
import { API_BASE } from "../lib/http";
import { getAuthToken, hasTokenGetter } from "../lib/authToken";
import { withImpersonation } from "../lib/impersonation";
import { registerBacktestActions } from "./actions/backtest";
import { registerSweepActions } from "./actions/sweep";
import { registerDealingActions } from "./actions/dealing";
import { registerDrawingActions } from "./actions/drawings";
import { registerChartActions } from "./actions/chart";
import { registerIndicatorActions } from "./actions/indicators";

let initialized = false;

export function agentBridgeEnabled(): boolean {
  const env = (import.meta as unknown as { env?: Record<string, string | boolean> }).env ?? {};
  const flag = env.VITE_AGENT_BRIDGE;
  if (flag === "1" || flag === "true") return true;
  if (flag === "0" || flag === "false") return false;
  // Never dial out from a unit-test run (vitest sets DEV too, and a real
  // WebSocket there would leave a reconnect loop running across the suite).
  if (env.MODE === "test" || env.TEST === true || env.TEST === "true") return false;
  return Boolean(env.DEV);
}

export function initAgentBridge(): void {
  if (initialized) return;
  initialized = true;
  // The module flag covers StrictMode's double invoke; a Vite HMR reload of
  // THIS module resets it, and registerAction throws on a duplicate name, so
  // keep a re-registration from taking the app down with it.
  try {
    registerBacktestActions();
    registerSweepActions();
    registerDealingActions();
    registerDrawingActions();
    registerChartActions();
    registerIndicatorActions();
    registerTabActions();
  } catch (e) {
    console.debug("agent: actions already registered (HMR?)", e);
  }
  if (!agentBridgeEnabled()) return;
  startAgentBridge({
    url: `${API_BASE.replace(/^http/, "ws")}/ws/agent-ui`,
    // Resolved per (re)connect, not once: ClerkTokenBridge may register its
    // getter after this runs, and Clerk tokens live about 60s. With no getter
    // registered (local dev, tests) this answers null synchronously and the
    // bridge dials in the same tick, exactly as it did before auth existed.
    token: () => (hasTokenGetter() ? getAuthToken() : null),
    decorateUrl: withImpersonation,
  });
}
```

- [ ] **Step 8: Add `caption` to BOTH `chart.screenshot` return sites**

`frontend/src/agent/actions/chart.ts` returns from the handler twice. Edit both.

Extension path, replace:
```ts
          return { epic, cellId, resolution, mime: shot.mime, image_base64: shot.image_base64, via: "extension" };
```
with:
```ts
          return {
            epic, cellId, resolution, caption: `${epic} ${resolution} (cell ${cellId})`,
            mime: shot.mime, image_base64: shot.image_base64, via: "extension",
          };
```

Canvas fallback path, replace:
```ts
        return { epic, cellId, resolution, mime: shot.mime, image_base64: shot.b64, via: "canvas" };
```
with:
```ts
        return {
          epic, cellId, resolution, caption: `${epic} ${resolution} (cell ${cellId})`,
          mime: shot.mime, image_base64: shot.b64, via: "canvas",
        };
```

`caption` is what the package's `ui_screenshot` turns into the text block beside the image; without it on the canvas path the line silently degrades to "screenshot via canvas" exactly when the extension is absent.

- [ ] **Step 9: Delete the moved modules and tests**

```bash
cd /Users/mahmoudparham/projects/auto_trader
git rm -f frontend/src/agent/bridge.ts \
          frontend/src/agent/bridge.test.ts \
          frontend/src/agent/registry.test.ts \
          frontend/src/agent/confirm.test.ts \
          frontend/src/agent/actions/tab.test.ts \
          frontend/src/lib/tabBridge.test.ts
```

- [ ] **Step 10: Run only the affected frontend tests**

Run: `cd /Users/mahmoudparham/projects/auto_trader/frontend && npx vitest run src/agent`
Expected: PASS (the `src/agent/actions/*.test.ts` files plus `index.test.ts`).

`src/agent` is the whole affected set. Do NOT widen this to `src/lib`: that
directory holds 399 test files, and running it locks up the laptop. The only
`src/lib` test that touched the bridge was `tabBridge.test.ts`, which Step 9
deleted (it moved to the package), so there is nothing left there to run. The
shim is exercised indirectly by `src/agent/actions/chart.test.ts`, which mocks
it. Never run the full suite.

If `src/agent/actions/chart.test.ts` fails on `vi.mock("../../lib/tabBridge")`, the auto-mock could not derive the shape through the `export *`; fix by naming the exports explicitly in the shim (`export { probeTabBridge, tabBridgeScreenshot, tabBridgeFocus, invalidateTabBridge, resetTabBridgeForTest, TabBridgeError } from "agent-ui-bridge/tab-bridge"; export type { TabBridgeHello, ScreenshotArgs, ScreenshotResult } from "agent-ui-bridge/tab-bridge";`) rather than by editing the test.

- [ ] **Step 11: Typecheck parity**

Run: `cd /Users/mahmoudparham/projects/auto_trader/frontend && npx tsc -b`
Expected: no NEW errors in the files this task touched. `tsc --noEmit` is a no-op in this project; judge by per-file parity against the pre-change run, and do not chase pre-existing errors in files this task did not touch.

- [ ] **Step 12: Commit (explicit paths only)**

```bash
cd /Users/mahmoudparham/projects/auto_trader
git add frontend/package.json frontend/package-lock.json \
        frontend/src/agent/registry.ts frontend/src/agent/confirm.ts \
        frontend/src/agent/AgentConfirmHost.tsx frontend/src/agent/index.ts \
        frontend/src/agent/actions/tab.ts frontend/src/agent/actions/chart.ts \
        frontend/src/lib/tabBridge.ts
git commit -m "$(cat <<'EOF'
refactor(agent): consume agent-ui-bridge for the frontend bridge

The registry, relay client, confirm gate, confirm dialog, tab.title.set and
the Tab Bridge client now come from github:maparham/agent-ui-bridge. Every
import path App.tsx uses stays, as a shim, so App.tsx is untouched.

startAgentBridge is configured rather than importing Chartkar modules: URL
from API_BASE, token resolved per dial so a late ClerkTokenBridge still
counts, decorateUrl = withImpersonation. chart.screenshot now returns a
caption, which is what the package's ui_screenshot prints beside the image.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SoZ7wfsyG7HZxLXuC4au8p
EOF
)"
```

The six deleted files are NOT in that `git add` list: `git rm -f` in Step 9
already staged their deletion, and `git add` on a path that exists in neither
the worktree nor the index fails the whole command with `fatal: pathspec ...
did not match any files`, so the commit would never run.

Never `git add -A`. `frontend/src/App.tsx`, `App.css`, `IndicatorSettings.tsx`, `indicatorSettings/DefaultsMenu.tsx`, `lib/indicatorMeta.ts` and `mobile/MobileModals.tsx` carry other people's uncommitted work and must not appear in this commit.

---

### Task 7: Chartkar backend rewire

**Files:**
- Modify: `backend/pyproject.toml` (dependency + `[tool.uv.sources]`)
- Modify: `backend/auto_trader/api/agent_bridge.py` (becomes the hub instance)
- Modify: `backend/auto_trader/api/routers/agent.py` (calls `serve_tab`)
- Modify: `backend/auto_trader/api/mcp_server.py` (drops the `ui_*` half, calls `register_ui_tools`)
- Modify: `backend/scripts/agent_bridge_probe.py` (wrapper)
- Create: `backend/tests/test_mcp_registration.py`
- Delete: `backend/tests/test_agent_bridge_hub.py`, `test_mcp_tools.py`, `test_mcp_browser_tabs.py`, `test_mcp_screenshot.py`
- Test: `cd backend && uv run pytest tests/test_mcp_direct_tools.py tests/test_mcp_registration.py`

**Interfaces:**
- Consumes: the published Python package from Task 5; `caption` from Task 6.
- Produces: `auto_trader.api.agent_bridge.HUB` unchanged in name and type; `mcp_server.mcp` still lists the ten `ui_*` tools plus the direct tools; `mcp_server` still exports `configure_direct_tools`, `mcp_http_app`, `mcp_session`, `_ASGI_APP`, `_path_id` and every `ta_*`/`wf_*`/`runs_*` tool that `tests/test_mcp_direct_tools.py` drives.

`_friendly` is DELETED from Chartkar, not kept and not imported. Verified: every direct tool goes through `_api_get`/`_api_post`, which raise `RuntimeError` themselves; `_friendly`'s only callers were the `ui_*` functions that leave. The package owns its own copy.

- [ ] **Step 1: Add the dependency**

In `backend/pyproject.toml`, add to `dependencies` (right after `"mcp>=2.0",`):
```toml
    "agent-ui-bridge",
```
and add a new section after `[project.optional-dependencies]`:
```toml
[tool.uv.sources]
agent-ui-bridge = { git = "https://github.com/maparham/agent-ui-bridge", subdirectory = "python" }
```

Run: `cd /Users/mahmoudparham/projects/auto_trader/backend && uv sync`
Expected: resolves and installs `agent-ui-bridge` from git; `uv.lock` updated.

```bash
cd /Users/mahmoudparham/projects/auto_trader/backend && uv run python -c "import agent_ui_bridge; print(agent_ui_bridge.__file__)"
```

- [ ] **Step 2: Rewrite `backend/auto_trader/api/agent_bridge.py`**

Replace the ENTIRE file with:

```python
"""Chartkar's relay hub instance for the Agent UI Bridge.

The hub itself (request/reply futures, handle store, session routing) lives in
the agent_ui_bridge package. This module keeps the import path the routers and
mcp_server already use, and owns the single process-wide instance. Tests that
want a clean hub monkeypatch the consumer's reference, not this one.
"""
from __future__ import annotations

from agent_ui_bridge.hub import (
    ActionFailedError,
    BridgeHub,
    NoTabError,
    TabTimeoutError,
)

__all__ = ["HUB", "BridgeHub", "NoTabError", "TabTimeoutError", "ActionFailedError"]

HUB = BridgeHub()
```

- [ ] **Step 3: Rewrite the WebSocket body in `backend/auto_trader/api/routers/agent.py`**

Add the import beside the existing ones:
```python
from agent_ui_bridge import serve_tab
```
Then replace the tail of `ws_agent_ui` (everything from `await websocket.accept()` to the end of the function):

```python
    await websocket.accept()
    try:
        await serve_tab(HUB, websocket)
    except WebSocketDisconnect:
        pass
```

The `register` / receive-loop / `finally: HUB.unregister(sid)` shape is now inside `serve_tab`; `WebSocketDisconnect` stays here because only this route knows what a disconnect means. Everything above `await websocket.accept()` (the token check, the origin check, `verify_ws`) is unchanged, and so are the module docstring and both close-code constants.

- [ ] **Step 4: Slim `backend/auto_trader/api/mcp_server.py`**

Delete these, in order, from the top of the file down:
- `_friendly`
- `ui_sessions`, `ui_actions`, `TITLE_ACTION`, `_require_titled`, `ui_set_title`, `ui_invoke`, `ui_wait`, `ui_read_state`, `ui_screenshot`
- the whole `# --- browser tab control (macOS, local dev only) ---` block: `import asyncio`, `import sys`, `_IS_MACOS`, `_SAFE_URL_RE`, `_frontend_url`, `_require_not_hosted`, `_require_local_macos`, `_OSASCRIPT_TIMEOUT_S`, `_AUTOMATION_HINT`, `_osascript`, `_focus_script`, `_open_script`, `_close_script`, `ui_focus_tab`, `ui_open_tab`, `ui_close_tab`

Keep: `_ASGI_APP`, `configure_direct_tools`, `_auth_headers`, `_SAFE_ID_RE`, `_path_id`, `_api_get`, `_api_post`, every `ta_*` / `wf_*` / `runs_list` / `run_get` tool, `_ARCHIVES`, `mcp_http_app`, `mcp_session`.

Then replace the module header (docstring through the `mcp = MCPServer(...)` line) with exactly this:

```python
"""MCP server for Chartkar, mounted on the FastAPI app at /mcp.

Agents (Claude Code etc.) connect over streamable HTTP and get two families of
tools. The `ui_*` tools relay to the connected browser tab via agent_bridge.HUB;
they are registered by the agent_ui_bridge package, which owns their behaviour
(ten tools: sessions, actions, set_title, invoke, wait, read_state, screenshot,
and the three macOS browser tab helpers). The direct (no-tab) tools live here
and call the app's own REST routes in-process over httpx.ASGITransport,
configured via `configure_direct_tools`: `ta_*` (candles, indicator series,
pattern search/scan/families), `wf_*` (run/status/cancel/fold a walk-forward
job), and `runs_list`/`run_get` (the backtest/sweep/walkforward archives).
Errors surface as tool errors with actionable messages (the MCP SDK converts
raised exceptions).
"""
from __future__ import annotations

import os
import re
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from agent_ui_bridge import register_ui_tools
from mcp.server import MCPServer  # mcp>=2.0 API (1.x called this mcp.server.fastmcp.FastMCP)

from .agent_bridge import HUB
from .guard import API_TOKEN_ENV

mcp = MCPServer("auto-trader-ui")

# The ui_* tools, registered at import time so the manifest is complete before
# the first request. Every Chartkar-specific word the agent reads is passed in
# here, which is why the package itself has none: app_name and screenshot_doc
# keep the tool descriptions byte-identical to what agents saw before the
# extraction.
register_ui_tools(
    mcp,
    HUB,
    screenshot_action="chart.screenshot",
    # Byte-identical to the old ui_screenshot docstring, four-space continuation
    # indents included: the SDK registers the string verbatim, with no cleandoc.
    screenshot_doc="""Screenshot of the focused chart in the connected tab, as an image the
    client renders natively. Pairs with ui_read_state("chart.state") for the
    numbers behind the pixels. Refused with UNTITLED_TAB until ui_set_title
    has named the tab.""",
    app_name="Chartkar",
    app_url_label="FRONTEND_URL",
    frontend_url=lambda: os.environ.get("FRONTEND_URL", "http://localhost:5173"),
    hosted=lambda: bool(os.environ.get("CLERK_JWKS_URL")),
)
```

`ImageContent` / `TextContent` and the `ActionFailedError` / `NoTabError` / `TabTimeoutError` imports go with the code that used them; leaving them would trip ruff's F401.

- [ ] **Step 5: Turn the probe script into a wrapper**

Replace the ENTIRE contents of `backend/scripts/agent_bridge_probe.py` with:

```python
"""Thin wrapper: the probe lives in the agent_ui_bridge package now.

    cd backend && python3 -m agent_ui_bridge.probe --read-state backtest.config.get
"""
from agent_ui_bridge.probe import cli

if __name__ == "__main__":
    cli()
```

- [ ] **Step 6: Delete the moved tests**

```bash
cd /Users/mahmoudparham/projects/auto_trader
git rm -f backend/tests/test_agent_bridge_hub.py \
          backend/tests/test_mcp_tools.py \
          backend/tests/test_mcp_browser_tabs.py \
          backend/tests/test_mcp_screenshot.py
```

- [ ] **Step 7: Write `backend/tests/test_mcp_registration.py`**

This is the transport half of the old `test_mcp_tools.py`, kept verbatim in behaviour, plus one assertion that the direct tools survived the slimming. The old `hub` fixture is gone: the tools close over the real `HUB`, and with no tab registered both assertions still hold.

```python
"""Chartkar's MCP mount: the server answers at exactly /mcp and lists both
tool families (the ten ui_* tools from agent_ui_bridge, plus the direct ones
this repo defines)."""
import re

from fastapi.testclient import TestClient

_INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"}}}
_HDR = {"Accept": "application/json, text/event-stream",
        "Content-Type": "application/json"}


def _client():
    # 127.0.0.1 because the SDK's DNS-rebinding protection rejects other hosts.
    from auto_trader.api.app import app
    return TestClient(app, base_url="http://127.0.0.1:8000")


def _session(c):
    """Initialize an MCP session; returns headers for follow-up calls."""
    r = c.post("/mcp", json=_INIT, headers=_HDR, follow_redirects=False)
    h = {**_HDR, "mcp-session-id": r.headers["mcp-session-id"],
         "MCP-Protocol-Version": "2025-06-18"}
    c.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=h)
    return h


def _call(c, h, name, args, rid=9):
    return c.post("/mcp", headers=h, json={
        "jsonrpc": "2.0", "id": rid, "method": "tools/call",
        "params": {"name": name, "arguments": args}})


def _tools_list_text():
    # Two startups: the session manager must be rebuilt per lifespan (it can
    # only be run() once), or the second TestClient would blow up.
    with _client():
        pass
    with _client() as c:
        h = _session(c)
        r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                   headers=h)
    return r.text


def test_mcp_serves_initialize_at_exactly_slash_mcp():
    with _client() as c:
        r = c.post("/mcp", json=_INIT, headers=_HDR, follow_redirects=False)
    assert r.status_code == 200, r.text  # not a 307 to /mcp/, not a 404
    assert r.headers.get("mcp-session-id")


def test_mcp_lists_the_ui_tools_and_survives_a_second_startup():
    text = _tools_list_text()
    assert sorted(set(re.findall(r'"name":\s?"(ui_\w+)"', text))) == [
        "ui_actions", "ui_close_tab", "ui_focus_tab", "ui_invoke",
        "ui_open_tab", "ui_read_state", "ui_screenshot", "ui_sessions",
        "ui_set_title", "ui_wait",
    ]


def test_mcp_still_lists_the_direct_tools():
    # The ui_* half moved to agent_ui_bridge; the direct half must not have
    # been collateral damage of that edit.
    text = _tools_list_text()
    names = set(re.findall(r'"name":\s?"(\w+)"', text))
    assert {
        "ta_candles", "ta_indicator_series", "ta_pattern_search", "ta_pattern_scan",
        "ta_pattern_families", "wf_run", "wf_status", "wf_cancel", "wf_fold",
        "runs_list", "run_get",
    } <= names


def test_ui_set_title_description_still_names_the_gate():
    # The docstrings are the agent-visible contract; app_name/screenshot_doc
    # exist so the extraction did not change a word of them.
    text = _tools_list_text()
    assert "REQUIRED before ui_invoke" in text
    assert "Chartkar browser tab to the front" in text


def test_tools_call_over_http_returns_a_result():
    with _client() as c:
        r = _call(c, _session(c), "ui_sessions", {})
    assert r.status_code == 200, r.text
    assert '"isError":true' not in r.text.replace(" ", "")


def test_tools_call_surfaces_the_no_tab_message_as_a_tool_error():
    # The SDK converts the raised RuntimeError into an MCP tool error, so the
    # agent reads the actionable message rather than a transport failure.
    with _client() as c:
        r = _call(c, _session(c), "ui_invoke", {"action": "x", "args": {}})
    assert r.status_code == 200, r.text
    assert '"isError":true' in r.text.replace(" ", "")
    assert "no UI session connected" in r.text
```

- [ ] **Step 8: Run only the named backend tests**

Run:
```bash
cd /Users/mahmoudparham/projects/auto_trader/backend && uv run pytest tests/test_mcp_direct_tools.py tests/test_mcp_registration.py -q
```
Expected: PASS. If `test_tools_call_surfaces_the_no_tab_message_as_a_tool_error` fails because a previous test left a tab registered on the real `HUB`, that is a genuine ordering bug: no test in these two files registers one, so investigate rather than adding a fixture.

- [ ] **Step 9: Lint the slimmed module for dead names**

Run: `cd /Users/mahmoudparham/projects/auto_trader/backend && uv run ruff check auto_trader/api/mcp_server.py auto_trader/api/agent_bridge.py auto_trader/api/routers/agent.py scripts/agent_bridge_probe.py`
Expected: clean. F401 here means an import survived the code that used it.

- [ ] **Step 10: Commit (explicit paths only)**

```bash
cd /Users/mahmoudparham/projects/auto_trader
git add backend/pyproject.toml backend/uv.lock \
        backend/auto_trader/api/agent_bridge.py \
        backend/auto_trader/api/routers/agent.py \
        backend/auto_trader/api/mcp_server.py \
        backend/scripts/agent_bridge_probe.py \
        backend/tests/test_mcp_registration.py
git commit -m "$(cat <<'EOF'
refactor(mcp): consume agent-ui-bridge for the hub and the ui_* tools

BridgeHub, the WebSocket pump and all ten ui_* tools now come from the
agent-ui-bridge package. agent_bridge.py keeps the HUB instance, the route
calls serve_tab, and mcp_server.py is down to the direct ta_*/wf_*/runs_*
tools plus one register_ui_tools call whose app_name and screenshot_doc keep
every agent-visible docstring byte-identical.

The moved tests went with the code; test_mcp_registration.py keeps the
transport-level checks that the mount answers at exactly /mcp and lists both
tool families.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SoZ7wfsyG7HZxLXuC4au8p
EOF
)"
```

The four deleted test files are NOT in that `git add` list: Step 6's `git rm -f`
already staged their deletion, and adding a path that no longer exists aborts
the whole command.

---

### Task 8: Chartkar docs, extension removal, and the final push check

**Files:**
- Modify: `/Users/mahmoudparham/projects/auto_trader/CLAUDE.md` (the "Agent UI Bridge" section)
- Delete: `/Users/mahmoudparham/projects/auto_trader/extension/` (all nine files)

**Interfaces:**
- Consumes: Tasks 6 and 7.
- Produces: docs that describe where the code actually lives; no stale copy of the extension in Chartkar.

- [ ] **Step 1: Update the probe line in CLAUDE.md**

In the "Agent UI Bridge" section, replace:

```
End-to-end probe: `cd backend && python3 -m scripts.agent_bridge_probe
[--url URL] [--run] [--invoke ACTION --args JSON] [--screenshot [PATH]]`.
`--screenshot` (default path `chart.png`) calls `ui_screenshot`, decodes the
image block, and writes it to PATH.
```

with:

```
End-to-end probe: `cd backend && python3 -m agent_ui_bridge.probe
[--url URL] [--read-state KEY] [--invoke ACTION --args JSON]
[--screenshot [PATH]]`. `--screenshot` (default path `screenshot.png`) calls
`ui_screenshot`, decodes the image block, and writes it to PATH. The old
`--run` shorthand is gone; use `--invoke backtest.run`.
```

- [ ] **Step 2: Update the Tab Bridge paragraph in CLAUDE.md**

Replace:

```
Tab Bridge extension (`extension/` at the repo root, generic, unpacked
install per `extension/README.md`): a page can screenshot or focus its own
tab through `chrome.debugger` / `chrome.tabs`, which works while the tab is
backgrounded.
```

with:

```
Tab Bridge extension (`extension/` in the agent-ui-bridge repo, generic,
unpacked install per that repo's `extension/README.md`): a page can
screenshot or focus its own tab through `chrome.debugger` / `chrome.tabs`,
which works while the tab is backgrounded. Action descriptions and the
TAB_HIDDEN message still say "extension/README.md"; that path now means the
one in github.com/maparham/agent-ui-bridge, and the wording is left alone on
purpose because it is part of the agent-visible contract.
```

- [ ] **Step 3: Add a paragraph naming the package**

Immediately after the paragraph that begins "MCP agents can drive the running UI: connect to `http://localhost:8000/mcp`", insert:

```
The generic half of this lives in github.com/maparham/agent-ui-bridge: the
npm package `agent-ui-bridge` (action registry, relay client, confirm gate,
confirm dialog, tab.title.set, the Tab Bridge client) and the python package
of the same name (`agent_ui_bridge`: BridgeHub, serve_tab, the ten ui_*
tools, the probe). Chartkar depends on both by git URL and keeps shims at
`frontend/src/agent/{registry,confirm,index}.ts`,
`frontend/src/agent/AgentConfirmHost.tsx`,
`frontend/src/agent/actions/tab.ts` and `frontend/src/lib/tabBridge.ts`, so
the app's import paths did not move. Chartkar's OWN actions (`chart.*`,
`backtest.*`, `sweep.*`, dealing, drawings, indicators, `market.select`, the
tab helpers) and the direct `ta_*`/`wf_*`/`runs_*` tools stay here. Editing
the bridge itself means editing that repo; `npm link` and
`uv pip install -e ../agent-ui-bridge/python` for local iteration.
```

- [ ] **Step 4: Delete Chartkar's copy of the extension**

```bash
cd /Users/mahmoudparham/projects/auto_trader && git rm -r -f extension
```
Expected: nine files removed.

- [ ] **Step 5: Re-verify nothing in Chartkar still references the deleted directory in code**

```bash
cd /Users/mahmoudparham/projects/auto_trader && grep -rn "extension/README.md\|extension/" --include="*.ts" --include="*.tsx" --include="*.py" frontend/src backend | grep -v node_modules
```
Expected: only the intentional agent-visible strings in `frontend/src/agent/actions/chart.ts` (the `chart.screenshot` description, the TAB_HIDDEN messages and the `tab.focus` NO_EXTENSION message). Leave them exactly as they are; the Global Constraints keep error and description strings byte-identical, and Step 2 documented what the path now means.

- [ ] **Step 6: Commit (explicit paths only)**

```bash
cd /Users/mahmoudparham/projects/auto_trader
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs(agent): point the bridge docs at the agent-ui-bridge repo

The extension, the relay hub and the ui_* tools live in
github.com/maparham/agent-ui-bridge now, so Chartkar's copy of extension/ is
removed and CLAUDE.md names the two packages, the shim paths and the new
probe command.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SoZ7wfsyG7HZxLXuC4au8p
EOF
)"
```

`extension` is not in the `git add` list: Step 4's `git rm -r -f` already staged
every one of those deletions, and the directory no longer exists to be added.

- [ ] **Step 7: Live end-to-end check**

With the backend and frontend running and a browser tab open:

1. `ui_sessions` lists the tab.
2. `ui_set_title("US100 4H review")` succeeds and the tab title gains the robot mark.
3. `ui_screenshot` returns an image plus a text line reading `US100 HOUR_4 (cell <id>) via extension`. The `via extension` half proves the Tab Bridge path still works; the caption half proves Task 6 Step 8 landed on the path that actually ran.
4. `ui_read_state("chart.state")` returns the numeric state.

Expected: all four. A text line reading just `screenshot via canvas` means `caption` is missing from the canvas return site.

- [ ] **Step 8: Push the new repo again only if it changed**

```bash
cd /Users/mahmoudparham/projects/agent-ui-bridge && git status --short && git log --oneline origin/main..HEAD
```
If both are empty, nothing to do: the repo was pushed once at Task 5 and is still current. If a later task forced a fix in the package, commit it by explicit path and `git push`. Chartkar is never pushed, at any point.

---

## Self-Review

**1. Spec coverage**

| Spec section | Task |
| --- | --- |
| Repository layout | 1, 2, 3, 4 |
| Frontend library: package.json, exports, prepare, peer deps | 1 |
| Frontend public API, `BridgeOptions`, `./react`, `./tab-bridge` | 2 |
| `bridge.ts` behavioural change is options only | 2 Step 3 |
| Backend `hub.py` verbatim minus `HUB` | 3 Step 2 |
| Backend `ws.serve_tab` | 3 Step 3 (+ test Step 12) |
| Backend `tools.register_ui_tools`, `TITLE_ACTION`, `_require_titled`, `_friendly`, caption | 3 Step 5 |
| Backend `browser.py` | 3 Step 4 |
| Backend `probe.py` | 3 Step 7 |
| `mcp>=2.0` only dependency | 3 Step 1 |
| Extension moves verbatim, README line | 4 |
| Repo README | 4 Step 4 |
| Chartkar frontend deps + six shims + deletions + `caption` | 6 |
| Chartkar backend deps + three shims + slimmed mcp_server + tests | 7 |
| CLAUDE.md, `extension/` deleted | 8 |
| Ordering constraint (push before rewire) | 5, gated by 5 Step 5 |
| Testing section (three suites new repo, two narrow suites Chartkar, tsc parity, live check) | 2, 3, 4, 6, 7, 8 |
| Security unchanged | no code path touched; guards moved verbatim (3 Step 5), route auth untouched (7 Step 3) |

No gaps.

**2. Placeholder scan**

No "TBD", no "similar to Task N", no "add error handling". Every file that changes has its full new content or an exact old/new replacement pair. The only "copy verbatim" instructions are for files that genuinely move unchanged (`registry.ts`, `confirm.ts`, `tab.ts`, `tabBridge.ts`, `hub.py`, the eight extension source files, `registry.test.ts`, `confirm.test.ts`), each with its edit list spelled out beside it.

**3. Type consistency**

- `startAgentBridge(opts: BridgeOptions)` is defined in Task 2 Step 3 and called with `{ url, token, decorateUrl }` in Task 2 Step 6 (test) and Task 6 Step 7 (Chartkar). Consistent.
- `register_ui_tools(mcp, hub, *, screenshot_action, screenshot_doc, app_name, app_url_label, frontend_url, hosted) -> dict` is defined in Task 3 Step 5 and called with those exact keywords in Task 3 Steps 9/10/11 and Task 7 Step 4. `app_url_label` is optional and only Task 3 Step 9 and Task 7 Step 4 pass it. Consistent.
- `browser.focus_script` / `open_script` / `close_script` (no leading underscore) are defined in Task 3 Step 4 and called that way in Task 3 Step 5. `_osascript` and `_IS_MACOS` keep their underscores because the moved tests monkeypatch those names.
- `serve_tab(hub, websocket)` defined Task 3 Step 3, called Task 3 Step 12 and Task 7 Step 3.
- `caption` is produced in Task 6 Step 8 and consumed in Task 3 Step 5; the fallback string `"screenshot"` is asserted in Task 3 Step 10.
- `probe.cli()` defined in Task 3 Step 7, imported in Task 7 Step 5.
- `AgentConfirmHost` is exported both named and default in Task 2 Step 4; Task 6 Step 4 imports it named.
