from __future__ import annotations

from rich.markdown import Markdown
from rich.panel import Panel

from crisai.cli import display
from crisai.cli.display import render_peer_message
from crisai.cli.peer_transcript import make_peer_message


def test_render_peer_message_returns_panel() -> None:
    msg = make_peer_message("design_challenger", "I disagree with this assumption.")
    panel = render_peer_message(msg)
    assert isinstance(panel, Panel)


def test_print_agent_output_non_verbose_uses_markdown_panel(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(display.console, "print", lambda value: captured.append(value))

    display.print_agent_output("design", "**Bold** rollout with `gates`.", verbose=False)

    assert len(captured) == 1
    assert isinstance(captured[0], Panel)
    panel = captured[0]
    assert isinstance(panel.renderable, Markdown)


def test_print_agent_output_verbose_uses_markdown_panel(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(display.console, "print", lambda value: captured.append(value))

    display.print_agent_output("design", "- one\n- two", verbose=True)

    assert len(captured) == 1
    panel = captured[0]
    assert isinstance(panel.renderable, Markdown)


def test_print_agent_output_hides_evidence_json_in_verbose(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(display.console, "print", lambda value: captured.append(value))
    body = """Found files.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "find docs",
  "items": [],
  "gaps": []
}
```
"""

    display.print_agent_output("retrieval_planner", body, verbose=True)

    md = captured[0].renderable
    assert isinstance(md, Markdown)
    assert "Found files." in md.markup
    assert "evidence_bundle_v1" not in md.markup


def test_print_final_answer_hides_bare_evidence_json(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(display.console, "print", lambda value: captured.append(value))
    body = """Here are the documents.

{
  "schema_version": "evidence_bundle_v1",
  "request": "find docs",
  "items": [],
  "gaps": []
}
"""

    display.print_final_answer(body)

    md = captured[0].renderable
    assert isinstance(md, Markdown)
    assert "Here are the documents." in md.markup
    assert "evidence_bundle_v1" not in md.markup


def test_print_agent_output_hides_task_contract_json(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(display.console, "print", lambda value: captured.append(value))
    body = """Task selected.

```json
{
  "schema_version": "task_contract_v1",
  "primary_intent": "summarize_source",
  "deliverable_type": "deck_summary"
}
```

Ready.
"""

    display.print_agent_output("summary", body, verbose=True)

    md = captured[0].renderable
    assert isinstance(md, Markdown)
    assert "Task selected." in md.markup
    assert "Ready." in md.markup
    assert "task_contract_v1" not in md.markup


def test_print_agent_output_hides_structured_handoff_json(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(display.console, "print", lambda value: captured.append(value))
    body = """Structured retrieval handoff

```json
{
  "topics_activated": ["intent.summary"],
  "queries_expanded": ["summary"],
  "source_priority": ["generic_retrieval"]
}
```

Human note.
"""

    display.print_agent_output("retrieval_planner", body, verbose=True)

    md = captured[0].renderable
    assert isinstance(md, Markdown)
    assert "Structured retrieval handoff" in md.markup
    assert "Human note." in md.markup
    assert "topics_activated" not in md.markup
    assert "queries_expanded" not in md.markup


def test_print_agent_output_hides_bare_structured_handoff_json(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(display.console, "print", lambda value: captured.append(value))
    body = """Structured retrieval handoff

{
  "topics_activated": ["intent.summary"],
  "queries_expanded": ["summary"],
  "source_priority": ["generic_retrieval"]
}

Human note.
"""

    display.print_agent_output("retrieval_planner", body, verbose=True)

    md = captured[0].renderable
    assert isinstance(md, Markdown)
    assert "Structured retrieval handoff" in md.markup
    assert "Human note." in md.markup
    assert "topics_activated" not in md.markup
    assert "queries_expanded" not in md.markup


def test_print_final_answer_hides_unclosed_evidence_json_and_fence(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(display.console, "print", lambda value: captured.append(value))
    body = """Done.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "find docs",
  "items": []
"""

    display.print_final_answer(body)

    md = captured[0].renderable
    assert isinstance(md, Markdown)
    assert "Done." in md.markup
    assert "```json" not in md.markup
    assert "evidence_bundle_v1" not in md.markup


def test_sanitize_user_visible_text_removes_dangling_json_fence() -> None:
    result = display.sanitize_user_visible_text("Found files.\n\n```json")

    assert result == "Found files."


def test_print_agent_output_hides_nested_evidence_json(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(display.console, "print", lambda value: captured.append(value))
    body = """Here are the documents.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "find docs",
  "items": [
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "Deck.pptx",
        "open_url": "https://example.com/deck.pptx"
      },
      "evidence_level": "content_read",
      "read_status": "read",
      "read_tool": "read_sharepoint_document_by_handle",
      "content_excerpt": "Outline",
      "raw_error": ""
    }
  ],
  "gaps": [
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "Other deck.pptx"
      },
      "reason": "Not needed"
    }
  ]
}
```
"""

    display.print_agent_output("context_retrieval", body, verbose=True)

    md = captured[0].renderable
    assert isinstance(md, Markdown)
    assert "Here are the documents." in md.markup
    assert "evidence_bundle_v1" not in md.markup
    assert "Other deck.pptx" not in md.markup
    assert '"reason": "Not needed"' not in md.markup


def test_print_final_answer_hides_nested_bare_evidence_json(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(display.console, "print", lambda value: captured.append(value))
    body = """Here are the documents.

{
  "schema_version": "evidence_bundle_v1",
  "request": "find docs",
  "items": [
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "Deck.pptx"
      },
      "evidence_level": "content_read"
    }
  ],
  "gaps": [
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "Other deck.pptx"
      },
      "reason": "Not needed"
    }
  ]
}

Done.
"""

    display.print_final_answer(body)

    md = captured[0].renderable
    assert isinstance(md, Markdown)
    assert "Here are the documents." in md.markup
    assert "Done." in md.markup
    assert "evidence_bundle_v1" not in md.markup
    assert "Other deck.pptx" not in md.markup


def test_print_agent_output_non_verbose_markdown_is_short_summary_not_full_body(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(display.console, "print", lambda value: captured.append(value))

    long_body = "## Report\n\n" + ("First finding supports the compromise. " * 15)
    display.print_agent_output("context_synthesizer", long_body, verbose=False)

    panel = captured[0]
    md = panel.renderable
    assert isinstance(md, Markdown)
    assert md.markup.startswith("**Summary:**")
    assert len(md.markup) < len(long_body) * 0.6


def test_render_stage_output_text_matches_clean_default() -> None:
    body = """Retrieved the source.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "x",
  "items": []
}
```
"""

    result = display.render_stage_output_text("context_retrieval", body, verbose=False)

    assert result.startswith("**Summary:**")
    assert "Retrieved the source" in result
    assert "evidence_bundle_v1" not in result


def test_print_status_message_keeps_router_literal_text(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(display.console, "print", lambda value: captured.append(value))

    display.print_status_message("router:auto • pipeline • retrieval_planner", title="🧭 Routing decision")

    assert len(captured) == 1
