from __future__ import annotations

from types import SimpleNamespace

import pytest
import typer

from crisai.cli import pipelines


class FakeWorkflowSession:
    """Test double for pipeline workflow orchestration."""

    def __init__(self, trace_calls: list[tuple[str, str]], stage_calls: list[tuple[str, str]], final_output: str) -> None:
        self._trace_calls = trace_calls
        self._stage_calls = stage_calls
        self._final_output = final_output

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def start_workflow(self, content: str, *, metadata=None) -> None:
        del metadata
        self._trace_calls.append(("WORKFLOW_START", content))

    def trace_user_input(self, content: str, *, metadata=None) -> None:
        del metadata
        self._trace_calls.append(("USER INPUT", content))

    def finish_workflow(self, content: str, *, metadata=None) -> None:
        del metadata
        self._trace_calls.append(("WORKFLOW_END", content))

    def skip_stage(self, trace_label: str, content: str, *, agent_id=None) -> str:
        del agent_id
        self._trace_calls.append((trace_label, content))
        return content

    async def run_stage(self, *, ui_agent_id: str, prompt: str, **kwargs) -> str:
        del kwargs
        self._stage_calls.append((ui_agent_id, prompt))
        if ui_agent_id == "judge":
            return "Decision: accept"
        if ui_agent_id == "orchestrator":
            return self._final_output
        return f"{ui_agent_id}-output"


class FakeWorkflowEngine:
    """Test double for the workflow engine wiring used by pipelines.py."""

    def __init__(self, session: FakeWorkflowSession) -> None:
        self._session = session
        self.agent_specs = None

    def session(self, agent_specs):
        self.agent_specs = list(agent_specs)
        return self._session


def test_build_context_synthesizer_prompt_creates_grounded_context_brief_prompt():
    prompt = pipelines.build_context_synthesizer_prompt(
        "Draft a solution design from local documents.",
        "Found design_notes.md and constraints.md in the workspace.",
    )

    assert "You are the Context Synthesizer agent" in prompt
    assert "Draft a solution design from local documents." in prompt
    assert "Found design_notes.md and constraints.md" in prompt
    assert "Use only facts supported by the context retrieval output." in prompt
    assert "Do not draft, recommend, or optimise the solution design." in prompt
    assert "## Relevant Facts" in prompt
    assert "## Gaps and Uncertainties" in prompt


def test_resolve_agent_max_turns_defaults_to_safe_value(monkeypatch):
    monkeypatch.delenv("CRISAI_AGENT_MAX_TURNS", raising=False)
    assert pipelines._resolve_agent_max_turns() == 30


def test_resolve_agent_max_turns_handles_invalid_env_value(monkeypatch):
    monkeypatch.setenv("CRISAI_AGENT_MAX_TURNS", "invalid")
    assert pipelines._resolve_agent_max_turns() == 30


def test_resolve_agent_max_turns_respects_positive_env_value(monkeypatch):
    monkeypatch.setenv("CRISAI_AGENT_MAX_TURNS", "42")
    assert pipelines._resolve_agent_max_turns() == 42


@pytest.mark.anyio
async def test_run_pipeline_skips_review_when_disabled(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []
    session = FakeWorkflowSession(trace_calls, stage_calls, "orchestrator-output")
    engine = FakeWorkflowEngine(session)

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings: SimpleNamespace(trace_file=tmp_path / "trace.log"),
    )
    monkeypatch.setattr(
        pipelines,
        "resolve_required_agents",
        lambda agent_specs, required_ids, mode_name=None: {
            agent_id: SimpleNamespace(id=agent_id, allowed_servers=[])
            for agent_id in required_ids
        },
    )
    monkeypatch.setattr(pipelines, "WorkflowEngine", lambda **kwargs: engine)

    result = await pipelines.run_pipeline(
        "hello",
        verbose=False,
        review=False,
        settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
        server_specs={},
        agent_specs={},
    )

    assert result == "orchestrator-output"
    assert [name for name, _ in stage_calls] == [
        "retrieval_planner",
        "context_retrieval",
        "context_synthesizer",
        "design",
        "orchestrator",
    ]
    assert trace_calls == [
        ("WORKFLOW_START", "Starting pipeline workflow."),
        ("USER INPUT", "hello"),
        ("REVIEW OUTPUT", "Review stage skipped because review is disabled."),
        ("WORKFLOW_END", "Pipeline workflow completed."),
    ]


