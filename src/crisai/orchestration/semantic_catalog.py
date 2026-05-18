"""Legacy semantic catalogue for router, peer verifier, and peer contract.

New task-intent and retrieval-expansion semantics live in
``registry/semantic_graph.yaml``. This module keeps the older catalogue shape
for router and peer subsystems that have not moved to graph-emitted facts yet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from crisai.config import load_settings


@dataclass(frozen=True)
class RouterTerms:
    discovery_terms: frozenset[str]
    design_terms: frozenset[str]
    review_terms: frozenset[str]
    operations_terms: frozenset[str]
    peer_terms: frozenset[str]
    publication_terms: frozenset[str]
    explicit_discovery_patterns: frozenset[str]
    explicit_peer_patterns: frozenset[str]
    criticality_terms: frozenset[str]
    source_markers: frozenset[str]
    architecture_location_markers: frozenset[str]


@dataclass(frozen=True)
class PeerVerifierPatterns:
    pattern_gap_line: str
    leaf_file_pattern: str
    leaf_file_terms: frozenset[str]
    data_architecture_terms: frozenset[str]
    intranet_evidence_positive_marker: str
    intranet_evidence_negative_markers: frozenset[str]
    agent_output_signatures: dict[str, re.Pattern[str]]
    boilerplate_strip_patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class PeerContractMarkers:
    """Substring markers for infer_peer_run_contract (lowercased; spacing preserved)."""

    file_write_markers: frozenset[str]
    code_change_markers: frozenset[str]
    code_target_markers: frozenset[str]
    grounding_markers: frozenset[str]
    assessment_markers: frozenset[str]
    document_export_native_markers: frozenset[str]
    document_export_source_markers: frozenset[str]


@dataclass(frozen=True)
class PeerJudgeDecisionMarkers:
    """Substring markers for parsing peer judge decisions."""

    accept_markers: frozenset[str]
    revise_markers: frozenset[str]
    rework_markers: frozenset[str]


@dataclass(frozen=True)
class RetrievalConstraintTerms:
    """Terms used to infer generic source-fit constraints from user requests."""

    object_type_terms: frozenset[str]
    source_scope_markers: dict[str, frozenset[str]]


@dataclass(frozen=True)
class LexiconTerms:
    """Language-level prompt terms shared by semantic features."""

    function_words: dict[str, frozenset[str]]
    prompt_noise_terms: frozenset[str]
    title_relation_terms: frozenset[str]
    continuation_intent_template: dict[str, str] = dataclass_field(default_factory=dict)

    @property
    def all_function_words(self) -> frozenset[str]:
        """Return all configured standalone function words."""
        terms: set[str] = set()
        for values in self.function_words.values():
            terms.update(values)
        return frozenset(terms)


@dataclass(frozen=True)
class InteractionPatterns:
    """Regex patterns for explicit mode detection and peer retrieval overrides."""

    explicit_mode_patterns: dict[str, tuple[re.Pattern[str], ...]]
    continuation_patterns: tuple[re.Pattern[str], ...]
    generative_peer_patterns: tuple[re.Pattern[str], ...]
    retrieval_required_patterns: tuple[re.Pattern[str], ...]
    peer_retrieval_force_patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class ArtifactLifecycleTerms:
    """Terms and mappings used by generated artefact lifecycle helpers."""

    persisted_deliverable_filenames: dict[str, str] = dataclass_field(default_factory=dict)


@dataclass(frozen=True)
class SessionAnchorTerms:
    """Vocabulary used to extract and resolve user-visible session anchors."""

    kinds: dict[str, frozenset[str]] = dataclass_field(default_factory=dict)
    order_columns: frozenset[str] = dataclass_field(default_factory=frozenset)
    title_columns: frozenset[str] = dataclass_field(default_factory=frozenset)
    summary_columns: frozenset[str] = dataclass_field(default_factory=frozenset)
    status_columns: frozenset[str] = dataclass_field(default_factory=frozenset)
    preferred_markers: frozenset[str] = dataclass_field(default_factory=frozenset)


@dataclass(frozen=True)
class SessionMemoryTerms:
    """Vocabulary used by deterministic session-memory extraction."""

    decision_markers: frozenset[str] = dataclass_field(default_factory=frozenset)
    rejected_option_markers: frozenset[str] = dataclass_field(default_factory=frozenset)
    assumption_markers: frozenset[str] = dataclass_field(default_factory=frozenset)
    constraint_markers: frozenset[str] = dataclass_field(default_factory=frozenset)
    source_finding_markers: frozenset[str] = dataclass_field(default_factory=frozenset)
    next_action_markers: frozenset[str] = dataclass_field(default_factory=frozenset)
    open_question_starters: frozenset[str] = dataclass_field(default_factory=frozenset)


@dataclass(frozen=True)
class SemanticCatalog:
    router: RouterTerms
    peer_verifier: PeerVerifierPatterns
    peer_contract: PeerContractMarkers
    peer_judge: PeerJudgeDecisionMarkers
    lexicon: LexiconTerms
    retrieval_constraints: RetrievalConstraintTerms
    interaction: InteractionPatterns
    artifact_lifecycle: ArtifactLifecycleTerms = dataclass_field(default_factory=ArtifactLifecycleTerms)
    session_anchors: SessionAnchorTerms = dataclass_field(default_factory=SessionAnchorTerms)
    session_memory: SessionMemoryTerms = dataclass_field(default_factory=SessionMemoryTerms)


class SemanticCatalogError(ValueError):
    """Raised when the semantic catalogue file is missing or invalid."""


def _as_frozenset(values: Any) -> frozenset[str]:
    if not isinstance(values, list):
        return frozenset()
    clean = [str(v).strip().lower() for v in values if str(v).strip()]
    return frozenset(clean)


def _peer_marker_phrases(values: Any) -> frozenset[str]:
    """Lowercase peer-contract marker phrases; preserve trailing spaces (e.g. ``function ``)."""
    if not isinstance(values, list):
        return frozenset()
    phrases: list[str] = []
    for item in values:
        text = str(item).lower()
        if not text.strip():
            continue
        phrases.append(text)
    return frozenset(phrases)


def _peer_contract_marker_field(data: dict[str, Any], field: str) -> frozenset[str]:
    """Resolve one peer_contract marker list from catalog data."""
    raw_block = data.get("peer_contract")
    block: dict[str, Any] = raw_block if isinstance(raw_block, dict) else {}
    raw = block.get(field)
    return _peer_marker_phrases(raw) if isinstance(raw, list) else frozenset()


def _source_scope_markers(values: Any) -> dict[str, frozenset[str]]:
    if not isinstance(values, dict):
        return {}
    result: dict[str, frozenset[str]] = {}
    for scope, markers in values.items():
        clean_scope = str(scope).strip().lower()
        if not clean_scope:
            continue
        marker_set = _as_frozenset(markers)
        if marker_set:
            result[clean_scope] = marker_set
    return result


def _string_mapping(values: Any) -> dict[str, str]:
    """Return a clean string-to-string mapping from optional YAML data."""
    if not isinstance(values, dict):
        return {}
    result: dict[str, str] = {}
    for key, value in values.items():
        clean_key = str(key or "").strip()
        clean_value = str(value or "").strip()
        if clean_key and clean_value:
            result[clean_key] = clean_value
    return result


def _function_words(values: Any) -> dict[str, frozenset[str]]:
    if not isinstance(values, dict):
        return {}
    result: dict[str, frozenset[str]] = {}
    for category, terms in values.items():
        clean_category = str(category).strip().lower()
        if not clean_category:
            continue
        term_set = _as_frozenset(terms)
        if term_set:
            result[clean_category] = term_set
    return result


def _anchor_kinds(values: Any) -> dict[str, frozenset[str]]:
    if not isinstance(values, dict):
        return {}
    result: dict[str, frozenset[str]] = {}
    for kind, terms in values.items():
        clean_kind = str(kind).strip().lower()
        term_set = _as_frozenset(terms)
        if clean_kind and term_set:
            result[clean_kind] = term_set
    return result


def merge_semantic_catalog_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge two catalogue dicts (fork overlays, tests).

    Dict values merge recursively; non-dict values (including lists) replace
    the corresponding key in the result.
    """
    merged: dict[str, Any] = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = merge_semantic_catalog_dicts(base[key], value)
        else:
            merged[key] = value
    return merged


