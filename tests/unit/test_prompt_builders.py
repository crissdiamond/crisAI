from crisai.cli.prompt_builders import (
    build_author_prompt,
    build_challenger_prompt,
    build_design_prompt,
    build_discovery_prompt,
    build_judge_prompt,
    build_peer_final_prompt,
    build_pipeline_final_prompt,
    build_refiner_prompt,
    build_review_prompt,
)


def test_build_discovery_prompt_contains_only_runtime_context():
    text = build_discovery_prompt("Find the latest design note")
    assert "User request:\nFind the latest design note" in text
    assert "Task:\nFrame the request for the downstream workflow." in text
    assert "Rules:" not in text
    assert "Return:" not in text


def test_build_design_prompt_normalises_empty_discovery():
    text = build_design_prompt("Draft an approach", "")
    assert "Discovery findings:\nNone." in text
    assert "Task:\nProduce the best possible architecture, design, or documentation response" in text


def test_build_review_prompt_includes_inputs_without_policy_duplication():
    text = build_review_prompt("Review this", "facts", "draft")
    assert "User request:\nReview this" in text
    assert "Discovery findings:\nfacts" in text
    assert "Draft design response:\ndraft" in text
    assert "Rules:" not in text
    assert "Highlight:" not in text


def test_build_pipeline_final_prompt_keeps_only_transition_specific_guidance():
    text = build_pipeline_final_prompt("Question", "facts", "design", "review")
    assert "Handoff guidance:" in text
    assert "Do not mention internal pipeline stages" not in text
    assert "do not mention internal pipeline stages unless the user explicitly asked" in text.lower()


def test_peer_builders_use_stable_section_labels():
    challenger = build_challenger_prompt("Question", "facts", "draft")
    refiner = build_refiner_prompt("Question", "facts", "draft", "challenge")
    judge = build_judge_prompt("Question", "facts", "challenge", "refined")
    peer_final = build_peer_final_prompt("Question", "facts", "draft", "challenge", "refined", "accept")

    assert "Draft:\ndraft" in challenger
    assert "Original draft:\ndraft" in refiner
    assert "Refined draft:\nrefined" in judge
    assert "Judge decision:\naccept" in peer_final


def test_author_prompt_is_minimal_runtime_handoff():
    text = build_author_prompt("Draft it", "retrieved")
    assert "User request:\nDraft it" in text
    assert "Discovery findings:\nretrieved" in text
    assert "Rules:" not in text
