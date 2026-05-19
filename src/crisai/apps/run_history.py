from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from crisai.cli.session_store import sanitize_session_name, task_metadata_dir, tasks_dir

RUN_HISTORY_SCHEMA_VERSION = "ui_run_history_v1"
RUN_HISTORY_DETAIL_SCHEMA_VERSION = "ui_run_state_v1"
MAX_RUN_HISTORY_ITEMS = 50
MAX_LIST_LIMIT = 50
DEFAULT_LIST_LIMIT = 20
MAX_EVENTS_PER_RUN = 500
MAX_EVENT_CONTENT_CHARS = 20_000
MAX_FINAL_OUTPUT_CHARS = 120_000
MAX_SUMMARY_CHARS = 160
_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9]{1,128}$")
_TERMINAL_STATUSES = {"completed", "failed"}


def utc_now_iso() -> str:
    """Return a compact UTC timestamp for persisted run metadata."""
    return datetime.now(timezone.utc).isoformat()


def is_safe_run_id(run_id: str) -> bool:
    """Return True when a run id is safe to use as one local JSON filename."""
    return bool(_SAFE_RUN_ID.fullmatch(str(run_id or "")))


def is_safe_session_route_value(session_name: str) -> bool:
    """Return True when a session route value cannot express traversal."""
    raw = str(session_name or "")
    return bool(raw.strip()) and "/" not in raw and "\\" not in raw and ".." not in raw


def runs_dir(session_name: str, *, create: bool = True) -> Path:
    """Return the task-local run history directory for a session."""
    safe_session = sanitize_session_name(session_name)
    if create:
        path = task_metadata_dir(safe_session) / "runs"
        path.mkdir(parents=True, exist_ok=True)
    else:
        path = tasks_dir() / safe_session / ".crisai" / "runs"
    return path


def run_detail_file(session_name: str, run_id: str, *, create: bool = True) -> Path:
    """Return one run detail path after validating the filename token."""
    if not is_safe_run_id(run_id):
        raise ValueError("Invalid run id.")
    return runs_dir(session_name, create=create) / f"{run_id}.json"


def load_run_detail(session_name: str, run_id: str) -> dict[str, Any] | None:
    """Load one persisted run detail, returning None when it does not exist."""
    try:
        path = run_detail_file(session_name, run_id, create=False)
    except ValueError:
        return None
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get("status") or "") not in _TERMINAL_STATUSES:
        return None
    return payload


def load_run_summaries(session_name: str, *, limit: int = DEFAULT_LIST_LIMIT) -> list[dict[str, Any]]:
    """Load persisted run summaries sorted newest first."""
    directory = runs_dir(session_name, create=False)
    if not directory.exists():
        return []
    capped_limit = min(max(int(limit), 1), MAX_LIST_LIMIT)
    summaries: list[dict[str, Any]] = []
    for path in directory.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(payload, dict) and str(payload.get("status") or "") in _TERMINAL_STATUSES:
            summaries.append(_summary_from_detail(payload))
    summaries.sort(key=_summary_sort_key, reverse=True)
    return [
        {**summary, "display_order": index}
        for index, summary in enumerate(summaries[:capped_limit], start=1)
    ]


def persist_run_snapshot(snapshot: dict[str, Any]) -> None:
    """Persist one terminal run snapshot and prune old details."""
    if str(snapshot.get("status") or "") not in _TERMINAL_STATUSES:
        raise ValueError("Run history only persists terminal runs.")
    session = sanitize_session_name(str(snapshot.get("session") or "default"))
    run_id = str(snapshot.get("run_id") or "")
    detail_path = run_detail_file(session, run_id)
    detail = _bounded_detail(snapshot)
    _atomic_write_json(detail_path, detail)
    _prune_old_runs(session)


def build_run_history_response(
    session_name: str,
    *,
    limit: int = DEFAULT_LIST_LIMIT,
) -> dict[str, Any]:
    """Build the session-scoped run history response."""
    safe_session = sanitize_session_name(session_name)
    summaries = load_run_summaries(safe_session, limit=limit)
    return {
        "schema_version": RUN_HISTORY_SCHEMA_VERSION,
        "session": safe_session,
        "runs": summaries,
    }


def stage_count(events: list[dict[str, Any]]) -> int:
    """Return the number of distinct stage-bearing UI events."""
    stages = {
        str(event.get("stage") or event.get("agent_id") or "")
        for event in events
        if str(event.get("event_type") or "").startswith("stage_")
    }
    return len({stage for stage in stages if stage})


def _prune_old_runs(session_name: str) -> None:
    summaries = load_run_summaries(session_name, limit=MAX_RUN_HISTORY_ITEMS)
    retained_ids = {str(item.get("run_id")) for item in summaries}
    for file_path in runs_dir(session_name).glob("*.json"):
        if file_path.stem not in retained_ids:
            try:
                file_path.unlink()
            except OSError:
                pass


