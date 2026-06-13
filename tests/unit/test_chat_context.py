from __future__ import annotations

from pathlib import Path

from crisai.cli import chat_context


def _repo_catalog_path() -> Path:
    return Path(__file__).resolve().parents[2] / "registry"


def _repo_catalog():
    return chat_context.load_semantic_catalog(str(_repo_catalog_path()))


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


def test_build_chat_input_wraps_session_baseline_without_history(monkeypatch):
    captured = {}

    def fake_render_cli_text(template: str, **kwargs):
        captured["template"] = template
        captured["kwargs"] = kwargs
        return "wrapped"

    monkeypatch.setattr(chat_context, "render_cli_text", fake_render_cli_text)

    result = chat_context.build_runtime_context_package("hello", [], session_name="demo")

    assert result.prompt == "wrapped"
    assert "Active task context:" in captured["kwargs"]["transcript"]
    assert "workspace/tasks/demo" in captured["kwargs"]["transcript"]


def test_build_chat_input_normalises_legacy_context_path_without_history():
    assert chat_context.build_chat_input("Read workspace/context/templates/hld.md", []) == (
        "Read workspace/knowledge/templates/hld.md"
    )


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
    assert "Task goal:" in transcript
    assert "Known sources:" in transcript
    assert "knowledge/integration-strategy.md" in transcript
    assert "Relevant recent turns:" in transcript
    assert "User: Now continue with Integration Strategy details." in transcript


def test_continuation_intent_message_uses_previous_exchange() -> None:
    history = [
        ("user", "Find all documents in my OneDrive with integration strategy in the title."),
        (
            "assistant",
            "I found 10 OneDrive documents.\n\n"
            "| File | Note |\n"
            "|---|---|\n"
            "| UCL Integration Strategy full deck v3.pptx | Exact phrase. |",
        ),
    ]

    message = chat_context.continuation_intent_message(
        "continue",
        history,
        registry_dir=Path(__file__).resolve().parents[2] / "registry",
    )

    assert "Previous user request:" in message
    assert "Find all documents in my OneDrive" in message
    assert "Previous assistant result:" in message
    assert "| UCL Integration Strategy full deck v3.pptx | Exact phrase. |" in message
    assert "Current user instruction:" in message


def test_continuation_intent_message_folds_previous_exchange() -> None:
    history = [
        ("user", "Find documents in OneDrive with integration strategy in the title."),
        ("assistant", "I found 10 documents."),
    ]

    message = chat_context.continuation_intent_message(
        "continue",
        history,
        registry_dir=Path(__file__).resolve().parents[2] / "registry",
    )

    assert "Previous user request:" in message
    assert "Find documents in OneDrive" in message
    assert "Current user instruction:" in message
    assert message.endswith("continue")


def test_continuation_request_degrades_when_catalog_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(chat_context, "load_semantic_catalog", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("missing")))

    assert chat_context.is_continuation_request("continue") is False
    assert chat_context.continuation_intent_message(
        "continue",
        [("user", "Find OneDrive documents."), ("assistant", "Found documents.")],
    ) == "continue"


def test_bare_continuation_preserves_previous_assistant_table_in_runtime_context(monkeypatch):
    captured = {}

    def fake_render_cli_text(template: str, **kwargs):
        captured.update(kwargs)
        return "wrapped"

    monkeypatch.setattr(chat_context, "render_cli_text", fake_render_cli_text)
    history = [
        ("user", "Find all documents in my OneDrive with integration strategy in the title."),
        ("assistant", "Result:\n\n| File | Note |\n|---|---|\n| UCL Integration Strategy full deck v3.pptx | Exact phrase. |"),
    ]

    assert chat_context.build_chat_input("continue", history, session_name="demo") == "wrapped"
    assert "| UCL Integration Strategy full deck v3.pptx | Exact phrase. |" in captured["transcript"]


def test_runtime_context_package_normalises_legacy_context_path_in_wrapper(monkeypatch):
    captured = {}

    def fake_render_cli_text(template: str, **kwargs):
        captured.update(kwargs)
        return "wrapped"

    monkeypatch.setattr(chat_context, "render_cli_text", fake_render_cli_text)

    chat_context.build_runtime_context_package(
        "Open context/reference/template/hld.md",
        [("user", "prior"), ("assistant", "prior answer")],
    )

    assert captured["user_input"] == "Open workspace/knowledge/reference/template/hld.md"


