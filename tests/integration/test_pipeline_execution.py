"""
Integration tests for pipeline execution modes.

These tests exercise real prompt builders, real evidence bundle parsing, real task
contract inference, and real registry loading. Only the LLM boundary
(_run_agent_with_transient_box → Runner.run) and MCP server startup
(MultiServerContext) are stubbed.

The distinction from the orchestration-level tests (tests/orchestration/) is that
those tests also stub the prompt builders and AgentFactory, meaning a broken prompt
file or a regression in prompt building would pass silently. These tests catch that
class of failure.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import crisai.cli.pipelines as pipelines
from crisai.agents.factory import AgentFactory as _RealAgentFactory
from crisai.orchestration.peer_verifier import PeerVerificationResult
from crisai.registry import Registry

_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Stub outputs
# ---------------------------------------------------------------------------

# Minimal valid evidence_bundle_v1 block accepted by the evidence contract.
_EVIDENCE_BUNDLE = json.dumps(
    {
        "schema_version": "evidence_bundle_v1",
        "request": "architecture documentation",
        "items": [
            {
                "source": {
                    "source_type": "workspace_document",
                    "title": "architecture.md",
                    "open_url": "",
                    "location": "",
                    "read_handle": "workspace://architecture.md",
                    "workspace_path": "",
                    "content_id": "",
                    "metadata": {},
                },
                "evidence_level": "metadata_read",
                "read_status": "ok",
                "read_tool": "",
                "content_excerpt": "",
                "raw_error": "",
            }
        ],
        "gaps": [],
    },
    indent=2,
)

_STUB_STAGE_OUTPUTS: dict[str, str] = {
    "retrieval_planner": "Search plan: query workspace for architecture documentation.",
    "context_retrieval": f"Context retrieved.\n\n```json\n{_EVIDENCE_BUNDLE}\n```",
    "context_synthesizer": "## Synthesized Context\nThe system uses a layered architecture.",
    "design": "## Architecture Design\nThe proposed design introduces three service tiers.",
    "summary": "## Summary\nThe architecture spans frontend, backend, and data tiers.",
    "review": "## Review\nThe design is coherent and grounded in the retrieved evidence.",
    "orchestrator": "The architecture analysis is complete.",
    "design_author": "## Initial Design\nProposal: event-driven architecture with CQRS.",
    "design_challenger": "## Challenge\nThe CQRS pattern adds operational complexity.",
    "design_refiner": "## Refined Design\nSimplified CQRS with an in-process read model.",
    # First non-empty line must start with "Decision:" for _parse_judge_decision.
    "judge": "Decision: accept\nReason: The refined design addresses all raised concerns.",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _PromptValidatingFactory:
    """Loads real prompt files from disk; returns lightweight agent stubs.

    Calling load_prompt() for every spec means a broken or missing prompt file
    raises FileNotFoundError before the test can pass — exactly the regression we
    want to catch.
    """

    def __init__(self, root_dir: Path) -> None:
        self._real = _RealAgentFactory(root_dir, model_specs=[])

    def build_agent(self, spec, mcp_servers):
        self._real.load_prompt(spec.prompt_file)
        return SimpleNamespace(id=spec.id)


class _FakeRuntimeManager:
    def __init__(self, root_dir: Path) -> None:
        pass

    def build_server(self, spec):
        return spec


class _NoOpServerContext:
    def __init__(self, servers):
        pass

    async def __aenter__(self):
        return {}

    async def __aexit__(self, *_):
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _registry_specs():
    registry = Registry(_ROOT / "registry")
    return {
        "server_specs": {s.id: s for s in registry.load_servers()},
        "agent_specs": {a.id: a for a in registry.load_agents()},
        "model_specs": registry.load_models(),
    }


@pytest.fixture()
def integration_env(monkeypatch, tmp_path, _registry_specs):
    """Patch LLM boundary and MCP startup; keep real prompt builders and evidence handling."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    settings = SimpleNamespace(
        openai_api_key="test-key",
        log_dir=log_dir,
        registry_dir=str(_ROOT / "registry"),
        workspace_dir=str(tmp_path / "workspace"),
        root_dir=str(_ROOT),
    )

    called_stages: list[str] = []

    async def _stub_stage_runner(agent_id: str, agent, prompt: str) -> str:
        called_stages.append(agent_id)
        return _STUB_STAGE_OUTPUTS.get(agent_id, f"stub:{agent_id}")

    async def _stub_agent_silently(agent, prompt: str) -> str:
        agent_id = getattr(agent, "id", "unknown")
        called_stages.append(agent_id)
        return _STUB_STAGE_OUTPUTS.get(agent_id, f"stub:{agent_id}")

    _empty_verifier_result = PeerVerificationResult(checked_files=(), violations=())

    monkeypatch.setattr(
        pipelines,
        "_build_agent_factory",
        lambda root_dir, *a, **kw: _PromptValidatingFactory(root_dir),
    )
    monkeypatch.setattr(pipelines, "RuntimeManager", _FakeRuntimeManager)
    monkeypatch.setattr(pipelines, "MultiServerContext", _NoOpServerContext)
    monkeypatch.setattr(pipelines, "_run_agent_with_transient_box", _stub_stage_runner)
    monkeypatch.setattr(pipelines, "_run_agent_silently", _stub_agent_silently)
    monkeypatch.setattr(pipelines, "append_trace", lambda *a, **kw: None)
    monkeypatch.setattr(pipelines, "print_agent_output", lambda *a, **kw: None)
    monkeypatch.setattr(pipelines, "snapshot_tree", lambda *a, **kw: frozenset())
    monkeypatch.setattr(pipelines, "changed_paths", lambda *a, **kw: frozenset())
    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda s: None)
    monkeypatch.setattr(pipelines, "enforce_workspace_write_policy", lambda *a, **kw: frozenset())
    monkeypatch.setattr(pipelines, "enforce_intranet_fetch_policy", lambda *a, **kw: None)
    monkeypatch.setattr(
        pipelines,
        "enforce_peer_final_deliverable_verification",
        lambda *a, **kw: _empty_verifier_result,
    )

    return {**_registry_specs, "settings": settings, "called_stages": called_stages}


