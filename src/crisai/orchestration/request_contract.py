"""Execution request contract inferred before routing."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .retrieval_association_graph import (
    DeterministicRetrievalContext,
    deterministic_context_from_registry,
)
from .semantic_catalog import SemanticCatalog, load_semantic_catalog
from .session_anchors import AnchorReference, AnchorRegistry, resolve_anchor_references
from .task_contract import TaskContract, infer_task_contract

_WORKSPACE_PATH_RE = re.compile(r"`?(workspace/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)`?")
_SOURCE_NAME_RE = re.compile(
    r"`([^`]+\.(?:aspx|html|htm|pdf|docx?|pptx?|xlsx?|md|txt))`"
    r"|([^\s`'\",;:]+\.(?:aspx|html|htm|pdf|docx?|pptx?|xlsx?|md|txt))",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class RequestContract:
    """Normalized execution contract used by router and workflow gates."""

    schema_version: str
    workflow_preference: str
    task_contract: TaskContract
    source_required: bool
    source_families: tuple[str, ...] = field(default_factory=tuple)
    named_sources: tuple[str, ...] = field(default_factory=tuple)
    required_evidence_level: str = "as_needed"
    output_path: str | None = None
    output_target_subdir: str | None = None
    actions: tuple[str, ...] = field(default_factory=tuple)
    quality_gates: tuple[str, ...] = field(default_factory=tuple)
    route_hints: tuple[str, ...] = field(default_factory=tuple)
    referenced_anchors: tuple[AnchorReference, ...] = field(default_factory=tuple)

    @property
    def primary_intent(self) -> str:
        """Return the task-contract primary intent."""
        return self.task_contract.primary_intent

    @property
    def deliverable_type(self) -> str:
        """Return the task-contract deliverable type."""
        return self.task_contract.deliverable_type

    @property
    def is_summary(self) -> bool:
        """Return whether the requested deliverable is a summary."""
        return self.task_contract.is_summary

    def has_hint(self, hint: str) -> bool:
        """Return whether a route hint is active."""
        return hint in self.route_hints

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "schema_version": self.schema_version,
            "workflow_preference": self.workflow_preference,
            "task_contract": self.task_contract.to_dict(),
            "source_required": self.source_required,
            "source_families": list(self.source_families),
            "named_sources": list(self.named_sources),
            "required_evidence_level": self.required_evidence_level,
            "output_path": self.output_path,
            "output_target_subdir": self.output_target_subdir,
            "actions": list(self.actions),
            "quality_gates": list(self.quality_gates),
            "route_hints": list(self.route_hints),
            "referenced_anchors": [ref.to_dict() for ref in self.referenced_anchors],
        }

    def to_json(self) -> str:
        """Render deterministic JSON for traces and prompts."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def infer_request_contract(
    message: str,
    *,
    current_mode: str | None = None,
    registry_dir: Path | None = None,
    catalog: SemanticCatalog | None = None,
    deterministic_context: DeterministicRetrievalContext | None = None,
    anchor_registry: AnchorRegistry | None = None,
) -> RequestContract:
    """Infer an execution contract by combining task, source, output, and mode facts."""
    catalog = catalog or _load_catalog(registry_dir)
    task_contract = infer_task_contract(message, registry_dir=registry_dir)
    text = _normalise(message)
    deterministic_context = deterministic_context or _deterministic_context(message, registry_dir)

    source_families = _source_families(text, catalog, deterministic_context)
    named_sources = _named_sources(message)
    output_path = _workspace_output_path(message)
    output_target_subdir = _parent_subdir(output_path)
    publication_requested = _score_terms(text, catalog.router.publication_terms) >= 1 or output_path is not None
    source_resolution_required = (
        task_contract.source_resolution not in {"", "none", "as_needed"}
        and not publication_requested
    )
    explicit_source_families = tuple(family for family in source_families if family != "workspace")
    source_required = bool(
        explicit_source_families
        or named_sources
        or source_resolution_required
        or _requires_retrieval_by_pattern(message, catalog)
    )
    workflow_preference = current_mode or _explicit_workflow_preference(message, catalog) or "auto"

    route_hints = _route_hints(
        text,
        catalog,
        task_contract=task_contract,
        source_required=source_required,
        output_path=output_path,
    )
    actions = _actions(
        source_required=source_required,
        output_path=output_path,
        route_hints=route_hints,
        task_contract=task_contract,
    )
    quality_gates = _quality_gates(
        source_required=source_required,
        output_path=output_path,
        evidence_level=task_contract.required_evidence_level,
        source_families=source_families,
    )
    referenced_anchors = (
        resolve_anchor_references(message, anchor_registry, registry_dir=registry_dir)
        if anchor_registry is not None
        else ()
    )
    return RequestContract(
        schema_version="request_contract_v1",
        workflow_preference=workflow_preference,
        task_contract=task_contract,
        source_required=source_required,
        source_families=source_families,
        named_sources=named_sources,
        required_evidence_level=task_contract.required_evidence_level,
        output_path=output_path,
        output_target_subdir=output_target_subdir,
        actions=actions,
        quality_gates=quality_gates,
        route_hints=route_hints,
        referenced_anchors=referenced_anchors,
    )