def test_compact_memory_canonicalizes_workspace_prefix_sources():
    history = [
        ("user", "Use the local source."),
        ("assistant", "Read [reporting-standard.txt](file:///workspace/knowledge/standards/reporting-standard.txt)."),
        ("assistant", "Also used `knowledge/patterns/reporting-patterns.txt`."),
    ]

    memory = chat_context.compact_session_memory(history)

    assert "knowledge/standards/reporting-standard.txt" in memory.known_sources
    assert "knowledge/patterns/reporting-patterns.txt" in memory.known_sources


def test_compact_memory_extracts_sharepoint_source_candidates_from_inventory_table():
    history = [
        ("user", "Find Integration Strategy files."),
        (
            "assistant",
            "Found files:\n\n"
            "| File | Location | Note |\n"
            "|---|---|---|\n"
            "| [UCL Integration Strategy_Full Presentation v2.pptx]"
            "(https://liveuclac.sharepoint.com/sites/DataTeam/_layouts/15/Doc.aspx?file=x) "
            "| Data & Integration Team | Exact title phrase. |",
        ),
    ]

    memory = chat_context.compact_session_memory(history)

    assert memory.source_candidates
    candidate = memory.source_candidates[0]
    assert candidate.title == "UCL Integration Strategy_Full Presentation v2.pptx"
    assert candidate.source_family == "sharepoint_docs"
    assert candidate.source_type == "sharepoint_document"
    assert candidate.source_scope == "sharepoint"
    assert candidate.location == "Data & Integration Team"
    assert candidate.open_url.startswith("https://liveuclac.sharepoint.com/")
    assert not hasattr(candidate, "read_handle")


def test_compact_memory_extracts_evidence_source_candidates_without_read_handle():
    history = [
        ("user", "Summarise the deck."),
        (
            "assistant",
            """Retrieved source.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "Summarise the deck.",
  "items": [
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "UCL Integration Strategy_Full Presentation v2.pptx",
        "open_url": "https://liveuclac.sharepoint.com/sites/DataTeam/doc.pptx",
        "read_handle": "sharepoint_doc:secret",
        "metadata": {
          "read_handle": "sharepoint_doc:nested-secret",
          "site_display_name": "Data & Integration Team"
        }
      },
      "evidence_level": "content_read",
      "read_status": "read"
    }
  ],
  "gaps": []
}
```
""",
        ),
    ]

    memory = chat_context.compact_session_memory(history)
    payload = memory.source_candidates[0].to_dict()

    assert payload["title"] == "UCL Integration Strategy_Full Presentation v2.pptx"
    assert payload["evidence_level"] == "content_read"
    assert "read_handle" not in payload
    assert "read_handle" not in payload["metadata"]
    assert payload["metadata"]["site_display_name"] == "Data & Integration Team"


def test_persist_session_source_candidates_from_single_output(tmp_path, monkeypatch):
    from crisai.cli import session_store

    settings = type("Settings", (), {"workspace_dir": tmp_path, "registry_dir": _repo_catalog_path()})()
    monkeypatch.setattr(session_store, "load_settings", lambda: settings)
    monkeypatch.setattr(chat_context, "load_settings", lambda: settings)

    output = (
        "Found files:\n\n"
        "| File | Location | Note |\n"
        "|---|---|---|\n"
        "| [UCL Integration Strategy_Full Presentation v2.pptx]"
        "(https://liveuclac.sharepoint.com/sites/DataTeam/_layouts/15/Doc.aspx?sourcedoc=%7BDD876D07-51C7-54B0-8ACE-E78B49D3F954%7D&file=v2.pptx) "
        "| OneDrive | Exact title phrase. |\n"
    )

    candidates = chat_context.persist_session_source_candidates_from_output("NewTest-04", output)
    memory = session_store.load_session_memory("NewTest-04")

    assert len(candidates) == 1
    assert memory.source_candidates[0].title == "UCL Integration Strategy_Full Presentation v2.pptx"
    assert memory.source_candidates[0].source_family == "sharepoint_docs"
    assert memory.source_candidates[0].source_type == "sharepoint_document"


