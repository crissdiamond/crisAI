from crisai.orchestration.peer_judge import _judge_reason_excerpt, _parse_judge_decision


def test_parse_judge_decision_handles_accept_revise_unknown():
    assert _parse_judge_decision("Decision: accept") == "accept"
    assert _parse_judge_decision("Decision - revise") == "revise"
    assert _parse_judge_decision("Decision: not acceptable") == "revise"
    assert _parse_judge_decision("Decision: acceptable but missing details") == "accept"
    assert _parse_judge_decision("Decision: reject and revise") == "revise"
    assert _parse_judge_decision("Result\nDecision: revise") == "revise"
    assert _parse_judge_decision("Looks good but no explicit label") == "unknown"


def test_judge_reason_excerpt_prefers_reason_field():
    text = "Decision: revise\nReason: Missing file coverage for ingestion patterns."
    excerpt = _judge_reason_excerpt(text)
    assert excerpt == "Missing file coverage for ingestion patterns."


def test_judge_reason_excerpt_fallbacks_to_first_non_decision_line():
    text = "Decision: accept\nLooks complete and grounded."
    excerpt = _judge_reason_excerpt(text)
    assert excerpt == "Looks complete and grounded."
