from __future__ import annotations

from pathlib import Path

from crisai.cli.chat_context import continuation_intent_message
from crisai.orchestration.request_contract import (
    infer_request_contract,
    render_request_contract_brief,
)
from crisai.orchestration.session_anchors import SessionSourceCandidate

REGISTRY_DIR = Path(__file__).resolve().parents[2] / "registry"


def test_request_contract_detects_source_backed_workspace_artifact() -> None:
    contract = infer_request_contract(
        (
            "Search SharePoint/intranet context first. Find and read HLD%20Template.aspx. "
            "Using that page as the source of truth, create a generic HLD template and save it as "
            "`workspace/knowledge/reference/template/hld_generic.md`."
        ),
        registry_dir=REGISTRY_DIR,
    )

    assert contract.schema_version == "request_contract_v1"
    assert contract.source_required is True
    assert "intranet" in contract.source_families
    assert "sharepoint" in contract.source_families
    assert "HLD%20Template.aspx" in contract.named_sources
    assert contract.output_path == "workspace/knowledge/reference/template/hld_generic.md"
    assert contract.output_target_subdir == "workspace/knowledge/reference/template"
    assert "retrieve_source" in contract.actions
    assert "write_workspace_file" in contract.actions
    assert "workspace_file_changed" in contract.quality_gates


def test_request_contract_detects_explicit_pipeline_mode_from_catalog() -> None:
    contract = infer_request_contract(
        "Use the pipeline. Summarise the latest Integration Strategy document from OneDrive.",
        registry_dir=REGISTRY_DIR,
    )

    assert contract.workflow_preference == "pipeline"
    assert contract.is_summary is True
    assert contract.source_required is True


def test_request_contract_keeps_pasted_text_summary_source_free() -> None:
    contract = infer_request_contract("Summarise this text.", registry_dir=REGISTRY_DIR)

    assert contract.is_summary is True
    assert contract.source_required is False
    assert contract.actions == ("summarize",)


def test_request_contract_detects_source_inventory_as_main_ask() -> None:
    contract = infer_request_contract(
        "Find all the documents in my onedrive with Integration Strategy in the title and list the best 3 candidates",
        registry_dir=REGISTRY_DIR,
    )

    assert contract.primary_intent == "retrieve_source"
    assert contract.deliverable_type == "source_inventory"
    assert contract.source_required is True
    assert "personal_onedrive" in contract.source_families
    assert "retrieve_source" in contract.actions
    assert "summarize" not in contract.actions


def test_request_contract_detects_source_inventory_newtest_drive_wording() -> None:
    contract = infer_request_contract(
        "Search for files called Integration Strategy on my drive and select the 3 most relevant ones.",
        registry_dir=REGISTRY_DIR,
    )

    assert contract.primary_intent == "retrieve_source"
    assert contract.deliverable_type == "source_inventory"
    assert contract.source_required is True
    assert "personal_onedrive" in contract.source_families
    assert "retrieve_source" in contract.actions


def test_bare_continue_contract_preserves_previous_source_lookup_context() -> None:
    history = [
        (
            "user",
            "find all the documents in my onedrive with integration strategy in the title. "
            "List the 3 best candidate.",
        ),
        ("assistant", "I found 10 OneDrive documents with integration strategy in the title."),
    ]
    message = continuation_intent_message("continue", history, registry_dir=REGISTRY_DIR)

    contract = infer_request_contract(message, registry_dir=REGISTRY_DIR)

    assert contract.source_required is True
    assert "personal_onedrive" in contract.source_families
    assert "retrieve_source" in contract.actions


def test_request_contract_brief_is_human_readable_not_json() -> None:
    contract = infer_request_contract(
        "Use the pipeline. Summarise the latest Integration Strategy document from OneDrive.",
        registry_dir=REGISTRY_DIR,
    )

    rendered = render_request_contract_brief(contract, selected_mode="pipeline", selected_agent="summary")

    assert "Intent: summarize_source" in rendered
    assert "Deliverable: document_summary" in rendered
    assert "Workflow: pipeline" in rendered
    assert "Agent: summary" in rendered
    assert "```json" not in rendered
    assert "schema_version" not in rendered


