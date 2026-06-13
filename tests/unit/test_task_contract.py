from pathlib import Path

from crisai.orchestration.task_contract import infer_task_contract

REGISTRY_DIR = Path(__file__).resolve().parents[2] / "registry"


def test_infer_summary_contract_for_latest_deck_request() -> None:
    contract = infer_task_contract("Summarise the latest Integration Strategy deck.", registry_dir=REGISTRY_DIR)

    assert contract.primary_intent == "summarize_source"
    assert contract.deliverable_type == "deck_summary"
    assert contract.source_resolution == "latest_matching_source"
    assert contract.required_evidence_level == "content_read"


def test_infer_summary_contract_for_document_request() -> None:
    contract = infer_task_contract("Summarise this document.", registry_dir=REGISTRY_DIR)

    assert contract.primary_intent == "summarize_source"
    assert contract.deliverable_type == "document_summary"


def test_infer_source_inventory_contract_for_find_only_request() -> None:
    contract = infer_task_contract("Find all Integration Strategy documents.", registry_dir=REGISTRY_DIR)

    assert contract.primary_intent == "retrieve_source"
    assert contract.deliverable_type == "source_inventory"
    assert contract.source_resolution == "matching_source"
    assert contract.required_evidence_level == "metadata_read"


def test_infer_source_inventory_contract_for_newtest_source_discovery_wording() -> None:
    contract = infer_task_contract(
        "Search for files called Integration Strategy on my drive and select the 3 most relevant ones.",
        registry_dir=REGISTRY_DIR,
    )

    assert contract.primary_intent == "retrieve_source"
    assert contract.deliverable_type == "source_inventory"
    assert contract.source_resolution == "matching_source"
    assert contract.required_evidence_level == "metadata_read"


def test_ranking_language_without_source_context_is_not_source_inventory() -> None:
    for message in (
        "List the best approach for this implementation.",
        "Show me relevant ones from the previous answer.",
    ):
        contract = infer_task_contract(message, registry_dir=REGISTRY_DIR)

        assert contract.primary_intent != "retrieve_source"
        assert contract.deliverable_type != "source_inventory"


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
