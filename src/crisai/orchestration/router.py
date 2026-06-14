from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from crisai.orchestration import request_contract as request_module
from crisai.orchestration import retrieval_association_graph as graph_module
from crisai.orchestration import semantic_catalog as catalog_module


@dataclass
class RoutingDecision:
    intent: str
    mode: str
    agent: str | None
    needs_retrieval: bool
    needs_review: bool
    confidence: float
    reason: str


# Pins and saved sessions may still use the pre-rename agent id.
_LEGACY_AGENT_ALIASES = {"discovery": "retrieval_planner"}


def _normalize_explicit_agent(agent_id: str | None) -> str | None:
    """Normalizes the explicit agent ID, translating legacy names.

    Args:
        agent_id: The logical identifier of the agent, or None.

    Returns:
        The normalized agent identifier, or None.
    """
    if agent_id is None:
        return None
    return _LEGACY_AGENT_ALIASES.get(agent_id, agent_id)


def normalize_agent_id(agent_id: str | None) -> str | None:
    """Returns the registry agent id, mapping legacy IDs.

    Args:
        agent_id: The logical agent identifier, or None.

    Returns:
        The normalized registry agent identifier, or None.
    """
    return _normalize_explicit_agent(agent_id)


def _normalise(text: str) -> str:
    """Normalizes input text by folding case, stripping, and collapsing spaces.

    Args:
        text: The raw input string.

    Returns:
        The normalized whitespace-collapsed lowercase string.
    """
    return " ".join(text.lower().strip().split())


def _contains_any(text: str, phrases: frozenset[str]) -> bool:
    """Checks if any of the specified phrases are present in the text.

    Args:
        text: The string to search within.
        phrases: A set of substring phrases to check.

    Returns:
        True if at least one phrase is found in the text, otherwise False.
    """
    return any(phrase in text for phrase in phrases)


def _is_native_document_export(text: str) -> bool:
    """Returns whether a request asks to export an existing artefact to a native file.

    Args:
        text: The normalized query text.

    Returns:
        True if the request indicates a native document export request.
    """
    markers = load_semantic_catalog().peer_contract
    return (
        _contains_any(text, markers.document_export_native_markers)
        and _contains_any(text, markers.document_export_source_markers)
    )


def _deterministic_source_nudge(text: str, registry_dir: Path | None) -> bool:
    """Returns whether deterministic graph expansion points to a retrieval source.

    Args:
        text: The normalized query text.
        registry_dir: The directory containing the registry configurations.

    Returns:
        True if the deterministic association graph indicates retrieval is required.
    """
    if registry_dir is None:
        return False
    context, graph_loaded = deterministic_context_from_registry(text, registry_dir)
    if not graph_loaded or not context.is_active:
        return False
    return bool({"intranet", "sharepoint_docs", "workspace"} & set(context.suggested_sources))


