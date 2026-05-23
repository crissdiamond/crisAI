from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_hcom_team_hints_remain_short_and_do_not_repeat_memory_policy() -> None:
    for relative_path in ("scripts/hcom_start.sh", "scripts/hcom_claude_review.sh"):
        source = (ROOT / relative_path).read_text(encoding="utf-8")

        assert 'export HCOM_HINTS="$TEAM_HINTS"' in source
        assert 'export HCOM_HINTS="$TEAM_HINTS $MEMORY_WRITE_POLICY"' not in source
        assert "Direct hcom requests are assignments" in source


def test_hcom_team_docs_warn_against_long_repeated_hints() -> None:
    source = (ROOT / "reference/development/operating_model.md").read_text(encoding="utf-8")

    assert "hcom appends" in source
    assert "must remain concise" in source
    assert "not repeated message hints" in source


def test_start_hcom_supports_antigravity_gemini_review_mode() -> None:
    source = (ROOT / "start").read_text(encoding="utf-8")

    assert "agy|antigravity)" in source
    assert "gemini)" in source
    assert 'HCOM_MODEL_FAMILY="gemini"' in source
    assert "gemini-3-flash-preview" in source
    assert 'export HCOM_TEAM_REVIEW_MODEL_FAMILY="$HCOM_MODEL_FAMILY"' in source
    assert 'export HCOM_TEAM_REVIEW_MODEL="$HCOM_REVIEW_MODEL"' in source
    assert "hcom gemini reviewers require the agy/antigravity provider" in source


def test_antigravity_review_scripts_pass_explicit_model_to_hcom() -> None:
    start_source = (ROOT / "scripts/hcom_start.sh").read_text(encoding="utf-8")
    review_source = (ROOT / "scripts/hcom_review.sh").read_text(encoding="utf-8")
    preflight_source = (ROOT / "scripts/hcom_antigravity_preflight.sh").read_text(encoding="utf-8")

    assert 'REVIEW_MODEL="${HCOM_TEAM_REVIEW_MODEL:-${HCOM_TEAM_ANTIGRAVITY_MODEL:-}}"' in start_source
    assert 'printf \'%s\\n\' --model "$REVIEW_MODEL"' in start_source
    assert 'CMD+=(--model "$REVIEW_MODEL")' in review_source
    assert 'MODEL="${HCOM_TEAM_REVIEW_MODEL:-${HCOM_TEAM_ANTIGRAVITY_MODEL:-}}"' in preflight_source
    assert "hcom agy --model" in preflight_source
    assert "normalized_response\" != *claude*" not in preflight_source
