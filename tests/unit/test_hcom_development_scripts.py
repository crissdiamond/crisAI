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
