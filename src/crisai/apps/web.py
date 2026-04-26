from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import typer
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from crisai.cli.main import (
    _apply_decision_overrides,
    _detect_explicit_mode,
    _resolve_route,
    _run_async,
    _run_with_routing,
)
from crisai.cli.session_store import (
    load_history,
    sanitize_session_name,
    save_history,
    session_dir,
)
from crisai.config import load_settings

app = FastAPI(title="crisAI Web")


class RunRequest(BaseModel):
    """Represent one web execution request."""

    message: str = Field(min_length=1)
    mode: str = Field(default="auto")
    agent: str = Field(default="auto")
    review: bool = False
    verbose: bool = False
    session: str = Field(default="default")


class SessionCreateRequest(BaseModel):
    """Represent a request to create a new web session."""

    session: str = Field(min_length=1)


def _trace_file_path() -> Path:
    """Return the configured trace file path."""
    settings = load_settings()
    return settings.log_dir / "agent_trace.jsonl"


def _read_json_lines_from_offset(path: Path, offset: int) -> list[dict[str, Any]]:
    """Read JSONL entries appended after a byte offset."""
    if not path.exists():
        return []

    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file_obj:
        file_obj.seek(max(offset, 0))
        for raw_line in file_obj:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                entries.append(payload)
    return entries


