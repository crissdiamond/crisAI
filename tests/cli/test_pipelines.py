from __future__ import annotations

from types import SimpleNamespace

import pytest

from crisai.cli import pipelines
from crisai.orchestration import peer_judge
from crisai.orchestration.exceptions import WorkflowValidationError


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
        self._stage_calls.append((ui_agent_id, prompt))
        if ui_agent_id == "judge":
            result = "Decision: accept"
        elif ui_agent_id == "orchestrator":
            result = self._final_output
        else:
            result = f"{ui_agent_id}-output"
        output_processor = kwargs.get("output_processor")
        if output_processor is not None:
            output_processor(result)
        return result


class FakeWorkflowEngine:
    """Test double for the workflow engine wiring used by pipelines.py."""

    def __init__(self, session: FakeWorkflowSession) -> None:
        self._session = session
        self.agent_specs = None

    def session(self, agent_specs):
        self.agent_specs = list(agent_specs)
        return self._session


def test_resolve_agent_max_turns_defaults_to_safe_value(monkeypatch):
    monkeypatch.delenv("CRISAI_AGENT_MAX_TURNS", raising=False)
    assert pipelines._resolve_agent_max_turns() == 30


def test_resolve_agent_max_turns_handles_invalid_env_value(monkeypatch):
    monkeypatch.setenv("CRISAI_AGENT_MAX_TURNS", "invalid")
    assert pipelines._resolve_agent_max_turns() == 30


def test_resolve_agent_max_turns_respects_positive_env_value(monkeypatch):
    monkeypatch.setenv("CRISAI_AGENT_MAX_TURNS", "42")
    assert pipelines._resolve_agent_max_turns() == 42


def test_validated_evidence_text_fails_closed_for_document_summary_without_bundle():
    with pytest.raises(pipelines.WorkflowPolicyViolation, match="valid evidence bundle"):
        pipelines._validated_evidence_text("Can you summarise this document?", "metadata only")


def test_validated_evidence_text_fails_closed_without_content_read():
    raw = """
```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "Can you summarise this document?",
  "items": [
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "Deck.pptx",
        "open_url": "https://example.com/deck.pptx",
        "read_handle": "sharepoint_doc:abc",
        "metadata": {}
      },
      "evidence_level": "metadata_read",
      "read_status": "metadata_read",
      "read_tool": "get_sharepoint_document_metadata_by_handle",
      "content_excerpt": "",
      "raw_error": ""
    }
  ],
  "gaps": []
}
```
"""
    with pytest.raises(pipelines.WorkflowPolicyViolation, match="content_read"):
        pipelines._validated_evidence_text("Can you summarise this document?", raw)


def test_validated_evidence_text_accepts_trace_legacy_string_source():
    raw = """
Retrieved the likely master deck and read the candidate content.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "Can you summarise the most recent and likely master document?",
  "items": [
    {
      "source": "UCL Integration Strategy_Full Presentation v2.pptx",
      "evidence_level": "content_read",
      "read_status": "read",
      "read_tool": "read_sharepoint_document_by_handle",
      "content_excerpt": "Integration Strategy v1.0, September 2021.",
      "raw_error": null
    }
  ]
}
```
"""
    result = pipelines._validated_evidence_text(
        "Can you summarise the most recent and likely master document?",
        raw,
    )

    assert "## Validated Evidence Summary" in result
    assert "UCL Integration Strategy_Full Presentation v2.pptx" in result
    assert "content_read / read" in result
    assert "evidence_bundle_v1" not in result


def test_validated_evidence_text_accepts_unclosed_fenced_bundle():
    raw = """
Retrieved and read the selected deck.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "Can you summarise this document?",
  "items": [
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "Deck.pptx",
        "read_handle": "sharepoint_doc:abc"
      },
      "evidence_level": "content_read",
      "read_status": "read",
      "read_tool": "read_sharepoint_document_by_handle",
      "content_excerpt": "Readable slide text.",
      "raw_error": ""
    }
  ],
  "gaps": []
}
"""
    result = pipelines._validated_evidence_text("Can you summarise this document?", raw)

    assert "## Validated Evidence Summary" in result
    assert "Deck.pptx" in result
    assert "evidence_bundle_v1" not in result


def test_validated_evidence_text_rejects_content_read_source_that_misses_title_constraint():
    raw = """
Retrieved and read a deck.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "Summarise the most recent Integration Strategy document.",
  "items": [
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "Local people planning guide.pptx",
        "open_url": "https://liveuclac.sharepoint.com/sites/UCLPeopleandCulture/guide.pptx",
        "read_handle": "sharepoint_doc:abc"
      },
      "evidence_level": "content_read",
      "read_status": "read",
      "read_tool": "read_sharepoint_document_by_handle",
      "content_excerpt": "People planning guide.",
      "raw_error": ""
    }
  ],
  "gaps": []
}
```
"""

    with pytest.raises(pipelines.WorkflowPolicyViolation, match="source constraints"):
        pipelines._validated_evidence_text(
            "Summarise in 4 paragraphs the content of the most recent Integration Strategy document.",
            raw,
        )


