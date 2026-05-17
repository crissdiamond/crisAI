import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  CrisaiRuntimeClient,
  cssVariablesForSurface,
  deriveStageSummaries,
  isCheckpointWaiting,
  isTerminalEvent,
  latestFinalContent,
  type UiEvent,
  type UiHistoryEntry,
  type UiRunState,
  type UiSessionState,
  type UiStageSummary
} from "@crisai/contracts";
import "./styles.css";

const runtime = new CrisaiRuntimeClient({
  baseUrl: import.meta.env.VITE_CRISAI_RUNTIME_URL ?? "http://127.0.0.1:8000"
});

function App() {
  const [message, setMessage] = useState("");
  const [session, setSession] = useState("default");
  const [sessions, setSessions] = useState<string[]>(["default"]);
  const [history, setHistory] = useState<UiHistoryEntry[]>([]);
  const [memorySummary, setMemorySummary] = useState("");
  const [newSessionName, setNewSessionName] = useState("");
  const [mode, setMode] = useState("auto");
  const [verbose, setVerbose] = useState(false);
  const [run, setRun] = useState<UiRunState | null>(null);
  const [events, setEvents] = useState<UiEvent[]>([]);
  const [error, setError] = useState("");
  const [redirectInstruction, setRedirectInstruction] = useState("");
  const latestStatus = useMemo(() => events.at(-1)?.status ?? run?.status ?? "idle", [events, run]);
  const stages = useMemo(() => deriveStageSummaries(events, run?.expected_stages ?? []), [events, run]);
  const finalContent = useMemo(() => latestFinalContent(run, events), [run, events]);
  const checkpointWaiting = useMemo(() => isCheckpointWaiting(events), [events]);

  useEffect(() => {
    runtime
      .getTheme()
      .then((theme) => {
        const variables = cssVariablesForSurface(theme, "web");
        for (const [name, value] of Object.entries(variables)) {
          document.documentElement.style.setProperty(name, value);
        }
      })
      .catch(() => {
        // Fallback CSS variables keep the experimental client usable offline.
      });
  }, []);

  useEffect(() => {
    refreshSessions().catch((reason: unknown) => setError(String(reason)));
  }, []);

  async function refreshSessions(preferredSession?: string) {
    const state = preferredSession ? await runtime.getSession(preferredSession) : await runtime.listSessions();
    applySessionState(state);
  }

  function applySessionState(state: UiSessionState) {
    setSessions(state.sessions.length > 0 ? state.sessions : [state.current_session]);
    setSession(state.current_session);
    setHistory(state.history);
    setMemorySummary(state.memory?.summary ?? "");
  }

  async function selectSession(value: string) {
    setError("");
    await refreshSessions(value);
  }

  async function createSession(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!newSessionName.trim()) return;
    setError("");
    const state = await runtime.createSession(newSessionName);
    applySessionState(state);
    setNewSessionName("");
  }

  async function submitRun(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!message.trim()) return;
    setError("");
    setEvents([]);
    setRun(null);
    setRedirectInstruction("");
    const started = await runtime.startRun({
      message,
      session,
      mode,
      verbose,
      agent: "auto",
      review: false
    });
    setRun(started);
    setEvents(started.events);
    const source = runtime.subscribe(
      started.run_id,
      (item) => {
        setEvents((current) => dedupeEvents([...current, item]));
        if (isTerminalEvent(item)) {
          source.close();
          runtime
            .getRun(started.run_id)
            .then((state) => {
              setRun(state);
              return refreshSessions(state.session);
            })
            .catch((reason: unknown) => setError(String(reason)));
        }
      },
      () => setError("Runtime event stream disconnected.")
    );
  }

  async function checkpoint(action: "continue" | "redirect" | "stop", instruction = "") {
    if (!run) return;
    await runtime.submitCheckpoint(run.run_id, { action, redirect_instruction: instruction });
    setRedirectInstruction("");
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Architecture workstation</p>
          <h1>crisAI Web</h1>
        </div>
        <p className="status">status: {latestStatus}</p>
      </header>

      <form className="composer" onSubmit={submitRun}>
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Ask for a recommendation, summary, option paper, HLD, or review..."
        />
        <div className="controls">
          <label>
            Session
            <select value={session} onChange={(event) => void selectSession(event.target.value)}>
              {sessions.map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
          </label>
          <label>
            Mode
            <select value={mode} onChange={(event) => setMode(event.target.value)}>
              <option value="auto">auto</option>
              <option value="single">single</option>
              <option value="pipeline">pipeline</option>
              <option value="peer">peer</option>
            </select>
          </label>
          <label className="toggle">
            <input type="checkbox" checked={verbose} onChange={(event) => setVerbose(event.target.checked)} />
            Verbose
          </label>
          <button type="submit" disabled={latestStatus === "running" || latestStatus === "checkpoint_waiting"}>
            Run
          </button>
        </div>
      </form>

      <form className="session-create" onSubmit={createSession}>
        <label>
          New session
          <input
            value={newSessionName}
            onChange={(event) => setNewSessionName(event.target.value)}
            placeholder="task-name"
          />
        </label>
        <button type="submit">Create</button>
      </form>

      {error ? <section className="alert">{error}</section> : null}

      <section className="workspace">
        <StageRail stages={stages} />
        <Transcript
          events={events}
          finalContent={finalContent}
          checkpointWaiting={checkpointWaiting}
          redirectInstruction={redirectInstruction}
          onRedirectInstructionChange={setRedirectInstruction}
          onCheckpoint={checkpoint}
        />
        <HistoryPanel history={history} memorySummary={memorySummary} />
      </section>
    </main>
  );
}