def render_request_contract_block(contract: RequestContract) -> str:
    """Render the request contract as a fenced machine block for traces."""
    return "```json\n" + contract.to_json() + "\n```"


def _load_catalog(registry_dir: Path | None) -> SemanticCatalog:
    if registry_dir is None:
        return load_semantic_catalog()
    return load_semantic_catalog(str(registry_dir))


def _deterministic_context(message: str, registry_dir: Path | None) -> DeterministicRetrievalContext | None:
    if registry_dir is None:
        return None
    context, graph_loaded = deterministic_context_from_registry(message, registry_dir)
    return context if graph_loaded else None


def _normalise(text: str) -> str:
    return " ".join((text or "").lower().strip().split())


def _contains_any(text: str, phrases: frozenset[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _score_terms(text: str, terms: frozenset[str]) -> int:
    return sum(1 for term in terms if term in text)


def _explicit_workflow_preference(message: str, catalog: SemanticCatalog) -> str | None:
    normalized = _normalise(message)
    interaction = getattr(catalog, "interaction", None)
    explicit_modes = getattr(interaction, "explicit_mode_patterns", {}) if interaction is not None else {}
    for mode, patterns in explicit_modes.items():
        if any(pattern.search(normalized) for pattern in patterns):
            return mode
    return None


def _requires_retrieval_by_pattern(message: str, catalog: SemanticCatalog) -> bool:
    normalized = _normalise(message)
    interaction = getattr(catalog, "interaction", None)
    patterns = getattr(interaction, "retrieval_required_patterns", ()) if interaction is not None else ()
    return any(pattern.search(normalized) for pattern in patterns)


def _source_families(
    text: str,
    catalog: SemanticCatalog,
    deterministic_context: DeterministicRetrievalContext | None,
) -> tuple[str, ...]:
    families: set[str] = set()
    if deterministic_context is not None and deterministic_context.is_active:
        families.update(
            source
            for source in deterministic_context.suggested_sources
            if source != "generic_retrieval"
        )
    retrieval_constraints = getattr(catalog, "retrieval_constraints", None)
    source_scope_markers = (
        getattr(retrieval_constraints, "source_scope_markers", {})
        if retrieval_constraints is not None
        else {}
    )
    for scope, markers in source_scope_markers.items():
        if _contains_any(text, markers):
            families.add(scope)
    return tuple(sorted(families))


def _named_sources(message: str) -> tuple[str, ...]:
    found: list[str] = []
    for match in _SOURCE_NAME_RE.finditer(message or ""):
        value = (match.group(1) or match.group(2) or "").strip(" `.,")
        if (
            value
            and value not in found
            and not value.startswith(".")
            and not value.startswith("workspace/")
        ):
            found.append(value)
    return tuple(found)


def _workspace_output_path(message: str) -> str | None:
    match = _WORKSPACE_PATH_RE.search(message or "")
    if not match:
        return None
    return match.group(1).strip("`")


def _parent_subdir(path: str | None) -> str | None:
    if not path:
        return None
    parent = Path(path).parent.as_posix()
    return parent if parent != "." else None


def _route_hints(
    text: str,
    catalog: SemanticCatalog,
    *,
    task_contract: TaskContract,
    source_required: bool,
    output_path: str | None,
) -> tuple[str, ...]:
    terms = catalog.router
    discovery_score = _score_terms(text, terms.discovery_terms)
    source_marker_signal = _contains_any(text, terms.source_markers)
    design_score = _score_terms(text, terms.design_terms)
    review_score = _score_terms(text, terms.review_terms)
    operations_score = _score_terms(text, terms.operations_terms)
    peer_score = _score_terms(text, terms.peer_terms)
    publication_score = _score_terms(text, terms.publication_terms)
    criticality_score = _score_terms(text, terms.criticality_terms)
    if _contains_any(text, terms.architecture_location_markers) and design_score > 0:
        design_score -= 1

    hints: list[str] = []
    if operations_score >= 2:
        hints.append("operations")
    if _contains_any(text, terms.explicit_discovery_patterns):
        hints.append("retrieval_only")
    if publication_score >= 1 or output_path:
        hints.append("publication")
    if _is_native_document_export(text, catalog):
        hints.append("native_document_export")
    if source_required or source_marker_signal:
        hints.append("source_required")
    if discovery_score >= 2 or source_marker_signal:
        hints.append("source_lookup")
    if design_score >= 2 or task_contract.primary_intent in {"design", "recommend"}:
        hints.append("design")
    if review_score >= 2 or task_contract.primary_intent == "assess":
        hints.append("review")
    if task_contract.is_summary:
        hints.append("summary")
    if (
        _contains_any(text, terms.explicit_peer_patterns)
        or peer_score >= 2 and (design_score >= 1 or review_score >= 1)
    ):
        hints.append("peer")
    if criticality_score >= 1:
        hints.append("criticality")
    category_count = sum(
        (
            discovery_score >= 1,
            design_score >= 2 or task_contract.primary_intent in {"design", "recommend"},
            review_score >= 2 or task_contract.primary_intent == "assess",
            peer_score >= 1,
        )
    )
    if category_count >= 2 and discovery_score + design_score + review_score + peer_score >= 3:
        hints.append("mixed_complexity")
    return tuple(dict.fromkeys(hints))


def _is_native_document_export(text: str, catalog: SemanticCatalog) -> bool:
    markers = getattr(catalog, "peer_contract", None)
    if markers is None:
        return False
    return (
        _contains_any(text, markers.document_export_native_markers)
        and _contains_any(text, markers.document_export_source_markers)
    )


def _actions(
    *,
    source_required: bool,
    output_path: str | None,
    route_hints: tuple[str, ...],
    task_contract: TaskContract,
) -> tuple[str, ...]:
    actions: list[str] = []
    if source_required:
        actions.append("retrieve_source")
    if task_contract.is_summary:
        actions.append("summarize")
    elif task_contract.primary_intent in {"design", "recommend"}:
        actions.append("draft")
    elif task_contract.primary_intent == "assess":
        actions.append("assess")
    if "publication" in route_hints:
        actions.append("publish_artifact")
    if output_path:
        actions.append("write_workspace_file")
    return tuple(dict.fromkeys(actions))


def _quality_gates(
    *,
    source_required: bool,
    output_path: str | None,
    evidence_level: str,
    source_families: tuple[str, ...],
) -> tuple[str, ...]:
    gates: list[str] = []
    if source_required:
        gates.append("source_evidence")
    if evidence_level == "content_read":
        gates.append("content_read_evidence")
    if "intranet" in source_families:
        gates.append("intranet_fetch")
    if output_path:
        gates.append("workspace_file_changed")
    return tuple(dict.fromkeys(gates))