def _select_latest_run(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return entries for the latest run id found in appended trace lines."""
    run_id = None
    for entry in entries:
        candidate = entry.get("run_id")
        if isinstance(candidate, str) and candidate:
            run_id = candidate
    if run_id is None:
        return []
    return [entry for entry in entries if entry.get("run_id") == run_id]


def _collect_stage_outputs(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build ordered stage output records for UI tabs."""
    stage_records: list[dict[str, str]] = []
    for entry in entries:
        event_type = str(entry.get("event_type", ""))
        if event_type not in {"stage_output", "stage_skipped"}:
            continue
        agent_id = str(entry.get("agent_id") or "system")
        stage_records.append(
            {
                "agent_id": agent_id,
                "stage": str(entry.get("stage", "")),
                "event_type": event_type,
                "content": str(entry.get("content", "")),
            }
        )
    return stage_records


def _resolve_decision(payload: RunRequest):
    """Resolve router decision from web request preferences."""
    explicit_mode = _detect_explicit_mode(payload.message)
    mode_override = None if payload.mode == "auto" else payload.mode
    if mode_override is None:
        mode_override = explicit_mode
    agent_override = None if payload.agent == "auto" else payload.agent
    decision = _resolve_route(
        payload.message,
        review_enabled=payload.review,
        mode_override=mode_override,
        agent_override=agent_override,
    )
    return _apply_decision_overrides(payload.message, explicit_mode, decision)


def _to_http_exception(exc: Exception) -> HTTPException:
    """Map runtime failures to user-facing HTTP errors."""
    message = str(exc).strip() or "Unknown runtime error."
    lowered = message.lower()
    if "max turns" in lowered and "exceeded" in lowered:
        return HTTPException(
            status_code=422,
            detail=(
                "Agent run exceeded max turns. Increase CRISAI_AGENT_MAX_TURNS "
                "or simplify the prompt to reduce iterative steps."
            ),
        )
    return HTTPException(status_code=500, detail=message)


async def _execute(payload: RunRequest) -> dict[str, Any]:
    """Execute one request and return final output plus stage records."""
    trace_path = _trace_file_path()
    before_size = trace_path.stat().st_size if trace_path.exists() else 0
    decision = _resolve_decision(payload)
    try:
        final_output = await _run_with_routing(
            message=payload.message,
            verbose=payload.verbose,
            review=payload.review,
            decision=decision,
        )
    except Exception as exc:  # noqa: BLE001
        raise _to_http_exception(exc) from exc

    appended_entries = _read_json_lines_from_offset(trace_path, before_size)
    run_entries = _select_latest_run(appended_entries)
    stage_outputs = _collect_stage_outputs(run_entries)

    return {
        "decision": asdict(decision),
        "final_output": final_output,
        "stage_outputs": stage_outputs,
    }


def _list_session_names() -> list[str]:
    """List available persisted chat sessions."""
    names: list[str] = []
    for file_path in session_dir().glob("*.json"):
        names.append(file_path.stem)
    if "default" not in names:
        names.append("default")
    return sorted(set(names))


def _serialize_history(history: list[tuple[str, str]]) -> list[dict[str, str]]:
    """Convert tuple-based history to JSON-serializable objects."""
    return [{"role": role, "content": content} for role, content in history]


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Return the single-page web interface."""
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>crisAI Web</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
    .container { max-width: 1100px; margin: 0 auto; padding: 20px; }
    .panel { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; margin-bottom: 16px; }
    .row { display: flex; gap: 12px; flex-wrap: wrap; }
    label { display: block; font-size: 13px; margin-bottom: 6px; color: #cbd5e1; }
    input, textarea, select, button { width: 100%; box-sizing: border-box; border-radius: 8px; border: 1px solid #475569; background: #0b1220; color: #f8fafc; padding: 10px; }
    textarea { min-height: 120px; resize: vertical; }
    button { cursor: pointer; font-weight: bold; }
    .col { flex: 1 1 220px; }
    .switch { display: flex; align-items: center; gap: 8px; }
    .switch input { width: auto; }
    .tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
    .tab-btn { width: auto; padding: 8px 12px; background: #0b1220; border: 1px solid #334155; }
    .tab-btn.active { background: #1d4ed8; border-color: #1d4ed8; }
    pre { background: #020617; border: 1px solid #334155; border-radius: 8px; padding: 12px; overflow-x: auto; white-space: pre-wrap; }
    #sessionHistory {
      line-height: 1.4;
      max-height: calc(20 * 1.4em);
      overflow-y: auto;
      background: #020617;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 12px;
    }
    #sessionHistory .history-entry {
      padding: 8px 0;
      border-bottom: 1px dashed #334155;
    }
    #sessionHistory .history-entry:last-child { border-bottom: none; }
    #sessionHistory .history-meta { font-size: 12px; color: #93c5fd; margin-bottom: 6px; }
    #sessionHistory .history-entry.user .history-meta { color: #86efac; }
    #sessionHistory .history-content { color: #e2e8f0; }
    #sessionHistory .history-content code {
      background: #0b1220;
      border: 1px solid #334155;
      border-radius: 4px;
      padding: 1px 4px;
    }
    #sessionHistory .history-content pre {
      margin: 8px 0;
      background: #0b1220;
    }
    .muted { color: #94a3b8; font-size: 13px; }
  </style>
</head>
<body>
  <div class="container">
    <h1>crisAI Web Interface</h1>
    <p class="muted">Runs the same routing and agent workflows as the CLI.</p>

    <div class="panel">
      <h2>Prompt Workspace</h2>
      <div class="row">
        <div class="col">
          <label for="sessionSelect">Session</label>
          <select id="sessionSelect"></select>
          <p class="muted" id="currentSessionText">Current session: default</p>
        </div>
        <div class="col">
          <label for="newSessionName">Create new session</label>
          <input id="newSessionName" placeholder="e.g. architecture-review" />
          <div style="margin-top: 8px;">
            <button id="createSessionBtn" type="button">Create Session</button>
          </div>
        </div>
      </div>
      <label for="sessionHistory">Session history</label>
      <div id="sessionHistory">No history for this session yet.</div>
      <label for="message" style="margin-top: 12px;">New prompt</label>
      <textarea id="message" placeholder="Describe your request..."></textarea>
      <div class="row" style="margin-top: 12px;">
        <div class="col">
          <label for="mode">Mode</label>
          <select id="mode">
            <option value="auto">auto</option>
            <option value="single">single</option>
            <option value="pipeline">pipeline</option>
            <option value="peer">peer</option>
          </select>
        </div>
        <div class="col">
          <label for="agent">Agent override</label>
          <input id="agent" value="auto" />
        </div>
        <div class="col switch">
          <input type="checkbox" id="review" />
          <label for="review">Review on/off</label>
        </div>
        <div class="col switch">
          <input type="checkbox" id="verbose" />
          <label for="verbose">Verbose on/off</label>
        </div>
      </div>
      <div style="margin-top: 12px;">
        <button id="runBtn" type="button">Run</button>
      </div>
      <p class="muted" id="uiStatus">UI status: loading</p>
    </div>

    <div class="panel">
      <h2>Routing Decision</h2>
      <pre id="decision">No run yet.</pre>
    </div>

    <div class="panel">
      <h2>Agent Flow</h2>
      <div id="tabs" class="tabs"></div>
      <pre id="tabContent">No stage output yet.</pre>
    </div>

    <div class="panel">
      <h2>Final Output</h2>
      <pre id="finalOutput">No run yet.</pre>
    </div>
  </div>

  <script src="/app.js?v=3"></script>
</body>
</html>"""
    return HTMLResponse(
        content=html,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/app.js")
def app_js() -> Response:
    """Return frontend JavaScript for the web interface."""
    script = r"""
const tabs = document.getElementById("tabs");
const tabContent = document.getElementById("tabContent");
const finalOutput = document.getElementById("finalOutput");
const decision = document.getElementById("decision");
const runBtn = document.getElementById("runBtn");
const sessionSelect = document.getElementById("sessionSelect");
const createSessionBtn = document.getElementById("createSessionBtn");
const newSessionNameInput = document.getElementById("newSessionName");
const currentSessionText = document.getElementById("currentSessionText");
const sessionHistory = document.getElementById("sessionHistory");
const messageInput = document.getElementById("message");
const uiStatus = document.getElementById("uiStatus");

let stageData = [];
let sessions = [];
let currentSession = "default";

function setUiStatus(text) {
  if (uiStatus) uiStatus.textContent = `UI status: ${text}`;
}

function handleUiError(error) {
  const message = String(error);
  if (finalOutput) finalOutput.textContent = message;
  setUiStatus(`error - ${message}`);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function markdownToSafeHtml(markdown) {
  let html = escapeHtml(markdown || "");

  html = html.replace(/```([\s\S]*?)```/g, (_match, code) => `<pre><code>${code}</code></pre>`);
  html = html.replace(/^### (.*)$/gm, "<h4>$1</h4>");
  html = html.replace(/^## (.*)$/gm, "<h3>$1</h3>");
  html = html.replace(/^# (.*)$/gm, "<h2>$1</h2>");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\n/g, "<br>");
  return html;
}

function renderTabs(records) {
  tabs.innerHTML = "";
  stageData = records || [];
  if (!stageData.length) {
    tabContent.textContent = "No stage output captured for this run.";
    return;
  }
  stageData.forEach((record, index) => {
    const btn = document.createElement("button");
    btn.className = "tab-btn" + (index === 0 ? " active" : "");
    const labelAgent = record.agent_id || "system";
    btn.textContent = `${index + 1}. ${labelAgent}`;
    btn.onclick = () => selectTab(index);
    tabs.appendChild(btn);
  });
  selectTab(0);
}

function selectTab(index) {
  Array.from(tabs.children).forEach((child, idx) => {
    child.classList.toggle("active", idx === index);
  });
  const record = stageData[index];
  if (!record) return;
  tabContent.textContent = `[${record.event_type}] ${record.stage}\n\n${record.content}`;
}

function renderSessionSelector() {
  sessionSelect.innerHTML = "";
  sessions.forEach((sessionName) => {
    const option = document.createElement("option");
    option.value = sessionName;
    option.textContent = sessionName;
    option.selected = sessionName === currentSession;
    sessionSelect.appendChild(option);
  });
  currentSessionText.textContent = `Current session: ${currentSession}`;
}

function renderSessionHistory(items) {
  if (!items || !items.length) {
    sessionHistory.textContent = "No history for this session yet.";
    return;
  }

  const entryHtml = items.map((entry, index) => {
    const role = entry.role === "assistant" ? "assistant" : "user";
    const roleLabel = role === "assistant" ? "ASSISTANT" : "USER";
    const contentHtml = markdownToSafeHtml(entry.content || "");
    return (
      `<div class="history-entry ${role}">` +
      `<div class="history-meta">#${index + 1} [${roleLabel}]</div>` +
      `<div class="history-content">${contentHtml}</div>` +
      `</div>`
    );
  });
  sessionHistory.innerHTML = entryHtml.join("");
}

async function loadSessionMeta() {
  const response = await fetch("/api/sessions");
  const data = await response.json();
  sessions = data.sessions || ["default"];
  currentSession = data.current_session || sessions[0] || "default";
  renderSessionSelector();
  renderSessionHistory(data.history || []);
}

async function switchSession(sessionName) {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionName)}`);
  const data = await response.json();
  currentSession = data.current_session;
  if (!sessions.includes(currentSession)) sessions.push(currentSession);
  renderSessionSelector();
  renderSessionHistory(data.history || []);
}

async function createSession() {
  const proposed = newSessionNameInput.value.trim();
  if (!proposed) return;
  const response = await fetch("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session: proposed }),
  });
  const data = await response.json();
  currentSession = data.current_session;
  sessions = data.sessions || sessions;
  renderSessionSelector();
  renderSessionHistory(data.history || []);
  newSessionNameInput.value = "";
}

async function runWorkflow() {
  runBtn.disabled = true;
  runBtn.textContent = "Running...";
  try {
    const payload = {
      message: messageInput.value.trim(),
      mode: document.getElementById("mode").value,
      agent: document.getElementById("agent").value.trim() || "auto",
      review: document.getElementById("review").checked,
      verbose: document.getElementById("verbose").checked,
      session: currentSession,
    };
    if (!payload.message) {
      throw new Error("Please enter a prompt.");
    }
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Request failed.");
    }
    decision.textContent = JSON.stringify(data.decision, null, 2);
    finalOutput.textContent = data.final_output || "";
    renderTabs(data.stage_outputs || []);
    renderSessionHistory(data.history || []);
    messageInput.value = "";
  } catch (error) {
    handleUiError(error);
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = "Run";
  }
}

function initUiBindings() {
  if (!runBtn || !createSessionBtn || !sessionSelect || !finalOutput) {
    setUiStatus("missing required elements");
    return;
  }
  runBtn.addEventListener("click", () => { runWorkflow().catch(handleUiError); });
  createSessionBtn.addEventListener("click", () => { createSession().catch(handleUiError); });
  sessionSelect.addEventListener("change", (event) => {
    const selected = event && event.target ? event.target.value : currentSession;
    switchSession(selected).catch(handleUiError);
  });
  setUiStatus("ready");
}

window.addEventListener("error", (event) => {
  handleUiError(event.error || event.message || "Unknown UI error");
});

initUiBindings();
if (finalOutput) {
  loadSessionMeta().catch(handleUiError);
}
"""
    return Response(
        content=script,
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.post("/api/run")
async def run(payload: RunRequest) -> dict[str, Any]:
    """Run a routed workflow and return decision plus outputs."""
    response = await _execute(payload)
    session_name = sanitize_session_name(payload.session)
    history = load_history(session_name)
    history.append(("user", payload.message))
    history.append(("assistant", response["final_output"]))
    save_history(session_name, history)
    response["history"] = _serialize_history(history)
    response["current_session"] = session_name
    return response


@app.get("/api/sessions")
def list_sessions() -> dict[str, Any]:
    """Return available sessions and default session history."""
    names = _list_session_names()
    current_session = "default" if "default" in names else names[0]
    history = load_history(current_session)
    return {
        "sessions": names,
        "current_session": current_session,
        "history": _serialize_history(history),
    }


@app.post("/api/sessions")
def create_session(payload: SessionCreateRequest) -> dict[str, Any]:
    """Create a new named session and return its initial state."""
    session_name = sanitize_session_name(payload.session)
    save_history(session_name, load_history(session_name))
    names = _list_session_names()
    history = load_history(session_name)
    return {
        "sessions": names,
        "current_session": session_name,
        "history": _serialize_history(history),
    }


@app.get("/api/sessions/{session_name}")
def get_session(session_name: str) -> dict[str, Any]:
    """Return one session history and identify it as current."""
    safe_name = sanitize_session_name(session_name)
    history = load_history(safe_name)
    return {
        "current_session": safe_name,
        "history": _serialize_history(history),
    }


def main() -> None:
    """Start the web application with Uvicorn."""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise typer.BadParameter(
            "Missing web dependencies. Install with: pip install fastapi uvicorn"
        ) from exc
    _run_async(uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8000)).serve())

