from __future__ import annotations

import asyncio
import base64
import binascii
import json
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import typer
import yaml
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from crisai import ms_graph
from crisai.apps.run_history import (
    DEFAULT_LIST_LIMIT,
    MAX_LIST_LIMIT,
    build_run_history_response,
    is_safe_run_id,
    is_safe_session_route_value,
    load_run_detail,
    persist_run_snapshot,
    utc_now_iso,
)
from crisai.cli.artefact_lifecycle import persist_reusable_deliverable
from crisai.cli.chat_context import (
    build_chat_input,
    build_session_context_package,
    continuation_intent_message,
    normalise_legacy_workspace_paths,
    render_session_memory,
    serialize_session_context,
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
from crisai.cli.pipeline_display import (
    _openai_streaming_construct_type_incompatible,
    _streaming_fallback_metadata,
    reset_stage_stream_callback,
    set_stage_stream_callback,
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
from crisai.orchestration.request_contract import (
    infer_request_contract,
    render_request_contract_brief,
)
from crisai.orchestration.retrieval_checkpoint import (
    RetrievalCheckpointDecision,
    RetrievalCheckpointSnapshot,
)
from crisai.orchestration.task_contract import TaskContract
from crisai.registry import Registry
from crisai.ui_events import UiEvent, UiEventType, make_ui_event
from crisai.workspace.safety import (
    SensitiveWorkspacePathError,
    WorkspacePathEscapeError,
    iter_visible_workspace_files,
    resolve_workspace_path,
)
from crisai.workspace.spaces import load_workspace_spaces


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Create log directory and application log file when the server starts."""
    configure_logging(load_settings())
    yield


app = FastAPI(title="crisAI Web", lifespan=_lifespan)
_RUN_JOBS: dict[str, dict[str, Any]] = {}
_MAX_COMPLETED_JOBS = 20
_MAX_WORKSPACE_UPLOAD_BYTES = 25 * 1024 * 1024
_UPLOAD_SUFFIXES = frozenset({
    ".csv",
    ".docx",
    ".gif",
    ".jpeg",
    ".jpg",
    ".json",
    ".md",
    ".mmd",
    ".pdf",
    ".png",
    ".pptx",
    ".txt",
    ".webp",
    ".xlsx",
    ".yaml",
    ".yml",
})

# File types the web UI may open, edit, save, and rename in place. Kept as a
# single source of truth so the tree listing, edit guard, and rename guard can
# never drift apart.
_EDITABLE_WORKSPACE_SUFFIXES = frozenset({
    ".md",
    ".txt",
    ".mmd",
    ".json",
    ".yaml",
    ".yml",
})

_DEFAULT_RATE_LIMIT_RPM = 0  # 0 = disabled
_RATE_LIMITED_PATHS = frozenset({"/api/run", "/api/run/start", "/api/v1/runs"})
_RATE_LIMIT_STATE: dict[str, Any] = {"window_start": 0.0, "count": 0}


def _resolve_rate_limit_rpm() -> int:
    """Return max POST requests/minute on execution endpoints; 0 = disabled."""
    raw = os.getenv("CRISAI_RATE_LIMIT_RPM", "").strip()
    if not raw:
        return _DEFAULT_RATE_LIMIT_RPM
    try:
        parsed = int(raw)
    except ValueError:
        return _DEFAULT_RATE_LIMIT_RPM
    return parsed if parsed > 0 else _DEFAULT_RATE_LIMIT_RPM


@app.middleware("http")
async def _rate_limit_middleware(request: Request, call_next: Any) -> Any:
    """Guard /api/run and /api/v1/runs against accidental budget exhaustion.

    Fixed-window counter: at most CRISAI_RATE_LIMIT_RPM POST requests per 60 s.
    No-op when the env var is 0 or unset. LIFO note: _auth_middleware is defined
    after this one, so auth executes first; only authenticated requests reach this
    counter.
    """
    limit = _resolve_rate_limit_rpm()
    if not limit or request.method != "POST" or request.url.path not in _RATE_LIMITED_PATHS:
        return await call_next(request)

    now = time.monotonic()
    window_start = _RATE_LIMIT_STATE["window_start"]
    if now - window_start >= 60.0:
        _RATE_LIMIT_STATE["window_start"] = now
        _RATE_LIMIT_STATE["count"] = 0
        window_start = now

    if _RATE_LIMIT_STATE["count"] >= limit:
        retry_after = int(60.0 - (now - window_start)) + 1
        return Response(
            content='{"detail":"Rate limit exceeded"}',
            status_code=429,
            media_type="application/json",
            headers={"Retry-After": str(retry_after)},
        )

    _RATE_LIMIT_STATE["count"] += 1
    return await call_next(request)


@app.middleware("http")
async def _auth_middleware(request: Request, call_next: Any) -> Any:
    """Enforce Bearer token auth when CRISAI_API_KEY is set.

    When CRISAI_API_KEY is empty or unset the middleware is a no-op so that
    local single-user deployments require no configuration change.

    CORS preflight (OPTIONS) is handled by the outermost CORSMiddleware before
    a request reaches this middleware, so no OPTIONS bypass is needed here; when
    a key is set, OPTIONS is authenticated like any other method.
    """
    api_key = os.getenv("CRISAI_API_KEY", "").strip()
    if not api_key:
        return await call_next(request)
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or not secrets.compare_digest(auth[len("Bearer "):], api_key):
        return Response(
            content='{"detail":"Unauthorized"}',
            status_code=401,
            media_type="application/json",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await call_next(request)


def _cors_allowed_origins() -> list[str]:
    """Return the CORS allowed origins for the web client.

    Defaults to the local React dev origins. Set CRISAI_CORS_ORIGINS to a
    comma-separated list to override for a deployment that serves the web client
    from a different origin, keeping the origin allow-list out of source.
    """
    raw = os.getenv("CRISAI_CORS_ORIGINS", "").strip()
    if not raw:
        return ["http://127.0.0.1:5173", "http://localhost:5173"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


# Register CORS last so it wraps the auth and rate-limit middleware as the
# outermost layer. Starlette runs the most recently added middleware first, so
# this answers preflight (OPTIONS) at the edge and keeps the 401/429 responses
# from the inner middleware readable by the browser client (they retain the
# Access-Control-Allow-Origin header instead of failing as opaque CORS errors).
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allowed_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


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


class WorkspaceFileRenameRequest(BaseModel):
    """Represent a web request to rename an editable workspace file in place."""

    path: str = Field(min_length=1)
    new_name: str = Field(min_length=1)


class WorkspaceUploadRequest(BaseModel):
    """Represent a web request to upload a source file into the workspace."""

    target: str = Field(default="task_inputs")
    session: str = Field(default="default")
    filename: str = Field(min_length=1)
    content_base64: str = Field(min_length=1)


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


def _stage_delta_observability() -> dict[str, object]:
    """Return trace-safe streaming metadata for live stage deltas."""
    return {
        "schema_version": "ui_stage_observability_v1",
        "streaming": {
            "attempted": True,
            # Live deltas are emitted only from the streamed path; fallback runs emit trace metadata later.
            "fallback": False,
        },
    }


def _stage_start_observability() -> dict[str, object]:
    """Return expected streaming delivery metadata for a just-started stage."""
    if _openai_streaming_construct_type_incompatible():
        streaming = dict(cast(dict[str, object], _streaming_fallback_metadata()["streaming"]))
        streaming["expected_delivery"] = "completion_only"
    else:
        streaming = {
            "attempted": True,
            "fallback": False,
            "expected_delivery": "delta",
        }
    return {
        "schema_version": "ui_stage_observability_v1",
        "streaming": streaming,
    }


def _append_stage_delta_event(job_id: str, agent_id: str, delta: str) -> None:
    """Append a coalesced streaming text update for one running stage."""
    if not delta:
        return
    job = _RUN_JOBS[job_id]
    buffers = job.setdefault("stream_buffers", {})
    emit_sizes = job.setdefault("stream_emit_sizes", {})
    content = str(buffers.get(agent_id, "")) + delta
    buffers[agent_id] = content
    last_size = int(emit_sizes.get(agent_id, 0))
    if len(content) - last_size < 80 and "\n" not in delta:
        return
    emit_sizes[agent_id] = len(content)
    summary = content.strip().splitlines()[-1] if content.strip() else "Streaming output."
    _append_job_event(
        job_id,
        make_ui_event(
            "stage_delta",
            run_id=job_id,
            session=_job_session(job),
            status=str(job.get("status") or "running"),
            title=f"{_stage_label(agent_id)} streaming",
            summary=summary[:240],
            content=content,
            verbose_content=content,
            mode=_job_mode(job),
            agent_id=agent_id,
            stage=agent_id,
            metadata={
                "partial": True,
                "content_length": len(content),
                "stage_key": agent_id,
                "stage_label": _stage_label(agent_id),
                "observability": _stage_delta_observability(),
            },
        ),
    )


def _job_session(job: dict[str, Any]) -> str:
    return str(job.get("current_session") or "default")


def _job_mode(job: dict[str, Any]) -> str | None:
    decision = job.get("decision")
    return str(getattr(decision, "mode", "")) or None


def _message_summary(message: str) -> str:
    """Return a compact single-line summary for run history labels."""
    return " ".join(str(message or "").strip().split())[:160]


def _agent_model_metadata(agent_id: str | None) -> dict[str, Any]:
    """Return registry model metadata for an agent when available."""
    if not agent_id:
        return {}
    try:
        registry = Registry(load_settings().registry_dir)
        agents = {agent.id: agent for agent in registry.load_agents()}
        models = {model.id: model for model in registry.load_models()}
    except Exception:  # noqa: BLE001 - UI metadata must not break execution.
        return {}
    agent = agents.get(agent_id)
    if agent is None:
        return {}
    model_ref = agent.model_ref or agent.model or ""
    model = models.get(model_ref)
    metadata: dict[str, Any] = {"agent_id": agent.id, "model_ref": model_ref}
    if model is not None:
        metadata.update({
            "provider": model.provider,
            "model_name": model.model_name,
        })
    elif agent.model:
        metadata["model_name"] = agent.model
    return {key: value for key, value in metadata.items() if value}


def _stage_label(stage_key: str | None) -> str:
    """Return the human label for a stable snake_case stage key."""
    key = str(stage_key or "").strip()
    if not key:
        return "System"
    return _load_stage_labels().get(key, key.replace("_", " ").capitalize())


def _stage_tab(stage_key: str) -> dict[str, str]:
    """Return one expected-stage entry for the shared UI contract."""
    return {"key": stage_key, "label": _stage_label(stage_key)}


def _load_stage_labels() -> dict[str, str]:
    """Load UI stage labels from registry-owned UI configuration."""
    try:
        ui_path = Path(load_settings().registry_dir) / "ui.yaml"
        raw = yaml.safe_load(ui_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - label fallback must not break run state.
        return {}
    if not isinstance(raw, dict) or not isinstance(raw.get("stage_labels"), dict):
        return {}
    return {
        str(key): str(value)
        for key, value in raw["stage_labels"].items()
        if str(key).strip() and str(value).strip()
    }


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
    stage_key = _extract_stage_key(
        {
            "agent_id": str(stage_entry.get("agent_id") or ""),
            "stage": str(stage_entry.get("stage", "")),
        }
    )
    content = str(stage_entry.get("full_content") or stage_entry.get("content") or "")
    summary = str(stage_entry.get("summary") or "").strip()
    if not summary:
        summary = content.splitlines()[0] if content else ""
    verbose_content = str(stage_entry.get("verbose_content") or content)
    raw_metadata = stage_entry.get("metadata")
    trace_metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
    observability = (
        trace_metadata.get("observability")
        if isinstance(trace_metadata.get("observability"), dict)
        else None
    )
    if observability is None and source_event == "stage_start":
        observability = _stage_start_observability()
    event = make_ui_event(
        event_type,
        run_id=job_id,
        session=_job_session(job),
        status=str(job.get("status") or "running"),
        title=_stage_label(stage_key),
        summary=summary,
        content=content,
        verbose_content=verbose_content,
        mode=_job_mode(job),
        agent_id=stage_key,
        stage=stage_key,
        metadata={
            "source_event_type": source_event,
            "trace_agent_id": agent_id,
            "trace_stage": str(stage_entry.get("stage") or ""),
            "stage_key": stage_key,
            "stage_label": _stage_label(stage_key),
            **({"observability": observability} if observability else {}),
            **({"trace_metadata": trace_metadata} if trace_metadata else {}),
        },
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


def _run_history_snapshot(job_id: str, *, updated_at: str | None = None) -> dict[str, Any]:
    """Build the persisted run-history snapshot for one job."""
    job = _RUN_JOBS[job_id]
    now = updated_at or utc_now_iso()
    completed_at = now if job.get("status") in {"completed", "failed"} else ""
    payload = job.get("payload")
    message = str(getattr(payload, "message", "") or "")
    expected_stages = _expected_flow_tabs(
        job.get("decision"),
        request_contract=job.get("request_contract"),
        is_summary=job.get("request_contract_is_summary"),
    )
    return {
        "schema_version": "ui_run_state_v1",
        "run_id": job_id,
        "session": _job_session(job),
        "status": str(job.get("status") or ""),
        "decision": job.get("decision_data", {}),
        "expected_stages": expected_stages,
        "events": job.get("events", []),
        "final_output": job.get("final_output", ""),
        "error": job.get("error", ""),
        "metadata": {
            "snapshot_schema_version": "crisai_run_snapshot_v1",
            "created_at": str(job.get("created_at") or now),
            "updated_at": now,
            "completed_at": completed_at,
            "message_summary": _message_summary(message),
            "trace_run_id": str(job.get("run_id") or ""),
            "request_contract": job.get("request_contract", {}),
        },
    }


def _persist_terminal_run_history(job_id: str) -> None:
    """Persist completed or failed run state without affecting live state."""
    job = _RUN_JOBS.get(job_id)
    if job is None or job.get("status") not in {"completed", "failed"}:
        return
    _refresh_job_from_trace(job_id)
    try:
        persist_run_snapshot(_run_history_snapshot(job_id))
    except Exception:  # noqa: BLE001 - history persistence must not change run outcome.
        return


def _resolve_decision(payload: RunRequest):
    """Resolve router decision from web request preferences."""
    message = _intent_message_for_payload(payload)
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


def _resolve_request_contract(payload: RunRequest, decision: Any):
    """Resolve a user-facing request contract for UI transparency."""
    message = _intent_message_for_payload(payload)
    settings = load_settings()
    session_name = sanitize_session_name(payload.session)
    source_candidates = tuple(load_session_memory(session_name).source_candidates)
    return infer_request_contract(
        message,
        current_mode=str(getattr(decision, "mode", "") or payload.mode or "auto"),
        registry_dir=Path(settings.registry_dir),
        source_candidates=source_candidates,
    )


def _intent_message_for_payload(payload: RunRequest, history: list[tuple[str, str]] | None = None) -> str:
    """Return the message used for routing, contracts, and workflow policy."""
    session_name = sanitize_session_name(payload.session)
    loaded_history = load_history(session_name) if history is None else history
    return continuation_intent_message(
        payload.message,
        loaded_history,
        registry_dir=Path(load_settings().registry_dir),
    )


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
    request_contract = _resolve_request_contract(payload, decision)
    session_name = sanitize_session_name(payload.session)
    history = load_history(session_name)
    runtime_message = normalise_legacy_workspace_paths(payload.message)
    intent_message = _intent_message_for_payload(payload, history)
    chat_input = build_chat_input(runtime_message, history, session_name=session_name)
    try:
        final_output = await _run_with_routing(
            message=chat_input,
            verbose=payload.verbose,
            review=payload.review,
            decision=decision,
            user_intent_message=intent_message,
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
        "request_contract": request_contract.to_dict(),
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
                verbose_content=snapshot.retrieval_prose,
                mode=_job_mode(job),
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


def _serialize_session_context(session_name: str, *, query: str = "", limit: int = 5) -> dict[str, Any]:
    """Return deterministic baseline context plus optional recall for one session."""
    safe_name = sanitize_session_name(session_name)
    package = build_session_context_package(
        safe_name,
        query=query,
        limit=limit,
        registry_dir=load_settings().registry_dir,
    )
    return serialize_session_context(package)


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
    root = _workspace_root()
    try:
        return resolve_workspace_path(root, relative_path)
    except WorkspacePathEscapeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SensitiveWorkspacePathError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


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
    if path.suffix.lower() not in _EDITABLE_WORKSPACE_SUFFIXES:
        raise HTTPException(status_code=403, detail="This file type is not editable in the web UI.")


def _safe_upload_filename(filename: str) -> str:
    """Return a bounded filename safe for workspace upload paths."""
    name = Path(filename).name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Upload filename is required.")
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    if not safe:
        raise HTTPException(status_code=422, detail="Upload filename has no usable characters.")
    suffix = Path(safe).suffix.lower()
    if suffix not in _UPLOAD_SUFFIXES:
        raise HTTPException(status_code=403, detail=f"Upload file type is not allowed: {suffix or '<none>'}.")
    if len(safe) <= 180:
        return safe
    stem = Path(safe).stem[: max(1, 180 - len(suffix))]
    return f"{stem}{suffix}"


def _safe_rename_name(new_name: str) -> str:
    """Validate a bare destination filename for an in-place rename.

    Rename changes the filename only; it never moves a file between
    directories. The name must therefore be a single path segment (no
    separators, not a dotfile) and must keep an editable file type so the
    result stays openable in the web UI.
    """
    name = new_name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="New file name is required.")
    if name != Path(name).name:
        raise HTTPException(status_code=400, detail="New file name must not contain path separators.")
    if name.startswith("."):
        raise HTTPException(status_code=400, detail="New file name must not start with a dot.")
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    if not safe:
        raise HTTPException(status_code=422, detail="New file name has no usable characters.")
    suffix = Path(safe).suffix.lower()
    if suffix not in _EDITABLE_WORKSPACE_SUFFIXES:
        raise HTTPException(status_code=403, detail="Renamed file must keep an editable file type.")
    if len(safe) > 180:
        stem = Path(safe).stem[: max(1, 180 - len(suffix))]
        safe = f"{stem}{suffix}"
    return safe


def _upload_target_dir(payload: WorkspaceUploadRequest) -> Path:
    """Resolve the upload target directory within the configured workspace."""
    roots = _browser_roots()
    if payload.target == "task_inputs":
        session_name = sanitize_session_name(payload.session)
        return _safe_workspace_path(f"{roots['tasks']}/{session_name}/inputs")
    if payload.target == "knowledge_intake":
        return _safe_workspace_path(f"{roots['knowledge']}/intake")
    raise HTTPException(status_code=422, detail="Upload target must be task_inputs or knowledge_intake.")


def _dedupe_upload_path(directory: Path, filename: str) -> Path:
    """Return a non-existing path by adding a numeric suffix when needed."""
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    path = Path(filename)
    stem = path.stem
    suffix = path.suffix
    for index in range(1, 1000):
        candidate = directory / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
    raise HTTPException(status_code=409, detail="Too many uploaded files with the same name.")


def upload_workspace_file(payload: WorkspaceUploadRequest) -> dict[str, Any]:
    """Save one uploaded source file into a bounded workspace location."""
    filename = _safe_upload_filename(payload.filename)
    try:
        content = base64.b64decode(payload.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Upload content must be valid base64.") from exc
    if len(content) > _MAX_WORKSPACE_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds the maximum allowed size.")
    directory = _upload_target_dir(payload)
    directory.mkdir(parents=True, exist_ok=True)
    path = _dedupe_upload_path(directory, filename)
    path.write_bytes(content)
    return {
        "path": path.relative_to(_workspace_root()).as_posix(),
        "filename": path.name,
        "size": len(content),
        "target": payload.target,
        "uploaded": True,
    }


def _workspace_tree(base: Path) -> list[dict[str, Any]]:
    root = _workspace_root()
    if not base.exists():
        return []
    entries: list[dict[str, Any]] = []
    for path in sorted(iter_visible_workspace_files(base, root)):
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
                "editable": path.suffix.lower() in _EDITABLE_WORKSPACE_SUFFIXES,
            }
        )
    return entries


def _expected_flow_tabs(
    decision: Any,
    *,
    request_contract: Any | None = None,
    is_summary: bool | None = None,
) -> list[dict[str, str]]:
    """Build expected flow tabs from routing decision and request contract."""
    mode = getattr(decision, "mode", "single")
    needs_review = bool(getattr(decision, "needs_review", False))
    needs_retrieval = bool(getattr(decision, "needs_retrieval", False))
    agent = getattr(decision, "agent", "orchestrator") or "orchestrator"
    summary_pipeline = _is_summary_contract(request_contract) if is_summary is None else is_summary

    tabs: list[dict[str, str]] = []
    if mode == "pipeline":
        tabs.append(_stage_tab("retrieval_planner"))
        tabs.append(_stage_tab("context_retrieval"))
        if summary_pipeline:
            tabs.append(_stage_tab("summary"))
        else:
            tabs.append(_stage_tab("context_synthesizer"))
            tabs.append(_stage_tab("design"))
            if needs_review:
                tabs.append(_stage_tab("review"))
            tabs.append(_stage_tab("orchestrator"))
    elif mode == "peer":
        if needs_retrieval:
            tabs.append(_stage_tab("retrieval_planner"))
            tabs.append(_stage_tab("context_retrieval"))
        tabs.extend(
            [
                _stage_tab("design_author"),
                _stage_tab("design_challenger"),
                _stage_tab("design_refiner"),
                _stage_tab("judge"),
                _stage_tab("orchestrator"),
            ]
        )
    else:
        tabs.append(_stage_tab(agent))

    tabs.append(_stage_tab("final_output"))
    return tabs


def _is_summary_contract(request_contract: Any | None) -> bool:
    """Return whether a request contract represents a summary deliverable."""
    if request_contract is None:
        return False
    is_summary = getattr(request_contract, "is_summary", None)
    if isinstance(is_summary, bool):
        return is_summary
    if isinstance(request_contract, dict):
        task_contract = request_contract.get("task_contract")
        if isinstance(task_contract, dict):
            return TaskContract.from_dict(task_contract).is_summary
    return False


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
    raw_content = str(entry.get("content", ""))
    summary = render_stage_output_text(agent_id, raw_content, verbose=False)
    full_content = render_stage_output_text(agent_id, raw_content, verbose=True)
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
        "content": render_stage_output_text(agent_id, raw_content, verbose=verbose),
        "summary": summary,
        "full_content": full_content,
        "verbose_content": full_content,
        "metadata": entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {},
    }


async def _run_job(job_id: str, payload: RunRequest, decision: Any) -> None:
    """Execute one background run and persist completion state."""
    job = _RUN_JOBS[job_id]
    stream_token = set_stage_stream_callback(
        lambda agent_id, delta: _append_stage_delta_event(job_id, agent_id, delta)
    )
    try:
        session_name = sanitize_session_name(payload.session)
        history = load_history(session_name)
        runtime_message = normalise_legacy_workspace_paths(payload.message)
        intent_message = _intent_message_for_payload(payload, history)
        chat_input = build_chat_input(runtime_message, history, session_name=session_name)
        final_output = await _run_with_routing(
            message=chat_input,
            verbose=payload.verbose,
            review=payload.review,
            decision=decision,
            user_intent_message=intent_message,
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
        _refresh_job_from_trace(job_id)
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
        _persist_terminal_run_history(job_id)
    except Exception as exc:  # noqa: BLE001
        job["status"] = "failed"
        job["error"] = _to_http_exception(exc).detail
        _refresh_job_from_trace(job_id)
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
        _persist_terminal_run_history(job_id)
    finally:
        reset_stage_stream_callback(stream_token)


def _evict_old_jobs(max_completed: int = _MAX_COMPLETED_JOBS) -> None:
    """Remove oldest completed/failed jobs, keeping at most max_completed."""
    terminal_ids = [
        job_id
        for job_id, job in _RUN_JOBS.items()
        if job.get("status") in {"completed", "failed"}
    ]
    for job_id in terminal_ids[: max(0, len(terminal_ids) - max_completed)]:
        del _RUN_JOBS[job_id]




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
    request_contract = _resolve_request_contract(payload, decision)
    trace_path = _trace_file_path()
    before_size = trace_path.stat().st_size if trace_path.exists() else 0
    job_id = uuid4().hex

    _RUN_JOBS[job_id] = {
        "status": "running",
        "created_at": utc_now_iso(),
        "payload": payload,
        "decision": decision,
        "decision_data": asdict(decision),
        "request_contract": request_contract.to_dict(),
        "request_contract_is_summary": request_contract.is_summary,
        "before_size": before_size,
        "run_id": None,
        "stage_outputs": [],
        "final_output": "",
        "error": "",
        "checkpoint": None,
        "checkpoint_future": None,
        "history": [],
        "current_session": sanitize_session_name(payload.session),
        "stream_buffers": {},
        "stream_emit_sizes": {},
        "events": [],
        "event_trace_keys": set(),
        "task": None,
    }
    expected_tabs = _expected_flow_tabs(
        decision,
        request_contract=request_contract,
        is_summary=request_contract.is_summary,
    )
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
            metadata={
                "expected_tabs": expected_tabs,
                "selected_agent": getattr(decision, "agent", None),
                **_agent_model_metadata(getattr(decision, "agent", None)),
            },
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
            verbose_content=str(getattr(decision, "reason", "")),
            mode=getattr(decision, "mode", None),
            metadata={
                **asdict(decision),
                **_agent_model_metadata(getattr(decision, "agent", None)),
            },
        ),
    )
    _append_job_event(
        job_id,
        make_ui_event(
            "task_contract",
            run_id=job_id,
            session=sanitize_session_name(payload.session),
            status="running",
            title="Task contract",
            summary=(
                f"{request_contract.primary_intent} -> "
                f"{request_contract.deliverable_type}; evidence: "
                f"{request_contract.required_evidence_level}."
            ),
            verbose_content=render_request_contract_brief(
                request_contract,
                selected_mode=str(getattr(decision, "mode", "") or ""),
                selected_agent=str(getattr(decision, "agent", "") or ""),
            ),
            mode=getattr(decision, "mode", None),
            metadata=request_contract.to_dict(),
        ),
    )
    _RUN_JOBS[job_id]["task"] = asyncio.create_task(_run_job(job_id, payload, decision))
    _evict_old_jobs()

    return {
        "job_id": job_id,
        "decision": asdict(decision),
        "request_contract": request_contract.to_dict(),
        "expected_tabs": expected_tabs,
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
    expected_stages = _expected_flow_tabs(
        job.get("decision"),
        request_contract=job.get("request_contract"),
        is_summary=job.get("request_contract_is_summary"),
    )
    return {
        "schema_version": "ui_run_state_v1",
        "run_id": job_id,
        "session": _job_session(job),
        "status": job.get("status"),
        "decision": job.get("decision_data", {}),
        "expected_stages": expected_stages,
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


@app.get("/api/v1/sessions/{session_name}/runs")
async def api_v1_session_runs(
    session_name: str,
    limit: int = Query(default=DEFAULT_LIST_LIMIT, ge=1, le=MAX_LIST_LIMIT),
) -> dict[str, Any]:
    """Return persisted previous-run summaries for one session."""
    if not is_safe_session_route_value(session_name):
        raise HTTPException(status_code=404, detail="Session not found.")
    return build_run_history_response(session_name, limit=limit)


@app.get("/api/v1/sessions/{session_name}/runs/{run_id}")
async def api_v1_session_run_detail(session_name: str, run_id: str) -> dict[str, Any]:
    """Return one persisted previous-run detail for a session."""
    if not is_safe_session_route_value(session_name) or not is_safe_run_id(run_id):
        raise HTTPException(status_code=404, detail="Run not found.")
    detail = load_run_detail(session_name, run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return detail


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


@app.get("/api/v1/sessions/{session_name}/context")
async def api_v1_session_context(
    session_name: str,
    query: str = Query(default=""),
    limit: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    """Return deterministic baseline context and optional recall for one session."""
    if not is_safe_session_route_value(session_name):
        raise HTTPException(status_code=404, detail="Session not found.")
    return _serialize_session_context(session_name, query=query, limit=limit)


@app.get("/api/v1/workspace/roots")
async def api_v1_workspace_roots() -> dict[str, Any]:
    """Return browseable workspace roots through the shared UI API."""
    return workspace_roots()


@app.get("/api/v1/workspace/tree/{root_name}")
async def api_v1_workspace_tree(root_name: str) -> dict[str, Any]:
    """Return a workspace tree through the shared UI API."""
    return workspace_tree(root_name)


@app.get("/api/v1/workspace/file")
async def api_v1_workspace_file(path: str) -> dict[str, Any]:
    """Read one workspace file through the shared UI API."""
    return workspace_file(path)


@app.post("/api/v1/workspace/file")
async def api_v1_save_workspace_file(payload: WorkspaceFileSaveRequest) -> dict[str, Any]:
    """Save one workspace file through the shared UI API."""
    return save_workspace_file(payload)


@app.post("/api/v1/workspace/rename")
async def api_v1_rename_workspace_file(payload: WorkspaceFileRenameRequest) -> dict[str, Any]:
    """Rename one workspace file through the shared UI API."""
    return rename_workspace_file(payload)


@app.post("/api/v1/workspace/upload")
async def api_v1_upload_workspace_file(payload: WorkspaceUploadRequest) -> dict[str, Any]:
    """Upload one source file through the shared UI API."""
    return upload_workspace_file(payload)


def _ensure_sharepoint_graph_configured() -> None:
    """Point ms_graph at the same token cache the SharePoint MCP server reads.

    The MCP server runs ``configure_workspace(<workspace>, namespace="sharepoint")``;
    using the same workspace root and namespace here means a token the web app
    acquires lands in the cache the server's silent refresh picks up.
    """
    ms_graph.configure_workspace(_workspace_root(), namespace="sharepoint")


@app.post("/api/v1/auth/sharepoint/start")
async def api_v1_sharepoint_login_start() -> dict[str, Any]:
    """Begin a SharePoint device-code login and return the code to display.

    The token is acquired and stored server-side; only the user-facing code and
    verification URL are returned. Runs behind the same auth middleware as every
    other endpoint.
    """
    _ensure_sharepoint_graph_configured()
    try:
        return ms_graph.start_device_login()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/v1/auth/sharepoint/status")
async def api_v1_sharepoint_login_status() -> dict[str, Any]:
    """Report SharePoint login progress so the UI can close its popup on success."""
    _ensure_sharepoint_graph_configured()
    try:
        return ms_graph.device_login_status()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
    names = _list_session_names()
    history = load_history(safe_name)
    return {
        "sessions": names,
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


@app.post("/api/workspace/rename")
def rename_workspace_file(payload: WorkspaceFileRenameRequest) -> dict[str, Any]:
    """Rename one editable workspace file in place (same directory).

    Both the source and the destination must clear the same path-safety and
    editable-area guards as a read or save, so rename grants no access a normal
    edit would not. The destination must not already exist.
    """
    source = _safe_workspace_path(payload.path)
    if not source.is_file():
        raise HTTPException(status_code=404, detail="Workspace file not found.")
    _assert_editable_workspace_file(source)
    root = _workspace_root()
    new_name = _safe_rename_name(payload.new_name)
    target_rel = (source.parent / new_name).relative_to(root).as_posix()
    target = _safe_workspace_path(target_rel)
    _assert_editable_workspace_file(target)
    if target == source:
        return {"path": source.relative_to(root).as_posix(), "renamed": False}
    if target.exists():
        raise HTTPException(status_code=409, detail="A file with that name already exists.")
    source.rename(target)
    return {"path": target.relative_to(root).as_posix(), "renamed": True}


@app.post("/api/workspace/upload")
def save_workspace_upload(payload: WorkspaceUploadRequest) -> dict[str, Any]:
    """Upload one source file into a task input or knowledge intake area."""
    return upload_workspace_file(payload)


def main() -> None:
    """Start the web application with Uvicorn."""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise typer.BadParameter(
            "Missing web dependencies. Install project dependencies with: uv sync --extra litellm"
        ) from exc
    _run_async(uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8000)).serve())
