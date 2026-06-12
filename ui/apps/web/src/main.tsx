import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  cssVariablesForSurface,
  deriveStageSummaries,
  isCheckpointWaiting,
  isTerminalEvent,
  latestFinalContent,
  type UiEvent,
  type UiHistoryEntry,
  type UiRunState,
  type UiSessionContext,
  type UiSessionState
} from "@crisai/contracts";
import { latestLiveStageEvent, stageOutputContent } from "./runDisplay.js";
import { apiKeyStorageKey, configuredApiKey, runtime } from "./lib/runtime.js";
import { asStringList, dedupeEvents, humanizeError, isAuthError } from "./lib/format.js";
import { StatusBadge } from "./components/StatusBadge.js";
import { StageRail } from "./components/StageRail.js";
import { Transcript, type StageDetail } from "./components/Transcript.js";
import { CheckpointModal } from "./components/CheckpointModal.js";
import { WorkspaceBrowser } from "./components/WorkspacePanel.js";
import { HistoryPanel, SessionContextBody } from "./components/SessionPanel.js";
import { SharePointAuthDialog } from "./components/SharePointAuthDialog.js";
import "./styles.css";

type SecondaryView = null | "workspace" | "history" | "memory";

function App() {
  const [apiKeyInput, setApiKeyInput] = useState(localStorage.getItem(apiKeyStorageKey) ?? configuredApiKey);
  const [apiKeyConfigured, setApiKeyConfigured] = useState(Boolean(apiKeyInput.trim()));
  const [secondaryView, setSecondaryView] = useState<SecondaryView>(null);
  const [showSharePointAuth, setShowSharePointAuth] = useState(false);
  const [message, setMessage] = useState("");
  const [session, setSession] = useState("default");
  const [sessions, setSessions] = useState<string[]>(["default"]);
  const [history, setHistory] = useState<UiHistoryEntry[]>([]);
  const [sessionContext, setSessionContext] = useState<UiSessionContext | null>(null);
  const [sessionContextStatus, setSessionContextStatus] = useState<"idle" | "loading" | "ready" | "empty" | "error">("idle");
  const [sessionContextError, setSessionContextError] = useState("");
  const [newSessionName, setNewSessionName] = useState("");
  const [showNewSession, setShowNewSession] = useState(false);
  const [mode, setMode] = useState("auto");
  const [verbose, setVerbose] = useState(false);
  const [retrievalCheckpoint, setRetrievalCheckpoint] = useState(true);
  const [run, setRun] = useState<UiRunState | null>(null);
  const [events, setEvents] = useState<UiEvent[]>([]);
  const [error, setError] = useState("");
  const [apiKeyHint, setApiKeyHint] = useState(false);
  const [redirectInstruction, setRedirectInstruction] = useState("");
  const [selectedStage, setSelectedStage] = useState<string | null>(null);

  /** Sets the single error region from a failure and hints the API key field on auth errors. */
  function reportError(reason: unknown) {
    setError(humanizeError(reason));
    setApiKeyHint(isAuthError(reason));
  }

  /** Clears the single error region before a new action. */
  function clearError() {
    setError("");
    setApiKeyHint(false);
  }
  const latestStatus = useMemo(() => events.at(-1)?.status ?? run?.status ?? "idle", [events, run]);
  const stages = useMemo(() => deriveStageSummaries(events, run?.expected_stages ?? []), [events, run]);
  const finalContent = useMemo(() => latestFinalContent(run, events), [run, events]);
  const checkpointWaiting = useMemo(() => isCheckpointWaiting(events), [events]);
  const liveStageEvent = useMemo(() => latestLiveStageEvent(events), [events]);
  const liveStageKey = liveStageEvent ? liveStageEvent.agent_id ?? liveStageEvent.stage ?? null : null;
  const running = latestStatus === "running" || latestStatus === "checkpoint_waiting";

  // The active stage is the one currently running; when nothing is streaming it
  // falls back to the most advanced (non-pending) stage.
  const activeStageKey = useMemo(() => {
    if (liveStageKey) return liveStageKey;
    for (let index = stages.length - 1; index >= 0; index -= 1) {
      if (stages[index].status !== "pending") return stages[index].key;
    }
    return stages.at(-1)?.key ?? null;
  }, [liveStageKey, stages]);

  // Auto-follow the active stage unless the user has pinned one by clicking it.
  const following = selectedStage === null;
  const effectiveStageKey = selectedStage ?? activeStageKey;

  const focusedStage = useMemo<StageDetail | null>(() => {
    if (!effectiveStageKey) return null;
    const stage = stages.find((item) => item.key === effectiveStageKey);
    if (!stage) return null;
    let content = stageOutputContent(events, effectiveStageKey, verbose);
    // While auto-following the live stage, show its streaming text as it lands.
    if (following && liveStageKey === effectiveStageKey && liveStageEvent?.content) {
      content = liveStageEvent.content;
    }
    // The terminal stage shows the assembled final answer.
    if (effectiveStageKey === stages.at(-1)?.key && finalContent) {
      content = finalContent;
    }
    return { label: stage.label, status: stage.status, content };
  }, [effectiveStageKey, following, stages, events, verbose, liveStageEvent, liveStageKey, finalContent]);

  const isLiveFocus = following && liveStageKey !== null && effectiveStageKey === liveStageKey;
  const checkpointEvent = useMemo(
    () => (checkpointWaiting ? events.find((event) => event.event_type === "checkpoint_requested") ?? null : null),
    [checkpointWaiting, events]
  );

  function toggleStage(key: string) {
    setSelectedStage((current) => (current === key ? null : key));
  }

  useEffect(() => {
    applyApiKey(apiKeyInput);
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

  function applyApiKey(value: string) {
    const token = value.trim();
    runtime.setApiToken(token);
    setApiKeyConfigured(Boolean(token));
    if (token) {
      localStorage.setItem(apiKeyStorageKey, token);
    } else {
      localStorage.removeItem(apiKeyStorageKey);
    }
  }

  function saveApiKey(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearError();
    applyApiKey(apiKeyInput);
    refreshSessions().catch(reportError);
  }

  useEffect(() => {
    refreshSessions().catch(reportError);
  }, []);

  async function refreshSessions(preferredSession?: string) {
    const state = preferredSession ? await runtime.getSession(preferredSession) : await runtime.listSessions();
    applySessionState(state);
  }

  function applySessionState(state: UiSessionState) {
    const sessions = state.sessions ?? [];
    setSessions(sessions.length > 0 ? sessions : [state.current_session]);
    setSession(state.current_session);
    setHistory(state.history);
    // Session memory is a secondary surface; only refresh its context fetch
    // when the memory panel is actually open so initial load stays quiet.
    if (secondaryView === "memory") {
      void loadSessionContext(state.current_session);
    }
  }

  function openSecondaryView(view: SecondaryView) {
    setSecondaryView((current) => {
      const next = current === view ? null : view;
      // Lazily load session context the first time the memory panel opens.
      if (next === "memory" && sessionContextStatus === "idle") {
        void loadSessionContext(session);
      }
      return next;
    });
  }

  async function loadSessionContext(sessionName = session, query?: string) {
    setSessionContextStatus("loading");
    setSessionContextError("");
    setSessionContext(null);
    try {
      const context = await runtime.getSessionContext(sessionName, query, 5);
      setSessionContext(context);
      setSessionContextStatus(hasSessionContextContent(context) ? "ready" : "empty");
    } catch (reason: unknown) {
      setSessionContext(null);
      setSessionContextStatus("error");
      setSessionContextError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  async function selectSession(value: string) {
    clearError();
    await refreshSessions(value);
  }

  async function createSession() {
    if (!newSessionName.trim()) return;
    clearError();
    const state = await runtime.createSession(newSessionName);
    applySessionState(state);
    setNewSessionName("");
    setShowNewSession(false);
  }

  async function submitRun(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!message.trim()) return;
    clearError();
    setEvents([]);
    setRun(null);
    setRedirectInstruction("");
    setSelectedStage(null);
    let started: UiRunState;
    try {
      started = await runtime.startRun({
        message,
        session,
        mode,
        verbose,
        retrieval_checkpoint: retrievalCheckpoint,
        agent: "auto",
        review: false
      });
    } catch (reason: unknown) {
      reportError(reason);
      return;
    }
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
              if (state.status === "failed") {
                const detail = latestFinalContent(state, state.events).trim();
                const shortReason = detail.length > 200 ? `${detail.slice(0, 197)}...` : detail;
                setError(shortReason ? `This run failed. ${shortReason}` : "This run failed.");
                setApiKeyHint(false);
              }
              return refreshSessions(state.session);
            })
            .catch(reportError);
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

  const hasRun = run !== null || events.length > 0;

  return (
    <main className="app-shell">
      <a className="skip-link" href="#run-composer">Skip to run prompt</a>
      <header className="topbar">
        <div className="topbar-brand">
          <h1>crisAI</h1>
          <StatusBadge status={latestStatus} />
        </div>
        <div className="topbar-actions">
          <form className="api-key-form" onSubmit={saveApiKey}>
            <label className="api-key-label" htmlFor="api-key-input">
              <span className="api-key-caption">API key</span>
              <input
                id="api-key-input"
                type="password"
                className={apiKeyHint ? "input-invalid" : undefined}
                aria-invalid={apiKeyHint || undefined}
                value={apiKeyInput}
                onChange={(event) => setApiKeyInput(event.target.value)}
                placeholder={apiKeyConfigured ? "configured" : "optional"}
              />
            </label>
            <button type="submit" className="btn-ghost btn-compact">{apiKeyConfigured ? "Update" : "Set"}</button>
          </form>
          <button
            type="button"
            className="btn-ghost btn-compact"
            onClick={() => setShowSharePointAuth(true)}
          >
            Connect SharePoint
          </button>
        </div>
      </header>
      {showSharePointAuth ? (
        <SharePointAuthDialog onClose={() => setShowSharePointAuth(false)} />
      ) : null}

      <form id="run-composer" className="composer" onSubmit={submitRun} tabIndex={-1}>
        <label className="sr-only" htmlFor="run-message">Your request to crisAI</label>
        <textarea
          id="run-message"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Ask for a recommendation, summary, option paper, high-level design (HLD), or review..."
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
          {showNewSession ? (
            <div className="new-session-inline">
              <label className="sr-only" htmlFor="new-session-name">New session name</label>
              <input
                id="new-session-name"
                value={newSessionName}
                onChange={(event) => setNewSessionName(event.target.value)}
                placeholder="task-name"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Enter") { e.preventDefault(); void createSession(); }
                  if (e.key === "Escape") { setShowNewSession(false); setNewSessionName(""); }
                }}
              />
              <button type="button" onClick={() => void createSession()}>Create</button>
              <button type="button" className="btn-ghost" onClick={() => { setShowNewSession(false); setNewSessionName(""); }}>✕</button>
            </div>
          ) : (
            <button type="button" className="btn-add-session" onClick={() => setShowNewSession(true)} aria-label="New session" title="New session">+</button>
          )}
          <label>
            How to run
            <select value={mode} onChange={(event) => setMode(event.target.value)}>
              <option value="auto">Automatic</option>
              <option value="single">Single agent</option>
              <option value="pipeline">Step-by-step</option>
              <option value="peer">Peer review</option>
            </select>
          </label>
          <div className="toggle-switch">
            <input
              type="checkbox"
              id="toggle-verbose"
              className="toggle-input"
              role="switch"
              checked={verbose}
              onChange={(event) => setVerbose(event.target.checked)}
            />
            <label htmlFor="toggle-verbose" className="toggle-label">Show detailed steps</label>
          </div>
          <div className="toggle-switch">
            <input
              type="checkbox"
              id="toggle-retrieval-checkpoint"
              className="toggle-input"
              role="switch"
              checked={retrievalCheckpoint}
              onChange={(event) => setRetrievalCheckpoint(event.target.checked)}
            />
            <label htmlFor="toggle-retrieval-checkpoint" className="toggle-label">Pause to review sources</label>
          </div>
          <button type="submit" disabled={latestStatus === "running" || latestStatus === "checkpoint_waiting"}>
            Run
          </button>
        </div>
      </form>

      {error ? (
        <div role="alert" className="alert alert-error">
          {error}
          {apiKeyHint ? <span className="alert-hint"> Enter it in the API key field above.</span> : null}
        </div>
      ) : null}

      <section className="run-area" aria-label="Run output">
        {hasRun ? (
          <div className="run-grid">
            <StageRail
              stages={stages}
              selectedStage={selectedStage}
              activeStage={activeStageKey}
              onSelectStage={toggleStage}
            />
            <Transcript
              focusedStage={focusedStage}
              isLiveFocus={isLiveFocus}
              pinned={!following}
              running={running}
              hasStages={stages.length > 0}
              onFollowLive={() => setSelectedStage(null)}
            />
          </div>
        ) : (
          <p className="run-empty">Ask a question to begin.</p>
        )}
      </section>
      {checkpointEvent ? (
        <CheckpointModal
          event={checkpointEvent}
          redirectInstruction={redirectInstruction}
          onRedirectInstructionChange={setRedirectInstruction}
          onCheckpoint={checkpoint}
          verbose={verbose}
        />
      ) : null}

      <nav className="secondary-toolbar" aria-label="Secondary surfaces">
        <button
          type="button"
          className="toolbar-toggle"
          aria-expanded={secondaryView === "workspace"}
          aria-controls="secondary-panel"
          onClick={() => openSecondaryView("workspace")}
        >
          Workspace
        </button>
        <button
          type="button"
          className="toolbar-toggle"
          aria-expanded={secondaryView === "history"}
          aria-controls="secondary-panel"
          onClick={() => openSecondaryView("history")}
        >
          History
        </button>
        <button
          type="button"
          className="toolbar-toggle"
          aria-expanded={secondaryView === "memory"}
          aria-controls="secondary-panel"
          onClick={() => openSecondaryView("memory")}
        >
          Session memory
        </button>
      </nav>

      {secondaryView !== null ? (
        <section
          id="secondary-panel"
          className="secondary-panel"
          aria-label={
            secondaryView === "workspace"
              ? "Workspace"
              : secondaryView === "history"
                ? "Session history"
                : "Session memory"
          }
        >
          <div className="secondary-panel-head">
            <h2>
              {secondaryView === "workspace"
                ? "Workspace"
                : secondaryView === "history"
                  ? "Session history"
                  : "Session memory"}
            </h2>
            <button
              type="button"
              className="btn-ghost btn-compact"
              onClick={() => setSecondaryView(null)}
              aria-label="Close panel"
            >
              Close
            </button>
          </div>
          {secondaryView === "workspace" ? <WorkspaceBrowser session={session} /> : null}
          {secondaryView === "history" ? (
            <HistoryPanel
              history={history}
              sessionContext={sessionContext}
              contextStatus={sessionContextStatus}
              contextError={sessionContextError}
              onRefreshContext={loadSessionContext}
              showContextPreview={false}
            />
          ) : null}
          {secondaryView === "memory" ? (
            <section className="session-context-preview" aria-labelledby="session-context-heading">
              <div className="panel-heading">
                <h3 id="session-context-heading">Context preview</h3>
                <span>{sessionContextStatus === "loading" ? "loading" : sessionContext?.session ?? session}</span>
              </div>
              <SessionMemoryQuery
                sessionName={sessionContext?.session ?? session}
                status={sessionContextStatus}
                onRefreshContext={loadSessionContext}
              />
              <SessionContextBody
                context={sessionContext}
                status={sessionContextStatus}
                error={sessionContextError}
              />
            </section>
          ) : null}
        </section>
      ) : null}
    </main>
  );
}

