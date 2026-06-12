import { type UiEvent } from "@crisai/contracts";
import {
  eventDisplayTitle,
  liveRunStatus,
  liveStageDisplayName,
  shouldShowTranscriptEvent
} from "../runDisplay.js";
import { MarkdownContent } from "./markdown.js";

export type StageDetail = { label: string; status: string; content: string };

export function Transcript({
  events,
  finalContent,
  liveStageEvent,
  checkpointWaiting,
  verbose,
  redirectInstruction,
  onRedirectInstructionChange,
  onCheckpoint,
  stageDetail,
  onClearStage
}: {
  events: UiEvent[];
  finalContent: string;
  liveStageEvent: UiEvent | null;
  checkpointWaiting: boolean;
  verbose: boolean;
  redirectInstruction: string;
  onRedirectInstructionChange: (value: string) => void;
  onCheckpoint: (action: "continue" | "redirect" | "stop", instruction?: string) => Promise<void>;
  stageDetail: StageDetail | null;
  onClearStage: () => void;
}) {
  const visibleEvents = events.filter((event) => shouldShowTranscriptEvent(event, verbose));
  const liveStatus = liveRunStatus(checkpointWaiting, liveStageEvent);

  if (stageDetail) {
    return (
      <section className="transcript" aria-label="Step output">
        <article className="event-card stage-detail-card">
          <header className="stage-detail-head">
            <h2>{stageDetail.label}</h2>
            <button type="button" className="btn-ghost btn-compact" onClick={onClearStage}>
              Show latest
            </button>
          </header>
          {stageDetail.content.trim()
            ? <MarkdownContent content={stageDetail.content} />
            : <p className="stage-detail-empty">This step produced no readable output{stageDetail.status === "pending" ? " yet" : ""}.</p>}
        </article>
      </section>
    );
  }

  return (
    <section className="transcript" aria-label="Run transcript">
      <p className="live-status" role="status" aria-live="polite" aria-atomic="true">
        {liveStatus}
      </p>
      {events.length === 0 ? <p>No output yet.</p> : null}
      {liveStageEvent ? (
        <article className="event-card streaming-card" aria-labelledby="streaming-card-heading">
          <header>
            <h2 id="streaming-card-heading">{liveStageDisplayName(liveStageEvent)}</h2>
            <span>streaming</span>
          </header>
          <pre aria-label={`Live output from ${liveStageDisplayName(liveStageEvent)}`}>{liveStageEvent.content}</pre>
        </article>
      ) : null}
      {visibleEvents.map((event, index) => (
        <article key={`${event.event_type}-${event.timestamp}-${index}`} className="event-card">
          <header>
            <h2>{eventDisplayTitle(event)}</h2>
          </header>
          {event.summary ? <p className="summary">{event.summary}</p> : null}
          {event.event_type === "checkpoint_requested" ? (
            <CheckpointDecisionPanel
              event={event}
              checkpointWaiting={checkpointWaiting}
              redirectInstruction={redirectInstruction}
              onRedirectInstructionChange={onRedirectInstructionChange}
              onCheckpoint={onCheckpoint}
              verbose={verbose}
            />
          ) : (
            <EventContent event={event} verbose={verbose} />
          )}
        </article>
      ))}
      {finalContent ? (
        <article className="event-card final-card">
          <header>
            <h2>Final answer</h2>
          </header>
          <MarkdownContent content={finalContent} />
        </article>
      ) : null}
    </section>
  );
}

function CheckpointDecisionPanel({
  event,
  checkpointWaiting,
  redirectInstruction,
  onRedirectInstructionChange,
  onCheckpoint,
  verbose
}: {
  event: UiEvent;
  checkpointWaiting: boolean;
  redirectInstruction: string;
  onRedirectInstructionChange: (value: string) => void;
  onCheckpoint: (action: "continue" | "redirect" | "stop", instruction?: string) => Promise<void>;
  verbose: boolean;
}) {
  const evidenceDetail = event.content || event.verbose_content;
  return (
    <div className="checkpoint-panel">
      <p className="checkpoint-decision">
        Review the retrieved sources before the run spends more time drafting the answer.
      </p>
      <div className="checkpoint-actions" aria-label="Checkpoint actions">
        <label>
          Redirect guidance
          <textarea
            value={redirectInstruction}
            onChange={(item) => onRedirectInstructionChange(item.target.value)}
            disabled={!checkpointWaiting}
            placeholder="Tell retrieval what to change before continuing"
          />
        </label>
        <button type="button" disabled={!checkpointWaiting} onClick={() => onCheckpoint("continue")}>
          Continue
          <small>Use these sources</small>
        </button>
        <button
          type="button"
          disabled={!checkpointWaiting || !redirectInstruction.trim()}
          onClick={() => onCheckpoint("redirect", redirectInstruction)}
        >
          Redirect
          <small>Refine retrieval</small>
        </button>
        <button type="button" disabled={!checkpointWaiting} onClick={() => onCheckpoint("stop")}>
          Stop
          <small>End this run</small>
        </button>
      </div>
      {evidenceDetail ? (
        <details className="checkpoint-evidence" open={verbose}>
          <summary>Evidence detail</summary>
          <pre>{verbose && event.verbose_content ? event.verbose_content : evidenceDetail}</pre>
        </details>
      ) : null}
    </div>
  );
}

function EventContent({ event, verbose }: { event: UiEvent; verbose: boolean }) {
  const content = verbose && event.verbose_content ? event.verbose_content : event.content;
  if (content.trim() && content.trim() === event.summary.trim()) return null;
  if (!content) return null;
  return <pre>{content}</pre>;
}