def test_update_session_memory_preserves_previously_persisted_source_candidates(tmp_path, monkeypatch):
    from crisai.cli import session_store

    settings = type("Settings", (), {"workspace_dir": tmp_path, "registry_dir": _repo_catalog_path()})()
    monkeypatch.setattr(session_store, "load_settings", lambda: settings)
    monkeypatch.setattr(chat_context, "load_settings", lambda: settings)

    chat_context.persist_session_source_candidates_from_output(
        "NewTest-04",
        "[Deck.pptx](https://liveuclac.sharepoint.com/sites/DataTeam/doc.pptx)",
    )
    memory = chat_context.update_session_memory(
        "NewTest-04",
        [("user", "Please summarise it."), ("assistant", "Summary without links.")],
    )

    assert memory.source_candidates
    assert memory.source_candidates[0].title == "Deck.pptx"


def test_source_candidate_dedupe_uses_sourcedoc_guid():
    history = [
        ("user", "Find files."),
        (
            "assistant",
            "| File | Location | Note |\n"
            "|---|---|---|\n"
            "| [Deck A.pptx](https://tenant.sharepoint.com/doc.aspx?sourcedoc=%7B4844F689-9858-498C-A888-95D025216DA8%7D&file=a.pptx) | OneDrive | A |\n"
            "| [Deck B.pptx](https://tenant.sharepoint.com/doc.aspx?sourcedoc=%7B4844F689-9858-498C-A888-95D025216DA8%7D&file=b.pptx) | OneDrive | B |",
        ),
    ]

    memory = chat_context.compact_session_memory(history)

    assert len(memory.source_candidates) == 1
    assert memory.source_candidates[0].title == "Deck A.pptx"


def test_source_type_inference_uses_semantic_catalog_markers():
    sharepoint_history = [
        ("user", "Find files."),
        (
            "assistant",
            "[Deck.pptx](https://liveuclac.sharepoint.com/sites/DataTeam/doc.pptx)",
        ),
    ]
    workspace_history = [
        ("user", "Use local source."),
        ("assistant", "Read [note.md](file:///workspace/knowledge/note.md)."),
    ]

    sharepoint_memory = chat_context.compact_session_memory(sharepoint_history)
    workspace_memory = chat_context.compact_session_memory(workspace_history)

    assert sharepoint_memory.source_candidates[0].source_type == "sharepoint_document"
    assert workspace_memory.source_candidates[0].source_type == "workspace_file"


def test_compact_memory_extracts_v2_structured_fields(monkeypatch):
    chat_context.load_semantic_catalog.cache_clear()
    catalog = _repo_catalog()
    monkeypatch.setattr(chat_context, "load_semantic_catalog", lambda: catalog)
    history = [
        ("user", "Build a reporting architecture. Must stay local. Assume Power BI is retained."),
        (
            "assistant",
            "Recommended approach should use semantic models. Rejected option: direct Excel extracts. "
            "Source finding: reporting standard requires certified datasets. Next action: draft the artefact.",
        ),
    ]

    memory = chat_context.compact_session_memory(history)

    assert memory.schema_version == "session_memory_v2"
    assert memory.scope
    assert any("Power BI" in item for item in memory.assumptions)
    assert any("Must stay local" in item for item in memory.constraints)
    assert any("Rejected option" in item for item in memory.rejected_options)
    assert any("Source finding" in item for item in memory.source_findings)
    assert any("Next action" in item for item in memory.next_actions)


