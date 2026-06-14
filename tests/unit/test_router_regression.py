"""Golden-set regression tests for the routing decision logic.

Each case maps a representative user query to the expected (intent, mode) pair so
that edits to the semantic catalog or router cascade immediately surface regressions.
The real semantic_catalog.yaml is used; deterministic graph nudge is suppressed via
registry_dir=None so cases depend only on the catalog terms.

Adding a new routing path: append a tuple to GOLDEN_CASES and verify it passes.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from crisai.cli.chat_context import continuation_intent_message
from crisai.orchestration.router import decide_route

REGISTRY_DIR = Path(__file__).resolve().parents[2] / "registry"

# (query, expected_intent, expected_mode)
GOLDEN_CASES: list[tuple[str, str, str]] = [
    # --- explicit discovery patterns -----------------------------------------
    (
        "Search SharePoint for integration strategy documents and return only a table.",
        "discovery",
        "single",
    ),
    (
        "List what documents are available in the architecture sites.",
        "discovery",
        "single",
    ),
    (
        "Find all files in my OneDrive with 'UCL integration strategy' in the title, "
        "list all of them in order of most likely authoritative version. "
        "Present the files in a table with linkable name, description, size, date.",
        "discovery",
        "single",
    ),
    # --- operations -----------------------------------------------------------
    (
        "Debug this error and fix the broken import in the CLI module.",
        "operations",
        "single",
    ),
    (
        "The auth flow is raising an exception — trace the bug and patch it.",
        "operations",
        "single",
    ),
    # --- publication ----------------------------------------------------------
    (
        "Convert this architecture summary into a .pptx slide deck.",
        "publication",
        "single",
    ),
    (
        "Package the final recommendation into a .docx document using the template.",
        "publication",
        "single",
    ),
    # --- summary pipeline (source + summary) ----------------------------------
    (
        "Summarise the latest integration strategy document from OneDrive.",
        "summary",
        "pipeline",
    ),
    (
        "Give me a summary of what the SharePoint files say about the target architecture.",
        "summary",
        "pipeline",
    ),
    # --- summary single (no clear source) ------------------------------------
    (
        "Summarise this text.",
        "summary",
        "single",
    ),
    (
        "Provide a brief summary of the following notes.",
        "summary",
        "single",
    ),
    # --- critical peer review -------------------------------------------------
    (
        "This is a critical decision: propose an architecture option and challenge it.",
        "critical_peer_review",
        "peer",
    ),
    (
        "Board level accuracy is required: propose an HLD and critique the design decisions.",
        "critical_peer_review",
        "peer",
    ),
    # --- peer review (explicit patterns) --------------------------------------
    (
        "Use peer mode: the author should propose, the challenger should criticise.",
        "peer_review",
        "peer",
    ),
    (
        "Debate this design: challenge it and then refine it.",
        "peer_review",
        "peer",
    ),
    # --- peer review (explicit pattern, no "peer mode" keyword) ---------------
    (
        "Challenge and refine the proposed design against the weak assumptions.",
        "peer_review",
        "peer",
    ),
    # --- discovery + design pipeline -----------------------------------------
    (
        "Find the docs about command handling and propose a design improvement.",
        "discovery_design",
        "pipeline",
    ),
    (
        "Look up the integration documents and draft an architecture blueprint.",
        "discovery_design",
        "pipeline",
    ),
    # --- design + review pipeline (no sources) --------------------------------
    (
        "Propose a simple CLI design and critique the main weaknesses.",
        "design_review",
        "pipeline",
    ),
    (
        "Draft an HLD for the new service and evaluate the assumptions.",
        "design_review",
        "pipeline",
    ),
    # --- review single (no design, no sources) --------------------------------
    (
        "Review these assumptions and evaluate the gaps in the proposal.",
        "review",
        "single",
    ),
    (
        "Critique this architecture and challenge its weak assumptions.",
        "review",
        "single",
    ),
    # --- design single --------------------------------------------------------
    (
        "Design a microservice architecture using a modular blueprint.",
        "design",
        "single",
    ),
    (
        "Draft a high-level architecture for the new integration platform.",
        "design",
        "single",
    ),
    # --- discovery single (source signal only) --------------------------------
    (
        "Find all files and documents in the project repository.",
        "discovery",
        "single",
    ),
    # --- mixed complexity pipeline --------------------------------------------
    (
        "Identify a design approach and check for gaps in integration.",
        "mixed_complexity",
        "pipeline",
    ),
    # --- orchestrator fallback ------------------------------------------------
    (
        "Hello, how are you?",
        "orchestrator",
        "single",
    ),
    (
        "What time is it?",
        "orchestrator",
        "single",
    ),
]


@pytest.mark.parametrize("query,expected_intent,expected_mode", GOLDEN_CASES, ids=[
    f"{i:02d}_{mode}_{intent}"
    for i, (_, intent, mode) in enumerate(GOLDEN_CASES)
])
def test_router_golden(
    query: str,
    expected_intent: str,
    expected_mode: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Assert that a canonical query routes to the expected intent and mode."""
    monkeypatch.setattr(
        "crisai.orchestration.router._deterministic_source_nudge",
        lambda text, registry_dir: False,
    )
    decision = decide_route(query, review_enabled=False, registry_dir=None)
    assert decision.intent == expected_intent, (
        f"Expected intent={expected_intent!r} but got {decision.intent!r} "
        f"(mode={decision.mode!r}, reason={decision.reason!r})"
    )
    assert decision.mode == expected_mode, (
        f"Expected mode={expected_mode!r} but got {decision.mode!r} "
        f"(intent={decision.intent!r}, reason={decision.reason!r})"
    )


