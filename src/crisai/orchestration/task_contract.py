"""Main-ask contract inferred before workflow execution."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from crisai import config
from crisai.orchestration import retrieval_association_graph as graph_module


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

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TaskContract:
        """Build a task contract from a serialized run-state payload."""
        return cls(
            schema_version=_as_str(payload.get("schema_version"), default="task_contract_v1"),
            primary_intent=_as_str(payload.get("primary_intent"), default="respond"),
            deliverable_type=_as_str(payload.get("deliverable_type"), default="general_answer"),
            source_resolution=_as_str(payload.get("source_resolution"), default="as_needed"),
            required_evidence_level=_as_str(payload.get("required_evidence_level"), default="as_needed"),
            success_criteria=_as_tuple(payload.get("success_criteria")),
            anti_goals=_as_tuple(payload.get("anti_goals")),
        )

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


def infer_task_contract(message: str, *, registry_dir: Path | None = None) -> TaskContract:
    """Infer the main user ask from graph-emitted semantic facts."""
    emits = _task_emits_from_graph(message, registry_dir=registry_dir)
    primary_intent = _as_str(emits.get("primary_intent"))
    if primary_intent:
        return TaskContract(
            schema_version="task_contract_v1",
            primary_intent=primary_intent,
            deliverable_type=_as_str(emits.get("deliverable_type"), default="general_answer"),
            source_resolution=_as_str(emits.get("source_resolution"), default="as_needed"),
            required_evidence_level=_as_str(emits.get("required_evidence_level"), default="as_needed"),
            success_criteria=_as_tuple(emits.get("success_criteria")),
            anti_goals=_as_tuple(emits.get("anti_goals")),
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


def _task_emits_from_graph(message: str, *, registry_dir: Path | None = None) -> dict[str, object]:
    root = _resolve_registry_dir(registry_dir)
    graph = graph_module.load_retrieval_association_graph(root)
    activated, _terms = graph_module.expand_retrieval_hints(message, graph)
    return graph_module.collect_graph_emits(graph, activated)


def _resolve_registry_dir(registry_dir: Path | None) -> Path:
    if registry_dir is not None:
        return registry_dir
    try:
        return Path(config.load_settings().registry_dir)
    except Exception:  # noqa: BLE001 - fail open when settings are unavailable in tests.
        return Path("registry")


def _as_str(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _as_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    text = str(value or "").strip()
    return (text,) if text else ()
