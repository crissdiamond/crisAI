from crisai.cli.main import _effective_pipeline_review
from crisai.orchestration.router import RoutingDecision


def _decision(mode: str, needs_review: bool) -> RoutingDecision:
    return RoutingDecision(
        intent="test",
        mode=mode,
        agent="design",
        needs_retrieval=False,
        needs_review=needs_review,
        confidence=1.0,
        reason="test",
    )


def test_effective_pipeline_review_enabled_only_for_pipeline_with_review_need():
    assert _effective_pipeline_review(_decision("pipeline", True)) is True


def test_effective_pipeline_review_disabled_for_pipeline_without_review_need():
    assert _effective_pipeline_review(_decision("pipeline", False)) is False


def test_effective_pipeline_review_disabled_for_single_mode():
    assert _effective_pipeline_review(_decision("single", True)) is False


def test_effective_pipeline_review_disabled_for_peer_mode():
    assert _effective_pipeline_review(_decision("peer", True)) is False
