"""
Integration tests for the peer pipeline loop paths.

Covers: judge accept on first pass (happy path), refinement round with
revise-then-accept, stagnation detection, escalation accepting after rounds
exhaust, full exhaustion raising, and the no-retrieval path.

Prompt builders, evidence handling, task contract inference, and registry loading
are all real. Only the LLM boundary (_run_agent_with_transient_box) and MCP server
startup (MultiServerContext) are stubbed.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import crisai.cli.pipelines as pipelines
from crisai.agents.factory import AgentFactory as _RealAgentFactory
from crisai.orchestration.exceptions import WorkflowValidationError
from crisai.orchestration.peer_verifier import PeerVerificationResult
from crisai.registry import Registry

_ROOT = Path(__file__).resolve().parents[2]

_EMPTY_VERIFIER = PeerVerificationResult(checked_files=(), violations=())

# Stub outputs for non-judge stages.
_STAGE_DEFAULTS: dict[str, str] = {
    "retrieval_planner": "Search plan: query workspace for architecture docs.",
    "context_retrieval": "Context: no bundle required for peer tests.",
    "context_synthesizer": "Synthesized context: layered architecture.",
    "design_author": "## Initial Design\nEvent-driven with CQRS.",
    "design_challenger": "## Challenge\nCQRS adds operational complexity.",
    "design_refiner": "## Refined Design v1\nSimplified CQRS with in-process read model.",
    "orchestrator": "Peer analysis complete.",
}

# Judge outputs for the single-accept happy path (initial + quality gate).
_JUDGE_ACCEPT = "Decision: accept\nReason: Design meets all requirements."


class _PromptValidatingFactory:
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


@pytest.fixture()
def peer_env(monkeypatch, tmp_path):
    """Base integration environment for peer pipeline tests.

    Stage runner defaults to _STAGE_DEFAULTS with judge returning accept.
    Individual tests override the stage runner for their specific scenario.
    """
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    settings = SimpleNamespace(
        openai_api_key="test-key",
        log_dir=log_dir,
        registry_dir=str(_ROOT / "registry"),
        workspace_dir=str(tmp_path / "workspace"),
        root_dir=str(_ROOT),
    )
    registry = Registry(_ROOT / "registry")
    server_specs = {s.id: s for s in registry.load_servers()}
    agent_specs = {a.id: a for a in registry.load_agents()}
    model_specs = registry.load_models()

    called_stages: list[str] = []

    async def _default_runner(agent_id: str, agent, prompt: str) -> str:
        called_stages.append(agent_id)
        if agent_id == "judge":
            return _JUDGE_ACCEPT
        return _STAGE_DEFAULTS.get(agent_id, f"stub:{agent_id}")

    monkeypatch.setattr(
        pipelines, "_build_agent_factory",
        lambda root_dir, *a, **kw: _PromptValidatingFactory(root_dir),
    )
    monkeypatch.setattr(pipelines, "RuntimeManager", _FakeRuntimeManager)
    monkeypatch.setattr(pipelines, "MultiServerContext", _NoOpServerContext)
    monkeypatch.setattr(pipelines, "_run_agent_with_transient_box", _default_runner)
    monkeypatch.setattr(pipelines, "_run_agent_silently", lambda a, p: None)
    monkeypatch.setattr(pipelines, "append_trace", lambda *a, **kw: None)
    monkeypatch.setattr(pipelines, "print_agent_output", lambda *a, **kw: None)
    monkeypatch.setattr(pipelines, "snapshot_tree", lambda *a, **kw: frozenset())
    monkeypatch.setattr(pipelines, "changed_paths", lambda *a, **kw: frozenset())
    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda s: None)
    monkeypatch.setattr(pipelines, "enforce_workspace_write_policy", lambda *a, **kw: frozenset())
    monkeypatch.setattr(pipelines, "enforce_intranet_fetch_policy", lambda *a, **kw: None)
    monkeypatch.setattr(
        pipelines, "enforce_peer_final_deliverable_verification",
        lambda *a, **kw: _EMPTY_VERIFIER,
    )

    return {
        "settings": settings,
        "server_specs": server_specs,
        "agent_specs": agent_specs,
        "model_specs": model_specs,
        "called_stages": called_stages,
    }


def _run_peer(env, *, needs_retrieval: bool = True, **kwargs):
    return pipelines.run_peer_pipeline(
        "design the authentication system",
        verbose=False,
        review=False,
        needs_retrieval=needs_retrieval,
        settings=env["settings"],
        server_specs=env["server_specs"],
        agent_specs=env["agent_specs"],
        model_specs=env["model_specs"],
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_peer_happy_path_all_core_stages_called(peer_env, monkeypatch):
    """All core peer stages run and the pipeline returns the orchestrator output."""
    monkeypatch.setenv("CRISAI_PEER_MAX_REFINEMENT_ROUNDS", "0")
    monkeypatch.setenv("CRISAI_PEER_MAX_ESCALATIONS", "0")

    result = await _run_peer(peer_env)

    stages = peer_env["called_stages"]
    for stage in ("design_author", "design_challenger", "design_refiner", "judge", "orchestrator"):
        assert stage in stages, f"expected {stage} to be called"
    # Judge called twice: initial accept + quality gate accept.
    assert stages.count("judge") == 2
    assert result == _STAGE_DEFAULTS["orchestrator"]


# ---------------------------------------------------------------------------
# Refinement round: judge revises then accepts
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_peer_refiner_reruns_when_judge_revises(peer_env, monkeypatch):
    """Refiner and judge run a second time when the first judge decision is 'revise'."""
    monkeypatch.setenv("CRISAI_PEER_MAX_REFINEMENT_ROUNDS", "1")
    monkeypatch.setenv("CRISAI_PEER_MAX_ESCALATIONS", "0")

    # Judge sequence: revise (round 0) → accept (round 1) → accept (quality gate).
    judge_seq = iter([
        "Decision: revise\nReason: Design lacks failure-handling detail.",
        "Decision: accept\nReason: Failure handling now addressed.",
        "Decision: accept",  # quality gate
    ])
    refiner_call = [0]

    async def _runner(agent_id: str, agent, prompt: str) -> str:
        peer_env["called_stages"].append(agent_id)
        if agent_id == "judge":
            return next(judge_seq)
        if agent_id == "design_refiner":
            refiner_call[0] += 1
            return f"## Refined Design (round {refiner_call[0]})\nUpdated content."
        return _STAGE_DEFAULTS.get(agent_id, f"stub:{agent_id}")

    monkeypatch.setattr(pipelines, "_run_agent_with_transient_box", _runner)

    result = await _run_peer(peer_env)

    stages = peer_env["called_stages"]
    assert stages.count("design_refiner") == 2, "refiner must run twice (initial + refinement round)"
    assert stages.count("judge") == 3, "judge: revise + accept + quality-gate accept"
    assert isinstance(result, str) and result


# ---------------------------------------------------------------------------
# Stagnation: refiner output unchanged, loop exits as unresolved
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_peer_stagnation_detected_when_refiner_output_is_unchanged(peer_env, monkeypatch):
    """Pipeline raises when stagnation is detected (refiner produces identical output)."""
    monkeypatch.setenv("CRISAI_PEER_MAX_REFINEMENT_ROUNDS", "2")
    monkeypatch.setenv("CRISAI_PEER_MAX_ESCALATIONS", "0")

    async def _runner(agent_id: str, agent, prompt: str) -> str:
        peer_env["called_stages"].append(agent_id)
        if agent_id == "judge":
            return "Decision: revise\nReason: Not good enough."
        if agent_id == "design_refiner":
            return "## Refined Design\nNo change."  # identical every call → stagnation
        return _STAGE_DEFAULTS.get(agent_id, f"stub:{agent_id}")

    monkeypatch.setattr(pipelines, "_run_agent_with_transient_box", _runner)

    with pytest.raises(WorkflowValidationError, match="Peer quality gate failed"):
        await _run_peer(peer_env)

    stages = peer_env["called_stages"]
    # Stagnation detected in round 1: refiner called exactly twice (initial + round 1).
    assert stages.count("design_refiner") == 2
    # Judge called once per round before stagnation; quality gate is skipped for "revise".
    assert stages.count("judge") >= 1


# ---------------------------------------------------------------------------
# Escalation: rounds exhaust, escalation judge accepts
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_peer_escalation_accepts_after_refinement_rounds_exhaust(peer_env, monkeypatch):
    """Escalation author/challenger/refiner reruns and the escalation judge accepts."""
    monkeypatch.setenv("CRISAI_PEER_MAX_REFINEMENT_ROUNDS", "1")
    monkeypatch.setenv("CRISAI_PEER_MAX_ESCALATIONS", "1")

    # Judge sequence:
    #   round 0 → revise
    #   round 1 → revise  (exhausts max_refinement_rounds)
    #   escalation 1 → accept
    #   quality gate → accept
    judge_seq = iter([
        "Decision: revise\nReason: Initial pass incomplete.",
        "Decision: revise\nReason: Round 1 still incomplete.",
        "Decision: accept\nReason: Escalated design accepted.",
        "Decision: accept",  # quality gate
    ])
    refiner_call = [0]

    async def _runner(agent_id: str, agent, prompt: str) -> str:
        peer_env["called_stages"].append(agent_id)
        if agent_id == "judge":
            return next(judge_seq)
        if agent_id == "design_refiner":
            refiner_call[0] += 1
            return f"## Refined Design (call {refiner_call[0]})\nVersion {refiner_call[0]} detail."
        if agent_id == "design_author":
            return f"## Author (call {peer_env['called_stages'].count('design_author')})"
        return _STAGE_DEFAULTS.get(agent_id, f"stub:{agent_id}")

    monkeypatch.setattr(pipelines, "_run_agent_with_transient_box", _runner)

    result = await _run_peer(peer_env)

    stages = peer_env["called_stages"]
    # Escalation reruns author, challenger, refiner once each beyond the initial set.
    assert stages.count("design_author") == 2, "author: initial + escalation"
    assert stages.count("design_challenger") == 2, "challenger: initial + escalation"
    assert stages.count("design_refiner") == 3, "refiner: initial + round 1 + escalation"
    # Judge: round 0 revise + round 1 revise + escalation accept + quality gate = 4.
    assert stages.count("judge") == 4
    assert isinstance(result, str) and result


# ---------------------------------------------------------------------------
# Full exhaustion: all rounds and escalations fail → raises
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_peer_raises_when_all_rounds_and_escalations_exhausted(peer_env, monkeypatch):
    """BadParameter is raised when judge never accepts within allowed rounds + escalations."""
    monkeypatch.setenv("CRISAI_PEER_MAX_REFINEMENT_ROUNDS", "1")
    monkeypatch.setenv("CRISAI_PEER_MAX_ESCALATIONS", "1")

    refiner_call = [0]

    async def _runner(agent_id: str, agent, prompt: str) -> str:
        peer_env["called_stages"].append(agent_id)
        if agent_id == "judge":
            return "Decision: revise\nReason: Always needs more work."
        if agent_id == "design_refiner":
            refiner_call[0] += 1
            return f"## Design attempt {refiner_call[0]}"  # unique each call → no stagnation
        return _STAGE_DEFAULTS.get(agent_id, f"stub:{agent_id}")

    monkeypatch.setattr(pipelines, "_run_agent_with_transient_box", _runner)

    with pytest.raises(WorkflowValidationError, match="Peer quality gate failed"):
        await _run_peer(peer_env)

    stages = peer_env["called_stages"]
    # Escalation reruns the full trio, so author + challenger appear twice.
    assert stages.count("design_author") == 2
    assert stages.count("design_challenger") == 2
    # Orchestrator must NOT be called — pipeline stops before finalization.
    assert "orchestrator" not in stages


# ---------------------------------------------------------------------------
# No-retrieval path
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_peer_skips_retrieval_stages_when_needs_retrieval_false(peer_env, monkeypatch):
    """Retrieval stages are skipped and peer stages still run with needs_retrieval=False."""
    monkeypatch.setenv("CRISAI_PEER_MAX_REFINEMENT_ROUNDS", "0")
    monkeypatch.setenv("CRISAI_PEER_MAX_ESCALATIONS", "0")

    result = await _run_peer(peer_env, needs_retrieval=False)

    stages = peer_env["called_stages"]
    for skipped in ("retrieval_planner", "context_retrieval", "context_synthesizer"):
        assert skipped not in stages, f"{skipped} should be skipped when needs_retrieval=False"
    for required in ("design_author", "design_challenger", "design_refiner", "judge", "orchestrator"):
        assert required in stages, f"{required} must run regardless of retrieval flag"
    assert isinstance(result, str) and result
