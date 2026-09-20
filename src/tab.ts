// Browser-tab actions that are not about the page: naming the tab. The
// backend's ui_set_title tool calls tab.title.set and refuses every other UI
// tool on a session until it has run, so an agent-driven tab is always named.
// The ✻ mark is stamped here, not left to the agent, so the owner can
// tell agent tabs from their own at a glance whatever title the agent picked.
import { ActionError, registerAction } from "./registry.js";

export const AGENT_TAB_MARK = "✻";

// The title survives a reload: sessionStorage is per tab and outlives the
// page, so a reloaded tab restores its name and announces it when the bridge
// reconnects, instead of coming back as an untitled session.
const TITLE_KEY = "agent-ui-bridge.title";

function remember(title: string): void {
  try { sessionStorage.setItem(TITLE_KEY, title); } catch { /* storage blocked */ }
}

/** The title this tab was last given by an agent, or null. */
export function storedTabTitle(): string | null {
  try { return sessionStorage.getItem(TITLE_KEY); } catch { return null; }
}

/** Re-apply a remembered title to document.title (call once at startup). */
export function restoreTabTitle(): string | null {
  const title = storedTabTitle();
  if (title) document.title = title;
  return title;
}

export function registerTabActions(): void {
  registerAction({
    name: "tab.title.set",
    description:
      "Name this browser tab (document.title) so the owner can tell agent-driven tabs apart. Prefixes a ✻ mark. Required before other actions; normally invoked through the ui_set_title MCP tool.",
    kind: "write",
    params: {
      type: "object",
      properties: { title: { type: "string", description: "short, specific, e.g. 'Orders review'" } },
      required: ["title"],
    },
    handler: async (args) => {
      const raw = String(args.title ?? "").trim();
      if (!raw) throw new ActionError("INVALID_ARGS", "title must be a non-empty string");
      const title = raw.startsWith(AGENT_TAB_MARK) ? raw : `${AGENT_TAB_MARK} ${raw}`;
      document.title = title;
      remember(title);
      return { title };
    },
  });
}
