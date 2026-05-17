import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { CrisaiRuntimeClient, type UiEvent, type UiRunState } from "@crisai/contracts";
import "./styles.css";

const runtime = new CrisaiRuntimeClient({
  baseUrl: import.meta.env.VITE_CRISAI_RUNTIME_URL ?? "http://127.0.0.1:8000"
});

function App() {
  const [message, setMessage] = useState("");
  const [session, setSession] = useState("default");
  const [mode, setMode] = useState("auto");
  const [verbose, setVerbose] = useState(false);
  const [run, setRun] = useState<UiRunState | null>(null);
  const [events, setEvents] = useState<UiEvent[]>([]);
  const [error, setError] = useState("");
  const latestStatus = useMemo(() => events.at(-1)?.status ?? run?.status ?? "idle", [events, run]);

  async function submitRun(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!message.trim()) return;
    setError("");
    setEvents([]);
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
        setEvents((current) => [...current, item]);
        if (item.event_type === "run_completed" || item.event_type === "run_failed") {
          source.close();
          runtime.getRun(started.run_id).then(setRun).catch((reason: unknown) => setError(String(reason)));
        }
      },
      () => setError("Runtime event stream disconnected.")
    );
  }

  async function checkpoint(action: "continue" | "redirect" | "stop") {
    if (!run) return;
    await runtime.submitCheckpoint(run.run_id, { action });
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
            <input value={session} onChange={(event) => setSession(event.target.value)} />
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
          <button type="submit">Run</button>
        </div>
      </form>

      {error ? <section className="alert">{error}</section> : null}

      <section className="workspace">
        <StageRail events={events} />
        <Transcript events={events} onCheckpoint={checkpoint} />
      </section>
    </main>
  );
}

function StageRail({ events }: { events: UiEvent[] }) {
  const stageEvents = events.filter((event) => event.stage || event.agent_id);
  return (
    <aside className="stage-rail" aria-label="Workflow stages">
      <h2>Stages</h2>
      {stageEvents.length === 0 ? <p>No stages yet.</p> : null}
      {stageEvents.map((event, index) => (
        <article key={`${event.event_type}-${event.timestamp}-${index}`} className={`stage ${event.event_type}`}>
          <strong>{event.agent_id ?? event.stage ?? event.event_type}</strong>
          <span>{event.status}</span>
        </article>
      ))}
    </aside>
  );
}

function Transcript({
  events,
  onCheckpoint
}: {
  events: UiEvent[];
  onCheckpoint: (action: "continue" | "redirect" | "stop") => Promise<void>;
}) {
  return (
    <section className="transcript" aria-live="polite">
      {events.length === 0 ? <p>No output yet.</p> : null}
      {events.map((event, index) => (
        <article key={`${event.event_type}-${event.timestamp}-${index}`} className="event-card">
          <header>
            <h2>{event.title}</h2>
            <span>{event.event_type}</span>
          </header>
          {event.summary ? <p className="summary">{event.summary}</p> : null}
          {event.content ? <pre>{event.content}</pre> : null}
          {event.event_type === "checkpoint_requested" ? (
            <div className="checkpoint-actions">
              <button type="button" onClick={() => onCheckpoint("continue")}>Continue</button>
              <button type="button" onClick={() => onCheckpoint("stop")}>Stop</button>
            </div>
          ) : null}
        </article>
      ))}
    </section>
  );
}

createRoot(document.getElementById("root") as HTMLElement).render(<App />);
