from crisai.cli.display import _role_led_summary
from crisai.cli.status_views import route_display
from crisai.orchestration.router import RoutingDecision


def test_role_led_summary_for_discovery_is_plain_language():
    summary = _role_led_summary("discovery", "Found three relevant documents about the integration strategy and the newest one is the best match.")
    assert summary.startswith("Discovery finds that")


def test_role_led_summary_for_review_is_plain_language():
    summary = _role_led_summary("review", "The draft has two weak assumptions around ownership and monitoring.")
    assert summary.startswith("The Review notes that")


def test_route_display_includes_review_and_retrieval_flags():
    decision = RoutingDecision(
        intent="design_review",
        mode="pipeline",
        agent="design",
        needs_retrieval=False,
        needs_review=True,
        confidence=0.9,
        reason="Prompt asks for both proposal and critique.",
    )
    rendered = route_display(decision)
    assert "review:on" in rendered
    assert "retrieval:off" in rendered
    assert "pipeline" in rendered
