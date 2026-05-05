"""Deterministic retrieval hint expansion from a YAML association graph.

The graph is intentionally small and registry-driven so behaviour evolves by
editing data, not by ballooning ``prompts/retrieval_planner_agent.md``.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path

import yaml

_DEFAULT_GRAPH_NAME = "retrieval_association_graph.yaml"


@dataclass(frozen=True)
class RetrievalAssociationGraph:
    """Adjacency list over topic vertices, each carrying hint terms."""

    vertex_terms: dict[str, frozenset[str]]
    neighbors: dict[str, frozenset[str]]
    max_hops: int


@dataclass(frozen=True)
class DeterministicRetrievalContext:
    """Structured deterministic retrieval expansion for runtime consumers."""

    schema_version: str
    activated_topic_ids: frozenset[str]
    suggested_terms: frozenset[str]
    suggested_sources: frozenset[str]
    graph_loaded: bool
    graph_version: str

    @property
    def is_active(self) -> bool:
        return bool(self.activated_topic_ids or self.suggested_terms)


def _infer_suggested_sources(seeds: frozenset[str], terms: frozenset[str]) -> frozenset[str]:
    joined = " ".join(sorted(seeds | terms)).lower()
    sources: set[str] = set()
    if any(token in joined for token in ("intranet", "site pages", "sitepages")):
        sources.add("intranet")
    if any(token in joined for token in ("sharepoint", "site drive", "list_sites")):
        sources.add("sharepoint_docs")
    if any(token in joined for token in ("workspace", "context/", "context_staging")):
        sources.add("workspace")
    if not sources:
        return frozenset({"generic_retrieval"})
    return frozenset(sorted(sources))


def _word_boundary_match(text: str, term: str) -> bool:
    return bool(re.search(rf"\b{re.escape(term)}\b", text, flags=re.IGNORECASE))


def _term_matches_message(message: str, term: str) -> bool:
    """Return whether ``term`` should count as present in ``message``."""
    t = (term or "").strip().lower()
    if not t:
        return False
    lowered = message.lower()
    if len(t) >= 5:
        return t in lowered
    return _word_boundary_match(lowered, t)


def _activated_vertices(graph: RetrievalAssociationGraph, message: str) -> frozenset[str]:
    active: set[str] = set()
    for vid, terms in graph.vertex_terms.items():
        if any(_term_matches_message(message, t) for t in terms):
            active.add(vid)
    return frozenset(active)


def _collect_terms_bfs(graph: RetrievalAssociationGraph, seeds: frozenset[str]) -> frozenset[str]:
    """Collect union of vertex terms reachable within ``max_hops`` edges from any seed."""
    if not seeds:
        return frozenset()
    collected: set[str] = set()
    queue: deque[tuple[str, int]] = deque()
    best_depth: dict[str, int] = {}
    for sid in sorted(seeds):
        queue.append((sid, 0))
        best_depth[sid] = 0
    while queue:
        vid, depth = queue.popleft()
        collected.update(graph.vertex_terms.get(vid, frozenset()))
        if depth >= graph.max_hops:
            continue
        for nb in sorted(graph.neighbors.get(vid, frozenset())):
            next_depth = depth + 1
            if next_depth < best_depth.get(nb, 10**9):
                best_depth[nb] = next_depth
                queue.append((nb, next_depth))
    return frozenset(collected)


def load_retrieval_association_graph(registry_dir: Path) -> RetrievalAssociationGraph | None:
    """Load ``retrieval_association_graph.yaml`` from the registry directory.

    Returns:
        Parsed graph, or ``None`` when the file is missing or invalid.
    """
    path = registry_dir / _DEFAULT_GRAPH_NAME
    if not path.is_file():
        return None
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(raw, dict):
        return None
    settings = raw.get("settings") or {}
    max_hops = 2
    if isinstance(settings, dict):
        try:
            max_hops = int(settings.get("max_hops") or 2)
        except (TypeError, ValueError):
            max_hops = 2
    max_hops = max(0, min(max_hops, 4))

    vertex_terms: dict[str, frozenset[str]] = {}
    vertices = raw.get("vertices") or []
    if not isinstance(vertices, list):
        return None
    for block in vertices:
        if not isinstance(block, dict):
            continue
        vid = str(block.get("id") or "").strip()
        if not vid:
            continue
        terms_raw = block.get("terms") or []
        if isinstance(terms_raw, str):
            terms_raw = [terms_raw]
        if not isinstance(terms_raw, list):
            continue
        terms = frozenset(str(t).strip().lower() for t in terms_raw if str(t).strip())
        if terms:
            vertex_terms[vid] = terms

    neighbors: dict[str, set[str]] = {vid: set() for vid in vertex_terms}
    edges = raw.get("edges") or []
    if isinstance(edges, list):
        for edge in edges:
            if isinstance(edge, (list, tuple)) and len(edge) == 2:
                a, b = str(edge[0]).strip(), str(edge[1]).strip()
            elif isinstance(edge, dict):
                a, b = str(edge.get("from") or "").strip(), str(edge.get("to") or "").strip()
            else:
                continue
            if a in vertex_terms and b in vertex_terms:
                neighbors[a].add(b)
                neighbors[b].add(a)

    if not vertex_terms:
        return None
    return RetrievalAssociationGraph(
        vertex_terms=vertex_terms,
        neighbors={k: frozenset(v) for k, v in neighbors.items()},
        max_hops=max_hops,
    )


def expand_retrieval_hints(message: str, graph: RetrievalAssociationGraph | None) -> tuple[frozenset[str], frozenset[str]]:
    """Expand user message into activated vertex ids and hint terms.

    Args:
        message: Raw user text.
        graph: Loaded graph or ``None``.

    Returns:
        Tuple of (activated_vertex_ids, all_hint_terms_from_BFS).
    """
    if graph is None or not (message or "").strip():
        return frozenset(), frozenset()
    seeds = _activated_vertices(graph, message)
    terms = _collect_terms_bfs(graph, seeds)
    return seeds, terms


def build_deterministic_retrieval_context(
    message: str,
    graph: RetrievalAssociationGraph | None,
    *,
    graph_loaded: bool = True,
    graph_version: str = "unknown",
) -> DeterministicRetrievalContext:
    """Return structured deterministic retrieval context from message + graph."""
    seeds, terms = expand_retrieval_hints(message, graph)
    return DeterministicRetrievalContext(
        schema_version="deterministic_context_v1",
        activated_topic_ids=seeds,
        suggested_terms=terms,
        suggested_sources=_infer_suggested_sources(seeds, terms),
        graph_loaded=graph_loaded,
        graph_version=graph_version,
    )


def format_retrieval_expansion_block(
    message: str,
    graph: RetrievalAssociationGraph | None = None,
    *,
    context: DeterministicRetrievalContext | None = None,
    max_terms: int = 36,
) -> str:
    """Return a markdown section for prompt injection, or empty string when idle."""
    ctx = context if context is not None else build_deterministic_retrieval_context(message, graph)
    if not ctx.is_active:
        return ""
    ordered_terms = sorted(ctx.suggested_terms)[:max_terms]
    lines = [
        "## Deterministic retrieval expansion (registry graph)",
        "",
        "The following hints were **pre-computed** from `registry/retrieval_association_graph.yaml` "
        "(topic association graph). Use them only when they **match the user request**; "
        "they are not a substitute for reading sources.",
        "",
        f"- **Activated topic ids:** {', '.join(sorted(ctx.activated_topic_ids)) or '(none)'}",
        f"- **Suggested query / tool hints:** {', '.join(ordered_terms) if ordered_terms else '(none)'}",
        f"- **Suggested source families:** {', '.join(sorted(ctx.suggested_sources)) or '(none)'}",
        "",
    ]
    return "\n".join(lines).strip() + "\n"


def deterministic_context_trace_metadata(context: DeterministicRetrievalContext) -> dict[str, object]:
    """Return compact metadata for tracing deterministic retrieval behaviour."""
    return {
        "schema_version": context.schema_version,
        "graph_loaded": context.graph_loaded,
        "graph_version": context.graph_version,
        "activated_topics_count": len(context.activated_topic_ids),
        "hint_terms_count": len(context.suggested_terms),
        "activated_topics": sorted(context.activated_topic_ids),
        "suggested_sources": sorted(context.suggested_sources),
    }


def deterministic_context_from_registry(
    message: str,
    registry_dir: Path,
) -> tuple[DeterministicRetrievalContext, bool]:
    """Load graph from registry and compute context.

    Returns:
        Tuple of (context, graph_loaded).
    """
    path = registry_dir / _DEFAULT_GRAPH_NAME
    graph_version = "unavailable"
    if path.is_file():
        try:
            payload = path.read_text(encoding="utf-8")
            graph_version = sha1(payload.encode("utf-8")).hexdigest()[:12]
        except OSError:
            graph_version = "unreadable"
    graph = load_retrieval_association_graph(registry_dir)
    if graph is None:
        return (
            DeterministicRetrievalContext(
                schema_version="deterministic_context_v1",
                activated_topic_ids=frozenset(),
                suggested_terms=frozenset(),
                suggested_sources=frozenset(),
                graph_loaded=False,
                graph_version=graph_version,
            ),
            False,
        )
    return build_deterministic_retrieval_context(
        message,
        graph,
        graph_loaded=True,
        graph_version=graph_version,
    ), True
