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


# ---------------------------------------------------------------------------
# Catalog-backed display functions
# ---------------------------------------------------------------------------


def _make_fake_catalog(sc_mod, *, signatures=None, boilerplate=()):
    """Build a fake SemanticCatalog with custom display patterns."""
    import re

    orig = sc_mod.load_semantic_catalog()
    fake_verifier = sc_mod.PeerVerifierPatterns(
        pattern_gap_line=orig.peer_verifier.pattern_gap_line,
        leaf_file_pattern=orig.peer_verifier.leaf_file_pattern,
        leaf_file_terms=orig.peer_verifier.leaf_file_terms,
        data_architecture_terms=orig.peer_verifier.data_architecture_terms,
        intranet_evidence_positive_marker=orig.peer_verifier.intranet_evidence_positive_marker,
        intranet_evidence_negative_markers=orig.peer_verifier.intranet_evidence_negative_markers,
        agent_output_signatures=signatures if signatures is not None else {},
        boilerplate_strip_patterns=tuple(boilerplate),
    )
    return sc_mod.SemanticCatalog(
        router=orig.router,
        peer_verifier=fake_verifier,
        peer_contract=orig.peer_contract,
        lexicon=orig.lexicon,
        retrieval_constraints=orig.retrieval_constraints,
    )


def test_strip_compact_agent_prefix_reads_signatures_from_catalog(monkeypatch):
    """_strip_compact_agent_prefix uses agent_output_signatures from the catalog."""
    import re
    from crisai.orchestration import semantic_catalog as sc_mod
    from crisai.cli.display import _strip_compact_agent_prefix

    fake_catalog = _make_fake_catalog(
        sc_mod,
        signatures={"custom_agent": re.compile(r"^CUSTOM PREFIX:\s*", re.I)},
    )
    sc_mod.load_semantic_catalog.cache_clear()
    monkeypatch.setattr(display, "load_semantic_catalog", lambda *a, **kw: fake_catalog)

    result = _strip_compact_agent_prefix("custom_agent", "CUSTOM PREFIX: the actual content")
    assert result == "the actual content"

    # real catalog signatures no longer in effect
    result2 = _strip_compact_agent_prefix("review", "The Review notes: something")
    assert result2 == "The Review notes: something"


def test_clean_agent_text_reads_boilerplate_from_catalog(monkeypatch):
    """_clean_agent_text uses boilerplate_strip_patterns from the catalog."""
    import re
    from crisai.orchestration import semantic_catalog as sc_mod
    from crisai.cli.display import _clean_agent_text

    fake_catalog = _make_fake_catalog(
        sc_mod,
        boilerplate=[re.compile(r"^CUSTOM BOILERPLATE\s+", re.I)],
    )
    sc_mod.load_semantic_catalog.cache_clear()
    monkeypatch.setattr(display, "load_semantic_catalog", lambda *a, **kw: fake_catalog)

    result = _clean_agent_text("CUSTOM BOILERPLATE real content here")
    assert result == "real content here"

    # original boilerplate no longer stripped
    result2 = _clean_agent_text("peer conversation should remain")
    assert "peer conversation" in result2
