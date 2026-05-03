from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TRACE_FILE_NAME = "agent_trace.jsonl"



def _utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()



def write_trace_event(log_file: Path, event: dict[str, Any]) -> None:
    """Write a single structured trace event as JSONL.

    Args:
        log_file: Destination JSONL file.
        event: Structured event payload.
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as file_obj:
        file_obj.write(json.dumps(event, ensure_ascii=False) + "\n")



def append_trace(
    log_file: Path,
    stage: str,
    content: str,
    *,
    run_id: str | None = None,
    event_type: str = "stage_output",
    agent_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append a structured workflow trace event.

    This preserves the original helper name for compatibility while changing
    the underlying storage format from plain text banners to JSONL.

    Args:
        log_file: Destination trace file.
        stage: Workflow stage label.
        content: Stage content or message.
        run_id: Optional workflow correlation id.
        event_type: Semantic event category.
        agent_id: Optional emitting agent identifier.
        metadata: Optional extra event fields.
    """
    event: dict[str, Any] = {
        "timestamp": _utc_now_iso(),
        "service": {"name": "crisai", "component": "agent_trace"},
        "event_type": event_type,
        "stage": stage,
        "content": content.strip(),
    }

    if run_id:
        event["run_id"] = run_id
    if agent_id:
        event["agent_id"] = agent_id
    if metadata:
        event["metadata"] = metadata

    write_trace_event(log_file, event)