def _validate_top_level(data: dict[str, Any]) -> None:
    for key in (
        "router",
        "peer_verifier",
        "peer_contract",
        "peer_judge",
        "lexicon",
        "retrieval_constraints",
    ):
        if key not in data or not isinstance(data[key], dict):
            raise SemanticCatalogError(
                f"registry/semantic_catalog.yaml must contain a top-level '{key}' mapping."
            )


def _validate_peer_contract_lists(peer_block: dict[str, Any]) -> None:
    required = (
        "file_write_markers",
        "code_change_markers",
        "code_target_markers",
        "grounding_markers",
        "assessment_markers",
    )
    for field in required:
        values = peer_block.get(field)
        if not isinstance(values, list) or not values:
            raise SemanticCatalogError(
                f"registry/semantic_catalog.yaml: peer_contract.{field} must be a non-empty list."
            )


def _validate_peer_judge_lists(peer_block: dict[str, Any]) -> None:
    required = ("accept_markers", "revise_markers", "rework_markers")
    for field in required:
        values = peer_block.get(field)
        if not isinstance(values, list) or not values:
            raise SemanticCatalogError(
                f"registry/semantic_catalog.yaml: peer_judge.{field} must be a non-empty list."
            )


def _build_catalog(data: dict[str, Any]) -> SemanticCatalog:
    _validate_top_level(data)
    _validate_peer_contract_lists(data["peer_contract"])
    _validate_peer_judge_lists(data["peer_judge"])
    router_block = data["router"]
    verifier_block = data["peer_verifier"]
    peer_judge_block = data["peer_judge"]
    lexicon_block = data["lexicon"]
    retrieval_block = data["retrieval_constraints"]
    lifecycle_block = data.get("artifact_lifecycle")
    lifecycle_block = lifecycle_block if isinstance(lifecycle_block, dict) else {}
    anchor_block = data.get("session_anchors")
    anchor_block = anchor_block if isinstance(anchor_block, dict) else {}
    session_memory_block = data.get("session_memory")
    session_memory_block = session_memory_block if isinstance(session_memory_block, dict) else {}
    pattern_gap_line = str(verifier_block.get("pattern_gap_line") or "").strip()
    leaf_file_pattern = str(verifier_block.get("leaf_file_pattern") or "").strip()
    if not pattern_gap_line or not leaf_file_pattern:
        raise SemanticCatalogError(
            "registry/semantic_catalog.yaml: peer_verifier.pattern_gap_line and "
            "peer_verifier.leaf_file_pattern must be non-empty strings."
        )
    leaf_terms = verifier_block.get("leaf_file_terms")
    data_terms = verifier_block.get("data_architecture_terms")
    if not isinstance(leaf_terms, list) or not leaf_terms:
        raise SemanticCatalogError(
            "registry/semantic_catalog.yaml: peer_verifier.leaf_file_terms must be a non-empty list."
        )
    if not isinstance(data_terms, list) or not data_terms:
        raise SemanticCatalogError(
            "registry/semantic_catalog.yaml: peer_verifier.data_architecture_terms must be "
            "a non-empty list."
        )
    intranet_positive = str(verifier_block.get("intranet_evidence_positive_marker") or "").strip()
    if not intranet_positive:
        raise SemanticCatalogError(
            "registry/semantic_catalog.yaml: peer_verifier.intranet_evidence_positive_marker "
            "must be a non-empty string."
        )
    intranet_negatives_raw = verifier_block.get("intranet_evidence_negative_markers")
    intranet_negatives = _as_frozenset(intranet_negatives_raw)
    raw_signatures = verifier_block.get("agent_output_signatures")
    agent_signatures: dict[str, re.Pattern[str]] = {}
    if isinstance(raw_signatures, dict):
        for agent_id, pattern_str in raw_signatures.items():
            if isinstance(pattern_str, str) and pattern_str.strip():
                agent_signatures[str(agent_id)] = re.compile(pattern_str, re.IGNORECASE)
    raw_boilerplate = verifier_block.get("boilerplate_strip_patterns")
    boilerplate_patterns: tuple[re.Pattern[str], ...]
    if isinstance(raw_boilerplate, list):
        boilerplate_patterns = tuple(
            re.compile(str(p), re.IGNORECASE)
            for p in raw_boilerplate
            if isinstance(p, str) and p.strip()
        )
    else:
        boilerplate_patterns = ()
    function_words = _function_words(lexicon_block.get("function_words"))
    if not function_words:
        raise SemanticCatalogError(
            "registry/semantic_catalog.yaml: lexicon.function_words must contain "
            "at least one non-empty category."
        )
    for field in ("prompt_noise_terms", "title_relation_terms"):
        values = lexicon_block.get(field)
        if not isinstance(values, list) or not values:
            raise SemanticCatalogError(
                f"registry/semantic_catalog.yaml: lexicon.{field} must be a non-empty list."
            )

    for field in ("object_type_terms",):
        values = retrieval_block.get(field)
        if not isinstance(values, list) or not values:
            raise SemanticCatalogError(
                f"registry/semantic_catalog.yaml: retrieval_constraints.{field} "
                "must be a non-empty list."
            )
    scope_markers = _source_scope_markers(retrieval_block.get("source_scope_markers"))
    if not scope_markers:
        raise SemanticCatalogError(
            "registry/semantic_catalog.yaml: retrieval_constraints.source_scope_markers "
            "must contain at least one non-empty scope."
        )

    _compile = re.IGNORECASE | re.DOTALL
    interaction_block = data.get("interaction")
    interaction_block = interaction_block if isinstance(interaction_block, dict) else {}
    raw_explicit_modes = interaction_block.get("explicit_mode_patterns")
    explicit_mode_patterns: dict[str, tuple[re.Pattern[str], ...]] = {}
    if isinstance(raw_explicit_modes, dict):
        for mode, pats in raw_explicit_modes.items():
            if isinstance(pats, list):
                explicit_mode_patterns[str(mode)] = tuple(
                    re.compile(str(p), _compile) for p in pats if isinstance(p, str) and p.strip()
                )

    def _compile_list(key: str) -> tuple[re.Pattern[str], ...]:
        raw = interaction_block.get(key)
        if not isinstance(raw, list):
            return ()
        return tuple(re.compile(str(p), _compile) for p in raw if isinstance(p, str) and p.strip())

    return SemanticCatalog(
        router=RouterTerms(
            discovery_terms=_as_frozenset(router_block.get("discovery_terms")),
            design_terms=_as_frozenset(router_block.get("design_terms")),
            review_terms=_as_frozenset(router_block.get("review_terms")),
            operations_terms=_as_frozenset(router_block.get("operations_terms")),
            peer_terms=_as_frozenset(router_block.get("peer_terms")),
            publication_terms=_as_frozenset(router_block.get("publication_terms")),
            explicit_discovery_patterns=_as_frozenset(router_block.get("explicit_discovery_patterns")),
            explicit_peer_patterns=_as_frozenset(router_block.get("explicit_peer_patterns")),
            criticality_terms=_as_frozenset(router_block.get("criticality_terms")),
            source_markers=_as_frozenset(router_block.get("source_markers")),
            architecture_location_markers=_as_frozenset(router_block.get("architecture_location_markers")),
        ),
        peer_verifier=PeerVerifierPatterns(
            pattern_gap_line=pattern_gap_line,
            leaf_file_pattern=leaf_file_pattern,
            leaf_file_terms=_as_frozenset(leaf_terms),
            data_architecture_terms=_as_frozenset(data_terms),
            intranet_evidence_positive_marker=intranet_positive,
            intranet_evidence_negative_markers=intranet_negatives,
            agent_output_signatures=agent_signatures,
            boilerplate_strip_patterns=boilerplate_patterns,
        ),
        peer_contract=PeerContractMarkers(
            file_write_markers=_peer_contract_marker_field(data, "file_write_markers"),
            code_change_markers=_peer_contract_marker_field(data, "code_change_markers"),
            code_target_markers=_peer_contract_marker_field(data, "code_target_markers"),
            grounding_markers=_peer_contract_marker_field(data, "grounding_markers"),
            assessment_markers=_peer_contract_marker_field(data, "assessment_markers"),
            document_export_native_markers=_peer_contract_marker_field(data, "document_export_native_markers"),
            document_export_source_markers=_peer_contract_marker_field(data, "document_export_source_markers"),
        ),
        peer_judge=PeerJudgeDecisionMarkers(
            accept_markers=_as_frozenset(peer_judge_block.get("accept_markers")),
            revise_markers=_as_frozenset(peer_judge_block.get("revise_markers")),
            rework_markers=_as_frozenset(peer_judge_block.get("rework_markers")),
        ),
        lexicon=LexiconTerms(
            function_words=function_words,
            prompt_noise_terms=_as_frozenset(lexicon_block.get("prompt_noise_terms")),
            title_relation_terms=_as_frozenset(lexicon_block.get("title_relation_terms")),
            continuation_intent_template=_string_mapping(lexicon_block.get("continuation_intent_template")),
        ),
        retrieval_constraints=RetrievalConstraintTerms(
            object_type_terms=_as_frozenset(retrieval_block.get("object_type_terms")),
            source_scope_markers=scope_markers,
        ),
        interaction=InteractionPatterns(
            explicit_mode_patterns=explicit_mode_patterns,
            continuation_patterns=_compile_list("continuation_patterns"),
            generative_peer_patterns=_compile_list("generative_peer_patterns"),
            retrieval_required_patterns=_compile_list("retrieval_required_patterns"),
            peer_retrieval_force_patterns=_compile_list("peer_retrieval_force_patterns"),
        ),
        artifact_lifecycle=ArtifactLifecycleTerms(
            persisted_deliverable_filenames=_string_mapping(
                lifecycle_block.get("persisted_deliverable_filenames")
            ),
        ),
        session_anchors=SessionAnchorTerms(
            kinds=_anchor_kinds(anchor_block.get("kinds")),
            order_columns=_as_frozenset(anchor_block.get("order_columns")),
            title_columns=_as_frozenset(anchor_block.get("title_columns")),
            summary_columns=_as_frozenset(anchor_block.get("summary_columns")),
            status_columns=_as_frozenset(anchor_block.get("status_columns")),
            preferred_markers=_as_frozenset(anchor_block.get("preferred_markers")),
        ),
        session_memory=SessionMemoryTerms(
            decision_markers=_as_frozenset(session_memory_block.get("decision_markers")),
            rejected_option_markers=_as_frozenset(session_memory_block.get("rejected_option_markers")),
            assumption_markers=_as_frozenset(session_memory_block.get("assumption_markers")),
            constraint_markers=_as_frozenset(session_memory_block.get("constraint_markers")),
            source_finding_markers=_as_frozenset(session_memory_block.get("source_finding_markers")),
            next_action_markers=_as_frozenset(session_memory_block.get("next_action_markers")),
            open_question_starters=_as_frozenset(session_memory_block.get("open_question_starters")),
        ),
    )


@lru_cache(maxsize=8)
def load_semantic_catalog(registry_dir: str | None = None) -> SemanticCatalog:
    """Load the semantic catalogue from ``<registry_dir>/semantic_catalog.yaml`` only.

    There are no in-code term defaults: edit the YAML to tune router, verifier,
    and peer-contract markers during testing.
    """
    if registry_dir is None:
        base_dir = load_settings().registry_dir
    else:
        base_dir = Path(registry_dir)
    path = base_dir / "semantic_catalog.yaml"
    if not path.is_file():
        raise FileNotFoundError(
            f"Semantic catalogue not found: {path}. "
            "Maintain the full dictionary in registry/semantic_catalog.yaml."
        )
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise SemanticCatalogError(f"Invalid YAML in semantic catalogue: {path}") from exc
    if not isinstance(raw, dict):
        raise SemanticCatalogError(f"Semantic catalogue must be a YAML mapping: {path}")
    return _build_catalog(raw)


def build_semantic_catalog_from_dict(data: dict[str, Any]) -> SemanticCatalog:
    """Build a ``SemanticCatalog`` from an in-memory dict (tests, tooling)."""
    return _build_catalog(data)
