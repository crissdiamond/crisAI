from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RoutingDecision:
    intent: str
    mode: str
    agent: str | None
    needs_retrieval: bool
    needs_review: bool
    confidence: float
    reason: str


DISCOVERY_TERMS = {
    "find", "search", "locate", "identify", "list", "show",
    "documents", "sources", "files", "inspect", "onedrive",
    "sharepoint", "drive", "site", "path", "read",
}

DESIGN_TERMS = {
    "design", "draft", "architecture", "hld", "lld", "proposal",
    "option", "options", "recommendation", "target state",
    "operating model", "blueprint", "solution", "summarise", "summary",
}

REVIEW_TERMS = {
    "review", "critique", "challenge", "refine", "improve",
    "gaps", "assumptions", "weaknesses", "judge",
}

OPERATIONS_TERMS = {
    "debug", "fix", "error", "issue", "broken", "failing",
    "logs", "auth", "token", "login", "timeout", "exception",
    "not working", "keeps prompting", "prompting",
}

EXPLICIT_DISCOVERY_PATTERNS = {
    "use discovery only",
    "discovery only",
    "do not use the design agent",
    "return only a list",
    "return only the list",
    "return only a table",
    "return only the table",
    "do not draft",
    "do not summarise",
}

EXPLICIT_PEER_PATTERNS = {
    "peer review",
    "debate this",
    "challenge and refine",
}


def _normalise(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _contains_any(text: str, phrases: set[str]) -> bool:
    return any(p in text for p in phrases)


def _score_terms(text: str, terms: set[str]) -> int:
    return sum(1 for term in terms if term in text)


def decide_route(
    user_input: str,
    review_enabled: bool,
    current_mode: str | None = None,
    selected_agent: str | None = None,
) -> RoutingDecision:
    text = _normalise(user_input)

    if current_mode is not None or selected_agent is not None:
        return RoutingDecision(
            intent="explicit",
            mode=current_mode or "single",
            agent=selected_agent,
            needs_retrieval=False,
            needs_review=review_enabled,
            confidence=1.0,
            reason="Mode or agent explicitly selected by user.",
        )

    if _contains_any(text, EXPLICIT_DISCOVERY_PATTERNS):
        return RoutingDecision(
            intent="discovery",
            mode="single",
            agent="discovery",
            needs_retrieval=True,
            needs_review=False,
            confidence=0.98,
            reason="Prompt explicitly requests retrieval-only behaviour.",
        )

    if _contains_any(text, EXPLICIT_PEER_PATTERNS):
        return RoutingDecision(
            intent="peer_review",
            mode="peer",
            agent="design_author",
            needs_retrieval=False,
            needs_review=True,
            confidence=0.95,
            reason="Prompt explicitly requests multi-agent critique/refinement.",
        )

    discovery_score = _score_terms(text, DISCOVERY_TERMS)
    design_score = _score_terms(text, DESIGN_TERMS)
    review_score = _score_terms(text, REVIEW_TERMS)
    operations_score = _score_terms(text, OPERATIONS_TERMS)

    retrieval_context = any(t in text for t in {"onedrive", "sharepoint", "documents", "files", "sources"})

    if operations_score >= 2:
        return RoutingDecision(
            intent="operations",
            mode="single",
            agent="operations",
            needs_retrieval=False,
            needs_review=False,
            confidence=0.85,
            reason="Prompt looks like debugging or platform troubleshooting.",
        )

    if discovery_score >= 2 and design_score >= 1:
        return RoutingDecision(
            intent="discovery_design",
            mode="pipeline",
            agent="discovery",
            needs_retrieval=True,
            needs_review=review_enabled,
            confidence=0.88,
            reason="Prompt combines source discovery with drafting or synthesis.",
        )

    if review_score >= 2:
        return RoutingDecision(
            intent="review",
            mode="single",
            agent="review",
            needs_retrieval=False,
            needs_review=True,
            confidence=0.84,
            reason="Prompt focuses on critique or evaluation.",
        )

    if design_score >= 2:
        return RoutingDecision(
            intent="design",
            mode="single",
            agent="design",
            needs_retrieval=False,
            needs_review=False,
            confidence=0.80,
            reason="Prompt primarily asks for drafting or architecture output.",
        )

    if discovery_score >= 2 or retrieval_context:
        return RoutingDecision(
            intent="discovery",
            mode="single",
            agent="discovery",
            needs_retrieval=True,
            needs_review=False,
            confidence=0.82 if discovery_score >= 2 else 0.75,
            reason="Prompt primarily asks for finding or inspecting sources.",
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