@pytest.mark.anyio
async def test_run_peer_pipeline_skips_retrieval_planner_when_retrieval_not_needed(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []
    session = FakeWorkflowSession(trace_calls, stage_calls, "Final recommendation\nKeep it simple.")
    engine = FakeWorkflowEngine(session)

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings: SimpleNamespace(trace_file=tmp_path / "trace.log"),
    )
    monkeypatch.setattr(
        pipelines,
        "resolve_required_agents",
        lambda agent_specs, required_ids, mode_name=None: {
            agent_id: SimpleNamespace(id=agent_id, allowed_servers=[])
            for agent_id in required_ids
        },
    )
    monkeypatch.setattr(pipelines, "WorkflowEngine", lambda **kwargs: engine)
    monkeypatch.setattr(pipelines, "build_author_prompt", lambda message, discovery_text: message)

    result = await pipelines.run_peer_pipeline(
        "hello",
        verbose=False,
        review=False,
        settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
        server_specs={},
        agent_specs={},
        needs_retrieval=False,
    )

    assert result == "Final recommendation\nKeep it simple."
    assert [name for name, _ in stage_calls] == [
        "design_author",
        "design_challenger",
        "design_refiner",
        "judge",
        "judge",
        "orchestrator",
    ]
    assert stage_calls[0][1] == "hello"
    assert trace_calls == [
        ("WORKFLOW_START", "Starting peer workflow."),
        ("USER INPUT", "hello"),
        ("RETRIEVAL_PLANNER OUTPUT", "Retrieval planner skipped because this peer task does not require retrieval."),
        ("CONTEXT RETRIEVAL OUTPUT", "Context retrieval skipped because this peer task does not require retrieval."),
        ("CONTEXT OUTPUT", "Context synthesizer skipped because this peer task does not require retrieval."),
        ("WORKFLOW_END", "Peer workflow completed."),
    ]


def test_parse_judge_decision_handles_accept_revise_unknown():
    assert pipelines._parse_judge_decision("Decision: accept") == "accept"
    assert pipelines._parse_judge_decision("Decision - revise") == "revise"
    assert pipelines._parse_judge_decision("Decision: not acceptable") == "revise"
    assert pipelines._parse_judge_decision("Decision: acceptable but missing details") == "accept"
    assert pipelines._parse_judge_decision("Decision: reject and revise") == "revise"
    assert pipelines._parse_judge_decision("Result\nDecision: revise") == "revise"
    assert pipelines._parse_judge_decision("Looks good but no explicit label") == "unknown"


@pytest.mark.anyio
async def test_run_peer_pipeline_revises_once_when_judge_requests_revision(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []

    class RevisionSession(FakeWorkflowSession):
        def __init__(self):
            super().__init__(trace_calls, stage_calls, "Final recommendation\nShip this.")
            self.judge_calls = 0

        async def run_stage(self, *, ui_agent_id: str, prompt: str, **kwargs) -> str:
            del kwargs
            self._stage_calls.append((ui_agent_id, prompt))
            if ui_agent_id == "judge":
                self.judge_calls += 1
                return "Decision: revise\nReason: tighten quality." if self.judge_calls == 1 else "Decision: accept"
            if ui_agent_id == "orchestrator":
                return self._final_output
            if ui_agent_id == "design_refiner" and self.judge_calls >= 1:
                return "refined-draft-round-2"
            return f"{ui_agent_id}-output"

    session = RevisionSession()
    engine = FakeWorkflowEngine(session)

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings: SimpleNamespace(trace_file=tmp_path / "trace.log"),
    )
    monkeypatch.setattr(
        pipelines,
        "resolve_required_agents",
        lambda agent_specs, required_ids, mode_name=None: {
            agent_id: SimpleNamespace(id=agent_id, allowed_servers=[])
            for agent_id in required_ids
        },
    )
    monkeypatch.setattr(pipelines, "WorkflowEngine", lambda **kwargs: engine)
    monkeypatch.setenv("CRISAI_PEER_MAX_REFINEMENT_ROUNDS", "2")

    result = await pipelines.run_peer_pipeline(
        "hello",
        verbose=False,
        review=False,
        settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
        server_specs={},
        agent_specs={},
        needs_retrieval=False,
    )

    assert result == "Final recommendation\nShip this."
    # Base peer stages plus one extra refiner/judge pair from revision loop.
    assert [name for name, _ in stage_calls] == [
        "design_author",
        "design_challenger",
        "design_refiner",
        "judge",
        "design_refiner",
        "judge",
        "judge",
        "orchestrator",
    ]


