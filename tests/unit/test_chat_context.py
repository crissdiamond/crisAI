from __future__ import annotations

from crisai.cli import chat_context


def test_render_history_formats_roles():
    history = [("user", "hello"), ("assistant", "hi")]

    result = chat_context.render_history(history)

    assert result == "User: hello\n\nAssistant: hi"


def test_render_history_sanitizes_legacy_assistant_machine_json():
    history = [
        ("user", "find docs"),
        (
            "assistant",
            """Found files.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "find docs",
  "items": []
}
```
""",
        ),
        ("user", "next"),
        ("assistant", "Ready.\n\n```json"),
    ]

    result = chat_context.render_history(history)

    assert "schema_version" not in result
    assert "```json" not in result
    assert "Assistant: Found files." in result
    assert "Assistant: Ready." in result


def test_build_chat_input_returns_plain_input_without_history():
    assert chat_context.build_chat_input("hello", []) == "hello"


def test_build_chat_input_wraps_compact_memory_and_relevant_tail(monkeypatch):
    captured = {}

    def fake_render_cli_text(template: str, **kwargs):
        captured["template"] = template
        captured["kwargs"] = kwargs
        return "wrapped"

    monkeypatch.setattr(chat_context, "render_cli_text", fake_render_cli_text)

    history = [
        ("user", "Summarise the Integration Strategy deck."),
        ("assistant", "Use `workspace/knowledge/integration-strategy.md` as the source."),
        ("user", "Now continue with Integration Strategy details."),
        ("assistant", "Recommended approach should use compact session memory."),
    ]

    result = chat_context.build_chat_input("Integration Strategy latest summary", history)

    assert result == "wrapped"
    assert captured["template"] == "chat/history_wrapper.md"
    assert captured["kwargs"]["user_input"] == "Integration Strategy latest summary"
    transcript = captured["kwargs"]["transcript"]
    assert "Compact session memory:" in transcript
    assert "Known sources:" in transcript
    assert "knowledge/integration-strategy.md" in transcript
    assert "Relevant recent turns:" in transcript
    assert "User: Now continue with Integration Strategy details." in transcript


def test_compact_memory_canonicalizes_workspace_prefix_sources():
    history = [
        ("user", "Use the local source."),
        ("assistant", "Read [reporting-standard.txt](file:///workspace/knowledge/standards/reporting-standard.txt)."),
        ("assistant", "Also used `knowledge/patterns/reporting-patterns.txt`."),
    ]

    memory = chat_context.compact_session_memory(history)

    assert "knowledge/standards/reporting-standard.txt" in memory.known_sources
    assert "knowledge/patterns/reporting-patterns.txt" in memory.known_sources


def test_runtime_context_package_flags_task_drift():
    history = [
        ("user", "Work on the Integration Strategy document summary."),
        ("assistant", "Current state: summary drafted from the source deck."),
    ]

    package = chat_context.build_runtime_context_package(
        "Create a Kubernetes deployment plan for the payments API.",
        history,
    )

    assert package.drift_nudge
    assert package.included_recent_entries <= 4


def test_session_memory_config_env_overrides_registry(tmp_path, monkeypatch):
    (tmp_path / "session_memory.yaml").write_text(
        """
session_memory:
  strategy: deterministic
  max_recent_turns: 9
  task_drift_nudge: true
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("CRISAI_SESSION_MEMORY_STRATEGY", "agentic")
    monkeypatch.setenv("CRISAI_SESSION_MEMORY_AGENT_ID", "custom_memory_agent")
    monkeypatch.setenv("CRISAI_SESSION_MEMORY_MAX_RECENT_TURNS", "3")
    monkeypatch.setenv("CRISAI_SESSION_MEMORY_MAX_RUNTIME_CHARS", "7000")
    monkeypatch.setenv("CRISAI_SESSION_MEMORY_MAX_MEMORY_CHARS", "3500")
    monkeypatch.setenv("CRISAI_SESSION_MEMORY_TASK_DRIFT_NUDGE", "false")

    config = chat_context.load_session_memory_config(tmp_path)

    assert config.strategy == "agentic"
    assert config.agentic_agent_id == "custom_memory_agent"
    assert config.max_recent_turns == 3
    assert config.max_runtime_chars == 7000
    assert config.max_memory_chars == 3500
    assert config.task_drift_nudge is False