# ---------------------------------------------------------------------------
# Pipeline mode
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_pipeline_calls_all_six_stages_in_order(integration_env):
    """run_pipeline invokes all six stages via real prompt builders and evidence handling."""
    result = await pipelines.run_pipeline(
        "what is the current architecture of our system?",
        verbose=False,
        review=False,
        settings=integration_env["settings"],
        server_specs=integration_env["server_specs"],
        agent_specs=integration_env["agent_specs"],
        model_specs=integration_env["model_specs"],
    )

    stages = integration_env["called_stages"]
    assert stages[:3] == ["retrieval_planner", "context_retrieval", "context_synthesizer"]
    assert "orchestrator" in stages
    assert isinstance(result, str) and result


@pytest.mark.anyio
async def test_pipeline_loads_all_prompt_files_without_error(integration_env):
    """All prompt files referenced by pipeline agents are present and readable.

    A missing or unreadable file causes _PromptValidatingFactory.build_agent to raise
    FileNotFoundError, failing this test before it reaches the assertion.
    """
    await pipelines.run_pipeline(
        "what is the current architecture of our system?",
        verbose=False,
        review=False,
        settings=integration_env["settings"],
        server_specs=integration_env["server_specs"],
        agent_specs=integration_env["agent_specs"],
        model_specs=integration_env["model_specs"],
    )


@pytest.mark.anyio
async def test_pipeline_parses_evidence_bundle_from_context_retrieval_stub(integration_env):
    """Evidence bundle embedded in the context_retrieval stub round-trips through the parser."""
    from crisai.orchestration.evidence_contract import parse_evidence_bundle

    bundle = parse_evidence_bundle(_STUB_STAGE_OUTPUTS["context_retrieval"])

    assert bundle.schema_version == "evidence_bundle_v1"
    assert len(bundle.items) == 1
    assert bundle.items[0].source.title == "architecture.md"
    assert bundle.items[0].source.source_type == "workspace_document"


# ---------------------------------------------------------------------------
# Single mode
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_single_mode_loads_real_prompt_and_returns_stub_output(integration_env):
    """run_single loads the real agent prompt file and returns the stub output."""
    result = await pipelines.run_single(
        "describe the authentication service",
        "design",
        settings=integration_env["settings"],
        server_specs=integration_env["server_specs"],
        agent_specs=integration_env["agent_specs"],
        model_specs=integration_env["model_specs"],
    )

    assert result == _STUB_STAGE_OUTPUTS["design"]
    assert integration_env["called_stages"] == ["design"]


@pytest.mark.anyio
async def test_single_mode_summary_agent_loads_real_prompt(integration_env):
    """Summary agent prompt file is present and loads without error."""
    result = await pipelines.run_single(
        "summarise the system components",
        "summary",
        settings=integration_env["settings"],
        server_specs=integration_env["server_specs"],
        agent_specs=integration_env["agent_specs"],
        model_specs=integration_env["model_specs"],
    )

    assert result == _STUB_STAGE_OUTPUTS["summary"]


# ---------------------------------------------------------------------------
# Peer mode
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_peer_pipeline_completes_when_judge_accepts_on_first_pass(
    integration_env, monkeypatch
):
    """run_peer_pipeline completes with judge acceptance on the first round."""
    monkeypatch.setenv("CRISAI_PEER_MAX_REFINEMENT_ROUNDS", "0")
    monkeypatch.setenv("CRISAI_PEER_MAX_ESCALATIONS", "0")

    result = await pipelines.run_peer_pipeline(
        "design the authentication system",
        verbose=False,
        review=False,
        settings=integration_env["settings"],
        server_specs=integration_env["server_specs"],
        agent_specs=integration_env["agent_specs"],
        model_specs=integration_env["model_specs"],
    )

    stages = integration_env["called_stages"]
    assert "design_author" in stages
    assert "design_challenger" in stages
    assert "design_refiner" in stages
    assert "judge" in stages
    assert "orchestrator" in stages
    assert isinstance(result, str) and result


@pytest.mark.anyio
async def test_peer_pipeline_loads_all_peer_prompt_files(integration_env, monkeypatch):
    """All prompt files for peer agents (author, challenger, refiner, judge) are readable."""
    monkeypatch.setenv("CRISAI_PEER_MAX_REFINEMENT_ROUNDS", "0")
    monkeypatch.setenv("CRISAI_PEER_MAX_ESCALATIONS", "0")

    await pipelines.run_peer_pipeline(
        "design the authentication system",
        verbose=False,
        review=False,
        settings=integration_env["settings"],
        server_specs=integration_env["server_specs"],
        agent_specs=integration_env["agent_specs"],
        model_specs=integration_env["model_specs"],
    )
