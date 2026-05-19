from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRACE_FILE_NAME = "agent_trace.jsonl"
_READ_HANDLE_VALUE_RE = re.compile(r'("read_handle"\s*:\s*)"[^"]*"', re.IGNORECASE)
_BARE_READ_HANDLE_RE = re.compile(r"(?<![\w:])sharepoint_doc:[^\s\"'`<>{}\[\]]+", re.IGNORECASE)



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
    event = redact_trace_payload(event)
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
        "content": redact_trace_text(content.strip()),
    }

    if run_id:
        event["run_id"] = run_id
    if agent_id:
        event["agent_id"] = agent_id
    if metadata:
        event["metadata"] = redact_trace_payload(metadata)

    write_trace_event(log_file, event)


def redact_trace_payload(value: Any) -> Any:
    """Return a trace-safe copy with transient read handles removed."""
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).strip().lower() == "read_handle":
                continue
            redacted[str(key)] = redact_trace_payload(item)
        return redacted
    if isinstance(value, list):
        return [redact_trace_payload(item) for item in value]
    if isinstance(value, tuple):
        return [redact_trace_payload(item) for item in value]
    if isinstance(value, str):
        return redact_trace_text(value)
    return value


def redact_trace_text(text: str) -> str:
    """Redact read-handle values embedded in text traces."""
    redacted = _READ_HANDLE_VALUE_RE.sub(r'\1"[redacted]"', text or "")
    return _BARE_READ_HANDLE_RE.sub("[redacted-read-handle]", redacted)
