from __future__ import annotations

import json
import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

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
from crisai.logging_utils import configure_logging
from crisai.apps.ui_config import UI_CONFIG


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Create log directory and application log file when the server starts."""
    configure_logging(load_settings())
    yield


app = FastAPI(title="crisAI Web", lifespan=_lifespan)
_RUN_JOBS: dict[str, dict[str, Any]] = {}
_UI_DIR = Path(__file__).parent / "ui"


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
            user_intent_message=payload.message,
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


def _session_name_newest_by_mtime() -> str | None:
    """Return the session whose JSON file was most recently modified, if any exist.

    Used on full page load so the UI reopens the last-created or last-touched
    session instead of always preferring the virtual ``default`` slot.
    """
    best_mtime: float | None = None
    best_name: str | None = None
    for file_path in session_dir().glob("*.json"):
        try:
            mtime = file_path.stat().st_mtime
        except OSError:
            continue
        if best_mtime is None or mtime >= best_mtime:
            best_mtime = mtime
            best_name = file_path.stem
    return best_name


def _serialize_history(history: list[tuple[str, str]]) -> list[dict[str, str]]:
    """Convert tuple-based history to JSON-serializable objects."""
    return [{"role": role, "content": content} for role, content in history]


def _read_ui_asset(name: str) -> str:
    """Read a UI asset file from the local apps UI directory."""
    return (_UI_DIR / name).read_text(encoding="utf-8")


def _expected_flow_tabs(decision: Any) -> list[dict[str, str]]:
    """Build expected flow tabs from routing decision."""
    mode = getattr(decision, "mode", "single")
    needs_review = bool(getattr(decision, "needs_review", False))
    needs_retrieval = bool(getattr(decision, "needs_retrieval", False))
    agent = getattr(decision, "agent", "orchestrator") or "orchestrator"

    tabs: list[dict[str, str]] = []
    if mode == "pipeline":
        tabs.extend(
            [
                {"key": "retrieval_planner", "label": "retrieval_planner"},
                {"key": "context_retrieval", "label": "context_retrieval"},
                {"key": "context_synthesizer", "label": "context_synthesizer"},
                {"key": "design", "label": "design"},
            ]
        )
        if needs_review:
            tabs.append({"key": "review", "label": "review"})
        tabs.append({"key": "orchestrator", "label": "orchestrator"})
    elif mode == "peer":
        if needs_retrieval:
            tabs.append({"key": "retrieval_planner", "label": "retrieval_planner"})
            tabs.append({"key": "context_retrieval", "label": "context_retrieval"})
        tabs.extend(
            [
                {"key": "design_author", "label": "design_author"},
                {"key": "design_challenger", "label": "design_challenger"},
                {"key": "design_refiner", "label": "design_refiner"},
                {"key": "judge", "label": "judge"},
                {"key": "orchestrator", "label": "orchestrator"},
            ]
        )
    else:
        tabs.append({"key": agent, "label": agent})

    tabs.append({"key": "final_output", "label": "final_output"})
    return tabs


def _extract_stage_key(entry: dict[str, str]) -> str:
    """Map a stage-output entry to a stable flow tab key."""
    agent_id = str(entry.get("agent_id", "")).strip()
    if agent_id:
        return agent_id
    stage = str(entry.get("stage", "")).strip().lower()
    if "final" in stage:
        return "final_output"
    return "system"


def _trace_line_to_stage_output(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Map one JSONL trace line to a UI stage_output row, or None if not renderable.

    Pipeline and peer runs emit ``stage_output`` / ``stage_skipped`` events.
    Single-agent runs log the assistant result as ``workflow_output`` with
    ``stage`` ``FINAL_OUTPUT`` and ``agent_id`` set; the web UI expects a
    stage-shaped row so flow tabs can replace placeholders.
    """
    event_type = str(entry.get("event_type", ""))
    if event_type in {"stage_output", "stage_skipped"}:
        render_event = event_type
    elif event_type == "workflow_output":
        stage_upper = str(entry.get("stage", "")).strip().upper()
        agent_raw = str(entry.get("agent_id", "")).strip()
        if stage_upper != "FINAL_OUTPUT" or not agent_raw:
            return None
        render_event = "stage_output"
    else:
        return None

    return {
        "key": _extract_stage_key(
            {
                "agent_id": str(entry.get("agent_id") or ""),
                "stage": str(entry.get("stage", "")),
            }
        ),
        "agent_id": str(entry.get("agent_id") or "system"),
        "stage": str(entry.get("stage", "")),
        "event_type": render_event,
        "content": str(entry.get("content", "")),
    }