function StageRail({ stages }: { stages: UiStageSummary[] }) {
  return (
    <aside className="stage-rail" aria-label="Workflow stages">
      <h2>Stages</h2>
      {stages.length === 0 ? <p>No stages yet.</p> : null}
      {stages.map((stage) => (
        <article key={stage.key} className={`stage stage-${stage.status}`}>
          <strong>{stage.label}</strong>
          <span>{stage.status}</span>
          {stage.summary ? <small>{stage.summary}</small> : null}
        </article>
      ))}
    </aside>
  );
}

function HistoryPanel({ history, memorySummary }: { history: UiHistoryEntry[]; memorySummary: string }) {
  const recentHistory = history.slice(-6);
  return (
    <aside className="history-panel" aria-label="Session history">
      <h2>Session</h2>
      {memorySummary ? <p className="memory-summary">{memorySummary}</p> : null}
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

function Transcript({
  events,
  finalContent,
  checkpointWaiting,
  redirectInstruction,
  onRedirectInstructionChange,
  onCheckpoint
}: {
  events: UiEvent[];
  finalContent: string;
  checkpointWaiting: boolean;
  redirectInstruction: string;
  onRedirectInstructionChange: (value: string) => void;
  onCheckpoint: (action: "continue" | "redirect" | "stop", instruction?: string) => Promise<void>;
}) {
  return (
    <section className="transcript" aria-live="polite">
      {events.length === 0 ? <p>No output yet.</p> : null}
      {events.filter((event) => event.event_type !== "final_answer").map((event, index) => (
        <article key={`${event.event_type}-${event.timestamp}-${index}`} className="event-card">
          <header>
            <h2>{event.title}</h2>
            <span>{event.event_type}</span>
          </header>
          {event.summary ? <p className="summary">{event.summary}</p> : null}
          {event.content ? <pre>{event.content}</pre> : null}
          {event.event_type === "checkpoint_requested" ? (
            <div className="checkpoint-actions">
              <label>
                Redirect guidance
                <textarea
                  value={redirectInstruction}
                  onChange={(item) => onRedirectInstructionChange(item.target.value)}
                  disabled={!checkpointWaiting}
                />
              </label>
              <button type="button" disabled={!checkpointWaiting} onClick={() => onCheckpoint("continue")}>Continue</button>
              <button
                type="button"
                disabled={!checkpointWaiting || !redirectInstruction.trim()}
                onClick={() => onCheckpoint("redirect", redirectInstruction)}
              >
                Redirect
              </button>
              <button type="button" disabled={!checkpointWaiting} onClick={() => onCheckpoint("stop")}>Stop</button>
            </div>
          ) : null}
        </article>
      ))}
      {finalContent ? (
        <article className="event-card final-card">
          <header>
            <h2>Final answer</h2>
            <span>final_answer</span>
          </header>
          <pre>{finalContent}</pre>
        </article>
      ) : null}
    </section>
  );
}

function dedupeEvents(items: UiEvent[]): UiEvent[] {
  const seen = new Set<string>();
  return items.filter((event) => {
    const key = `${event.event_type}-${event.timestamp}-${event.agent_id ?? ""}-${event.stage ?? ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

createRoot(document.getElementById("root") as HTMLElement).render(<App />);
