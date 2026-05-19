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
  type UiSessionContext,
  type UiSessionRecallResult,
  type UiSessionState,
  type UiStageSummary,
  type UiWorkspaceFileRecord,
  type UiWorkspaceUploadTarget
} from "@crisai/contracts";
import { parseMarkdownBlocks, shouldShowTranscriptEvent, type MarkdownInlineToken } from "./runDisplay.js";
import "./styles.css";

const apiKeyStorageKey = "crisai_api_key";
const configuredApiKey = import.meta.env.VITE_CRISAI_API_KEY ?? import.meta.env.VITE_CRISAI_API_TOKEN ?? "";

const runtime = new CrisaiRuntimeClient({
  baseUrl: import.meta.env.VITE_CRISAI_RUNTIME_URL ?? "http://127.0.0.1:8000",
  apiToken: configuredApiKey || localStorage.getItem(apiKeyStorageKey) || undefined
});

function App() {
  const [apiKeyInput, setApiKeyInput] = useState(localStorage.getItem(apiKeyStorageKey) ?? configuredApiKey);
  const [apiKeyConfigured, setApiKeyConfigured] = useState(Boolean(apiKeyInput.trim()));
  const [message, setMessage] = useState("");
  const [session, setSession] = useState("default");
  const [sessions, setSessions] = useState<string[]>(["default"]);
  const [history, setHistory] = useState<UiHistoryEntry[]>([]);
  const [sessionContext, setSessionContext] = useState<UiSessionContext | null>(null);
  const [sessionContextStatus, setSessionContextStatus] = useState<"idle" | "loading" | "ready" | "empty" | "error">("idle");
  const [sessionContextError, setSessionContextError] = useState("");
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
  const liveStageEvent = useMemo(() => latestLiveStageEvent(events), [events]);

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
    setError("");
    applyApiKey(apiKeyInput);
    refreshSessions().catch((reason: unknown) => setError(String(reason)));
  }

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
    void loadSessionContext(state.current_session);
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
        <div className="topbar-actions">
          <form className="api-key-form" onSubmit={saveApiKey}>
            <label>
              API key
              <input
                type="password"
                value={apiKeyInput}
                onChange={(event) => setApiKeyInput(event.target.value)}
                placeholder={apiKeyConfigured ? "configured" : "optional"}
              />
            </label>
            <button type="submit">{apiKeyConfigured ? "Update" : "Set"}</button>
          </form>
          <p className="status">status: {latestStatus}</p>
        </div>
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
          liveStageEvent={liveStageEvent}
          checkpointWaiting={checkpointWaiting}
          verbose={verbose}
          redirectInstruction={redirectInstruction}
          onRedirectInstructionChange={setRedirectInstruction}
          onCheckpoint={checkpoint}
        />
        <HistoryPanel
          history={history}
          sessionContext={sessionContext}
          contextStatus={sessionContextStatus}
          contextError={sessionContextError}
          onRefreshContext={loadSessionContext}
        />
      </section>

      <WorkspaceBrowser session={session} />
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

