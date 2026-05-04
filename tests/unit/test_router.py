from crisai.orchestration.router import decide_route


def test_route_discovery_only_for_source_lookup():
    decision = decide_route(
        "Search SharePoint for documents about integration strategy and return only a table.",
        review_enabled=False,
    )

    assert decision.mode == "single"
    assert decision.agent == "retrieval_planner"
    assert decision.needs_retrieval is True
    assert decision.needs_review is False


def test_route_discovery_for_architecture_site_retrieval_query():
    decision = decide_route(
        "Find all the documents in the Architecture sites on SharePoint about the integration strategy.",
        review_enabled=False,
    )

    assert decision.mode == "single"
    assert decision.agent == "retrieval_planner"
    assert decision.needs_retrieval is True
    assert decision.needs_review is False


def test_route_pipeline_for_source_based_design():
    decision = decide_route(
        "Find the docs about command handling and propose a simple design improvement.",
        review_enabled=False,
    )

    assert decision.mode == "pipeline"
    assert decision.agent == "retrieval_planner"
    assert decision.needs_retrieval is True
    assert decision.needs_review is True


def test_route_pipeline_for_design_plus_review_without_sources():
    decision = decide_route(
        "Propose a simple CLI design and critique the main weaknesses.",
        review_enabled=False,
    )

    assert decision.mode == "pipeline"
    assert decision.agent == "design"
    assert decision.needs_retrieval is False
    assert decision.needs_review is True


def test_route_peer_when_peer_workflow_is_requested():
    decision = decide_route(
        "Use peer mode. The author should propose, the challenger should criticise, the refiner should improve, and the judge should decide.",
        review_enabled=False,
    )

    assert decision.mode == "peer"
    assert decision.agent == "design_author"
    assert decision.needs_review is True


def test_route_pipeline_for_broad_mixed_prompt():
    decision = decide_route(
        "Summarise this architecture, critique weak assumptions, and improve the proposal.",
        review_enabled=False,
    )

    assert decision.mode == "pipeline"
    assert decision.agent == "design"
    assert decision.needs_retrieval is False
    assert decision.needs_review is True


def test_route_operations_for_debugging_requests():
    decision = decide_route(
        "Debug this traceback and fix the import error in the CLI.",
        review_enabled=False,
    )

    assert decision.mode == "single"
    assert decision.agent == "operations"
    assert decision.needs_retrieval is False


def test_explicit_peer_mode_keeps_retrieval_when_sources_are_requested():
    decision = decide_route(
        "Find documents in SharePoint and debate the best design.",
        review_enabled=False,
        current_mode="peer",
    )

    assert decision.mode == "peer"
    assert decision.agent == "design_author"
    assert decision.needs_retrieval is True
    assert decision.needs_review is True


def test_explicit_agent_override_wins_over_router():
    decision = decide_route(
        "Please propose a design and challenge it.",
        review_enabled=True,
        selected_agent="orchestrator",
    )

    assert decision.mode == "single"
    assert decision.agent == "orchestrator"
    assert decision.needs_retrieval is False
