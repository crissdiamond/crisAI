import React, { useState } from "react";
import {
  type UiHistoryEntry,
  type UiSessionContext,
  type UiSessionRecallResult
} from "@crisai/contracts";
import { humanizeLabel } from "../runDisplay.js";
import { asStringList, formatRecallScore, humanizeError } from "../lib/format.js";

type SessionContextStatus = "idle" | "loading" | "ready" | "empty" | "error";

export function HistoryPanel({
  history,
  sessionContext,
  contextStatus,
  contextError,
  onRefreshContext,
  showContextPreview = true
}: {
  history: UiHistoryEntry[];
  sessionContext: UiSessionContext | null;
  contextStatus: SessionContextStatus;
  contextError: string;
  onRefreshContext: (sessionName?: string, query?: string) => Promise<void>;
  showContextPreview?: boolean;
}) {
  const recentHistory = history.slice(-6);
  const [query, setQuery] = useState("");
  const sessionName = sessionContext?.session;

  function submitContextQuery(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void onRefreshContext(sessionName, query.trim() || undefined);
  }

  return (
    <aside className="history-panel" aria-label="Session history">
      {showContextPreview ? (
        <section className="session-context-preview" aria-labelledby="session-context-heading">
          <div className="panel-heading">
            <h3 id="session-context-heading">Context preview</h3>
            <span>{contextStatus === "loading" ? "loading" : sessionContext?.session ?? "current"}</span>
          </div>
          <form className="context-query" onSubmit={submitContextQuery}>
            <label>
              Recall query
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Optional focus"
                disabled={contextStatus === "loading"}
              />
            </label>
            <button type="submit" aria-label="Refresh context preview" disabled={contextStatus === "loading"}>
              Refresh
            </button>
          </form>
          <SessionContextBody context={sessionContext} status={contextStatus} error={contextError} />
        </section>
      ) : null}
      {recentHistory.length === 0 ? <p>No session history yet.</p> : null}
      {recentHistory.map((entry, index) => (
        <article key={`${entry.role}-${index}`} className="history-entry">
          <strong>{entry.role}</strong>
          <p>{entry.content}</p>
        </article>
      ))}
    </aside>
  );
}

export function SessionContextBody({
  context,
  status,
  error
}: {
  context: UiSessionContext | null;
  status: SessionContextStatus;
  error: string;
}) {
  if (status === "loading") {
    return <p className="context-status" role="status">Loading session context.</p>;
  }
  if (status === "idle") {
    return <p className="context-status">Context will load with the session.</p>;
  }
  if (status === "error") {
    return (
      <p className="context-status context-error" role="status">
        Context unavailable: {humanizeError(error)}
      </p>
    );
  }
  if (!context || status === "empty") {
    return <p className="context-status">No structured context has been captured for this session yet.</p>;
  }

  const fields = [
    ["What we're working on", context.memory.task_goal],
    ["Where things stand", context.memory.current_state],
    ["Summary", context.memory.summary],
    ["In scope", context.memory.scope],
    ["Assumptions", context.memory.assumptions],
    ["Constraints", context.memory.constraints],
    ["Decisions made", context.memory.important_decisions],
    ["Options we ruled out", context.memory.rejected_options],
    ["What the sources say", context.memory.source_findings],
    ["Sources we know", context.memory.known_sources],
    ["Active documents", context.memory.active_artefacts],
    ["Open questions", context.memory.open_questions],
    ["Next steps", context.memory.next_actions],
    ["Recent outputs", context.memory.last_outputs],
    ["Avoid repeating", context.memory.do_not_repeat]
  ].flatMap(([label, value]) => {
    const items = asStringList(value);
    return items.length > 0 ? [{ label: String(label), items }] : [];
  });

  return (
    <div className="context-body">
      {fields.length > 0 ? (
        <section className="context-section">
          <h4>What we remember</h4>
          {fields.map((field) => (
            <div key={field.label} className="context-field">
              <strong>{field.label}</strong>
              <ul>
                {field.items.slice(0, 4).map((item, index) => (
                  <li key={`${field.label}-${index}`}>{item}</li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      ) : null}
      {context.baseline_brief.trim() ? (
        <details className="context-section context-raw-brief">
          <summary>Raw brief</summary>
          <p className="context-brief">{context.baseline_brief}</p>
        </details>
      ) : null}
      <section className="context-section">
        <h4>Recall</h4>
        <p className="context-budget">
          {context.budget.recall_count} recalled, limit {context.budget.recall_limit}
          {context.budget.truncated ? ", truncated" : ""}
        </p>
        {context.recall_results.length === 0 ? <p>No recall matches for this preview.</p> : null}
        {context.recall_results.map((result, index) => (
          <RecallResultCard key={`${result.field}-${index}`} result={result} />
        ))}
      </section>
    </div>
  );
}

function RecallResultCard({ result }: { result: UiSessionRecallResult }) {
  return (
    <article className="recall-result">
      <header>
        <strong>{humanizeLabel(result.field, "Memory")}</strong>
        <span>score {formatRecallScore(result.score)}</span>
      </header>
      <p>{result.content}</p>
      <small>{result.provenance}</small>
      {result.matched_terms.length > 0 ? (
        <ul className="matched-terms" role="list" aria-label="Matched terms">
          {result.matched_terms.slice(0, 5).map((term) => (
            <li key={term}>{term}</li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}
