from pathlib import Path

from crisai.orchestration.task_contract import infer_task_contract

REGISTRY_DIR = Path(__file__).resolve().parents[2] / "registry"


def test_infer_summary_contract_for_latest_deck_request() -> None:
    contract = infer_task_contract("Summarise the latest Integration Strategy deck.", registry_dir=REGISTRY_DIR)

    assert contract.primary_intent == "summarize_source"
    assert contract.deliverable_type == "deck_summary"
    assert contract.source_resolution == "latest_matching_source"
    assert contract.required_evidence_level == "content_read"


def test_infer_summary_contract_for_italian_document_request() -> None:
    contract = infer_task_contract("Riassumi questo documento.", registry_dir=REGISTRY_DIR)

    assert contract.primary_intent == "summarize_source"
    assert contract.deliverable_type == "document_summary"


def test_infer_general_contract_for_find_only_request() -> None:
    contract = infer_task_contract("Find all Integration Strategy documents.", registry_dir=REGISTRY_DIR)

    assert contract.primary_intent == "respond"
    assert contract.deliverable_type == "general_answer"


def test_infer_sourced_recommendation_contract_for_architecture_advice() -> None:
    contract = infer_task_contract(
        (
            "Search workspace/knowledge before answering. I need a concise recommendation "
            "for a recurring monthly Power BI dashboard built from manually maintained Excel files."
        ),
        registry_dir=REGISTRY_DIR,
    )

    assert contract.primary_intent == "recommend"
    assert contract.deliverable_type == "architecture_recommendation"
    assert contract.required_evidence_level == "supporting_sources"


def test_infer_options_paper_contract_over_generic_recommendation() -> None:
    contract = infer_task_contract(
        "Prepare an options paper with a preferred recommendation for replacing the reporting platform.",
        registry_dir=REGISTRY_DIR,
    )

    assert contract.primary_intent == "recommend"
    assert contract.deliverable_type == "options_paper"