def _route_from_contract(contract: request_module.RequestContract, review_enabled: bool) -> RoutingDecision:
    """Infers the routing decision based on the request contract hints.

    Args:
        contract: The parsed request contract structure.
        review_enabled: Whether peer/pipeline review features are enabled.

    Returns:
        The RoutingDecision containing intent, mode, agent, and flags.
    """
    if contract.has_hint("retrieval_only"):
        return RoutingDecision(
            intent="discovery",
            mode="single",
            agent="retrieval_planner",
            needs_retrieval=True,
            needs_review=False,
            confidence=0.99,
            reason="Prompt explicitly requests retrieval-only behaviour.",
        )

    if contract.has_hint("operations"):
        return RoutingDecision(
            intent="operations",
            mode="single",
            agent="operations",
            needs_retrieval=False,
            needs_review=False,
            confidence=0.90,
            reason="Prompt looks like debugging or platform troubleshooting.",
        )

    if contract.has_hint("native_document_export"):
        return RoutingDecision(
            intent="document_export",
            mode="single",
            agent="document_formatter",
            needs_retrieval=True,
            needs_review=False,
            confidence=0.94,
            reason="Prompt asks to export an existing artefact into a native document format using a template.",
        )

    if contract.workflow_preference == "pipeline":
        return RoutingDecision(
            intent="source_backed_publication" if contract.has_hint("publication") and contract.source_required else "pipeline",
            mode="pipeline",
            agent="retrieval_planner" if contract.source_required else "design",
            needs_retrieval=contract.source_required,
            needs_review=review_enabled or contract.has_hint("review"),
            confidence=1.0,
            reason="Mode explicitly set to pipeline by user.",
        )

    if contract.workflow_preference == "peer":
        return RoutingDecision(
            intent="peer_review",
            mode="peer",
            agent="design_author",
            needs_retrieval=contract.source_required,
            needs_review=True,
            confidence=1.0,
            reason="Mode explicitly set to peer by user.",
        )

    if contract.workflow_preference == "single":
        agent = _single_agent_for_contract(contract)
        return RoutingDecision(
            intent=agent or "single",
            mode="single",
            agent=agent,
            needs_retrieval=agent in {"retrieval_planner", "publisher", "document_formatter"},
            needs_review=agent == "review",
            confidence=1.0,
            reason="Mode explicitly set to single by user.",
        )

    if (
        contract.primary_intent == "retrieve_source"
        and contract.deliverable_type == "source_inventory"
        and contract.required_evidence_level == "metadata_read"
        and contract.source_required
        # A pure listing only. If the ask also writes/publishes the result (output
        # path or publication intent), fall through to the publication route so the
        # write is not dropped on the lightweight discovery path.
        and not contract.output_path
        and not contract.has_hint("publication")
    ):
        return RoutingDecision(
            intent="discovery",
            mode="single",
            agent="retrieval_planner",
            needs_retrieval=True,
            needs_review=False,
            confidence=0.96,
            reason="The structured task contract identifies a metadata-only source inventory request.",
        )

    if contract.has_hint("publication") and contract.source_required:
        return RoutingDecision(
            intent="source_backed_publication",
            mode="pipeline",
            agent="retrieval_planner",
            needs_retrieval=True,
            needs_review=review_enabled,
            confidence=0.91,
            reason="Prompt asks to retrieve source material and generate or save a publication artefact; pipeline is required.",
        )

    if contract.has_hint("publication"):
        return RoutingDecision(
            intent="publication",
            mode="single",
            agent="publisher",
            needs_retrieval=True,
            needs_review=False,
            confidence=0.93,
            reason="Prompt asks to package output into a formal artefact using templates or a requested document format.",
        )

    if contract.is_summary and contract.source_required:
        return RoutingDecision(
            intent="summary",
            mode="pipeline",
            agent="retrieval_planner",
            needs_retrieval=True,
            needs_review=False,
            confidence=0.91,
            reason="Prompt asks for a summary of source material; pipeline runs retrieval and summary drafting.",
        )

    if contract.has_hint("criticality") and (
        contract.has_hint("design")
        or contract.has_hint("review")
        or (contract.source_required and contract.has_hint("design"))
    ):
        return RoutingDecision(
            intent="critical_peer_review",
            mode="peer",
            agent="design_author",
            needs_retrieval=contract.source_required,
            needs_review=True,
            confidence=0.93,
            reason="Prompt signals high-criticality/high-accuracy design work; peer challenge and judgement are preferred over pipeline.",
        )

    if contract.has_hint("peer"):
        return RoutingDecision(
            intent="peer_review",
            mode="peer",
            agent="design_author",
            needs_retrieval=contract.source_required,
            needs_review=True,
            confidence=0.92,
            reason="Prompt requests peer-style proposal, challenge, refinement, and judgement.",
        )

    if contract.source_required and contract.has_hint("design"):
        return RoutingDecision(
            intent="discovery_design",
            mode="pipeline",
            agent="retrieval_planner",
            needs_retrieval=True,
            needs_review=True,
            confidence=0.89,
            reason="Prompt combines source lookup with drafting or synthesis; pipeline runs with review for quality control on complex multi-stage work.",
        )

    if contract.has_hint("design") and contract.has_hint("review"):
        return RoutingDecision(
            intent="design_review",
            mode="pipeline",
            agent="design",
            needs_retrieval=False,
            needs_review=True,
            confidence=0.86,
            reason="Prompt asks for both proposal and critique, so a pipeline is more suitable than design-only or review-only.",
        )

    if contract.has_hint("review") and not contract.has_hint("design") and not contract.source_required:
        return RoutingDecision(
            intent="review",
            mode="single",
            agent="review",
            needs_retrieval=False,
            needs_review=True,
            confidence=0.85,
            reason="Prompt primarily focuses on critique or evaluation.",
        )

    if contract.is_summary:
        return RoutingDecision(
            intent="summary",
            mode="single",
            agent="summary",
            needs_retrieval=False,
            needs_review=False,
            confidence=0.86,
            reason="Prompt primarily asks for a summary without a clear retrieval source.",
        )

    if contract.has_hint("mixed_complexity"):
        return RoutingDecision(
            intent="mixed_complexity",
            mode="pipeline",
            agent="design",
            needs_retrieval=False,
            needs_review=True,
            confidence=0.78,
            reason="Prompt contains mixed design/review/retrieval signals; pipeline with review is safer than single-agent fallback.",
        )

    if contract.has_hint("design"):
        return RoutingDecision(
            intent="design",
            mode="single",
            agent="design",
            needs_retrieval=False,
            needs_review=False,
            confidence=0.82,
            reason="Prompt primarily asks for drafting or architecture output.",
        )

    if contract.source_required or contract.has_hint("source_lookup"):
        return RoutingDecision(
            intent="discovery",
            mode="single",
            agent="retrieval_planner",
            needs_retrieval=True,
            needs_review=False,
            confidence=0.85,
            reason="Prompt primarily asks for finding or inspecting sources.",
        )

    return RoutingDecision(
        intent="orchestrator",
        mode="single",
        agent="orchestrator",
        needs_retrieval=False,
        needs_review=False,
        confidence=0.50,
        reason="No strong routing signal detected; using orchestrator fallback.",
    )