def test_validated_evidence_text_rejects_content_read_source_that_misses_onedrive_scope():
    raw = """
Retrieved and read a deck.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "Summarise the most recent Integration Strategy document in my OneDrive.",
  "items": [
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "UCL Integration Strategy full deck v3.pptx",
        "open_url": "https://liveuclac.sharepoint.com/sites/Architecture/Shared%20Documents/UCL%20Integration%20Strategy.pptx",
        "read_handle": "sharepoint_doc:abc"
      },
      "evidence_level": "content_read",
      "read_status": "read",
      "read_tool": "read_sharepoint_document_by_handle",
      "content_excerpt": "Integration Strategy.",
      "raw_error": ""
    }
  ],
  "gaps": []
}
```
"""

    with pytest.raises(pipelines.WorkflowPolicyViolation, match="personal_onedrive"):
        pipelines._validated_evidence_text(
            "Summarise the most recent Integration Strategy document in my OneDrive.",
            raw,
        )


def test_validated_evidence_text_rejects_auxiliary_reads_when_target_read_failed():
    raw = """
Retrieved local context and failed to read the latest deck.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "Summarise the latest Integration Strategy document in 4 paragraphs",
  "items": [
    {
      "source": {
        "source_type": "workspace_file",
        "title": "context/reference/landscape/integration-operating-model.txt",
        "workspace_path": "context/reference/landscape/integration-operating-model.txt"
      },
      "evidence_level": "content_read",
      "read_status": "read",
      "read_tool": "read_workspace_file",
      "content_excerpt": "Federated model of empowered product teams.",
      "raw_error": ""
    },
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "UCL Integration Strategy full deck v3 1.pptx",
        "read_handle": "sharepoint_doc:bad"
      },
      "evidence_level": "read_failed",
      "read_status": "not_read",
      "read_tool": "read_sharepoint_document_by_handle",
      "content_excerpt": "",
      "raw_error": "Malformed SharePoint read_handle."
    }
  ],
  "gaps": []
}
```
"""

    with pytest.raises(pipelines.WorkflowPolicyViolation, match="required source read failed"):
        pipelines._validated_evidence_text(
            "Summarise the latest Integration Strategy document in 4 paragraphs",
            raw,
        )


def test_validated_evidence_text_rejects_latest_version_date_conflict():
    raw = """
Retrieved and read the newest modified deck.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "Summarise the most recent Integration Strategy document.",
  "items": [
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "UCL Integration Strategy_Full Presentation v2_data.pptx",
        "open_url": "https://example.com/v2-data.pptx",
        "read_handle": "sharepoint_doc:v2",
        "metadata": {
          "lastModifiedDateTime": "2023-11-17T12:52:10Z"
        }
      },
      "evidence_level": "content_read",
      "read_status": "read",
      "read_tool": "inspect_sharepoint_powerpoint_by_handle",
      "content_excerpt": "Readable slide text.",
      "raw_error": ""
    },
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "UCL Integration Strategy full deck v3.pptx",
        "open_url": "https://example.com/v3.pptx",
        "read_handle": "sharepoint_doc:v3",
        "metadata": {
          "lastModifiedDateTime": "2022-02-01T09:00:00Z"
        }
      },
      "evidence_level": "search_hit_only",
      "read_status": "not_read",
      "read_tool": "",
      "content_excerpt": "",
      "raw_error": ""
    }
  ],
  "gaps": []
}
```
"""

    with pytest.raises(pipelines.WorkflowPolicyViolation, match="newest modified file"):
        pipelines._validated_evidence_text(
            "Summarise the most recent Integration Strategy document.",
            raw,
        )


