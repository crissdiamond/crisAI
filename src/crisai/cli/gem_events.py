from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

GemStageState = Literal["pending", "running", "complete", "skipped", "failed"]
GemEventKind = Literal[
    "status",
    "routing",
    "stage_started",
    "stage_output",
    "stage_completed",
    "stage_skipped",
    "stage_failed",
    "checkpoint",
    "final",
    "error",
]


@dataclass(frozen=True, slots=True)
class GemEvent:
    """User-interface event consumed by the future Gem terminal app."""

    kind: GemEventKind
    title: str
    body: str = ""
    stage: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class GemStage:
    """One pipeline or peer stage shown in the Gem stage rail."""

    name: str
    state: GemStageState = "pending"
    summary: str = ""


@dataclass(slots=True)
class GemUiState:
    """Minimal reducer state for Gem's transcript and stage rail."""

    transcript: list[GemEvent] = field(default_factory=list)
    stages: dict[str, GemStage] = field(default_factory=dict)
    current_stage: str | None = None


def apply_gem_event(state: GemUiState, event: GemEvent) -> GemUiState:
    """Apply one event to Gem UI state.

    The reducer is intentionally independent of Textual so workflow display
    behaviour can be tested without a terminal application.
    """
    if event.stage:
        stage = state.stages.setdefault(event.stage, GemStage(name=event.stage))
        if event.kind == "stage_started":
            stage.state = "running"
            state.current_stage = event.stage
        elif event.kind == "stage_completed":
            stage.state = "complete"
            stage.summary = event.body
            if state.current_stage == event.stage:
                state.current_stage = None
        elif event.kind == "stage_skipped":
            stage.state = "skipped"
            stage.summary = event.body
            if state.current_stage == event.stage:
                state.current_stage = None
        elif event.kind == "stage_failed":
            stage.state = "failed"
            stage.summary = event.body
            if state.current_stage == event.stage:
                state.current_stage = None

    if event.kind in {"status", "routing", "stage_output", "checkpoint", "final", "error"}:
        state.transcript.append(event)

    return state