def test_request_contract_resolves_followup_source_from_session_candidates() -> None:
    candidate = SessionSourceCandidate(
        title="UCL Integration Strategy_Full Presentation v2.pptx",
        source_family="sharepoint_docs",
        source_type="sharepoint_document",
        source_scope="sharepoint",
        open_url="https://liveuclac.sharepoint.com/sites/DataTeam/doc.pptx",
        location="Data & Integration Team",
        evidence_level="metadata_read",
        read_status="metadata_read",
        rank=3,
    )

    contract = infer_request_contract(
        "Please summarise in detail the Full presentation v2 deck, why the strategy, what is it, how, who and when.",
        registry_dir=REGISTRY_DIR,
        source_candidates=(candidate,),
    )

    assert contract.primary_intent == "summarize_source"
    assert contract.source_required is True
    assert "sharepoint_docs" in contract.source_families
    assert "sharepoint" in contract.source_families
    assert contract.resolved_sources
    assert contract.resolved_sources[0].source.title == "UCL Integration Strategy_Full Presentation v2.pptx"
    assert "UCL Integration Strategy_Full Presentation v2.pptx" in contract.named_sources
    assert "read_handle" not in contract.to_dict()["resolved_sources"][0]["source"]


def test_source_file_reference_is_not_publication() -> None:
    # CRISAI-ADR-014 / TODO-048: a referenced source file (a .pptx/.docx the user
    # wants to read/list/summarise) must not be classified as a publish request —
    # the publish_artifact mis-classification that killed completed runs.
    for msg in (
        "Summarize the UCL Integration Strategy_Full Presentation v2.pptx deck.",
        "List the decks: UCL Strategy v2.pptx and v3.pptx, ranked by authority.",
        "Find files in my OneDrive ending in .docx and rank them.",
    ):
        contract = infer_request_contract(msg, registry_dir=REGISTRY_DIR)
        assert "publish_artifact" not in contract.actions, msg


def test_produce_requests_still_classify_as_publication() -> None:
    for msg in (
        "Convert this architecture summary into a .pptx slide deck.",
        "Create a powerpoint of the integration strategy.",
        "Turn this into a Word document using the template.",
        "Export this design as a powerpoint.",
    ):
        contract = infer_request_contract(msg, registry_dir=REGISTRY_DIR)
        assert "publish_artifact" in contract.actions, msg


def test_produce_artefact_intents_draft_with_specific_deliverable() -> None:
    # Asks to produce an architecture artefact that already has a workspace
    # validation profile now classify to that deliverable type and draft it
    # (primary_intent design/recommend -> "draft" action), rather than falling
    # back to a generic deliverable or being mistaken for a publish request.
    cases = [
        ("Write the ADR for choosing Kafka over RabbitMQ.", "decision"),
        ("Produce the logical data model for the customer domain.", "data_model"),
        ("Create the integration design for the CRM-to-ERP interface.", "integration"),
        ("Build the migration plan to move off the legacy ESB.", "migration_plan"),
        ("Produce the source-to-target mapping document for the load.", "mapping"),
    ]
    for message, deliverable in cases:
        contract = infer_request_contract(message, registry_dir=REGISTRY_DIR)
        assert contract.deliverable_type == deliverable, message
        assert "draft" in contract.actions, message
        assert "publish_artifact" not in contract.actions, message


def test_continuation_folding_prior_deck_summary_is_not_publication() -> None:
    # Long-session reproduction: a follow-up turn whose continuation message folds
    # in the prior assistant's deck summary (full of .pptx names) must not become
    # a publish request (CRISAI-ADR-014).
    history = [
        ("user", "Find the UCL integration strategy decks in my OneDrive."),
        (
            "assistant",
            "I found four decks: UCL Integration Strategy_Full Presentation v2.pptx, "
            "UCL Integration Strategy full deck v3_cd.pptx, and two v1 variants (.pptx).",
        ),
    ]
    msg = continuation_intent_message("continue", history, registry_dir=REGISTRY_DIR)
    assert ".pptx" in msg  # confirm the prior summary (with source names) was folded in
    contract = infer_request_contract(msg, registry_dir=REGISTRY_DIR)
    assert "publish_artifact" not in contract.actions