def test_compact_memory_uses_semantic_catalog_session_memory_terms(monkeypatch):
    catalog = _repo_catalog()
    custom_catalog = type(catalog)(
        router=catalog.router,
        peer_verifier=catalog.peer_verifier,
        peer_contract=catalog.peer_contract,
        peer_judge=catalog.peer_judge,
        lexicon=catalog.lexicon,
        retrieval_constraints=catalog.retrieval_constraints,
        interaction=catalog.interaction,
        artifact_lifecycle=catalog.artifact_lifecycle,
        session_anchors=catalog.session_anchors,
        session_memory=type(catalog.session_memory)(
            decision_markers=frozenset({"chosen"}),
            rejected_option_markers=frozenset({"discarded"}),
            assumption_markers=frozenset({"given"}),
            constraint_markers=frozenset({"bounded"}),
            source_finding_markers=frozenset({"observed"}),
            next_action_markers=frozenset({"afterwards"}),
            open_question_starters=frozenset({"whether"}),
        ),
    )
    monkeypatch.setattr(chat_context, "load_semantic_catalog", lambda: custom_catalog)
    history = [
        ("user", "Build a reporting architecture. Given Power BI. Bounded to local sources. Whether model A?"),
        (
            "assistant",
            "Chosen approach keeps semantic models. Discarded direct extracts. "
            "Observed the reporting standard. Afterwards draft the artefact.",
        ),
    ]

    memory = chat_context.compact_session_memory(history)

    assert memory.important_decisions == ["Chosen approach keeps semantic models."]
    assert memory.rejected_options == ["Discarded direct extracts."]
    assert memory.assumptions == ["Given Power BI."]
    assert memory.constraints == ["Bounded to local sources."]
    assert memory.source_findings == ["Observed the reporting standard."]
    assert memory.next_actions == ["Afterwards draft the artefact."]
    assert memory.open_questions == ["Whether model A?"]


def test_content_terms_fail_soft_when_semantic_catalog_unavailable(monkeypatch):
    monkeypatch.setattr(chat_context, "load_semantic_catalog", lambda: (_ for _ in ()).throw(RuntimeError("missing")))

    assert "about" in chat_context._content_terms("about reporting target")
    assert chat_context.compact_session_memory([("user", "Create reporting target architecture.")]).task_goal


def test_compact_memory_preserves_initial_task_goal_across_followups():
    history = [
        ("user", "Create an enterprise reporting architecture options paper for finance leadership."),
        ("assistant", "Drafted the initial options paper and recommended option 2."),
        ("user", "Add a risk section."),
        ("assistant", "Added delivery and data quality risks."),
        ("user", "Update option 2 with the governance caveat."),
    ]

    memory = chat_context.compact_session_memory(history)

    assert memory.task_goal == "Create an enterprise reporting architecture options paper for finance leadership."
    assert "Update option 2" in memory.scope[0]


def test_compact_memory_ignores_runtime_failure_notes():
    history = [
        ("user", "Create a Power BI recommendation."),
        ("assistant", "Request failed: RuntimeError: asyncio.run() cannot be called from a running event loop"),
    ]

    memory = chat_context.compact_session_memory(history)

    assert "Request failed" not in memory.current_state
    assert "RuntimeError" not in memory.current_state
    assert memory.last_outputs == []


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


def test_recall_session_memory_scores_with_provenance(monkeypatch):
    memory = chat_context.SessionMemory(
        task_goal="Design reporting architecture.",
        important_decisions=["Use certified semantic models for reporting."],
        source_findings=["Reporting standard requires certified datasets."],
    )
    monkeypatch.setattr(chat_context, "load_history_for_recall", lambda _: [])

    results = chat_context.recall_session_memory(
        "demo",
        "certified reporting datasets",
        memory=memory,
        registry_dir=None,
    )

    assert results
    assert results[0].score > 0
    assert results[0].provenance.startswith("memory.")
    assert "reporting" in results[0].matched_terms


def test_build_session_context_package_serializes_recall(monkeypatch):
    monkeypatch.setattr(
        chat_context,
        "load_session_memory",
        lambda _: chat_context.SessionMemory(task_goal="Review integration design."),
    )
    monkeypatch.setattr(chat_context, "load_history_for_recall", lambda _: [])

    package = chat_context.build_session_context_package("demo", query="integration", registry_dir=None)
    payload = chat_context.serialize_session_context(package)

    assert payload["schema_version"] == "ui_session_context_v1"
    assert payload["session"] == "demo"
    assert "Active task context" in payload["baseline_brief"]
    assert payload["budget"]["baseline_chars"] == len(payload["baseline_brief"])


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