def _single_agent_for_contract(contract: request_module.RequestContract) -> str:
    """Determines the single fallback agent based on request contract hints.

    Args:
        contract: The parsed request contract structure.

    Returns:
        The logical string identifier of the chosen agent.
    """
    if contract.has_hint("native_document_export"):
        return "document_formatter"
    if contract.source_required or contract.has_hint("source_lookup"):
        return "retrieval_planner"
    if contract.has_hint("publication"):
        return "publisher"
    if contract.has_hint("review"):
        return "review"
    if contract.is_summary:
        return "summary"
    if contract.has_hint("design"):
        return "design"
    if contract.has_hint("operations"):
        return "operations"
    return "orchestrator"


def _infer_auto_route(text: str, review_enabled: bool, *, registry_dir: Path | None = None) -> RoutingDecision:
    """Infers the routing decision automatically from the raw user query text.

    Args:
        text: The normalized query string.
        review_enabled: Whether peer/pipeline review features are enabled.
        registry_dir: Optional path to the registry configurations.

    Returns:
        The inferred RoutingDecision.
    """
    try:
        catalog = load_semantic_catalog(str(registry_dir)) if registry_dir is not None else load_semantic_catalog()
    except TypeError:
        catalog = load_semantic_catalog()
    deterministic_context = None
    if registry_dir is not None:
        context, graph_loaded = deterministic_context_from_registry(text, registry_dir)
        deterministic_context = context if graph_loaded else None
    deterministic_nudge = _deterministic_source_nudge(text, registry_dir)
    contract = request_module.infer_request_contract(
        text,
        registry_dir=registry_dir,
        catalog=catalog,
        deterministic_context=deterministic_context,
    )
    if deterministic_nudge and not contract.source_required:
        contract = replace(
            contract,
            source_required=True,
            source_families=tuple(dict.fromkeys((*contract.source_families, "deterministic"))),
            route_hints=tuple(dict.fromkeys((*contract.route_hints, "source_required", "source_lookup"))),
        )
    return _route_from_contract(contract, review_enabled=review_enabled)


def _apply_explicit_overrides(
    base: RoutingDecision,
    *,
    current_mode: str | None,
    selected_agent: str | None,
    review_enabled: bool,
) -> RoutingDecision:
    """Applies user-specified overrides (agent/mode) to a base RoutingDecision.

    Args:
        base: The automatically inferred RoutingDecision.
        current_mode: The workflow mode explicitly requested by the user, if any.
        selected_agent: The agent ID explicitly requested by the user, if any.
        review_enabled: Whether review features are enabled.

    Returns:
        The modified RoutingDecision reflecting the overrides.
    """
    if selected_agent is not None:
        return RoutingDecision(
            intent="explicit",
            mode="single",
            agent=selected_agent,
            needs_retrieval=selected_agent in {"retrieval_planner", "publisher", "document_formatter"},
            needs_review=selected_agent == "review",
            confidence=1.0,
            reason="Agent explicitly selected by user.",
        )

    if current_mode is None:
        return base

    if current_mode == "peer":
        return RoutingDecision(
            intent="explicit",
            mode="peer",
            agent="design_author",
            needs_retrieval=base.needs_retrieval,
            needs_review=True,
            confidence=1.0,
            reason="Mode explicitly set to peer by user.",
        )

    if current_mode == "pipeline":
        return RoutingDecision(
            intent="explicit",
            mode="pipeline",
            agent=base.agent if base.agent in {"retrieval_planner", "design"} else "design",
            needs_retrieval=base.needs_retrieval,
            needs_review=review_enabled or base.needs_review,
            confidence=1.0,
            reason="Mode explicitly set to pipeline by user.",
        )

    return RoutingDecision(
        intent="explicit",
        mode="single",
        agent=base.agent,
        needs_retrieval=base.agent in {"retrieval_planner", "publisher", "document_formatter"},
        needs_review=base.agent == "review",
        confidence=1.0,
        reason="Mode explicitly set to single by user.",
    )


def decide_route(
    user_input: str,
    review_enabled: bool,
    current_mode: str | None = None,
    selected_agent: str | None = None,
    registry_dir: Path | None = None,
) -> RoutingDecision:
    """Determines the final routing decision for a given user input.

    Args:
        user_input: The raw prompt text from the user.
        review_enabled: Whether peer/pipeline review features are enabled.
        current_mode: The workflow mode explicitly requested by the user, if any.
        selected_agent: The agent ID explicitly requested by the user, if any.
        registry_dir: Optional path to the registry configurations.

    Returns:
        The final RoutingDecision to execute the request.
    """
    text = _normalise(user_input)
    base = _infer_auto_route(text, review_enabled=review_enabled, registry_dir=registry_dir)
    return _apply_explicit_overrides(
        base,
        current_mode=current_mode,
        selected_agent=_normalize_explicit_agent(selected_agent),
        review_enabled=review_enabled,
    )


# Expose loaded functions at module level for compatibility with unit test monkeypatching
load_semantic_catalog = catalog_module.load_semantic_catalog
deterministic_context_from_registry = graph_module.deterministic_context_from_registry