def test_deterministic_nudge_sets_needs_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    """A nudge from the semantic graph forces needs_retrieval=True."""
    monkeypatch.setattr(
        "crisai.orchestration.router._deterministic_source_nudge",
        lambda text, registry_dir: True,
    )
    decision = decide_route(
        "please gather integration guidance",
        review_enabled=False,
        registry_dir=None,
    )
    assert decision.needs_retrieval is True


@pytest.mark.parametrize(
    "query",
    [
        # Two architecture terms that used to collide with operations_terms and,
        # at >= 2 matches, mis-route a design ask to the troubleshooting agent.
        "Fix the authentication and token lifetime in the target architecture.",
        "The key issue with this integration approach is the login timeout policy.",
        "Design the error handling and exception strategy for the API.",
    ],
)
def test_architecture_prompts_do_not_route_to_operations(query: str) -> None:
    """CRISAI-ADR-014: architecture vocabulary must not trip the crisAI-runtime
    troubleshooting agent."""
    decision = decide_route(query, review_enabled=False, registry_dir=None)
    assert decision.intent != "operations", decision.reason


@pytest.mark.parametrize(
    "query",
    [
        "crisAI keeps prompting for the device code and the MCP server won't start.",
        "Stack trace shows a module not found error in the CLI startup script.",
    ],
)
def test_crisai_runtime_troubles_still_route_to_operations(query: str) -> None:
    """Genuine local-runtime problems remain reachable via the scoped terms."""
    decision = decide_route(query, review_enabled=False, registry_dir=None)
    assert decision.intent == "operations", decision.reason


def test_bare_continue_routes_like_previous_source_lookup_task() -> None:
    history = [
        (
            "user",
            "find all the documents in my onedrive with integration strategy in the title. "
            "List the 3 best candidate.",
        ),
        ("assistant", "I found 10 OneDrive documents with integration strategy in the title."),
    ]
    message = continuation_intent_message("continue", history, registry_dir=REGISTRY_DIR)

    decision = decide_route(message, review_enabled=False, registry_dir=REGISTRY_DIR)

    assert decision.intent == "discovery"
    assert decision.mode == "single"
    assert decision.agent == "retrieval_planner"
    assert decision.needs_retrieval is True


def test_explicit_pipeline_mode_overrides_single_agent_publication_route() -> None:
    """Pinned pipeline mode keeps the route in pipeline even for single-agent intents."""
    decision = decide_route(
        "Package this final recommendation into a .docx document.",
        review_enabled=False,
        current_mode="pipeline",
    )

    assert decision.intent == "explicit"
    assert decision.mode == "pipeline"
    assert decision.agent == "design"
    assert decision.needs_retrieval is True
