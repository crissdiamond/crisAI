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
    source_markers: frozenset[str]
    architecture_location_markers: frozenset[str]


@dataclass(frozen=True)
class PeerVerifierPatterns:
    pattern_gap_line: str
    leaf_file_pattern: str
    leaf_file_terms: frozenset[str]
    data_architecture_terms: frozenset[str]


@dataclass(frozen=True)
class SemanticCatalog:
    router: RouterTerms
    peer_verifier: PeerVerifierPatterns


_DEFAULTS: dict[str, Any] = {
    "router": {
        "discovery_terms": [
            "find", "search", "locate", "identify", "list",
            "documents", "document", "docs", "sources", "files", "inspect", "onedrive",
            "sharepoint", "intranet", "drive", "site", "path", "read",
            "pages", "page",
            "find me", "look up", "look for",
            "trova", "cerca", "individua", "elenca",
            "documenti", "documento", "sorgenti", "fonti", "file", "leggi",
            "pagine", "pagina",
        ],
        "design_terms": [
            "design", "draft", "architecture", "hld", "lld", "proposal",
            "option", "options", "recommendation", "target state",
            "operating model", "blueprint", "solution", "summarise", "summary",
            "propose", "plan",
            "progetta", "architettura", "proposta", "opzioni",
            "raccomandazione", "modello operativo", "soluzione", "sintesi",
            "riassumi", "piano",
        ],
        "review_terms": [
            "review", "critique", "challenge", "refine", "improve",
            "gaps", "assumptions", "weaknesses", "judge",
            "revision", "evaluate", "evaluation",
            "rivedi", "critica", "migliora", "lacune",
            "debolezze", "giudica", "valuta", "valutazione",
        ],
        "operations_terms": [
            "debug", "fix", "error", "issue", "broken", "failing",
            "logs", "auth", "token", "login", "timeout", "exception",
            "not working", "keeps prompting", "prompting",
            "bug", "stack trace", "traceback", "importerror",
            "correggi", "errore", "problema", "rotto",
            "non funziona", "eccezione", "traceback",
        ],
        "peer_terms": [
            "peer mode", "peer conversation", "author", "challenger", "refiner", "judge",
            "debate", "peer review", "use peer mode", "show the peer conversation",
            "challenge and refine", "autore", "sfidante", "giudice", "dibattito",
        ],
        "publication_terms": [
            "template", "templates", "document this", "document the outcome", "turn this into",
            "convert this into", "create a document", "create the document", "create a report",
            "create slides", "create a slide deck", "create a powerpoint", "create a spreadsheet",
            "create an excel", "write this up", "package this", "publish this",
            "prepare the artefact", "prepare a document", ".doc", ".docx", ".ppt", ".pptx",
            ".xls", ".xlsx", ".txt", ".md", "template in workspace", "using the template",
            "usa il template", "usa i template", "trasforma questo in", "crea un documento",
            "crea il documento", "crea delle slide", "crea una presentazione", "crea un powerpoint",
            "crea un foglio excel", "crea un file excel", "documenta questo", "documenta l'esito",
            "impacchetta questo",
        ],
        "explicit_discovery_patterns": [
            "use discovery only", "discovery only", "do not use the design agent",
            "return only a list", "return only the list", "return only a table",
            "return only the table", "do not draft", "do not summarise",
            "usa solo discovery", "solo discovery", "non usare il design agent",
            "restituisci solo una lista", "restituisci solo una tabella", "non fare la sintesi",
        ],
        "explicit_peer_patterns": [
            "use peer mode", "peer mode", "peer review", "peer conversation",
            "show the peer conversation", "debate this", "challenge and refine",
            "author should propose", "challenger should", "refiner should", "judge should",
            "usa peer mode", "mostra la conversazione peer", "autore dovrebbe",
            "sfidante dovrebbe", "giudice dovrebbe",
        ],
        "source_markers": [
            "onedrive", "sharepoint", "intranet", "documents", "document", "docs", "documenti",
            "files", "file", "sources", "fonti", "sorgenti", "site", "drive", "path", "read",
            "pages", "page", "pagine", "pagina",
        ],
        "architecture_location_markers": [
            "architecture site", "architecture sites", "sito architecture", "siti architecture",
            "sharepoint architecture site", "sharepoint architecture sites",
        ],
    },
    "peer_verifier": {
        "pattern_gap_line": r"^\s*-\s*(Consumer|Producer|Ingestion)\s+Pattern\s+(\d+)\s*:",
        "leaf_file_pattern": r"workspace/context_staging/patterns/(consumer|producer|ingestion)-pattern-(\d+)\.md$",
        "leaf_file_terms": [
            "pattern",
            "patterns",
            "template",
            "templates",
            "hld",
            "high level design",
            "high-level-design",
            "lld",
            "low level design",
            "low-level-design",
            "guide",
            "guides",
            "guideline",
            "guidelines",
            "standard",
            "standards",
            "principle",
            "principles",
            "toolkit",
            "playbook",
            "reference architecture",
            "architecture pattern",
            "solution pattern",
        ],
        "data_architecture_terms": [
            "data architecture",
            "data model",
            "data modelling",
            "data modeling",
            "entity",
            "entities",
            "attribute",
            "attributes",
            "domain model",
            "canonical model",
            "enterprise data model",
            "edm",
            "schema",
            "schemas",
            "table",
            "tables",
            "column",
            "columns",
            "field",
            "fields",
            "dataset",
            "datasets",
            "lineage",
            "mapping",
            "mappings",
            "taxonomy",
            "ontology",
            "master data",
            "reference data",
            "data contract",
            "data contracts",
            "normalization",
            "denormalization",
            "metadata",
        ],
    },
}