@pytest.mark.anyio
async def test_run_peer_pipeline_quality_gate_forces_revision_after_initial_accept(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []

    class QualityGateSession(FakeWorkflowSession):
        def __init__(self):
            super().__init__(trace_calls, stage_calls, "Final recommendation\nShip this.")
            self.normal_judge_calls = 0
            self.quality_gate_calls = 0

        async def run_stage(self, *, ui_agent_id: str, prompt: str, **kwargs) -> str:
            del kwargs
            self._stage_calls.append((ui_agent_id, prompt))
            if ui_agent_id == "judge":
                if prompt.startswith("JUDGE_QUALITY_GATE::"):
                    self.quality_gate_calls += 1
                    # First quality gate blocks accept; second lets it pass.
                    return (
                        "Decision: revise\nReason: Missing implementation detail."
                        if self.quality_gate_calls == 1
                        else "Decision: accept\nReason: Coverage now complete."
                    )
                self.normal_judge_calls += 1
                return "Decision: accept\nReason: Looks good."
            if ui_agent_id == "orchestrator":
                return self._final_output
            if ui_agent_id == "design_refiner" and self.normal_judge_calls >= 1:
                return "refined-draft-round-2 with restored implementation detail"
            return f"{ui_agent_id}-output"

    session = QualityGateSession()
    engine = FakeWorkflowEngine(session)

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings: SimpleNamespace(trace_file=tmp_path / "trace.log"),
    )
    monkeypatch.setattr(
        pipelines,
        "resolve_required_agents",
        lambda agent_specs, required_ids, mode_name=None: {
            agent_id: SimpleNamespace(id=agent_id, allowed_servers=[])
            for agent_id in required_ids
        },
    )
    monkeypatch.setattr(pipelines, "WorkflowEngine", lambda **kwargs: engine)
    monkeypatch.setattr(
        pipelines,
        "build_judge_quality_gate_prompt",
        lambda message, discovery, challenge, refiner, judge: (
            "JUDGE_QUALITY_GATE::" + message + "::" + refiner
        ),
    )
    monkeypatch.setenv("CRISAI_PEER_MAX_REFINEMENT_ROUNDS", "2")

    result = await pipelines.run_peer_pipeline(
        "hello",
        verbose=False,
        review=False,
        settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
        server_specs={},
        agent_specs={},
        needs_retrieval=False,
    )

    assert result == "Final recommendation\nShip this."
    # Initial accept was blocked by quality gate, forcing one revision loop.
    assert [name for name, _ in stage_calls] == [
        "design_author",
        "design_challenger",
        "design_refiner",
        "judge",
        "judge",
        "design_refiner",
        "judge",
        "judge",
        "orchestrator",
    ]


