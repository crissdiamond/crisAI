"""Opt-in smoke tests for real LLM API integration.

These tests call real provider APIs and validate pipeline contract shapes.
They are designed to be cheap (small prompts, minimal turns, no MCP servers)
while still exercising the full stack: prompt assembly, model resolution,
agent execution, evidence contracts, trace output, and judge decision parsing.

Run with:
    CRISAI_RUN_SMOKE_TESTS=1 python -m pytest tests/smoke/ -v

Provider keys required per test:
    - single/<provider>: <PROVIDER>_API_KEY
    - pipeline: OPENAI_API_KEY + DEEPSEEK_API_KEY
    - peer: OPENAI_API_KEY + DEEPSEEK_API_KEY + GEMINI_API_KEY
"""

from __future__ import annotations

import os

import pytest

from crisai.cli import pipelines
from crisai.orchestration.exceptions import WorkflowValidationError
from crisai.orchestration.peer_verifier import PeerVerificationViolation
from crisai.registry import AgentSpec

from .conftest import (
    CHEAP_MODEL_REF,
    assert_stage_traced,
    read_trace,
    require_providers,
)

_SMOKE_QUESTION = "List two concrete benefits of using an API gateway in a microservice architecture."
_PIPELINE_QUESTION = "Describe the three main responsibilities of an API gateway in enterprise architecture."
_PEER_QUESTION = "Draft a brief explanation of the strangler fig migration pattern."

# Prompt file used for synthetic single-mode agents.
_ORCHESTRATOR_PROMPT = "prompts/orchestrator.md"


# ---------------------------------------------------------------------------
# Single mode — one test per provider
# ---------------------------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.anyio
@pytest.mark.timeout(120)
@pytest.mark.parametrize("provider", list(CHEAP_MODEL_REF))
async def test_single_agent_provider_responds(
    provider: str,
    smoke_settings,
    smoke_registry,
    monkeypatch,
) -> None:
    """Each configured provider resolves its model, builds an agent, and returns output.

    Contract: non-empty string response; trace contains a stage_output entry.
    """
    require_providers(provider)

    model_ref = CHEAP_MODEL_REF[provider]
    agent_id = f"smoke_{provider}"

    # Synthetic agent spec pointing to the cheap model for this provider.
    agent_spec = AgentSpec(
        id=agent_id,
        name=f"Smoke {provider.title()} Agent",
        model_ref=model_ref,
        prompt_file=_ORCHESTRATOR_PROMPT,
        allowed_servers=[],
    )

    # openai_api_key must be non-empty for ensure_openai_api_key guard.
    # For non-OpenAI tests the actual OpenAI key is not used by any agent.
    if provider != "openai":
        monkeypatch.setitem(os.environ, "OPENAI_API_KEY", "smoke-not-used")

    # Cap turns to reduce cost.
    monkeypatch.setenv("CRISAI_AGENT_MAX_TURNS", "5")

    result = await pipelines.run_single(
        _SMOKE_QUESTION,
        agent_id,
        settings=smoke_settings,
        server_specs={},
        agent_specs={agent_id: agent_spec},
        model_specs=smoke_registry["model_specs"],
    )

    assert result and result.strip(), f"Provider '{provider}' returned empty output"

    trace = read_trace(smoke_settings.log_dir)
    assert_stage_traced(trace, agent_id)


# ---------------------------------------------------------------------------
# Pipeline mode — all configured pipeline providers
# ---------------------------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.anyio
@pytest.mark.timeout(300)
async def test_pipeline_all_stages_traced(
    smoke_settings,
    smoke_registry,
    monkeypatch,
) -> None:
    """Pipeline completes and every expected stage appears in the trace.

    Requires OPENAI_API_KEY + DEEPSEEK_API_KEY (default pipeline model assignments).
    Uses a knowledge question — no MCP retrieval tools needed.

    Contract: all core stages present in trace with non-empty content.
    """
    require_providers("openai", "deepseek")
    monkeypatch.setenv("CRISAI_AGENT_MAX_TURNS", "5")

    result = await pipelines.run_pipeline(
        _PIPELINE_QUESTION,
        verbose=False,
        review=False,
        settings=smoke_settings,
        **smoke_registry,
    )

    assert result and result.strip(), "Pipeline returned empty final output"

    trace = read_trace(smoke_settings.log_dir)
    for stage in ("retrieval_planner", "context_retrieval", "context_synthesizer", "orchestrator"):
        assert_stage_traced(trace, stage)

    # design or summary stage (router picks one based on request)
    design_or_summary = [
        e for e in trace
        if e.get("stage") in ("design", "summary") and e.get("event_type") == "stage_output"
    ]
    assert design_or_summary, "Neither 'design' nor 'summary' stage found in trace"


# ---------------------------------------------------------------------------
# Peer mode — no retrieval, judge decision contract
# ---------------------------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.anyio
@pytest.mark.timeout(300)
async def test_peer_judge_decision_contract(
    smoke_settings,
    smoke_registry,
    monkeypatch,
) -> None:
    """Peer pipeline runs without retrieval and the judge produces a parseable decision.

    Requires OPENAI_API_KEY + DEEPSEEK_API_KEY + GEMINI_API_KEY.
    needs_retrieval=False skips the retrieval stages to reduce cost.
    max_refinement_rounds=0 prevents refine loops; WorkflowValidationError on
    'revise' is accepted (it proves the judge ran and produced a decision).

    Contract: judge stage in trace; content contains a supported peer decision.
    """
    require_providers("openai", "deepseek", "gemini")
    monkeypatch.setenv("CRISAI_AGENT_MAX_TURNS", "5")
    monkeypatch.setenv("CRISAI_PEER_MAX_REFINEMENT_ROUNDS", "0")
    monkeypatch.setenv("CRISAI_PEER_MAX_ESCALATIONS", "0")

    try:
        await pipelines.run_peer_pipeline(
            _PEER_QUESTION,
            verbose=False,
            review=False,
            needs_retrieval=False,
            settings=smoke_settings,
            **smoke_registry,
        )
    except (WorkflowValidationError, PeerVerificationViolation):
        # Judge revised and rounds/escalations were exhausted — expected outcome
        # when max rounds are capped. The trace still captures the judge decision.
        pass

    trace = read_trace(smoke_settings.log_dir)

    for stage in ("design_author", "design_challenger", "judge"):
        assert_stage_traced(trace, stage)

    # Judge must have produced a parseable decision line.
    judge_entries = [
        e for e in trace
        if e.get("stage") == "judge" and e.get("event_type") == "stage_output"
    ]
    judge_content = "\n".join(e.get("content", "") for e in judge_entries)
    assert "Decision:" in judge_content, (
        f"Judge output does not contain 'Decision:' marker.\nJudge content:\n{judge_content}"
    )
