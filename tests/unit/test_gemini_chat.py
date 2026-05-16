from __future__ import annotations

from crisai.cli.gemini_chat import GeminiChatDisplay, GeminiChatStatus


def _status() -> GeminiChatStatus:
    return GeminiChatStatus(
        session="PowerBI-4",
        mode="pipeline",
        agent="auto",
        model="gpt-test",
        verbose=False,
        review=False,
        retrieval_checkpoint=True,
        mode_pinned=False,
        agent_pinned=False,
    )


def test_gemini_display_footer_includes_runtime_state() -> None:
    display = GeminiChatDisplay()
    display.update_status(_status())

    rendered = display._render_footer()
    text = rendered.renderable.plain

    assert "PowerBI-4" in text
    assert "mode:pipeline" in text
    assert "agent:auto" in text
    assert "checkpoint:on" in text


def test_gemini_display_sanitizes_machine_json() -> None:
    display = GeminiChatDisplay()
    display.append(
        "Retrieval",
        'Visible text\n\n```json\n{"schema_version":"evidence_bundle_v1","items":[]}\n```',
    )

    assert display.entries == [("Retrieval", "Visible text")]


def test_gemini_display_agent_progress_updates_footer_stage() -> None:
    display = GeminiChatDisplay()
    display.update_status(_status())

    display.agent_started("context_synthesizer", "Working...")

    assert display.status_state is not None
    assert display.status_state.activity == "working"
    assert display.status_state.current_stage == "context_synthesizer"
