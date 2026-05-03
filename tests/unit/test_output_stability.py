from crisai.cli.display import (
    _role_led_summary,
    _strip_compact_agent_prefix,
    _substantive_sentence_list,
    _truncate_for_summary,
)
from crisai.cli.status_views import route_display
from crisai.orchestration.router import RoutingDecision


def test_role_led_summary_for_retrieval_planner_is_plain_language():
    summary = _role_led_summary(
        "retrieval_planner",
        "Search OneDrive under /Projects/Integration for the latest strategy memo and the constraints doc.",
    )
    assert summary.startswith("The Retrieval planner:")
    assert "strategy memo" in summary


def test_role_led_summary_for_review_is_plain_language():
    summary = _role_led_summary("review", "The draft has two weak assumptions around ownership and monitoring.")
    assert summary.startswith("The Review notes:")
    assert "weak assumptions" in summary


def test_role_led_summary_includes_multiple_sentences_for_context_synthesizer():
    body = (
        "The retrieved context is strong. It supports a staged approach. "
        "Gaps remain on lineage ownership for Excel-fed datasets."
    )
    summary = _role_led_summary("context_synthesizer", body)
    assert summary.startswith("Context Synthesizer:")
    assert "staged approach" in summary
    assert "Gaps remain" in summary or "lineage" in summary


def test_strip_compact_agent_prefix_removes_duplicate_role_label():
    raw = "The Retrieval planner: Search notes and patterns for governance."
    assert _strip_compact_agent_prefix("retrieval_planner", raw) == "Search notes and patterns for governance."


def test_truncate_for_summary_drops_dangling_short_tail_word():
    blob = (
        "Retrieval focus: search local context for a pattern around a dashboard "
        "that starts from Excel and needs a controlled ingestion path for governance"
    )
    out = _truncate_for_summary(blob, 95)
    assert out.endswith("…")
    assert not out.endswith(" a…")
    assert "needs" in out or "Excel" in out


def test_substantive_sentence_list_caps_run_on_without_sentence_endings():
    """Regression: a single 'sentence' must not be the entire model output."""
    blob = "a" * 800 + " word " + "b" * 800
    parts = _substantive_sentence_list(blob, max_count=1, max_chars=120, min_sentence_len=10)
    assert len(parts) == 1
    assert len(parts[0]) <= 125
    assert parts[0].endswith("…")


def test_role_led_summary_compact_uses_single_fragment():
    body = (
        "The retrieved context is strong. It supports a staged approach. "
        "Gaps remain on lineage ownership for Excel-fed datasets."
    )
    full = _role_led_summary("context_synthesizer", body, compact=False)
    tight = _role_led_summary("context_synthesizer", body, compact=True)
    assert len(tight) < len(full)
    assert "strong" in tight
    assert "staged approach" not in tight


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
