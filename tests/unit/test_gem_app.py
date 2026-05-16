from __future__ import annotations

from crisai.cli import gem_app
from crisai.cli.gem_events import GemEvent, GemUiState, apply_gem_event
from crisai.cli.gem_theme import GEM_CSS, gem_palette_as_dict


def test_gem_palette_matches_web_tokens() -> None:
    palette = gem_palette_as_dict()

    assert palette["primary_dark"] == "#361a54"
    assert palette["background"] == "#fafafa"
    assert palette["accent_blue"] == "#30d6ff"
    assert palette["warning"] == "#FFCA36"


def test_gem_css_uses_ucl_palette() -> None:
    assert "#361a54" in GEM_CSS
    assert "#eedeff" in GEM_CSS
    assert "#30d6ff" in GEM_CSS


def test_apply_gem_event_updates_stage_state() -> None:
    state = GemUiState()

    apply_gem_event(state, GemEvent(kind="stage_started", title="Retrieval", stage="context_retrieval"))
    assert state.stages["context_retrieval"].state == "running"
    assert state.current_stage == "context_retrieval"

    apply_gem_event(
        state,
        GemEvent(
            kind="stage_completed",
            title="Retrieval",
            body="Read two sources.",
            stage="context_retrieval",
        ),
    )
    assert state.stages["context_retrieval"].state == "complete"
    assert state.stages["context_retrieval"].summary == "Read two sources."
    assert state.current_stage is None


def test_apply_gem_event_records_transcript_events() -> None:
    state = GemUiState()
    event = GemEvent(kind="routing", title="Routing", body="pipeline")

    apply_gem_event(state, event)

    assert state.transcript == [event]


def test_textual_available_false_when_missing(monkeypatch) -> None:
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "textual":
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    assert gem_app.textual_available() is False