def test_validated_evidence_text_accepts_latest_when_date_and_version_agree():
    raw = """
Retrieved and read the selected deck.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "Summarise the most recent Integration Strategy document.",
  "items": [
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "UCL Integration Strategy full deck v3.pptx",
        "open_url": "https://example.com/v3.pptx",
        "read_handle": "sharepoint_doc:v3",
        "metadata": {
          "lastModifiedDateTime": "2023-11-17T12:52:10Z"
        }
      },
      "evidence_level": "content_read",
      "read_status": "read",
      "read_tool": "inspect_sharepoint_powerpoint_by_handle",
      "content_excerpt": "Readable slide text.",
      "raw_error": ""
    },
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "UCL Integration Strategy_Full Presentation v2_data.pptx",
        "open_url": "https://example.com/v2-data.pptx",
        "read_handle": "sharepoint_doc:v2",
        "metadata": {
          "lastModifiedDateTime": "2022-02-01T09:00:00Z"
        }
      },
      "evidence_level": "search_hit_only",
      "read_status": "not_read",
      "read_tool": "",
      "content_excerpt": "",
      "raw_error": ""
    }
  ],
  "gaps": []
}
```
"""

    result = pipelines._validated_evidence_text(
        "Summarise the most recent Integration Strategy document.",
        raw,
    )

    assert "## Validated Evidence Summary" in result
    assert "evidence_bundle_v1" not in result


def test_validated_evidence_transport_keeps_bundle_in_metadata_not_prose():
    raw = """
Retrieved and read the selected deck.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "Can you summarise this document?",
  "items": [
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "Deck.pptx",
        "read_handle": "sharepoint_doc:abc"
      },
      "evidence_level": "content_read",
      "read_status": "read",
      "read_tool": "read_sharepoint_document_by_handle",
      "content_excerpt": "Readable slide text.",
      "raw_error": ""
    }
  ],
  "gaps": []
}
```
"""
    transport = pipelines._validated_evidence_transport("Can you summarise this document?", raw)

    assert transport.prose == "Retrieved and read the selected deck."
    assert transport.trace_metadata is not None
    assert transport.trace_metadata["artifacts"]["evidence_bundle_v1"]["items"][0]["source"]["title"] == "Deck.pptx"
    assert "evidence_bundle_v1" not in transport.prompt_text


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
async def test_run_pipeline_repairs_missing_required_evidence_bundle(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []
    evidence_bundle = """
Retrieved and read the deck.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "Summarise this document",
  "items": [
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "Deck.pptx",
        "open_url": "https://example.com/deck.pptx",
        "read_handle": "sharepoint_doc:abc",
        "metadata": {}
      },
      "evidence_level": "content_read",
      "read_status": "read",
      "read_tool": "read_sharepoint_document_by_handle",
      "content_excerpt": "Slide 1: Strategy overview.",
      "raw_error": ""
    }
  ],
  "gaps": []
}
```
"""

    class RepairingWorkflowSession(FakeWorkflowSession):
        def __init__(self) -> None:
            super().__init__(trace_calls, stage_calls, "final summary")
            self.context_calls = 0

        async def run_stage(self, *, ui_agent_id: str, prompt: str, **kwargs) -> str:
            self._stage_calls.append((ui_agent_id, prompt))
            if ui_agent_id == "context_retrieval":
                self.context_calls += 1
                result = "I read the deck but forgot the evidence bundle." if self.context_calls == 1 else evidence_bundle
            elif ui_agent_id == "orchestrator":
                result = self._final_output
            elif ui_agent_id == "summary":
                result = "summary draft"
            else:
                result = f"{ui_agent_id}-output"
            output_processor = kwargs.get("output_processor")
            if output_processor is not None:
                output_processor(result)
            return result

    session = RepairingWorkflowSession()
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
        "Summarise this document",
        verbose=False,
        review=False,
        settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
        server_specs={},
        agent_specs={},
    )

    context_prompts = [prompt for name, prompt in stage_calls if name == "context_retrieval"]
    assert result == "final summary"
    assert len(context_prompts) == 2
    assert "Repair the retrieval evidence contract" in context_prompts[1]
    assert any(name == "summary" for name, _ in stage_calls)


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
    judge_prompts = [prompt for name, prompt in stage_calls if name == "judge"]
    assert any("## Filesystem evidence (runtime)" in prompt for prompt in judge_prompts)


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
        peer_judge,
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
        peer_judge,
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

    with pytest.raises(WorkflowValidationError) as exc:
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
    with pytest.raises(WorkflowValidationError) as exc:
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
async def test_run_single_emits_fail_open_deterministic_trace_when_graph_missing(monkeypatch, tmp_path):
    captured_events: list[tuple[str, str, dict | None]] = []

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings: SimpleNamespace(
            trace_file=tmp_path / "trace.log",
            runtime=SimpleNamespace(build_server=lambda server_spec: server_spec),
            factory=SimpleNamespace(build_agent=lambda spec, active_servers: SimpleNamespace(id=spec.id)),
            run_id="test-run-id",
        ),
    )
    monkeypatch.setattr(
        pipelines,
        "deterministic_context_from_registry",
        lambda message, registry_dir: (pipelines._empty_deterministic_context(), False),
    )

    async def _fake_run_agent_silently(agent, prompt: str) -> str:
        del agent, prompt
        return "ok"

    monkeypatch.setattr(pipelines, "_run_agent_silently", _fake_run_agent_silently)
    monkeypatch.setattr(
        pipelines,
        "_append_trace_entry_compat",
        lambda environment, stage, content, **kwargs: captured_events.append((stage, content, kwargs.get("metadata"))),
    )

    await pipelines.run_single(
        "Find integration principles.",
        "retrieval_planner",
        settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path, registry_dir=tmp_path / "registry"),
        server_specs={},
        agent_specs={"retrieval_planner": SimpleNamespace(id="retrieval_planner", allowed_servers=[])},
    )
    deterministic_events = [event for event in captured_events if event[0] == "DETERMINISTIC_RETRIEVAL_CONTEXT"]
    assert deterministic_events
    assert "fail-open" in deterministic_events[0][1]
    assert deterministic_events[0][2]["mode"] == "single"


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

    with pytest.raises(WorkflowValidationError) as exc:
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
async def test_run_peer_pipeline_passes_deterministic_context_to_peer_builders(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []
    session = FakeWorkflowSession(trace_calls, stage_calls, "Final recommendation\nDone.")
    engine = FakeWorkflowEngine(session)
    capture: dict[str, object] = {}

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
        "deterministic_context_from_registry",
        lambda message, registry_dir: (
            SimpleNamespace(
                schema_version="deterministic_context_v1",
                graph_loaded=True,
                graph_version="g123",
                is_active=True,
                activated_topic_ids=frozenset({"integration_principles_corpus"}),
                suggested_terms=frozenset({"integration principles"}),
                suggested_sources=frozenset({"intranet"}),
            ),
            True,
        ),
    )

    def _capture_author(message, discovery, run_contract_text="", **kwargs):
        capture["author_kwargs"] = kwargs
        return message

    monkeypatch.setattr(pipelines, "build_author_prompt", _capture_author)

    await pipelines.run_peer_pipeline(
        "hello",
        verbose=False,
        review=False,
        settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path, registry_dir=tmp_path / "registry"),
        server_specs={},
        agent_specs={},
        needs_retrieval=False,
    )
    assert "deterministic_context" in capture["author_kwargs"]


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

    with pytest.raises(WorkflowValidationError) as exc:
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