async def _run_job(job_id: str, payload: RunRequest, decision: Any) -> None:
    """Execute one background run and persist completion state."""
    job = _RUN_JOBS[job_id]
    try:
        final_output = await _run_with_routing(
            message=payload.message,
            verbose=payload.verbose,
            review=payload.review,
            decision=decision,
            user_intent_message=payload.message,
        )
        session_name = sanitize_session_name(payload.session)
        history = load_history(session_name)
        history.append(("user", payload.message))
        history.append(("assistant", final_output))
        save_history(session_name, history)

        job["status"] = "completed"
        job["final_output"] = final_output
        job["history"] = _serialize_history(history)
        job["current_session"] = session_name
    except Exception as exc:  # noqa: BLE001
        job["status"] = "failed"
        job["error"] = _to_http_exception(exc).detail


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Return the single-page web interface."""
    html = _read_ui_asset("index.html")
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
    script = _read_ui_asset("app.js")
    return Response(
        content=script,
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/styles.css")
def styles_css() -> Response:
    """Return stylesheet for web interface."""
    css = _read_ui_asset("styles.css").replace(
        "__HISTORY_MAX_LINES__", str(UI_CONFIG.history_max_lines)
    )
    return Response(
        content=css,
        media_type="text/css",
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


@app.post("/api/run/start")
async def run_start(payload: RunRequest) -> dict[str, Any]:
    """Start a run in background and return a job id."""
    if any(job.get("status") == "running" for job in _RUN_JOBS.values()):
        raise HTTPException(status_code=409, detail="Another run is already in progress.")

    decision = _resolve_decision(payload)
    trace_path = _trace_file_path()
    before_size = trace_path.stat().st_size if trace_path.exists() else 0
    job_id = uuid4().hex

    _RUN_JOBS[job_id] = {
        "status": "running",
        "payload": payload,
        "decision": decision,
        "decision_data": asdict(decision),
        "before_size": before_size,
        "run_id": None,
        "stage_outputs": [],
        "final_output": "",
        "error": "",
        "history": [],
        "current_session": sanitize_session_name(payload.session),
        "task": None,
    }
    _RUN_JOBS[job_id]["task"] = asyncio.create_task(_run_job(job_id, payload, decision))

    return {
        "job_id": job_id,
        "decision": asdict(decision),
        "expected_tabs": _expected_flow_tabs(decision),
    }


@app.get("/api/run/status/{job_id}")
def run_status(job_id: str) -> dict[str, Any]:
    """Return progressive status and stage outputs for a run job."""
    job = _RUN_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Run job not found.")

    trace_path = _trace_file_path()
    new_entries = _read_json_lines_from_offset(trace_path, int(job.get("before_size", 0)))
    if trace_path.exists():
        job["before_size"] = trace_path.stat().st_size

    if job.get("run_id") is None:
        for entry in new_entries:
            candidate = entry.get("run_id")
            if isinstance(candidate, str) and candidate:
                job["run_id"] = candidate

    run_id = job.get("run_id")
    if run_id:
        run_entries = [entry for entry in new_entries if entry.get("run_id") == run_id]
    else:
        run_entries = []

    for entry in run_entries:
        stage_entry = _trace_line_to_stage_output(entry)
        if stage_entry is None:
            continue
        job["stage_outputs"] = [e for e in job["stage_outputs"] if e.get("key") != stage_entry["key"]]
        job["stage_outputs"].append(stage_entry)

    return {
        "status": job.get("status"),
        "stage_outputs": job.get("stage_outputs", []),
        "final_output": job.get("final_output", ""),
        "history": job.get("history", []),
        "current_session": job.get("current_session"),
        "error": job.get("error", ""),
    }


@app.get("/api/sessions")
def list_sessions() -> dict[str, Any]:
    """Return available sessions and default session history."""
    names = _list_session_names()
    newest = _session_name_newest_by_mtime()
    if newest is not None and newest in names:
        current_session = newest
    elif "default" in names:
        current_session = "default"
    else:
        current_session = names[0] if names else "default"
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