function HistoryPanel({
  history,
  sessionContext,
  contextStatus,
  contextError,
  onRefreshContext
}: {
  history: UiHistoryEntry[];
  sessionContext: UiSessionContext | null;
  contextStatus: "idle" | "loading" | "ready" | "empty" | "error";
  contextError: string;
  onRefreshContext: (sessionName?: string, query?: string) => Promise<void>;
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
      <h2>Session</h2>
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

function SessionContextBody({
  context,
  status,
  error
}: {
  context: UiSessionContext | null;
  status: "idle" | "loading" | "ready" | "empty" | "error";
  error: string;
}) {
  if (status === "loading") {
    return <p className="context-status" role="status">Loading session context.</p>;
  }
  if (status === "idle") {
    return <p className="context-status">Context will load with the session.</p>;
  }
  if (status === "error") {
    return <p className="context-status context-error" role="alert">Context unavailable: {error}</p>;
  }
  if (!context || status === "empty") {
    return <p className="context-status">No structured context has been captured for this session yet.</p>;
  }

  const fields = [
    ["Task goal", context.memory.task_goal],
    ["Current state", context.memory.current_state],
    ["Scope", context.memory.scope],
    ["Assumptions", context.memory.assumptions],
    ["Constraints", context.memory.constraints],
    ["Important decisions", context.memory.important_decisions],
    ["Rejected options", context.memory.rejected_options],
    ["Source findings", context.memory.source_findings],
    ["Known sources", context.memory.known_sources],
    ["Active artefacts", context.memory.active_artefacts],
    ["Open questions", context.memory.open_questions],
    ["Next actions", context.memory.next_actions],
    ["Last outputs", context.memory.last_outputs],
    ["Do not repeat", context.memory.do_not_repeat]
  ].flatMap(([label, value]) => {
    const items = asStringList(value);
    return items.length > 0 ? [{ label: String(label), items }] : [];
  });

  return (
    <div className="context-body">
      {context.baseline_brief ? (
        <section className="context-section">
          <h4>Baseline brief</h4>
          <p className="context-brief">{context.baseline_brief}</p>
        </section>
      ) : null}
      {fields.length > 0 ? (
        <section className="context-section">
          <h4>Memory fields</h4>
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
        <strong>{humanizeLabel(result.field)}</strong>
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

function WorkspaceBrowser({ session }: { session: string }) {
  const [roots, setRoots] = useState<Record<string, string>>({});
  const [rootName, setRootName] = useState("knowledge");
  const [files, setFiles] = useState<UiWorkspaceFileRecord[]>([]);
  const [filter, setFilter] = useState("");
  const [selectedPath, setSelectedPath] = useState("");
  const [content, setContent] = useState("");
  const [status, setStatus] = useState("Workspace ready.");
  const [uploadTarget, setUploadTarget] = useState<UiWorkspaceUploadTarget>("task_inputs");
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  useEffect(() => {
    runtime
      .getWorkspaceRoots()
      .then((state) => {
        setRoots(state.roots);
        const firstRoot = Object.keys(state.roots)[0] ?? "knowledge";
        setRootName(firstRoot);
        return loadTree(firstRoot);
      })
      .catch((reason: unknown) => setStatus(String(reason)));
  }, []);

  async function loadTree(nextRoot = rootName) {
    const tree = await runtime.getWorkspaceTree(nextRoot);
    setRootName(tree.root);
    setFiles(tree.files);
    setSelectedPath("");
    setContent("");
    setStatus(`${tree.files.length} files in ${tree.path}.`);
  }

  async function openFile(path: string) {
    const file = await runtime.getWorkspaceFile(path);
    setSelectedPath(file.path);
    setContent(file.content);
    setStatus(`Opened ${file.path}.`);
  }

  async function saveFile() {
    if (!selectedPath) return;
    const result = await runtime.saveWorkspaceFile(selectedPath, content);
    setStatus(result.saved ? `Saved ${result.path}.` : `Save did not complete for ${result.path}.`);
    await loadTree(rootName);
    setSelectedPath(result.path);
  }

  async function uploadSelectedFile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!uploadFile) return;
    const contentBase64 = await fileToBase64(uploadFile);
    const result = await runtime.uploadWorkspaceFile({
      target: uploadTarget,
      session,
      filename: uploadFile.name,
      content_base64: contentBase64
    });
    setStatus(`Uploaded ${result.path}.`);
    setUploadFile(null);
    await loadTree(uploadTarget === "task_inputs" ? "tasks" : "knowledge");
  }

  const visibleFiles = files.filter((file) => file.path.toLowerCase().includes(filter.toLowerCase()));

  return (
    <section className="workspace-browser" aria-label="Workspace browser">
      <header>
        <h2>Workspace</h2>
        <p>{status}</p>
      </header>
      <div className="workspace-controls">
        <label>
          Space
          <select value={rootName} onChange={(event) => void loadTree(event.target.value)}>
            {Object.entries(roots).map(([name, path]) => (
              <option key={name} value={name}>{name}: {path}</option>
            ))}
          </select>
        </label>
        <label>
          Filter
          <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Find files" />
        </label>
      </div>
      <form className="workspace-upload" onSubmit={uploadSelectedFile}>
        <label>
          Upload target
          <select
            value={uploadTarget}
            onChange={(event) => setUploadTarget(event.target.value as UiWorkspaceUploadTarget)}
          >
            <option value="task_inputs">Current task inputs</option>
            <option value="knowledge_intake">Knowledge intake</option>
          </select>
        </label>
        <label>
          Source file
          <input type="file" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} />
        </label>
        <button type="submit" disabled={!uploadFile}>Upload</button>
      </form>
      <div className="workspace-editor-grid">
        <div className="workspace-files">
          {visibleFiles.length === 0 ? <p>No files found.</p> : null}
          {visibleFiles.map((file) => (
            <button
              key={file.path}
              type="button"
              className={file.path === selectedPath ? "selected-file" : ""}
              disabled={!file.editable}
              onClick={() => void openFile(file.path)}
            >
              <span>{file.name}</span>
              <small>{file.path}</small>
            </button>
          ))}
        </div>
        <div className="workspace-editor">
          <p>{selectedPath || "No file selected."}</p>
          <textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            disabled={!selectedPath}
            spellCheck={false}
          />
          <button type="button" disabled={!selectedPath} onClick={() => void saveFile()}>Save</button>
        </div>
      </div>
    </section>
  );
}

async function fileToBase64(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.slice(index, index + chunkSize));
  }
  return btoa(binary);
}

function Transcript({
  events,
  finalContent,
  liveStageEvent,
  checkpointWaiting,
  verbose,
  redirectInstruction,
  onRedirectInstructionChange,
  onCheckpoint
}: {
  events: UiEvent[];
  finalContent: string;
  liveStageEvent: UiEvent | null;
  checkpointWaiting: boolean;
  verbose: boolean;
  redirectInstruction: string;
  onRedirectInstructionChange: (value: string) => void;
  onCheckpoint: (action: "continue" | "redirect" | "stop", instruction?: string) => Promise<void>;
}) {
  const visibleEvents = events.filter((event) => shouldShowTranscriptEvent(event, verbose));
  const liveStatus = checkpointWaiting
    ? "Decision needed: review retrieved sources."
    : liveStageEvent
      ? `Running ${liveStageEvent.title || humanizeLabel(liveStageEvent.agent_id ?? liveStageEvent.stage ?? "stage")}.`
      : "";

  return (
    <section className="transcript" aria-label="Run transcript">
      <p className="live-status" role="status" aria-live="polite" aria-atomic="true">
        {liveStatus}
      </p>
      {events.length === 0 ? <p>No output yet.</p> : null}
      {liveStageEvent ? (
        <article className="event-card streaming-card">
          <header>
            <h2>{liveStageEvent.title}</h2>
            <span>streaming</span>
          </header>
          <pre>{liveStageEvent.content}</pre>
        </article>
      ) : null}
      {visibleEvents.map((event, index) => (
        <article key={`${event.event_type}-${event.timestamp}-${index}`} className="event-card">
          <header>
            <h2>{event.title}</h2>
            <span>{event.event_type}</span>
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
            <span>final_answer</span>
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

function MarkdownContent({ content }: { content: string }) {
  return <div className="markdown-content">{renderMarkdownBlocks(content)}</div>;
}

function renderMarkdownBlocks(content: string): React.ReactNode[] {
  return parseMarkdownBlocks(content).map((block, index) => {
    if (block.type === "heading") {
      const Tag = `h${block.level}` as React.ElementType;
      return <Tag key={index}>{renderInlineMarkdown(block.children)}</Tag>;
    }
    if (block.type === "code") {
      return (
        <pre key={index} className="markdown-code">
          <code>{block.value}</code>
        </pre>
      );
    }
    if (block.type === "list") {
      return (
        <ul key={index}>
          {block.items.map((item, itemIndex) => (
            <li key={itemIndex}>{renderInlineMarkdown(item)}</li>
          ))}
        </ul>
      );
    }
    if (block.type === "table") {
      return (
        <div key={index} className="markdown-table-scroll">
          <table>
            <thead>
              <tr>
                {block.headers.map((header, headerIndex) => (
                  <th key={headerIndex}>{renderInlineMarkdown(header)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {block.headers.map((_, cellIndex) => (
                    <td key={cellIndex}>{renderInlineMarkdown(row[cellIndex] ?? [])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    return <p key={index}>{renderInlineMarkdown(block.children)}</p>;
  });
}

function renderInlineMarkdown(tokens: MarkdownInlineToken[]): React.ReactNode[] {
  return tokens.map((token, index) => {
    if (token.type === "strong") {
      return <strong key={index}>{token.value}</strong>;
    }
    if (token.type === "code") {
      return <code key={index}>{token.value}</code>;
    }
    return token.value;
  });
}

function latestLiveStageEvent(events: UiEvent[]): UiEvent | null {
  const terminal = [...events].reverse().find((event) => isTerminalEvent(event));
  if (terminal) return null;
  return [...events].reverse().find((event) => event.event_type === "stage_delta") ?? null;
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

function asStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
  }
  if (typeof value === "string" && value.trim()) {
    return [value];
  }
  return [];
}

function humanizeLabel(value: string): string {
  const label = value.replaceAll("_", " ").trim();
  return label ? label.charAt(0).toUpperCase() + label.slice(1) : "Memory";
}

function formatRecallScore(score: number): string {
  return Number.isInteger(score) ? String(score) : score.toFixed(2);
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
