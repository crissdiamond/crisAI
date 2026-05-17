from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import typer
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from crisai.apps.ui_config import UI_CONFIG
from crisai.cli.artefact_lifecycle import persist_reusable_deliverable
from crisai.cli.chat_context import (
    build_chat_input,
    normalise_legacy_workspace_paths,
    render_session_memory,
    update_session_memory,
)
from crisai.cli.display import render_stage_output_text, sanitize_user_visible_text
from crisai.cli.main import (
    _apply_decision_overrides,
    _detect_explicit_mode,
    _resolve_route,
    _run_async,
    _run_with_routing,
)
from crisai.cli.session_store import (
    list_task_names,
    load_history,
    load_session_memory,
    sanitize_session_name,
    save_history,
    session_dir,
    tasks_dir,
)
from crisai.config import load_settings
from crisai.logging_utils import configure_logging
from crisai.orchestration.exceptions import WorkflowValidationError
from crisai.orchestration.retrieval_checkpoint import (
    RetrievalCheckpointDecision,
    RetrievalCheckpointSnapshot,
)
from crisai.ui_events import UiEvent, UiEventType, make_ui_event
from crisai.workspace.spaces import load_workspace_spaces


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Create log directory and application log file when the server starts."""
    configure_logging(load_settings())
    yield


app = FastAPI(title="crisAI Web", lifespan=_lifespan)
_RUN_JOBS: dict[str, dict[str, Any]] = {}
_UI_DIR = Path(__file__).parent / "ui"
_MAX_COMPLETED_JOBS = 20


class RunRequest(BaseModel):
    """Represent one web execution request."""

    message: str = Field(min_length=1)
    mode: str = Field(default="auto")
    agent: str = Field(default="auto")
    review: bool = False
    verbose: bool = False
    session: str = Field(default="default")
    retrieval_checkpoint: bool | None = None


class CheckpointRequest(BaseModel):
    """Represent a web retrieval checkpoint decision."""

    action: str
    redirect_instruction: str = Field(default="")


class SessionCreateRequest(BaseModel):
    """Represent a request to create a new web session."""

    session: str = Field(min_length=1)


class WorkspaceFileSaveRequest(BaseModel):
    """Represent a web request to save editable workspace Markdown."""

    path: str = Field(min_length=1)
    content: str = Field(default="")


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


def _collect_stage_outputs(entries: list[dict[str, Any]], *, verbose: bool = False) -> list[dict[str, str]]:
    """Build ordered stage output records for UI tabs."""
    stage_records: list[dict[str, str]] = []
    for entry in entries:
        event_type = str(entry.get("event_type", ""))
        if event_type not in {"stage_start", "stage_output", "stage_skipped", "stage_error"}:
            continue
        agent_id = str(entry.get("agent_id") or "system")
        stage_records.append(
            {
                "agent_id": agent_id,
                "stage": str(entry.get("stage", "")),
                "event_type": event_type,
                "content": render_stage_output_text(agent_id, str(entry.get("content", "")), verbose=verbose),
            }
        )
    return stage_records


def _append_job_event(job_id: str, event: UiEvent) -> None:
    """Append one canonical UI event to a background job."""
    job = _RUN_JOBS[job_id]
    job.setdefault("events", []).append(event.to_dict())


def _job_session(job: dict[str, Any]) -> str:
    return str(job.get("current_session") or "default")


def _job_mode(job: dict[str, Any]) -> str | None:
    decision = job.get("decision")
    return str(getattr(decision, "mode", "")) or None


def _trace_entry_event_key(entry: dict[str, Any]) -> str:
    """Return a stable key for de-duplicating trace-backed UI events."""
    return "|".join(
        [
            str(entry.get("run_id", "")),
            str(entry.get("event_type", "")),
            str(entry.get("agent_id", "")),
            str(entry.get("stage", "")),
            str(entry.get("timestamp", "")),
            str(hash(str(entry.get("content", "")))),
        ]
    )


def _ui_event_from_stage_entry(
    *,
    job_id: str,
    job: dict[str, Any],
    stage_entry: dict[str, Any],
) -> dict[str, Any]:
    """Convert a rendered stage row into the shared UI event contract."""
    source_event = str(stage_entry.get("event_type") or "")
    event_type = cast(UiEventType, {
        "stage_start": "stage_started",
        "stage_output": "stage_output",
        "stage_skipped": "stage_skipped",
        "stage_error": "stage_failed",
    }.get(source_event, "stage_output"))
    agent_id = str(stage_entry.get("agent_id") or "system")
    content = str(stage_entry.get("content") or "")
    event = make_ui_event(
        event_type,
        run_id=job_id,
        session=_job_session(job),
        status=str(job.get("status") or "running"),
        title=agent_id.replace("_", " ").title(),
        summary=content.splitlines()[0] if content else "",
        content=content,
        verbose_content=content,
        mode=_job_mode(job),
        agent_id=agent_id,
        stage=str(stage_entry.get("stage") or ""),
        metadata={"source_event_type": source_event},
    )
    return event.to_dict()


def _refresh_job_from_trace(job_id: str) -> None:
    """Update legacy stage rows and canonical UI events from appended trace lines."""
    job = _RUN_JOBS[job_id]
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
    run_entries = [entry for entry in new_entries if entry.get("run_id") == run_id] if run_id else []
    seen = job.setdefault("event_trace_keys", set())
    for entry in run_entries:
        payload = job.get("payload")
        stage_entry = _trace_line_to_stage_output(entry, verbose=bool(getattr(payload, "verbose", False)))
        if stage_entry is None:
            continue
        job["stage_outputs"] = [e for e in job["stage_outputs"] if e.get("key") != stage_entry["key"]]
        job["stage_outputs"].append(stage_entry)
        event_key = _trace_entry_event_key(entry)
        if event_key in seen:
            continue
        seen.add(event_key)
        job.setdefault("events", []).append(
            _ui_event_from_stage_entry(job_id=job_id, job=job, stage_entry=stage_entry)
        )


def _resolve_decision(payload: RunRequest):
    """Resolve router decision from web request preferences."""
    message = normalise_legacy_workspace_paths(payload.message)
    explicit_mode = _detect_explicit_mode(message)
    mode_override = None if payload.mode == "auto" else payload.mode
    if mode_override is None:
        mode_override = explicit_mode
    agent_override = None if payload.agent == "auto" else payload.agent
    decision = _resolve_route(
        message,
        review_enabled=payload.review,
        mode_override=mode_override,
        agent_override=agent_override,
    )
    return _apply_decision_overrides(message, explicit_mode, decision)


def _to_http_exception(exc: Exception) -> HTTPException:
    """Map runtime failures to user-facing HTTP errors."""
    message = str(exc).strip() or "Unknown runtime error."
    lowered = message.lower()
    if isinstance(exc, WorkflowValidationError):
        return HTTPException(status_code=422, detail=message)
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
    session_name = sanitize_session_name(payload.session)
    history = load_history(session_name)
    runtime_message = normalise_legacy_workspace_paths(payload.message)
    chat_input = build_chat_input(runtime_message, history, session_name=session_name)
    try:
        final_output = await _run_with_routing(
            message=chat_input,
            verbose=payload.verbose,
            review=payload.review,
            decision=decision,
            user_intent_message=runtime_message,
            session_name=session_name,
            retrieval_checkpoint_enabled=False,
        )
        final_output = persist_reusable_deliverable(
            session_name=session_name,
            user_input=runtime_message,
            final_output=final_output,
            registry_dir=load_settings().registry_dir,
        )
    except Exception as exc:  # noqa: BLE001
        raise _to_http_exception(exc) from exc

    appended_entries = _read_json_lines_from_offset(trace_path, before_size)
    run_entries = _select_latest_run(appended_entries)
    stage_outputs = _collect_stage_outputs(run_entries, verbose=payload.verbose)

    return {
        "decision": asdict(decision),
        "final_output": sanitize_user_visible_text(final_output),
        "stage_outputs": stage_outputs,
    }


def _make_web_checkpoint_handler(job_id: str):
    """Return a pipeline checkpoint handler bound to a web job."""

    async def _handler(snapshot: RetrievalCheckpointSnapshot) -> RetrievalCheckpointDecision:
        job = _RUN_JOBS[job_id]
        loop = asyncio.get_running_loop()
        future: asyncio.Future[RetrievalCheckpointDecision] = loop.create_future()
        job["checkpoint_future"] = future
        job["checkpoint"] = snapshot.to_dict()
        job["status"] = "checkpoint_waiting"
        _append_job_event(
            job_id,
            make_ui_event(
                "checkpoint_requested",
                run_id=job_id,
                session=_job_session(job),
                status="checkpoint_waiting",
                title="Retrieval checkpoint",
                summary="Retrieval evidence is ready for confirmation.",
                content=snapshot.evidence_brief,
                mode=_job_mode(job),
                agent_id="retrieval_checkpoint",
                stage="retrieval_checkpoint",
                metadata=snapshot.to_dict(),
            ),
        )
        decision = await future
        job["checkpoint"] = None
        job["checkpoint_future"] = None
        job["status"] = "running"
        return decision

    return _handler


def _list_session_names() -> list[str]:
    """List available persisted task sessions, including legacy sessions."""
    names: list[str] = []
    names.extend(list_task_names())
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
    candidates = list(session_dir().glob("*.json"))
    for task_name in list_task_names():
        candidates.append(tasks_dir() / task_name / ".crisai" / "history.json")
    for file_path in candidates:
        try:
            mtime = file_path.stat().st_mtime
        except OSError:
            continue
        stem = file_path.stem
        if file_path.name == "history.json" and file_path.parent.name == ".crisai":
            stem = file_path.parent.parent.name
        if best_mtime is None or mtime >= best_mtime:
            best_mtime = mtime
            best_name = stem
    return best_name


def _serialize_history(history: list[tuple[str, str]]) -> list[dict[str, str]]:
    """Convert tuple-based history to JSON-serializable objects."""
    return [{"role": role, "content": content} for role, content in history]


def _serialize_memory(session_name: str) -> dict[str, Any]:
    """Return compact memory metadata for session APIs."""
    memory = load_session_memory(session_name)
    return {
        "schema_version": memory.schema_version,
        "summary": render_session_memory(memory),
        "known_sources_count": len(memory.known_sources),
        "updated_at": memory.updated_at,
    }


def _read_ui_asset(name: str) -> str:
    """Read a UI asset file from the local apps UI directory."""
    return (_UI_DIR / name).read_text(encoding="utf-8")


def _read_ui_theme_config() -> dict[str, Any]:
    """Read shared UI theme configuration from the registry."""
    path = Path(load_settings().registry_dir) / "ui.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Shared UI theme registry not found.") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="Shared UI theme registry must be a mapping.")
    if data.get("schema_version") != "ui_theme_v1":
        raise HTTPException(status_code=500, detail="Shared UI theme registry must use schema_version ui_theme_v1.")
    return data


def _workspace_root() -> Path:
    return load_settings().workspace_dir.resolve()


def _safe_workspace_path(relative_path: str) -> Path:
    raw = str(relative_path or "").strip().lstrip("/")
    if raw.startswith("workspace/"):
        raw = raw[len("workspace/") :]
    root = _workspace_root()
    candidate = (root / raw).resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(status_code=400, detail="Path escapes workspace root.")
    return candidate


def _browser_roots() -> dict[str, str]:
    spaces = load_workspace_spaces(load_settings().registry_dir)
    return {
        "knowledge": spaces.knowledge_root,
        "tasks": spaces.tasks_root,
        "staging": spaces.knowledge_staging_root,
    }


def _assert_editable_workspace_file(path: Path) -> None:
    root = _workspace_root()
    rel = path.relative_to(root).as_posix()
    roots = _browser_roots()
    editable_roots = (roots["knowledge"], roots["tasks"], roots["staging"])
    if not any(rel == item or rel.startswith(f"{item}/") for item in editable_roots):
        raise HTTPException(status_code=403, detail="File is outside editable workspace areas.")
    if path.suffix.lower() not in {".md", ".txt", ".mmd", ".json", ".yaml", ".yml"}:
        raise HTTPException(status_code=403, detail="This file type is not editable in the web UI.")


def _workspace_tree(base: Path) -> list[dict[str, Any]]:
    root = _workspace_root()
    if not base.exists():
        return []
    entries: list[dict[str, Any]] = []
    for path in sorted(base.rglob("*")):
        if path.name.startswith(".") and path.is_dir():
            continue
        if path.is_dir():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        entries.append(
            {
                "path": rel,
                "name": path.name,
                "size": stat.st_size,
                "editable": path.suffix.lower() in {".md", ".txt", ".mmd", ".json", ".yaml", ".yml"},
            }
        )
    return entries


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


def _trace_line_to_stage_output(entry: dict[str, Any], *, verbose: bool = False) -> dict[str, Any] | None:
    """Map one JSONL trace line to a UI stage_output row, or None if not renderable.

    Pipeline and peer runs emit ``stage_start`` / ``stage_output`` /
    ``stage_skipped`` / ``stage_error`` events.
    Single-agent runs log the assistant result as ``workflow_output`` with
    ``stage`` ``FINAL_OUTPUT`` and ``agent_id`` set; the web UI expects a
    stage-shaped row so flow tabs can replace placeholders.
    """
    event_type = str(entry.get("event_type", ""))
    if event_type in {"stage_start", "stage_output", "stage_skipped", "stage_error"}:
        render_event = event_type
    elif event_type == "workflow_output":
        stage_upper = str(entry.get("stage", "")).strip().upper()
        agent_raw = str(entry.get("agent_id", "")).strip()
        if stage_upper != "FINAL_OUTPUT" or not agent_raw:
            return None
        render_event = "stage_output"
    else:
        return None

    agent_id = str(entry.get("agent_id") or "system")
    return {
        "key": _extract_stage_key(
            {
                "agent_id": str(entry.get("agent_id") or ""),
                "stage": str(entry.get("stage", "")),
            }
        ),
        "agent_id": agent_id,
        "stage": str(entry.get("stage", "")),
        "event_type": render_event,
        "content": render_stage_output_text(agent_id, str(entry.get("content", "")), verbose=verbose),
    }


async def _run_job(job_id: str, payload: RunRequest, decision: Any) -> None:
    """Execute one background run and persist completion state."""
    job = _RUN_JOBS[job_id]
    try:
        session_name = sanitize_session_name(payload.session)
        history = load_history(session_name)
        runtime_message = normalise_legacy_workspace_paths(payload.message)
        chat_input = build_chat_input(runtime_message, history, session_name=session_name)
        final_output = await _run_with_routing(
            message=chat_input,
            verbose=payload.verbose,
            review=payload.review,
            decision=decision,
            user_intent_message=runtime_message,
            session_name=session_name,
            retrieval_checkpoint_enabled=getattr(payload, "retrieval_checkpoint", None),
            retrieval_checkpoint_handler=_make_web_checkpoint_handler(job_id),
        )
        final_output = persist_reusable_deliverable(
            session_name=session_name,
            user_input=runtime_message,
            final_output=final_output,
            registry_dir=load_settings().registry_dir,
        )
        history.append(("user", payload.message))
        history.append(("assistant", sanitize_user_visible_text(final_output)))
        save_history(session_name, history)
        update_session_memory(session_name, history)

        job["status"] = "completed"
        job["final_output"] = sanitize_user_visible_text(final_output)
        job["history"] = _serialize_history(history)
        job["current_session"] = session_name
        _append_job_event(
            job_id,
            make_ui_event(
                "final_answer",
                run_id=job_id,
                session=session_name,
                status="completed",
                title="Final answer",
                summary="Run completed with a final answer.",
                content=job["final_output"],
                mode=_job_mode(job),
                agent_id="final_output",
                stage="final_output",
            ),
        )
        _append_job_event(
            job_id,
            make_ui_event(
                "run_completed",
                run_id=job_id,
                session=session_name,
                status="completed",
                title="Run completed",
                summary="Workflow completed.",
                mode=_job_mode(job),
            ),
        )
    except Exception as exc:  # noqa: BLE001
        job["status"] = "failed"
        job["error"] = _to_http_exception(exc).detail
        _append_job_event(
            job_id,
            make_ui_event(
                "run_failed",
                run_id=job_id,
                session=_job_session(job),
                status="failed",
                title="Run failed",
                summary=str(job["error"]),
                content=str(job["error"]),
                mode=_job_mode(job),
            ),
        )


def _evict_old_jobs(max_completed: int = _MAX_COMPLETED_JOBS) -> None:
    """Remove oldest completed/failed jobs, keeping at most max_completed."""
    terminal_ids = [
        job_id
        for job_id, job in _RUN_JOBS.items()
        if job.get("status") in {"completed", "failed"}
    ]
    for job_id in terminal_ids[: max(0, len(terminal_ids) - max_completed)]:
        del _RUN_JOBS[job_id]


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
    history.append(("assistant", sanitize_user_visible_text(response["final_output"])))
    save_history(session_name, history)
    update_session_memory(session_name, history)
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
        "checkpoint": None,
        "checkpoint_future": None,
        "history": [],
        "current_session": sanitize_session_name(payload.session),
        "events": [],
        "event_trace_keys": set(),
        "task": None,
    }
    _append_job_event(
        job_id,
        make_ui_event(
            "run_created",
            run_id=job_id,
            session=sanitize_session_name(payload.session),
            status="running",
            title="Run created",
            summary="Workflow run accepted.",
            mode=getattr(decision, "mode", None),
            metadata={"expected_tabs": _expected_flow_tabs(decision)},
        ),
    )
    _append_job_event(
        job_id,
        make_ui_event(
            "routing_decision",
            run_id=job_id,
            session=sanitize_session_name(payload.session),
            status="running",
            title="Routing decision",
            summary=str(getattr(decision, "reason", "")),
            content=str(getattr(decision, "reason", "")),
            mode=getattr(decision, "mode", None),
            agent_id=getattr(decision, "agent", None),
            metadata=asdict(decision),
        ),
    )
    _RUN_JOBS[job_id]["task"] = asyncio.create_task(_run_job(job_id, payload, decision))
    _evict_old_jobs()

    return {
        "job_id": job_id,
        "decision": asdict(decision),
        "expected_tabs": _expected_flow_tabs(decision),
    }


@app.get("/api/run/status/{job_id}")
async def run_status(job_id: str) -> dict[str, Any]:
    """Return progressive status and stage outputs for a run job."""
    job = _RUN_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Run job not found.")

    _refresh_job_from_trace(job_id)

    return {
        "status": job.get("status"),
        "stage_outputs": job.get("stage_outputs", []),
        "final_output": job.get("final_output", ""),
        "checkpoint": job.get("checkpoint"),
        "history": job.get("history", []),
        "current_session": job.get("current_session"),
        "error": job.get("error", ""),
    }


@app.post("/api/run/checkpoint/{job_id}")
async def run_checkpoint(job_id: str, payload: CheckpointRequest) -> dict[str, Any]:
    """Resume a run that is waiting at the retrieval checkpoint."""
    if payload.action not in {"continue", "redirect", "stop"}:
        raise HTTPException(status_code=422, detail="Invalid checkpoint action.")
    job = _RUN_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Run job not found.")
    if job.get("status") != "checkpoint_waiting":
        raise HTTPException(status_code=409, detail="Run job is not waiting at a retrieval checkpoint.")
    future = job.get("checkpoint_future")
    if future is None or not hasattr(future, "done"):
        raise HTTPException(status_code=409, detail="Retrieval checkpoint is not resumable.")
    if future.done():
        raise HTTPException(status_code=409, detail="Retrieval checkpoint decision was already submitted.")
    instruction = payload.redirect_instruction.strip()
    if payload.action == "redirect" and not instruction:
        raise HTTPException(status_code=422, detail="Redirect requires non-empty guidance.")
    if payload.action == "continue":
        decision = RetrievalCheckpointDecision.continue_()
    elif payload.action == "stop":
        decision = RetrievalCheckpointDecision.stop()
    else:
        decision = RetrievalCheckpointDecision.redirect(instruction)
    future.set_result(decision)
    _append_job_event(
        job_id,
        make_ui_event(
            "checkpoint_decision",
            run_id=job_id,
            session=_job_session(job),
            status="running",
            title="Checkpoint decision",
            summary=f"Checkpoint decision: {decision.action}.",
            content=decision.redirect_instruction,
            mode=_job_mode(job),
            agent_id="retrieval_checkpoint",
            stage="retrieval_checkpoint",
            metadata=decision.to_dict(),
        ),
    )
    return {"status": "accepted", "action": decision.action}


def _run_state(job_id: str) -> dict[str, Any]:
    """Return the shared UI run state for React, Ink, and future clients."""
    job = _RUN_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Run job not found.")
    _refresh_job_from_trace(job_id)
    return {
        "schema_version": "ui_run_state_v1",
        "run_id": job_id,
        "session": _job_session(job),
        "status": job.get("status"),
        "decision": job.get("decision_data", {}),
        "expected_stages": _expected_flow_tabs(job.get("decision")),
        "events": job.get("events", []),
        "final_output": job.get("final_output", ""),
        "error": job.get("error", ""),
    }


@app.post("/api/v1/runs")
async def api_v1_run_start(payload: RunRequest) -> dict[str, Any]:
    """Start a run using the shared UI contract."""
    started = await run_start(payload)
    job_id = str(started["job_id"])
    state = _run_state(job_id)
    return {
        "schema_version": "ui_run_state_v1",
        "run_id": job_id,
        "session": state["session"],
        "status": state["status"],
        "decision": state["decision"],
        "expected_stages": state["expected_stages"],
        "events": state["events"],
        "final_output": state["final_output"],
        "error": state["error"],
    }


@app.get("/api/v1/runs/{job_id}")
async def api_v1_run_state(job_id: str) -> dict[str, Any]:
    """Return the latest shared UI state for a run."""
    return _run_state(job_id)


@app.post("/api/v1/runs/{job_id}/checkpoint")
async def api_v1_run_checkpoint(job_id: str, payload: CheckpointRequest) -> dict[str, Any]:
    """Submit a retrieval checkpoint decision through the shared UI API."""
    return await run_checkpoint(job_id, payload)


@app.get("/api/v1/runs/{job_id}/events")
async def api_v1_run_events(job_id: str) -> StreamingResponse:
    """Stream canonical UI events for one run using server-sent events."""
    if job_id not in _RUN_JOBS:
        raise HTTPException(status_code=404, detail="Run job not found.")

    async def _stream():
        cursor = 0
        while True:
            state = _run_state(job_id)
            events = state["events"]
            for event in events[cursor:]:
                yield f"event: {event['event_type']}\ndata: {json.dumps(event)}\n\n"
            cursor = len(events)
            if state["status"] in {"completed", "failed"} and cursor >= len(events):
                break
            await asyncio.sleep(0.25)

    return StreamingResponse(_stream(), media_type="text/event-stream")


@app.get("/api/v1/ui/theme")
async def api_v1_ui_theme() -> dict[str, Any]:
    """Return shared UI theme tokens for web, Gem, and future clients."""
    return _read_ui_theme_config()


@app.get("/api/v1/sessions")
async def api_v1_list_sessions() -> dict[str, Any]:
    """Return available sessions through the shared UI API."""
    return list_sessions()


@app.post("/api/v1/sessions")
async def api_v1_create_session(payload: SessionCreateRequest) -> dict[str, Any]:
    """Create or select a session through the shared UI API."""
    return create_session(payload)


@app.get("/api/v1/sessions/{session_name}")
async def api_v1_get_session(session_name: str) -> dict[str, Any]:
    """Return one session through the shared UI API."""
    return get_session(session_name)


@app.get("/api/config")
async def app_config() -> dict[str, Any]:
    """Return user-facing web defaults."""
    settings = load_settings()
    return {
        "retrieval_checkpoint_enabled": settings.retrieval_checkpoint_enabled,
        "retrieval_checkpoint_max_redirects": settings.retrieval_checkpoint_max_redirects,
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
        "memory": _serialize_memory(current_session),
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
        "memory": _serialize_memory(session_name),
    }


@app.get("/api/sessions/{session_name}")
def get_session(session_name: str) -> dict[str, Any]:
    """Return one session history and identify it as current."""
    safe_name = sanitize_session_name(session_name)
    history = load_history(safe_name)
    return {
        "current_session": safe_name,
        "history": _serialize_history(history),
        "memory": _serialize_memory(safe_name),
    }


@app.get("/api/workspace/roots")
def workspace_roots() -> dict[str, Any]:
    """Return browseable workspace roots."""
    return {"roots": _browser_roots()}


@app.get("/api/workspace/tree/{root_name}")
def workspace_tree(root_name: str) -> dict[str, Any]:
    """Return a flat file tree for one browseable workspace root."""
    roots = _browser_roots()
    if root_name not in roots:
        raise HTTPException(status_code=404, detail="Unknown workspace root.")
    base = _safe_workspace_path(roots[root_name])
    return {"root": root_name, "path": roots[root_name], "files": _workspace_tree(base)}


@app.get("/api/workspace/file")
def workspace_file(path: str) -> dict[str, Any]:
    """Read one workspace file for display/editing."""
    file_path = _safe_workspace_path(path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Workspace file not found.")
    _assert_editable_workspace_file(file_path)
    return {
        "path": file_path.relative_to(_workspace_root()).as_posix(),
        "content": file_path.read_text(encoding="utf-8"),
    }


@app.post("/api/workspace/file")
def save_workspace_file(payload: WorkspaceFileSaveRequest) -> dict[str, Any]:
    """Save one editable workspace file."""
    file_path = _safe_workspace_path(payload.path)
    _assert_editable_workspace_file(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(payload.content, encoding="utf-8")
    return {"path": file_path.relative_to(_workspace_root()).as_posix(), "saved": True}


def main() -> None:
    """Start the web application with Uvicorn."""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise typer.BadParameter(
            "Missing web dependencies. Install with: pip install fastapi uvicorn"
        ) from exc
    _run_async(uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8000)).serve())
