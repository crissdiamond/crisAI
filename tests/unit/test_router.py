from __future__ import annotations

from crisai.orchestration.router import RoutingDecision, decide_route


def assert_route(decision: RoutingDecision, *, mode: str, agent: str | None, intent: str) -> None:
    assert decision.mode == mode
    assert decision.agent == agent
    assert decision.intent == intent


def test_routes_retrieval_only_prompt_to_discovery() -> None:
    decision = decide_route(
        user_input="Search my personal OneDrive and find all documents related to the integration strategy. Return only a markdown table.",
        review_enabled=False,
    )
    assert_route(decision, mode="single", agent="discovery", intent="discovery")
    assert decision.needs_retrieval is True


def test_routes_retrieval_and_drafting_prompt_to_pipeline() -> None:
    decision = decide_route(
        user_input="Find the strongest documents on federated data architecture and draft a one-page HLD skeleton.",
        review_enabled=False,
    )
    assert_route(decision, mode="pipeline", agent="discovery", intent="discovery_design")


def test_routes_review_prompt_to_review_agent() -> None:
    decision = decide_route(
        user_input="Use review only. Critique this architecture note and identify weak assumptions.",
        review_enabled=True,
    )
    assert_route(decision, mode="single", agent="review", intent="review")


def test_routes_operations_prompt_to_operations_agent() -> None:
    decision = decide_route(
        user_input="Why is SharePoint login popping up every time? Debug the auth token issue.",
        review_enabled=False,
    )
    assert_route(decision, mode="single", agent="operations", intent="operations")


def test_routes_unknown_prompt_to_orchestrator_fallback() -> None:
    decision = decide_route(
        user_input="Help me think about this.",
        review_enabled=False,
    )
    assert_route(decision, mode="single", agent="orchestrator", intent="orchestrator")


def test_explicit_mode_override_wins() -> None:
    decision = decide_route(
        user_input="Find documents related to integration strategy.",
        review_enabled=False,
        current_mode="pipeline",
    )
    assert_route(decision, mode="pipeline", agent=None, intent="explicit")


def test_explicit_agent_override_wins() -> None:
    decision = decide_route(
        user_input="Find documents related to integration strategy.",
        review_enabled=False,
        selected_agent="design",
    )
    assert_route(decision, mode="single", agent="design", intent="explicit")