@pytest.mark.anyio
async def test_run_peer_pipeline_escalates_to_author_and_challenger_after_unresolved_refine_loop(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []

    class EscalationSession(FakeWorkflowSession):
        def __init__(self):
            super().__init__(trace_calls, stage_calls, "Final recommendation\nShip this.")
            self.normal_judge_calls = 0

        async def run_stage(self, *, ui_agent_id: str, prompt: str, **kwargs) -> str:
            del kwargs
            self._stage_calls.append((ui_agent_id, prompt))
            if ui_agent_id == "judge":
                if prompt.startswith("JUDGE_QUALITY_GATE::"):
                    return "Decision: accept\nReason: quality gate passed."
                self.normal_judge_calls += 1
                return (
                    "Decision: revise\nReason: needs structural revision."
                    if self.normal_judge_calls == 1
                    else "Decision: accept\nReason: escalation resolved."
                )
            if ui_agent_id == "orchestrator":
                return self._final_output
            if ui_agent_id == "design_author" and self.normal_judge_calls >= 1:
                return "author-escalated-output"
            if ui_agent_id == "design_challenger" and self.normal_judge_calls >= 1:
                return "challenger-escalated-output"
            if ui_agent_id == "design_refiner" and self.normal_judge_calls >= 1:
                return "refiner-escalated-output"
            return f"{ui_agent_id}-output"

    session = EscalationSession()
    engine = FakeWorkflowEngine(session)

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings: SimpleNamespace(trace_file=tmp_path / "trace.log"),
    )
    monkeypatch.setattr(
        pipelines,
        "resolve_required_agents",
        lambda agent_specs, required_ids, mode_name=None: {
            agent_id: SimpleNamespace(id=agent_id, allowed_servers=[])
            for agent_id in required_ids
        },
    )
    monkeypatch.setattr(pipelines, "WorkflowEngine", lambda **kwargs: engine)
    monkeypatch.setattr(
        pipelines,
        "build_judge_quality_gate_prompt",
        lambda message, discovery, challenge, refiner, judge: (
            "JUDGE_QUALITY_GATE::" + message + "::" + refiner
        ),
    )
    monkeypatch.setenv("CRISAI_PEER_MAX_REFINEMENT_ROUNDS", "0")
    monkeypatch.setenv("CRISAI_PEER_MAX_ESCALATIONS", "1")

    result = await pipelines.run_peer_pipeline(
        "hello",
        verbose=False,
        review=False,
        settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
        server_specs={},
        agent_specs={},
        needs_retrieval=False,
    )

    assert result == "Final recommendation\nShip this."
    assert [name for name, _ in stage_calls] == [
        "design_author",
        "design_challenger",
        "design_refiner",
        "judge",
        "design_author",
        "design_challenger",
        "design_refiner",
        "judge",
        "judge",
        "orchestrator",
    ]


@pytest.mark.anyio
async def test_run_peer_pipeline_uses_user_intent_message_for_contract_inference(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []
    session = FakeWorkflowSession(trace_calls, stage_calls, "Final recommendation\nDone.")
    engine = FakeWorkflowEngine(session)
    captured_message: dict[str, str] = {}

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings: SimpleNamespace(trace_file=tmp_path / "trace.log"),
    )
    monkeypatch.setattr(
        pipelines,
        "resolve_required_agents",
        lambda agent_specs, required_ids, mode_name=None: {
            agent_id: SimpleNamespace(id=agent_id, allowed_servers=[])
            for agent_id in required_ids
        },
    )
    monkeypatch.setattr(pipelines, "WorkflowEngine", lambda **kwargs: engine)

    def _fake_infer_peer_run_contract(message: str):
        captured_message["value"] = message
        return SimpleNamespace(
            expected_output_type="direct_answer",
            must_create_or_update_files=False,
            must_modify_code=False,
            must_ground_in_sources=False,
            acceptance_dimensions=("instruction_alignment",),
            role_focus_author="x",
            role_focus_challenger="x",
            role_focus_refiner="x",
            role_focus_judge="x",
        )

    monkeypatch.setattr(pipelines, "infer_peer_run_contract", _fake_infer_peer_run_contract)
    monkeypatch.setattr(
        pipelines,
        "render_peer_run_contract",
        lambda contract: "contract",
    )

    await pipelines.run_peer_pipeline(
        "wrapped message with history",
        verbose=False,
        review=False,
        settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
        server_specs={},
        agent_specs={},
        needs_retrieval=False,
        user_intent_message="latest raw user input",
    )

    assert captured_message["value"] == "latest raw user input"


@pytest.mark.anyio
async def test_run_peer_pipeline_stops_before_orchestrator_when_judge_not_accept(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []

    class RejectingSession(FakeWorkflowSession):
        async def run_stage(self, *, ui_agent_id: str, prompt: str, **kwargs) -> str:
            del kwargs
            self._stage_calls.append((ui_agent_id, prompt))
            if ui_agent_id == "judge":
                return "Decision: revise\nReason: still missing."
            if ui_agent_id == "orchestrator":
                return self._final_output
            return f"{ui_agent_id}-output"

    session = RejectingSession(trace_calls, stage_calls, "Final recommendation\nDone.")
    engine = FakeWorkflowEngine(session)

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings: SimpleNamespace(trace_file=tmp_path / "trace.log"),
    )
    monkeypatch.setattr(
        pipelines,
        "resolve_required_agents",
        lambda agent_specs, required_ids, mode_name=None: {
            agent_id: SimpleNamespace(id=agent_id, allowed_servers=[])
            for agent_id in required_ids
        },
    )
    monkeypatch.setattr(pipelines, "WorkflowEngine", lambda **kwargs: engine)
    monkeypatch.setenv("CRISAI_PEER_MAX_REFINEMENT_ROUNDS", "0")

    with pytest.raises(typer.BadParameter) as exc:
        await pipelines.run_peer_pipeline(
            "hello",
            verbose=False,
            review=False,
            settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
            server_specs={},
            agent_specs={},
            needs_retrieval=False,
        )

    assert "judge did not accept" in str(exc.value).lower()
    assert "orchestrator" not in [name for name, _ in stage_calls]