def _bounded_detail(snapshot: dict[str, Any]) -> dict[str, Any]:
    session = sanitize_session_name(str(snapshot.get("session") or "default"))
    run_id = str(snapshot.get("run_id") or "")
    if not is_safe_run_id(run_id):
        raise ValueError("Invalid run id.")
    status = str(snapshot.get("status") or "")
    metadata_value = snapshot.get("metadata")
    metadata: dict[str, Any] = metadata_value if isinstance(metadata_value, dict) else {}
    detail: dict[str, Any] = {
        "schema_version": RUN_HISTORY_DETAIL_SCHEMA_VERSION,
        "run_id": run_id,
        "session": session,
        "status": status,
        "decision": snapshot.get("decision") if isinstance(snapshot.get("decision"), dict) else {},
        "expected_stages": snapshot.get("expected_stages") if isinstance(snapshot.get("expected_stages"), list) else [],
        "events": [_bounded_event(event) for event in _event_list(snapshot.get("events"))[:MAX_EVENTS_PER_RUN]],
        "final_output": _truncate(str(snapshot.get("final_output") or ""), MAX_FINAL_OUTPUT_CHARS),
        "error": str(snapshot.get("error") or ""),
        "metadata": {
            "snapshot_schema_version": str(metadata.get("snapshot_schema_version") or "crisai_run_snapshot_v1"),
            "created_at": str(metadata.get("created_at") or snapshot.get("created_at") or utc_now_iso()),
            "updated_at": str(metadata.get("updated_at") or snapshot.get("updated_at") or utc_now_iso()),
            "completed_at": str(metadata.get("completed_at") or snapshot.get("completed_at") or ""),
            "message_summary": _truncate(str(metadata.get("message_summary") or ""), MAX_SUMMARY_CHARS),
            "trace_run_id": str(metadata.get("trace_run_id") or ""),
            "request_contract": metadata.get("request_contract") if isinstance(metadata.get("request_contract"), dict) else {},
        },
    }
    if isinstance(metadata.get("observability"), dict):
        detail["metadata"]["observability"] = metadata["observability"]
    return detail


def _summary_from_detail(detail: dict[str, Any]) -> dict[str, Any]:
    metadata_value = detail.get("metadata")
    metadata: dict[str, Any] = metadata_value if isinstance(metadata_value, dict) else {}
    events = _event_list(detail.get("events"))
    final_output = str(detail.get("final_output") or "")
    error = str(detail.get("error") or "")
    return _bounded_summary(
        {
            "run_id": str(detail.get("run_id") or ""),
            "session": str(detail.get("session") or "default"),
            "status": str(detail.get("status") or ""),
            "created_at": str(metadata.get("created_at") or ""),
            "updated_at": str(metadata.get("updated_at") or ""),
            "completed_at": str(metadata.get("completed_at") or ""),
            "message_summary": str(metadata.get("message_summary") or ""),
            "mode": _decision_value(detail, "mode"),
            "agent": _decision_value(detail, "agent"),
            "expected_stages": detail.get("expected_stages") if isinstance(detail.get("expected_stages"), list) else [],
            "event_count": len(events),
            "stage_count": stage_count(events),
            "final_answer_summary": _first_line(final_output),
            "final_answer_length": len(final_output),
            "error": error,
        }
    )


def _bounded_summary(summary: dict[str, Any]) -> dict[str, Any]:
    bounded = dict(summary)
    bounded["message_summary"] = _truncate(str(bounded.get("message_summary") or ""), MAX_SUMMARY_CHARS)
    bounded["final_answer_summary"] = _truncate(str(bounded.get("final_answer_summary") or ""), MAX_SUMMARY_CHARS)
    bounded["error"] = _truncate(str(bounded.get("error") or ""), MAX_SUMMARY_CHARS)
    return bounded


def _bounded_event(event: dict[str, Any]) -> dict[str, Any]:
    bounded = dict(event)
    bounded["content"] = _truncate(str(bounded.get("content") or ""), MAX_EVENT_CONTENT_CHARS)
    bounded["verbose_content"] = _truncate(str(bounded.get("verbose_content") or ""), MAX_EVENT_CONTENT_CHARS)
    return bounded


def _event_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _decision_value(detail: dict[str, Any], key: str) -> str:
    decision = detail.get("decision")
    if not isinstance(decision, dict):
        return ""
    return str(decision.get(key) or "")


def _first_line(text: str) -> str:
    return _truncate(text.strip().splitlines()[0] if text.strip() else "", MAX_SUMMARY_CHARS)


def _summary_sort_key(summary: dict[str, Any]) -> str:
    return str(summary.get("updated_at") or summary.get("completed_at") or summary.get("created_at") or "")


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    if max_chars <= 3:
        return value[:max_chars]
    return value[: max_chars - 3] + "..."


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(path)