function SessionMemoryQuery({
  sessionName,
  status,
  onRefreshContext
}: {
  sessionName: string;
  status: "idle" | "loading" | "ready" | "empty" | "error";
  onRefreshContext: (sessionName?: string, query?: string) => Promise<void>;
}) {
  const [query, setQuery] = useState("");

  function submitContextQuery(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void onRefreshContext(sessionName, query.trim() || undefined);
  }

  return (
    <form className="context-query" onSubmit={submitContextQuery}>
      <label>
        Recall query
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Optional focus"
          disabled={status === "loading"}
        />
      </label>
      <button type="submit" aria-label="Refresh context preview" disabled={status === "loading"}>
        Refresh
      </button>
    </form>
  );
}

function hasSessionContextContent(context: UiSessionContext): boolean {
  return Boolean(
    context.baseline_brief.trim() ||
      context.recall_results.length > 0 ||
      asStringList(context.memory.task_goal).length > 0 ||
      asStringList(context.memory.current_state).length > 0 ||
      asStringList(context.memory.scope).length > 0 ||
      asStringList(context.memory.assumptions).length > 0 ||
      asStringList(context.memory.constraints).length > 0 ||
      asStringList(context.memory.important_decisions).length > 0 ||
      asStringList(context.memory.rejected_options).length > 0 ||
      asStringList(context.memory.source_findings).length > 0 ||
      asStringList(context.memory.known_sources).length > 0 ||
      asStringList(context.memory.active_artefacts).length > 0 ||
      asStringList(context.memory.open_questions).length > 0 ||
      asStringList(context.memory.next_actions).length > 0 ||
      asStringList(context.memory.last_outputs).length > 0 ||
      asStringList(context.memory.do_not_repeat).length > 0
  );
}

createRoot(document.getElementById("root") as HTMLElement).render(<App />);
