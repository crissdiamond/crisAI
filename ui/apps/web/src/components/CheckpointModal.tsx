import { type UiEvent } from "@crisai/contracts";

// Retrieval checkpoint as a modal so the Continue / Redirect / Stop choice is
// never buried in the run output. Shown only while the run is paused waiting on
// the user, so its actions are always live.
export function CheckpointModal({
  event,
  redirectInstruction,
  onRedirectInstructionChange,
  onCheckpoint,
  verbose
}: {
  event: UiEvent;
  redirectInstruction: string;
  onRedirectInstructionChange: (value: string) => void;
  onCheckpoint: (action: "continue" | "redirect" | "stop", instruction?: string) => Promise<void>;
  verbose: boolean;
}) {
  const evidenceDetail = event.content || event.verbose_content;
  return (
    <div className="modal-overlay" role="presentation">
      <div
        className="modal checkpoint-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="checkpoint-title"
      >
        <div className="modal-header">
          <h2 id="checkpoint-title">Review sources</h2>
        </div>
        <p className="checkpoint-decision">
          Review the retrieved sources before the run spends more time drafting the answer.
        </p>
        <div className="checkpoint-actions" aria-label="Checkpoint actions">
          <label>
            Redirect guidance
            <textarea
              value={redirectInstruction}
              onChange={(item) => onRedirectInstructionChange(item.target.value)}
              placeholder="Tell retrieval what to change before continuing"
            />
          </label>
          <div className="checkpoint-buttons">
            <button type="button" onClick={() => onCheckpoint("continue")}>
              Continue
              <small>Use these sources</small>
            </button>
            <button
              type="button"
              className="btn-secondary"
              disabled={!redirectInstruction.trim()}
              onClick={() => onCheckpoint("redirect", redirectInstruction)}
            >
              Redirect
              <small>Refine retrieval</small>
            </button>
            <button type="button" className="btn-secondary" onClick={() => onCheckpoint("stop")}>
              Stop
              <small>End this run</small>
            </button>
          </div>
        </div>
        {evidenceDetail ? (
          <details className="checkpoint-evidence" open={verbose}>
            <summary>Evidence detail</summary>
            <pre>{verbose && event.verbose_content ? event.verbose_content : evidenceDetail}</pre>
          </details>
        ) : null}
      </div>
    </div>
  );
}