@pytest.mark.anyio
async def test_run_single_raises_for_unknown_agent(monkeypatch, tmp_path):
    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    with pytest.raises(typer.BadParameter) as exc:
        await pipelines.run_single(
            "hello",
            "missing",
            settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
            server_specs={},
            agent_specs={},
        )
    assert "Unknown agent_id: missing" in str(exc.value)


@pytest.mark.anyio
async def test_run_single_retrieval_planner_uses_retrieval_execution_prompt(monkeypatch, tmp_path):
    captured_prompt = None

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings: SimpleNamespace(
            trace_file=tmp_path / "trace.log",
            runtime=SimpleNamespace(
                build_server=lambda server_spec: server_spec
            ),
            factory=SimpleNamespace(
                build_agent=lambda spec, active_servers: SimpleNamespace(id=spec.id)
            ),
            run_id="test-run-id",
        ),
    )
    async def _fake_run_agent_silently(agent, prompt: str) -> str:
        nonlocal captured_prompt
        del agent
        captured_prompt = prompt
        return "ok"

    monkeypatch.setattr(pipelines, "_run_agent_silently", _fake_run_agent_silently)

    result = await pipelines.run_single(
        "Find files in my OneDrive related to integration strategy.",
        "retrieval_planner",
        settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
        server_specs={},
        agent_specs={"retrieval_planner": SimpleNamespace(id="retrieval_planner", allowed_servers=[])},
    )

    assert result == "ok"
    assert captured_prompt is not None
    assert "Perform retrieval now" in captured_prompt
    assert "Do not return a planning brief" in captured_prompt


@pytest.mark.anyio
async def test_run_pipeline_enforces_intranet_fetch_policy(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []
    session = FakeWorkflowSession(trace_calls, stage_calls, "orchestrator-output")
    engine = FakeWorkflowEngine(session)

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings: SimpleNamespace(trace_file=tmp_path / "trace.log"),
    )
    monkeypatch.setattr(
        pipelines,
        "resolve_required_agents",
        lambda agent_specs, required_ids, mode_name=None: {
            agent_id: SimpleNamespace(id=agent_id, allowed_servers=[])
            for agent_id in required_ids
        },
    )
    monkeypatch.setattr(pipelines, "WorkflowEngine", lambda **kwargs: engine)

    with pytest.raises(typer.BadParameter) as exc:
        await pipelines.run_pipeline(
            "Use intranet site pages only and produce grounded output.",
            verbose=False,
            review=True,
            settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
            server_specs={},
            agent_specs={},
        )

    assert "requires intranet-grounded evidence" in str(exc.value)


@pytest.mark.anyio
async def test_run_peer_pipeline_enforces_workspace_write_policy(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []
    session = FakeWorkflowSession(trace_calls, stage_calls, "Final recommendation\nNo files written.")
    engine = FakeWorkflowEngine(session)

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings: SimpleNamespace(trace_file=tmp_path / "trace.log"),
    )
    monkeypatch.setattr(
        pipelines,
        "resolve_required_agents",
        lambda agent_specs, required_ids, mode_name=None: {
            agent_id: SimpleNamespace(id=agent_id, allowed_servers=[])
            for agent_id in required_ids
        },
    )
    monkeypatch.setattr(pipelines, "WorkflowEngine", lambda **kwargs: engine)

    with pytest.raises(typer.BadParameter) as exc:
        await pipelines.run_peer_pipeline(
            "Write with write_workspace_file under workspace/context_staging/patterns/",
            verbose=False,
            review=False,
            settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
            server_specs={},
            agent_specs={},
            needs_retrieval=False,
        )

    assert "requires artefact creation/update" in str(exc.value)
