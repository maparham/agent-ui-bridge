// Public entry point. React lives behind the "agent-ui-bridge/react" export and
// the extension client behind "agent-ui-bridge/tab-bridge", so importing this
// module pulls in neither.
export type {
  ActionKind, ParamProperty, ParamSchema, ActionContext, AgentAction, ActionManifestEntry,
} from "./registry.js";
export {
  ActionError, registerAction, getAction, listActions, validateArgs, invokeAction,
  clearRegistryForTest,
} from "./registry.js";

export type { InboundFrame, BridgeOptions } from "./bridge.js";
export { startAgentBridge, handleFrame } from "./bridge.js";

export { Signal } from "./signal.js";
export type { AgentConfirmState } from "./confirm.js";
export { agentConfirmSignal, requestAgentConfirm, resolveAgentConfirm } from "./confirm.js";

export { registerTabActions, restoreTabTitle, storedTabTitle, AGENT_TAB_MARK } from "./tab.js";
