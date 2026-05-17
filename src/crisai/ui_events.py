from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

UiEventType = Literal[
    "run_created",
    "routing_decision",
    "task_contract",
    "stage_started",
    "stage_delta",
    "stage_output",
    "stage_completed",
    "stage_skipped",
    "stage_failed",
    "checkpoint_requested",
    "checkpoint_decision",
    "final_answer",
    "run_failed",
    "run_completed",
]


def utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class UiEvent:
    """Canonical UI event shared by web, Gem, and future clients."""

    schema_version: str
    event_type: UiEventType
    run_id: str
    timestamp: str
    session: str
    status: str
    title: str
    summary: str = ""
    content: str = ""
    verbose_content: str = ""
    mode: str | None = None
    agent_id: str | None = None
    stage: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable event payload."""
        return asdict(self)


def make_ui_event(
    event_type: UiEventType,
    *,
    run_id: str,
    session: str,
    status: str,
    title: str,
    summary: str = "",
    content: str = "",
    verbose_content: str = "",
    mode: str | None = None,
    agent_id: str | None = None,
    stage: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> UiEvent:
    """Create a canonical UI event with the current timestamp."""
    return UiEvent(
        schema_version="ui_event_v1",
        event_type=event_type,
        run_id=run_id,
        timestamp=utc_now_iso(),
        session=session,
        status=status,
        title=title,
        summary=summary,
        content=content,
        verbose_content=verbose_content,
        mode=mode,
        agent_id=agent_id,
        stage=stage,
        metadata=metadata or {},
    )
