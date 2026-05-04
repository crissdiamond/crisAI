from __future__ import annotations
from dataclasses import dataclass

from .semantic_catalog import load_semantic_catalog

@dataclass
class RoutingDecision:
    intent: str
    mode: str
    agent: str | None
    needs_retrieval: bool
    needs_review: bool
    confidence: float
    reason: str


# Pins and saved sessions may still use the pre-rename agent id.
_LEGACY_AGENT_ALIASES = {"discovery": "retrieval_planner"}


def _normalize_explicit_agent(agent_id: str | None) -> str | None:
    if agent_id is None:
        return None
    return _LEGACY_AGENT_ALIASES.get(agent_id, agent_id)


def normalize_agent_id(agent_id: str | None) -> str | None:
    """Return the registry agent id, mapping legacy ids (e.g. ``discovery``)."""
    return _normalize_explicit_agent(agent_id)


def _normalise(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _contains_any(text: str, phrases: set[str]) -> bool:
    return any(p in text for p in phrases)


def _score_terms(text: str, terms: set[str]) -> int:
    return sum(1 for term in terms if term in text)


def _has_source_signal(text: str, discovery_score: int, source_markers: frozenset[str]) -> bool:
    if discovery_score >= 2:
        return True
    return any(marker in text for marker in source_markers)


def _is_architecture_location_phrase(text: str, architecture_location_markers: frozenset[str]) -> bool:
    return any(marker in text for marker in architecture_location_markers)


def _infer_auto_route(text: str, review_enabled: bool) -> RoutingDecision:
    terms = load_semantic_catalog().router
    if _contains_any(text, set(terms.explicit_discovery_patterns)):
        return RoutingDecision(
            intent="discovery",
            mode="single",
            agent="retrieval_planner",
            needs_retrieval=True,
            needs_review=False,
            confidence=0.99,
            reason="Prompt explicitly requests retrieval-only behaviour.",
        )

    discovery_score = _score_terms(text, set(terms.discovery_terms))
    design_score = _score_terms(text, set(terms.design_terms))
    review_score = _score_terms(text, set(terms.review_terms))
    operations_score = _score_terms(text, set(terms.operations_terms))
    peer_score = _score_terms(text, set(terms.peer_terms))
    publication_score = _score_terms(text, set(terms.publication_terms))
    criticality_score = _score_terms(text, set(terms.criticality_terms))

    has_source_signal = _has_source_signal(text, discovery_score, terms.source_markers)
    has_design_signal = design_score >= 2
    architecture_used_as_location = _is_architecture_location_phrase(
        text,
        terms.architecture_location_markers,
    )
    if architecture_used_as_location and design_score > 0:
        # "Architecture site(s)" is usually a SharePoint location label, not a drafting ask.
        design_score -= 1
        has_design_signal = design_score >= 2
    has_review_signal = review_score >= 2
    has_peer_signal = _contains_any(text, set(terms.explicit_peer_patterns)) or (
        peer_score >= 2 and (design_score >= 1 or review_score >= 1)
    )
    has_publication_signal = publication_score >= 1
    has_criticality_signal = criticality_score >= 1

    if operations_score >= 2:
        return RoutingDecision(
            intent="operations",
            mode="single",
            agent="operations",
            needs_retrieval=False,
            needs_review=False,
            confidence=0.90,
            reason="Prompt looks like debugging or platform troubleshooting.",
        )

    if has_publication_signal:
        return RoutingDecision(
            intent="publication",
            mode="single",
            agent="publisher",
            needs_retrieval=True,
            needs_review=False,
            confidence=0.93,
            reason="Prompt asks to package output into a formal artefact using templates or a requested document format.",
        )

    if has_criticality_signal and (
        has_design_signal
        or has_review_signal
        or (has_source_signal and design_score >= 1)
    ):
        return RoutingDecision(
            intent="critical_peer_review",
            mode="peer",
            agent="design_author",
            needs_retrieval=has_source_signal,
            needs_review=True,
            confidence=0.93,
            reason="Prompt signals high-criticality/high-accuracy design work; peer challenge and judgement are preferred over pipeline.",
        )

    if has_peer_signal:
        return RoutingDecision(
            intent="peer_review",
            mode="peer",
            agent="design_author",
            needs_retrieval=has_source_signal,
            needs_review=True,
            confidence=0.96 if _contains_any(text, set(terms.explicit_peer_patterns)) else 0.92,
            reason="Prompt requests peer-style proposal, challenge, refinement, and judgement.",
        )

    if has_source_signal and (has_design_signal or design_score >= 1):
        return RoutingDecision(
            intent="discovery_design",
            mode="pipeline",
            agent="retrieval_planner",
            needs_retrieval=True,
            needs_review=True,
            confidence=0.89,
            reason="Prompt combines source lookup with drafting or synthesis; pipeline runs with review for quality control on complex multi-stage work.",
        )

    if has_design_signal and has_review_signal:
        return RoutingDecision(
            intent="design_review",
            mode="pipeline",
            agent="design",
            needs_retrieval=False,
            needs_review=True,
            confidence=0.86,
            reason="Prompt asks for both proposal and critique, so a pipeline is more suitable than design-only or review-only.",
        )

    if has_review_signal and not has_design_signal and not has_source_signal:
        return RoutingDecision(
            intent="review",
            mode="single",
            agent="review",
            needs_retrieval=False,
            needs_review=True,
            confidence=0.85,
            reason="Prompt primarily focuses on critique or evaluation.",
        )

    if has_design_signal:
        return RoutingDecision(
            intent="design",
            mode="single",
            agent="design",
            needs_retrieval=False,
            needs_review=False,
            confidence=0.82,
            reason="Prompt primarily asks for drafting or architecture output.",
        )

    if has_source_signal:
        return RoutingDecision(
            intent="discovery",
            mode="single",
            agent="retrieval_planner",
            needs_retrieval=True,
            needs_review=False,
            confidence=0.82,
            reason="Prompt primarily asks for finding or inspecting sources.",
        )

    mixed_complexity_score = discovery_score + design_score + review_score + peer_score
    if mixed_complexity_score >= 3:
        return RoutingDecision(
            intent="mixed_complexity",
            mode="pipeline",
            agent="design",
            needs_retrieval=False,
            needs_review=True,
            confidence=0.78,
            reason="Prompt contains mixed design/review/retrieval signals; pipeline with review is safer than single-agent fallback.",
        )

    return RoutingDecision(
        intent="orchestrator",
        mode="single",
        agent="orchestrator",
        needs_retrieval=False,
        needs_review=False,
        confidence=0.50,
        reason="No strong routing signal detected; using orchestrator fallback.",
    )


def _apply_explicit_overrides(
    base: RoutingDecision,
    *,
    current_mode: str | None,
    selected_agent: str | None,
    review_enabled: bool,
) -> RoutingDecision:
    if selected_agent is not None:
        return RoutingDecision(
            intent="explicit",
            mode="single",
            agent=selected_agent,
            needs_retrieval=selected_agent in {"retrieval_planner", "publisher"},
            needs_review=selected_agent == "review",
            confidence=1.0,
            reason="Agent explicitly selected by user.",
        )

    if current_mode is None:
        return base

    if current_mode == "peer":
        return RoutingDecision(
            intent="explicit",
            mode="peer",
            agent="design_author",
            needs_retrieval=base.needs_retrieval,
            needs_review=True,
            confidence=1.0,
            reason="Mode explicitly set to peer by user.",
        )

    if current_mode == "pipeline":
        return RoutingDecision(
            intent="explicit",
            mode="pipeline",
            agent=base.agent if base.agent in {"retrieval_planner", "design"} else "design",
            needs_retrieval=base.needs_retrieval,
            needs_review=review_enabled or base.needs_review,
            confidence=1.0,
            reason="Mode explicitly set to pipeline by user.",
        )

    return RoutingDecision(
        intent="explicit",
        mode="single",
        agent=base.agent,
        needs_retrieval=base.agent in {"retrieval_planner", "publisher"},
        needs_review=base.agent == "review",
        confidence=1.0,
        reason="Mode explicitly set to single by user.",
    )


def decide_route(
    user_input: str,
    review_enabled: bool,
    current_mode: str | None = None,
    selected_agent: str | None = None,
) -> RoutingDecision:
    text = _normalise(user_input)
    base = _infer_auto_route(text, review_enabled=review_enabled)
    return _apply_explicit_overrides(
        base,
        current_mode=current_mode,
        selected_agent=_normalize_explicit_agent(selected_agent),
        review_enabled=review_enabled,
    )