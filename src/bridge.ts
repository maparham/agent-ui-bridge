// WebSocket client side of the agent UI bridge. Connects to the host app's
// relay endpoint, executes registry actions on request, and streams progress
// for long-running invocations. Frame shapes are mirrored in the Python
// package's hub.py.
import {
  ActionError, getAction, invokeAction, listActions, validateArgs,
} from "./registry.js";
import { requestAgentConfirm } from "./confirm.js";
import { storedTabTitle } from "./tab.js";

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
        // Tell the hub the name this tab already carries (a reload or a
        // backend restart would otherwise leave the session untitled).
        const title = storedTabTitle();
        if (title && ws?.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ event: "title", title }));
        }
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
