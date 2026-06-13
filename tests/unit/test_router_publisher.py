from crisai.orchestration.router import decide_route


def test_route_publisher_for_template_based_document_request():
    decision = decide_route(
        "Turn this into a Word document using the template in workspace.",
        review_enabled=False,
    )

    assert decision.mode == "single"
    assert decision.agent == "publisher"
    assert decision.intent == "publication"
    assert decision.needs_retrieval is True
    assert decision.needs_review is False


def test_route_document_formatter_for_native_export_from_task_artifact():
    decision = decide_route(
        "Export workspace/tasks/reporting/artefacts/reporting-hld.md to .docx using the UCL HLD template manifest.",
        review_enabled=False,
    )

    assert decision.agent == "document_formatter"
    assert decision.intent == "document_export"
    assert decision.mode == "single"
    assert decision.needs_retrieval is True