@pytest.mark.anyio
async def test_run_peer_pipeline_repairs_final_output_for_repairable_verifier_mismatch(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []

    class RepairSession(FakeWorkflowSession):
        def __init__(self):
            super().__init__(trace_calls, stage_calls, "final-output-stale")
            self.orchestrator_calls = 0

        async def run_stage(self, *, ui_agent_id: str, prompt: str, **kwargs) -> str:
            del kwargs
            self._stage_calls.append((ui_agent_id, prompt))
            if ui_agent_id == "judge":
                return "Decision: accept\nReason: done."
            if ui_agent_id == "orchestrator":
                self.orchestrator_calls += 1
                return "final-output-stale" if self.orchestrator_calls == 1 else "Final recommendation\nRepair complete."
            return f"{ui_agent_id}-output"

    session = RepairSession()
    engine = FakeWorkflowEngine(session)
    verify_calls: list[str] = []

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
        "enforce_workspace_write_policy",
        lambda policy, root_dir, write_before: [
            "workspace/context_staging/patterns/producer-pattern-1-system-to-enterprise-api-ondemand-synchronous.md"
        ],
    )

    def _fake_verify(*, root_dir, contract, final_text, changed_paths):
        del root_dir, contract, changed_paths
        verify_calls.append(final_text)
        if len(verify_calls) == 1:
            raise pipelines.PeerVerificationViolation(
                "Peer verifier gate failed:\n- Referenced output file does not exist: "
                "workspace/context_staging/patterns/producer-pattern-1-system-to-enterprise-api-synchronous.md"
            )
        return SimpleNamespace(
            checked_files=(
                "workspace/context_staging/patterns/producer-pattern-1-system-to-enterprise-api-ondemand-synchronous.md",
            ),
            violations=(),
        )

    monkeypatch.setattr(pipelines, "enforce_peer_final_deliverable_verification", _fake_verify)

    result = await pipelines.run_peer_pipeline(
        "Write with write_workspace_file under workspace/context_staging/patterns/",
        verbose=False,
        review=False,
        settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
        server_specs={},
        agent_specs={},
        needs_retrieval=False,
    )

    assert result == "Final recommendation\nRepair complete."
    assert verify_calls == ["final-output-stale", "Final recommendation\nRepair complete."]
    assert [name for name, _ in stage_calls].count("orchestrator") == 2