def _as_frozenset(values: Any) -> frozenset[str]:
    if not isinstance(values, list):
        return frozenset()
    clean = [str(v).strip().lower() for v in values if str(v).strip()]
    return frozenset(clean)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = _deep_merge(base[key], value)
        else:
            merged[key] = value
    return merged


def _build_catalog(data: dict[str, Any]) -> SemanticCatalog:
    router_block = data.get("router") if isinstance(data.get("router"), dict) else {}
    verifier_block = data.get("peer_verifier") if isinstance(data.get("peer_verifier"), dict) else {}
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
            source_markers=_as_frozenset(router_block.get("source_markers")),
            architecture_location_markers=_as_frozenset(router_block.get("architecture_location_markers")),
        ),
        peer_verifier=PeerVerifierPatterns(
            pattern_gap_line=str(verifier_block.get("pattern_gap_line") or _DEFAULTS["peer_verifier"]["pattern_gap_line"]),
            leaf_file_pattern=str(verifier_block.get("leaf_file_pattern") or _DEFAULTS["peer_verifier"]["leaf_file_pattern"]),
            leaf_file_terms=_as_frozenset(
                verifier_block.get("leaf_file_terms")
                or _DEFAULTS["peer_verifier"]["leaf_file_terms"]
            ),
            data_architecture_terms=_as_frozenset(
                verifier_block.get("data_architecture_terms")
                or _DEFAULTS["peer_verifier"]["data_architecture_terms"]
            ),
        ),
    )


@lru_cache(maxsize=8)
def load_semantic_catalog(registry_dir: str | None = None) -> SemanticCatalog:
    """Load semantic catalog from registry/semantic_catalog.yaml with defaults."""
    if registry_dir is None:
        base_dir = load_settings().registry_dir
    else:
        base_dir = Path(registry_dir)
    path = base_dir / "semantic_catalog.yaml"
    merged_data = dict(_DEFAULTS)
    if path.exists():
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                merged_data = _deep_merge(_DEFAULTS, loaded)
        except Exception:
            merged_data = dict(_DEFAULTS)
    return _build_catalog(merged_data)
