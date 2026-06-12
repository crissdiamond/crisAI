import { MarkdownContent } from "./markdown.js";

export type StageDetail = { label: string; status: string; content: string };

// Focused run view: shows only the output of one stage at a time. By default
// it auto-follows the running agent; when the user pins a stage from the rail
// it stays there (running continues) until they choose to follow live again.
export function Transcript({
  focusedStage,
  isLiveFocus,
  pinned,
  running,
  hasStages,
  onFollowLive
}: {
  focusedStage: StageDetail | null;
  isLiveFocus: boolean;
  pinned: boolean;
  running: boolean;
  hasStages: boolean;
  onFollowLive: () => void;
}) {
  if (!hasStages || !focusedStage) {
    return (
      <section className="transcript" aria-label="Run output">
        <p className="run-empty">{running ? "Starting…" : "Ask a question to begin."}</p>
      </section>
    );
  }

  const empty = !focusedStage.content.trim();
  return (
    <section className="transcript" aria-label="Step output">
      <article className="event-card stage-focus-card">
        <header className="stage-focus-head">
          <div className="stage-focus-title">
            <h2>{focusedStage.label}</h2>
            <span
              className={`stage-focus-status${isLiveFocus ? " stage-focus-status--live" : ""}`}
              role="status"
              aria-live="polite"
            >
              {isLiveFocus ? "live" : focusedStage.status}
            </span>
          </div>
          {pinned && running ? (
            <button type="button" className="btn-secondary btn-compact" onClick={onFollowLive}>
              Follow live ▸
            </button>
          ) : null}
        </header>
        {empty ? (
          <p className="stage-detail-empty">
            This step produced no readable output{focusedStage.status === "pending" || running ? " yet" : ""}.
          </p>
        ) : (
          <MarkdownContent content={focusedStage.content} />
        )}
      </article>
    </section>
  );
}
