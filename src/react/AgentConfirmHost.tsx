// Renders the pending agent confirm request (if any) as a blocking modal.
// Approve runs the parked action handler; Reject (or timeout, handled in
// confirm.ts) refuses it. No CSS ships with this: pass the host app's own
// modal class names, and style .modal-head / .confirm-body / .modal-foot /
// .ghost / .confirm-primary / .agent-confirm-warning there too.
import { useSyncExternalStore } from "react";
import { agentConfirmSignal, resolveAgentConfirm } from "../confirm.js";

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
