from __future__ import annotations

import pytest

from crisai.cli import gem_app
from crisai.cli.gem_events import GemEvent, GemUiState, apply_gem_event
from crisai.cli.gem_theme import GEM_CSS, gem_palette_as_dict, render_gem_css


def test_gem_palette_matches_web_tokens() -> None:
    palette = gem_palette_as_dict()

    assert palette["primary_dark"] == "#361a54"
    assert palette["background"] == "#1f102f"
    assert palette["transcript_background"] == "#fafafa"
    assert palette["accent_blue"] == "#30d6ff"
    assert palette["warning"] == "#FFCA36"


def test_gem_css_uses_ucl_palette() -> None:
    assert "#361a54" in GEM_CSS
    assert "#1f102f" in GEM_CSS
    assert "#eedeff" in GEM_CSS
    assert "#30d6ff" in GEM_CSS
    assert "border: solid #993bff" in GEM_CSS
    assert "#transcript-content" in GEM_CSS


def test_render_gem_css_from_yaml_config(tmp_path) -> None:
    config = tmp_path / "gem_ui.yaml"
    config.write_text(
        """
theme:
  palette:
    primary_dark: "#361a54"
    background: "#1f102f"
    transcript_background: "#fafafa"
    composer_background: "#ffffff"
    accent_bright: "#993bff"
    accent_mid: "#ba82ff"
    surface_light: "#ddbdff"
    surface_pale: "#eedeff"
    accent_blue: "#30d6ff"
    text: "#1f1f2e"
    border: "#c9b7dd"
    vibrant_purple: "#500778"
    success: "#52C152"
    error: "#D50032"
    warning: "#FFCA36"
  css_template: |
    Screen { background: $background; }
""",
        encoding="utf-8",
    )

    assert "background: #1f102f" in render_gem_css(config)


def test_gem_palette_reports_missing_token(tmp_path) -> None:
    config = tmp_path / "gem_ui.yaml"
    config.write_text(
        """
theme:
  palette:
    primary_dark: "#361a54"
  css_template: "Screen { background: $background; }"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing token"):
        gem_palette_as_dict(config)


def test_gem_css_reports_unknown_template_token(tmp_path) -> None:
    config = tmp_path / "gem_ui.yaml"
    config.write_text(
        """
theme:
  palette:
    primary_dark: "#361a54"
    background: "#1f102f"
    transcript_background: "#fafafa"
    composer_background: "#ffffff"
    accent_bright: "#993bff"
    accent_mid: "#ba82ff"
    surface_light: "#ddbdff"
    surface_pale: "#eedeff"
    accent_blue: "#30d6ff"
    text: "#1f1f2e"
    border: "#c9b7dd"
    vibrant_purple: "#500778"
    success: "#52C152"
    error: "#D50032"
    warning: "#FFCA36"
  css_template: "Screen { background: $missing_token; }"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown token"):
        render_gem_css(config)


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
