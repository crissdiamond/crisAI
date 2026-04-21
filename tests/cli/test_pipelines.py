from __future__ import annotations

from types import SimpleNamespace

import pytest
import typer

from crisai.cli import pipelines


@pytest.mark.anyio
async def test_run_pipeline_skips_review_when_disabled(monkeypatch, tmp_path):
    trace_calls = []
    stage_calls = []

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

    class DummyContext:
        async def __aenter__(self):
            return ["server"]

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        pipelines,
        "workflow_server_context",
        lambda environment, specs, server_specs: DummyContext(),
    )

    def fake_append_trace_entry(environment, stage, content):
        trace_calls.append((stage, content))

    async def fake_run_traced_stage(**kwargs):
        stage_calls.append(kwargs["ui_agent_id"])
        return f"{kwargs['ui_agent_id']}-output"

    monkeypatch.setattr(pipelines, "append_trace_entry", fake_append_trace_entry)
    monkeypatch.setattr(pipelines, "run_traced_stage", fake_run_traced_stage)

    result = await pipelines.run_pipeline(
        "hello",
        verbose=False,
        review=False,
        settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
        server_specs={},
        agent_specs={},
    )

    assert result == "orchestrator-output"
    assert stage_calls == ["discovery", "design", "orchestrator"]
    assert trace_calls == [
        ("WORKFLOW_START", "Starting pipeline workflow."),
        ("USER INPUT", "hello"),
        ("REVIEW OUTPUT", "Review stage skipped because review is disabled."),
        ("WORKFLOW_END", "Pipeline workflow completed."),
    ]


@pytest.mark.anyio
async def test_run_peer_pipeline_skips_discovery_when_retrieval_not_needed(monkeypatch, tmp_path):
    trace_calls = []
    stage_calls = []

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

    class DummyContext:
        async def __aenter__(self):
            return ["server"]

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        pipelines,
        "workflow_server_context",
        lambda environment, specs, server_specs: DummyContext(),
    )

    def fake_append_trace_entry(environment, stage, content):
        trace_calls.append((stage, content))

    async def fake_run_traced_stage(**kwargs):
        stage_calls.append((kwargs["ui_agent_id"], kwargs["prompt"]))
        if kwargs["ui_agent_id"] == "orchestrator":
            return "Final recommendation\nKeep it simple."
        return f"{kwargs['ui_agent_id']}-output"

    monkeypatch.setattr(pipelines, "append_trace_entry", fake_append_trace_entry)
    monkeypatch.setattr(pipelines, "run_traced_stage", fake_run_traced_stage)
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
        "orchestrator",
    ]
    assert stage_calls[0][1] == "hello"
    assert trace_calls == [
        ("WORKFLOW_START", "Starting peer workflow."),
        ("USER INPUT", "hello"),
        ("DISCOVERY OUTPUT", "Discovery skipped because this peer task does not require retrieval."),
        ("WORKFLOW_END", "Peer workflow completed."),
    ]


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
