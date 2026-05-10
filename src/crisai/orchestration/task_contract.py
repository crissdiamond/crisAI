"""Main-ask contract inferred before workflow execution."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .semantic_catalog import load_semantic_catalog

SUMMARY_INTENTS = frozenset(
    {
        "summarise",
        "summarize",
        "summary",
        "recap",
        "overview",
        "brief me",
        "extract key points",
        "key points",
        "tell me what this says",
        "what does",
        "what is in",
        "riassumi",
        "sintesi",
        "riassunto",
        "punti principali",
        "cosa dice",
    }
)
SOURCE_RESOLUTION_MARKERS = frozenset(
    {
        "latest",
        "most recent",
        "newest",
        "current",
        "master",
        "best candidate",
        "likely master",
        "ultimo",
        "piu recente",
        "più recente",
        "corrente",
    }
)
DECK_MARKERS = frozenset({"deck", "presentation", "powerpoint", "ppt", "pptx", "slides", "slide"})
DOCUMENT_MARKERS = frozenset({"document", "doc", "docx", "file", "source", "page", "documento"})


@dataclass(frozen=True, slots=True)
class TaskContract:
    """User deliverable contract shared by workflow stages."""

    schema_version: str
    primary_intent: str
    deliverable_type: str
    source_resolution: str
    required_evidence_level: str
    success_criteria: tuple[str, ...] = field(default_factory=tuple)
    anti_goals: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_summary(self) -> bool:
        """Return whether the main deliverable is a summary."""
        return self.primary_intent == "summarize_source"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "schema_version": self.schema_version,
            "primary_intent": self.primary_intent,
            "deliverable_type": self.deliverable_type,
            "source_resolution": self.source_resolution,
            "required_evidence_level": self.required_evidence_level,
            "success_criteria": list(self.success_criteria),
            "anti_goals": list(self.anti_goals),
        }

    def to_json(self) -> str:
        """Render deterministic JSON for traces and prompts."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def infer_task_contract(message: str) -> TaskContract:
    """Infer the main user ask from text using deterministic semantic markers."""
    text = " ".join((message or "").lower().split())
    summary_terms = _summary_terms_from_catalog() | SUMMARY_INTENTS
    if any(term in text for term in summary_terms):
        deliverable_type = _infer_summary_deliverable_type(text)
        source_resolution = _infer_source_resolution(text)
        return TaskContract(
            schema_version="task_contract_v1",
            primary_intent="summarize_source",
            deliverable_type=deliverable_type,
            source_resolution=source_resolution,
            required_evidence_level="content_read",
            success_criteria=(
                "Produce the requested summary as the main answer.",
                "Use only content that was actually read or directly supplied.",
                "Keep source-selection rationale secondary when source resolution was required.",
            ),
            anti_goals=(
                "Do not make candidate ranking the main answer.",
                "Do not add unsupported caveats about unread content.",
            ),
        )
    return TaskContract(
        schema_version="task_contract_v1",
        primary_intent="respond",
        deliverable_type="general_answer",
        source_resolution="as_needed",
        required_evidence_level="as_needed",
        success_criteria=("Answer the user's request directly.",),
        anti_goals=("Do not replace the user deliverable with an internal subtask.",),
    )


def render_task_contract_block(contract: TaskContract) -> str:
    """Render the task contract as a fenced machine block for runtime prompts."""
    return "```json\n" + contract.to_json() + "\n```"


def render_task_contract_summary(contract: TaskContract) -> str:
    """Render a human-readable summary for prompts."""
    lines = [
        f"schema_version: {contract.schema_version}",
        f"primary_intent: {contract.primary_intent}",
        f"deliverable_type: {contract.deliverable_type}",
        f"source_resolution: {contract.source_resolution}",
        f"required_evidence_level: {contract.required_evidence_level}",
        "success_criteria:",
        *[f"- {item}" for item in contract.success_criteria],
        "anti_goals:",
        *[f"- {item}" for item in contract.anti_goals],
    ]
    return "\n".join(lines)


def _summary_terms_from_catalog() -> frozenset[str]:
    try:
        catalog = load_semantic_catalog()
    except Exception:  # noqa: BLE001 - fail open when registry is unavailable in tests.
        return frozenset()
    return getattr(catalog.router, "summary_terms", frozenset())


def _infer_summary_deliverable_type(text: str) -> str:
    if any(marker in text for marker in DECK_MARKERS):
        return "deck_summary"
    if any(marker in text for marker in DOCUMENT_MARKERS):
        return "document_summary"
    if "executive" in text or "leadership" in text:
        return "executive_summary"
    if "key point" in text or "punti principali" in text:
        return "key_points"
    return "text_summary"


def _infer_source_resolution(text: str) -> str:
    if any(marker in text for marker in SOURCE_RESOLUTION_MARKERS):
        return "latest_matching_source"
    if any(marker in text for marker in DOCUMENT_MARKERS | DECK_MARKERS):
        return "matching_source"
    return "none"
