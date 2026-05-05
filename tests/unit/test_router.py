from types import SimpleNamespace
from pathlib import Path

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


def test_route_peer_for_high_criticality_design_without_peer_keywords():
    decision = decide_route(
        "Find source docs and propose an architecture option for a mission critical rollout with high accuracy requirements.",
        review_enabled=False,
    )

    assert decision.mode == "peer"
    assert decision.agent == "design_author"
    assert decision.needs_retrieval is True
    assert decision.needs_review is True


def test_criticality_does_not_promote_retrieval_only_prompt_to_peer():
    decision = decide_route(
        "High accuracy needed: find the latest documents in SharePoint and return only a table.",
        review_enabled=False,
    )

    assert decision.mode == "single"
    assert decision.agent == "retrieval_planner"
    assert decision.needs_retrieval is True
    assert decision.needs_review is False


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


def test_router_uses_loaded_semantic_catalog_terms(monkeypatch):
    fake_terms = SimpleNamespace(
        discovery_terms=frozenset({"needleterm"}),
        design_terms=frozenset(),
        review_terms=frozenset(),
        operations_terms=frozenset(),
        peer_terms=frozenset(),
        publication_terms=frozenset(),
        explicit_discovery_patterns=frozenset(),
        explicit_peer_patterns=frozenset(),
        criticality_terms=frozenset(),
        source_markers=frozenset({"needleterm"}),
        architecture_location_markers=frozenset(),
    )
    monkeypatch.setattr(
        "crisai.orchestration.router.load_semantic_catalog",
        lambda: SimpleNamespace(router=fake_terms),
    )

    decision = decide_route("needleterm", review_enabled=False)

    assert decision.mode == "single"
    assert decision.agent == "retrieval_planner"


def test_router_uses_deterministic_nudge_for_retrieval(monkeypatch):
    fake_terms = SimpleNamespace(
        discovery_terms=frozenset(),
        design_terms=frozenset(),
        review_terms=frozenset(),
        operations_terms=frozenset(),
        peer_terms=frozenset(),
        publication_terms=frozenset(),
        explicit_discovery_patterns=frozenset(),
        explicit_peer_patterns=frozenset(),
        criticality_terms=frozenset(),
        source_markers=frozenset(),
        architecture_location_markers=frozenset(),
    )
    monkeypatch.setattr(
        "crisai.orchestration.router.load_semantic_catalog",
        lambda: SimpleNamespace(router=fake_terms),
    )
    fake_context = SimpleNamespace(
        is_active=True,
        suggested_sources=frozenset({"intranet"}),
    )
    monkeypatch.setattr(
        "crisai.orchestration.router.deterministic_context_from_registry",
        lambda text, registry_dir: (fake_context, True),
    )
    decision = decide_route(
        "please gather integration guidance",
        review_enabled=False,
        registry_dir=Path("/tmp/registry"),
    )
    assert decision.agent == "retrieval_planner"
    assert decision.needs_retrieval is True
