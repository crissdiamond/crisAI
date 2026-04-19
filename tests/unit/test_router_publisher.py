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


def test_route_publisher_for_slide_request_in_italian():
    decision = decide_route(
        "Crea una presentazione usando il template nel workspace.",
        review_enabled=False,
    )

    assert decision.mode == "single"
    assert decision.agent == "publisher"
    assert decision.intent == "publication"
