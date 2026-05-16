from __future__ import annotations

from pathlib import Path

from crisai.orchestration.request_contract import infer_request_contract

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
