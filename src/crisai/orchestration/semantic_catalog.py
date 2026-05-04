"""Semantic catalogue: one YAML pool for router, peer verifier, and peer contract.

All term lists and verifier regex strings live in ``registry/semantic_catalog.yaml``.
This module only loads, validates shape, and exposes typed views (`SemanticCatalog`).
"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class PeerContractMarkers:
    """Substring markers for infer_peer_run_contract (lowercased; spacing preserved)."""

    file_write_markers: frozenset[str]
    code_change_markers: frozenset[str]
    code_target_markers: frozenset[str]
    grounding_markers: frozenset[str]
    assessment_markers: frozenset[str]


@dataclass(frozen=True)
class SemanticCatalog:
    router: RouterTerms
    peer_verifier: PeerVerifierPatterns
    peer_contract: PeerContractMarkers


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
    block = data.get("peer_contract") if isinstance(data.get("peer_contract"), dict) else {}
    raw = block.get(field)
    return _peer_marker_phrases(raw) if isinstance(raw, list) else frozenset()


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
    for key in ("router", "peer_verifier", "peer_contract"):
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


def _build_catalog(data: dict[str, Any]) -> SemanticCatalog:
    _validate_top_level(data)
    _validate_peer_contract_lists(data["peer_contract"])
    router_block = data["router"]
    verifier_block = data["peer_verifier"]
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
        ),
        peer_contract=PeerContractMarkers(
            file_write_markers=_peer_contract_marker_field(data, "file_write_markers"),
            code_change_markers=_peer_contract_marker_field(data, "code_change_markers"),
            code_target_markers=_peer_contract_marker_field(data, "code_target_markers"),
            grounding_markers=_peer_contract_marker_field(data, "grounding_markers"),
            assessment_markers=_peer_contract_marker_field(data, "assessment_markers"),
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
