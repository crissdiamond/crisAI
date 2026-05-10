from crisai.orchestration.task_contract import infer_task_contract


def test_infer_summary_contract_for_latest_deck_request() -> None:
    contract = infer_task_contract("Summarise the latest Integration Strategy deck.")

    assert contract.primary_intent == "summarize_source"
    assert contract.deliverable_type == "deck_summary"
    assert contract.source_resolution == "latest_matching_source"
    assert contract.required_evidence_level == "content_read"


def test_infer_summary_contract_for_italian_document_request() -> None:
    contract = infer_task_contract("Riassumi questo documento.")

    assert contract.primary_intent == "summarize_source"
    assert contract.deliverable_type == "document_summary"


def test_infer_general_contract_for_find_only_request() -> None:
    contract = infer_task_contract("Find all Integration Strategy documents.")

    assert contract.primary_intent == "respond"
    assert contract.deliverable_type == "general_answer"
