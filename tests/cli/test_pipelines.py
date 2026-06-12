from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from crisai.cli import pipeline_display, pipelines
from crisai.orchestration import peer_judge
from crisai.orchestration.exceptions import WorkflowValidationError
from crisai.orchestration.retrieval_checkpoint import RetrievalCheckpointDecision

REGISTRY_DIR = Path(__file__).resolve().parents[2] / "registry"


def _workspace_retrieval_handoff(
    *,
    request: str = "Search workspace/knowledge before answering.",
    title: str = "reporting-standard.txt",
    path: str = "knowledge/reporting-standard.txt",
    excerpt: str = "Recurring reports need controlled preparation.",
) -> str:
    return f"""
## Retrieval Summary

Found and read the relevant workspace source.

## Retrieved Sources

### Workspace sources
- Source: `{path}`
  Link: [source](file://{path})
  Relevance: Relevant workspace evidence.
  Extract: {excerpt}

## Retrieval Gaps
- Gap: None.

## Tool Notes
- Tool: read_workspace_file
  Result: Read source content.

```json
{{
  "schema_version": "evidence_bundle_v1",
  "request": "{request}",
  "items": [
    {{
      "source": {{
        "source_type": "workspace_file",
        "title": "{title}",
        "workspace_path": "{path}",
        "metadata": {{}}
      }},
      "evidence_level": "content_read",
      "read_status": "read",
      "read_tool": "read_workspace_file",
      "content_excerpt": "{excerpt}",
      "raw_error": ""
    }}
  ],
  "gaps": []
}}
```
"""


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
        self.agent_specs: list[Any] | None = None

    def session(self, agent_specs):
        self.agent_specs = list(agent_specs)
        return self._session


class FallbackWorkflowSession(FakeWorkflowSession):
    """Workflow double that simulates an empty retrieval-planner response."""

    def trace_event(self, stage: str, content: str, **kwargs) -> None:
        del kwargs
        self._trace_calls.append((stage, content))

    async def run_stage(self, *, ui_agent_id: str, prompt: str, **kwargs) -> str:
        if ui_agent_id == "retrieval_planner":
            self._stage_calls.append((ui_agent_id, prompt))
            raise RuntimeError(
                "Stage retrieval_planner returned empty output. "
                "This stage is required to produce a handoff or answer."
            )
        if ui_agent_id == "context_retrieval":
            self._stage_calls.append((ui_agent_id, prompt))
            result = _workspace_retrieval_handoff()
            output_processor = kwargs.get("output_processor")
            if output_processor is not None:
                output_processor(result)
            return result
        return await super().run_stage(ui_agent_id=ui_agent_id, prompt=prompt, **kwargs)


def test_resolve_agent_max_turns_defaults_to_safe_value(monkeypatch):
    monkeypatch.delenv("CRISAI_AGENT_MAX_TURNS", raising=False)
    assert pipeline_display._resolve_agent_max_turns() == 30


def test_resolve_agent_max_turns_handles_invalid_env_value(monkeypatch):
    monkeypatch.setenv("CRISAI_AGENT_MAX_TURNS", "invalid")
    assert pipeline_display._resolve_agent_max_turns() == 30


def test_resolve_agent_max_turns_respects_positive_env_value(monkeypatch):
    monkeypatch.setenv("CRISAI_AGENT_MAX_TURNS", "42")
    assert pipeline_display._resolve_agent_max_turns() == 42


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


def test_validated_evidence_transport_preserves_legacy_plain_markdown_for_non_source_requests():
    result = pipelines._validated_evidence_transport(
        "Say hello.",
        "Plain markdown without source evidence.",
    )

    assert result.prose == "Plain markdown without source evidence."
    assert result.bundle is None


def test_validated_evidence_transport_requires_bundle_for_source_evidence_requests():
    with pytest.raises(pipelines.WorkflowPolicyViolation, match="valid evidence bundle"):
        pipelines._validated_evidence_transport(
            "Use retrieved workspace context to recommend an approach.",
            "## Retrieval Summary\n\nFound sources.\n\n## Retrieved Sources\n\n- Source: x",
            require_evidence_bundle=True,
            require_retrieval_structure=True,
        )


def test_validated_evidence_transport_rejects_final_answer_without_retrieval_sections():
    final_answer = """
## Solution design recommendation

Use a controlled pipeline rather than direct Excel-to-Power BI.
"""

    with pytest.raises(pipelines.WorkflowPolicyViolation, match="Retrieval Summary"):
        pipelines._validated_evidence_transport(
            "Use retrieved workspace context to recommend an approach.",
            final_answer,
            require_evidence_bundle=True,
            require_retrieval_structure=True,
        )


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
Retrieved local knowledge and failed to read the latest deck.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "Summarise the latest Integration Strategy document in 4 paragraphs",
  "items": [
    {
      "source": {
        "source_type": "workspace_file",
        "title": "knowledge/reference/landscape/integration-operating-model.txt",
        "workspace_path": "knowledge/reference/landscape/integration-operating-model.txt"
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


def test_validated_evidence_text_rejects_unmarked_named_source_variant_read():
    raw = """
Retrieved and read the requested deck plus a nearby variant.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "Please summarise the Integration Strategy full deck v3 1 in detail.",
  "items": [
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "UCL Integration Strategy full deck v3 1.pptx",
        "open_url": "https://example.com/v3-1.pptx",
        "read_handle": "sharepoint_doc:v3-1"
      },
      "evidence_level": "content_read",
      "read_status": "read",
      "read_tool": "inspect_sharepoint_powerpoint_by_handle",
      "content_excerpt": "Requested deck slide text.",
      "raw_error": ""
    },
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "UCL Integration Strategy_Full Presentation v2_data.pptx",
        "open_url": "https://example.com/v2-data.pptx",
        "read_handle": "sharepoint_doc:v2"
      },
      "evidence_level": "content_read",
      "read_status": "read",
      "read_tool": "inspect_sharepoint_powerpoint_by_handle",
      "content_excerpt": "Older variant slide text.",
      "raw_error": ""
    }
  ],
  "gaps": []
}
```
"""

    with pytest.raises(pipelines.WorkflowPolicyViolation, match="evidence_role='supplemental'"):
        pipelines._validated_evidence_text(
            "Please summarise the Integration Strategy full deck v3 1 in detail.",
            raw,
        )


def test_validated_evidence_text_accepts_supplemental_named_source_variant_read():
    raw = """
Retrieved and read the requested deck plus a nearby variant.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "Please summarise the Integration Strategy full deck v3 1 in detail.",
  "items": [
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "UCL Integration Strategy full deck v3 1.pptx",
        "open_url": "https://example.com/v3-1.pptx",
        "read_handle": "sharepoint_doc:v3-1"
      },
      "evidence_level": "content_read",
      "read_status": "read",
      "read_tool": "inspect_sharepoint_powerpoint_by_handle",
      "content_excerpt": "Requested deck slide text.",
      "raw_error": ""
    },
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "UCL Integration Strategy_Full Presentation v2_data.pptx",
        "open_url": "https://example.com/v2-data.pptx",
        "read_handle": "sharepoint_doc:v2"
      },
      "evidence_level": "content_read",
      "read_status": "read",
      "evidence_role": "supplemental",
      "read_tool": "inspect_sharepoint_powerpoint_by_handle",
      "content_excerpt": "Older variant slide text.",
      "raw_error": ""
    }
  ],
  "gaps": []
}
```
"""

    result = pipelines._validated_evidence_text(
        "Please summarise the Integration Strategy full deck v3 1 in detail.",
        raw,
    )

    assert "## Validated Evidence Summary" in result
    assert "supplemental content_read / read" in result
    assert "evidence_bundle_v1" not in result


def test_validated_evidence_text_rejects_all_supplemental_named_source_reads():
    raw = """
Retrieved a nearby variant.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "Please summarise the Integration Strategy full deck v3 1 in detail.",
  "items": [
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "UCL Integration Strategy_Full Presentation v2_data.pptx",
        "open_url": "https://example.com/v2-data.pptx",
        "read_handle": "sharepoint_doc:v2"
      },
      "evidence_level": "content_read",
      "read_status": "read",
      "evidence_role": "supplemental",
      "read_tool": "inspect_sharepoint_powerpoint_by_handle",
      "content_excerpt": "Older variant slide text.",
      "raw_error": ""
    }
  ],
  "gaps": []
}
```
"""

    with pytest.raises(pipelines.WorkflowPolicyViolation, match="no primary content-read evidence item"):
        pipelines._validated_evidence_text(
            "Please summarise the Integration Strategy full deck v3 1 in detail.",
            raw,
        )


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
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
async def test_run_pipeline_falls_back_when_retrieval_planner_is_empty(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []
    session = FallbackWorkflowSession(trace_calls, stage_calls, "orchestrator-output")
    engine = FakeWorkflowEngine(session)

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
        "Search workspace/knowledge before answering.",
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
    fallback = next(content for stage, content in trace_calls if stage == "RETRIEVAL_PLANNER FALLBACK")
    assert "deterministic fallback handoff" in fallback
    context_prompt = next(prompt for name, prompt in stage_calls if name == "context_retrieval")
    assert "deterministic fallback handoff" in context_prompt


@pytest.mark.anyio
async def test_run_pipeline_checkpoint_continue_runs_downstream_stages(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []
    session = FakeWorkflowSession(trace_calls, stage_calls, "orchestrator-output")
    engine = FakeWorkflowEngine(session)
    checkpoints = []

    async def checkpoint_handler(snapshot):
        checkpoints.append(snapshot)
        return RetrievalCheckpointDecision.continue_()

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
        settings=SimpleNamespace(
            openai_api_key="key",
            log_dir=tmp_path,
            retrieval_checkpoint_enabled=True,
            retrieval_checkpoint_max_redirects=2,
        ),
        server_specs={},
        agent_specs={},
        retrieval_checkpoint_handler=checkpoint_handler,
    )

    assert result == "orchestrator-output"
    assert len(checkpoints) == 1
    assert checkpoints[0].retrieval_prose == "context_retrieval-output"
    assert [name for name, _ in stage_calls] == [
        "retrieval_planner",
        "context_retrieval",
        "context_synthesizer",
        "design",
        "orchestrator",
    ]


@pytest.mark.anyio
async def test_run_pipeline_checkpoint_carries_sanitized_evidence_bundle(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []
    evidence_bundle = """
## Retrieval Summary

Retrieved and read the deck.

## Retrieved Sources

### SharePoint documents
- Source: `Deck.pptx`
  Link: [Deck.pptx](https://example.com/deck.pptx)
  Relevance: Requested document.
  Extract: Slide 1: Strategy overview.

## Retrieval Gaps
- Gap: None.

## Tool Notes
- Tool: read_sharepoint_document_by_handle
  Result: Read the deck.

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
        "read_handle": "sharepoint_doc:secret",
        "metadata": {"read_handle": "sharepoint_doc:nested"}
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

    class EvidenceWorkflowSession(FakeWorkflowSession):
        async def run_stage(self, *, ui_agent_id: str, prompt: str, **kwargs) -> str:
            self._stage_calls.append((ui_agent_id, prompt))
            result = evidence_bundle if ui_agent_id == "context_retrieval" else f"{ui_agent_id}-output"
            output_processor = kwargs.get("output_processor")
            if output_processor is not None:
                output_processor(result)
            return result

    session = EvidenceWorkflowSession(trace_calls, stage_calls, "summary-output")
    engine = FakeWorkflowEngine(session)
    checkpoints = []

    async def checkpoint_handler(snapshot):
        checkpoints.append(snapshot)
        return RetrievalCheckpointDecision.continue_()

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
        settings=SimpleNamespace(
            openai_api_key="key",
            log_dir=tmp_path,
            retrieval_checkpoint_enabled=True,
            retrieval_checkpoint_max_redirects=2,
        ),
        server_specs={},
        agent_specs={},
        retrieval_checkpoint_handler=checkpoint_handler,
    )

    assert result == "summary-output"
    assert checkpoints[0].evidence_bundle["schema_version"] == "evidence_bundle_v1"
    source = checkpoints[0].evidence_bundle["items"][0]["source"]
    assert source["title"] == "Deck.pptx"
    assert "read_handle" not in source
    assert "read_handle" not in source["metadata"]


@pytest.mark.anyio
async def test_run_pipeline_checkpoint_stop_skips_downstream_stages(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []
    session = FakeWorkflowSession(trace_calls, stage_calls, "orchestrator-output")
    engine = FakeWorkflowEngine(session)

    async def checkpoint_handler(snapshot):
        del snapshot
        return RetrievalCheckpointDecision.stop()

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
        settings=SimpleNamespace(
            openai_api_key="key",
            log_dir=tmp_path,
            retrieval_checkpoint_enabled=True,
            retrieval_checkpoint_max_redirects=2,
        ),
        server_specs={},
        agent_specs={},
        retrieval_checkpoint_handler=checkpoint_handler,
    )

    assert result == "Run stopped after retrieval checkpoint. No summary or design stages were executed."
    assert [name for name, _ in stage_calls] == ["retrieval_planner", "context_retrieval"]
    assert ("WORKFLOW_END", "Pipeline workflow stopped after retrieval checkpoint.") in trace_calls


@pytest.mark.anyio
async def test_run_pipeline_checkpoint_redirect_reruns_retrieval(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []
    session = FakeWorkflowSession(trace_calls, stage_calls, "orchestrator-output")
    engine = FakeWorkflowEngine(session)
    decisions = [
        RetrievalCheckpointDecision.redirect("Use the architecture standards folder."),
        RetrievalCheckpointDecision.continue_(),
    ]

    async def checkpoint_handler(snapshot):
        del snapshot
        return decisions.pop(0)

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
        settings=SimpleNamespace(
            openai_api_key="key",
            log_dir=tmp_path,
            retrieval_checkpoint_enabled=True,
            retrieval_checkpoint_max_redirects=2,
        ),
        server_specs={},
        agent_specs={},
        retrieval_checkpoint_handler=checkpoint_handler,
    )

    assert result == "orchestrator-output"
    assert [name for name, _ in stage_calls] == [
        "retrieval_planner",
        "context_retrieval",
        "retrieval_planner",
        "context_retrieval",
        "context_synthesizer",
        "design",
        "orchestrator",
    ]
    assert "Additional retrieval direction from checkpoint 1" in stage_calls[2][1]


@pytest.mark.anyio
async def test_run_pipeline_repairs_missing_required_evidence_bundle(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []
    evidence_bundle = """
## Retrieval Summary

Retrieved and read the deck.

## Retrieved Sources

### SharePoint documents
- Source: `Deck.pptx`
  Link: [Deck.pptx](https://example.com/deck.pptx)
  Relevance: Requested document.
  Extract: Slide 1: Strategy overview.

## Retrieval Gaps
- Gap: None.

## Tool Notes
- Tool: read_sharepoint_document_by_handle
  Result: Read the deck.

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
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
    assert result == "summary draft"
    assert len(context_prompts) == 2
    assert "Repair the retrieval evidence contract" in context_prompts[1]
    assert [name for name, _ in stage_calls] == [
        "retrieval_planner",
        "context_retrieval",
        "context_retrieval",
        "summary",
    ]
    assert ("CONTEXT OUTPUT", "Context synthesizer skipped for summary fast path; validated retrieval evidence passed directly to summary.") in trace_calls
    assert ("FINAL OUTPUT", "Final orchestration skipped for summary fast path; summary output is the final answer.") in trace_calls


@pytest.mark.anyio
async def test_run_pipeline_repairs_final_answer_returned_by_source_retrieval(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []
    retrieval_handoff = """
## Retrieval Summary

Found the active task source.

## Retrieved Sources

### Workspace sources
- Source: `knowledge/reporting-standard.txt`
  Link: [reporting-standard.txt](file://knowledge/reporting-standard.txt)
  Relevance: Reporting controls.
  Extract: Recurring reports need controlled preparation.

## Retrieval Gaps
- Gap: None.

## Tool Notes
- Tool: read_workspace_file
  Result: Read the standard.

```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "Use retrieved workspace context to produce a recommendation.",
  "items": [
    {
      "source": {
        "source_type": "workspace_file",
        "title": "reporting-standard.txt",
        "workspace_path": "knowledge/reporting-standard.txt",
        "metadata": {}
      },
      "evidence_level": "content_read",
      "read_status": "read",
      "read_tool": "read_workspace_file",
      "content_excerpt": "Recurring reports need controlled preparation.",
      "raw_error": ""
    }
  ],
  "gaps": []
}
```
"""

    class RepairingWorkflowSession(FakeWorkflowSession):
        def __init__(self) -> None:
            super().__init__(trace_calls, stage_calls, "final recommendation")
            self.context_calls = 0

        async def run_stage(self, *, ui_agent_id: str, prompt: str, **kwargs) -> str:
            self._stage_calls.append((ui_agent_id, prompt))
            if ui_agent_id == "context_retrieval":
                self.context_calls += 1
                result = (
                    "## Solution design recommendation\n\nUse a controlled Power BI pipeline."
                    if self.context_calls == 1
                    else retrieval_handoff
                )
            elif ui_agent_id == "orchestrator":
                result = self._final_output
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
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
        "Search workspace/knowledge before producing a solution design recommendation.",
        verbose=False,
        review=False,
        settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
        server_specs={},
        agent_specs={},
    )

    context_prompts = [prompt for name, prompt in stage_calls if name == "context_retrieval"]
    assert result == "final recommendation"
    assert len(context_prompts) == 2
    assert "Repair the retrieval evidence contract" in context_prompts[1]
    assert "## Retrieval Summary" in context_prompts[1]
    assert [name for name, _ in stage_calls] == [
        "retrieval_planner",
        "context_retrieval",
        "context_retrieval",
        "context_synthesizer",
        "design",
        "orchestrator",
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
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
async def test_run_peer_pipeline_rework_escalates_directly_to_author(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []

    class ReworkSession(FakeWorkflowSession):
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
                    "Decision: rework\nReason: foundational option choice is wrong."
                    if self.normal_judge_calls == 1
                    else "Decision: accept\nReason: escalation resolved."
                )
            if ui_agent_id == "orchestrator":
                return self._final_output
            return f"{ui_agent_id}-output"

    session = ReworkSession()
    engine = FakeWorkflowEngine(session)

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
async def test_run_peer_pipeline_quality_gate_rework_escalates_to_author(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []

    class QualityGateReworkSession(FakeWorkflowSession):
        def __init__(self):
            super().__init__(trace_calls, stage_calls, "Final recommendation\nShip this.")
            self.quality_gate_calls = 0

        async def run_stage(self, *, ui_agent_id: str, prompt: str, **kwargs) -> str:
            del kwargs
            self._stage_calls.append((ui_agent_id, prompt))
            if ui_agent_id == "judge":
                if prompt.startswith("JUDGE_QUALITY_GATE::"):
                    self.quality_gate_calls += 1
                    return (
                        "Decision: rework\nReason: foundational evidence use is wrong."
                        if self.quality_gate_calls == 1
                        else "Decision: accept\nReason: quality gate passed."
                    )
                return "Decision: accept\nReason: Looks good."
            if ui_agent_id == "orchestrator":
                return self._final_output
            return f"{ui_agent_id}-output"

    session = QualityGateReworkSession()
    engine = FakeWorkflowEngine(session)

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
        "judge",
        "design_author",
        "design_challenger",
        "design_refiner",
        "judge",
        "judge",
        "orchestrator",
    ]


@pytest.mark.anyio
async def test_run_peer_pipeline_revise_then_rework_exits_refiner_loop_for_author(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []

    class ReviseThenReworkSession(FakeWorkflowSession):
        def __init__(self):
            super().__init__(trace_calls, stage_calls, "Final recommendation\nShip this.")
            self.normal_judge_calls = 0
            self.refiner_calls = 0

        async def run_stage(self, *, ui_agent_id: str, prompt: str, **kwargs) -> str:
            del kwargs
            self._stage_calls.append((ui_agent_id, prompt))
            if ui_agent_id == "judge":
                if prompt.startswith("JUDGE_QUALITY_GATE::"):
                    return "Decision: accept\nReason: quality gate passed."
                self.normal_judge_calls += 1
                if self.normal_judge_calls == 1:
                    return "Decision: revise\nReason: tighten evidence."
                if self.normal_judge_calls == 2:
                    return "Decision: rework\nReason: still structurally wrong."
                return "Decision: accept\nReason: escalation resolved."
            if ui_agent_id == "orchestrator":
                return self._final_output
            if ui_agent_id == "design_refiner":
                self.refiner_calls += 1
                return f"refined-draft-{self.refiner_calls}"
            return f"{ui_agent_id}-output"

    session = ReviseThenReworkSession()
    engine = FakeWorkflowEngine(session)

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
        lambda settings, **kwargs: SimpleNamespace(
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
async def test_run_single_retrieval_planner_persists_session_source_candidates(monkeypatch, tmp_path):
    from crisai.cli import chat_context, session_store

    settings = SimpleNamespace(
        openai_api_key="key",
        log_dir=tmp_path,
        workspace_dir=tmp_path,
        registry_dir=Path(__file__).resolve().parents[2] / "registry",
    )
    monkeypatch.setattr(session_store, "load_settings", lambda: settings)
    monkeypatch.setattr(chat_context, "load_settings", lambda: settings)
    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings, **kwargs: SimpleNamespace(
            root_dir=tmp_path,
            trace_file=tmp_path / "trace.log",
            runtime=SimpleNamespace(build_server=lambda server_spec: server_spec),
            factory=SimpleNamespace(build_agent=lambda spec, active_servers: SimpleNamespace(id=spec.id)),
            run_id="test-run-id",
        ),
    )

    async def _fake_run_agent_silently(agent, prompt: str) -> str:
        del agent, prompt
        return (
            "Found files:\n\n"
            "| File | Location | Note |\n"
            "|---|---|---|\n"
            "| [UCL Integration Strategy_Full Presentation v2.pptx]"
            "(https://liveuclac.sharepoint.com/sites/DataTeam/_layouts/15/Doc.aspx?sourcedoc=%7BDD876D07-51C7-54B0-8ACE-E78B49D3F954%7D&file=v2.pptx) "
            "| OneDrive | Exact title phrase. |"
        )

    monkeypatch.setattr(pipelines, "_run_agent_silently", _fake_run_agent_silently)

    await pipelines.run_single(
        "Find Integration Strategy files on OneDrive.",
        "retrieval_planner",
        settings=settings,
        server_specs={},
        agent_specs={"retrieval_planner": SimpleNamespace(id="retrieval_planner", allowed_servers=[])},
        session_name="NewTest-04",
    )

    memory = session_store.load_session_memory("NewTest-04")

    assert memory.source_candidates
    assert memory.source_candidates[0].title == "UCL Integration Strategy_Full Presentation v2.pptx"


@pytest.mark.anyio
async def test_run_single_emits_fail_open_deterministic_trace_when_graph_missing(monkeypatch, tmp_path):
    captured_events: list[tuple[str, str, dict | None]] = []

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings, **kwargs: SimpleNamespace(
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
        "append_trace_entry",
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
    metadata = deterministic_events[0][2]
    assert metadata is not None
    assert metadata["mode"] == "single"


@pytest.mark.anyio
async def test_run_single_emits_stage_start_before_completion(monkeypatch, tmp_path):
    captured_events: list[tuple[str, str, dict]] = []

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings, **kwargs: SimpleNamespace(
            root_dir=tmp_path,
            trace_file=tmp_path / "trace.log",
            runtime=SimpleNamespace(build_server=lambda server_spec: server_spec),
            factory=SimpleNamespace(build_agent=lambda spec, active_servers: SimpleNamespace(id=spec.id)),
            run_id="test-run-id",
        ),
    )

    async def _fake_run_agent_silently(agent, prompt: str) -> str:
        del agent, prompt
        stage_events = [event for event in captured_events if event[2].get("event_type") == "stage_start"]
        assert stage_events
        return "single output"

    monkeypatch.setattr(pipelines, "_run_agent_silently", _fake_run_agent_silently)
    monkeypatch.setattr(
        pipelines,
        "append_trace_entry",
        lambda environment, stage, content, **kwargs: captured_events.append((stage, content, kwargs)),
    )

    result = await pipelines.run_single(
        "Find integration principles.",
        "retrieval_planner",
        settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
        server_specs={},
        agent_specs={"retrieval_planner": SimpleNamespace(id="retrieval_planner", allowed_servers=[])},
    )

    stage_events = [
        (stage, content, kwargs)
        for stage, content, kwargs in captured_events
        if kwargs.get("event_type") in {"stage_start", "stage_end"}
    ]
    assert result == "single output"
    assert stage_events == [
        (
            "RETRIEVAL_PLANNER OUTPUT_START",
            "Starting stage for retrieval_planner.",
            {"event_type": "stage_start", "agent_id": "retrieval_planner"},
        ),
        (
            "RETRIEVAL_PLANNER OUTPUT_END",
            "Completed stage for retrieval_planner.",
            {"event_type": "stage_end", "agent_id": "retrieval_planner"},
        ),
    ]


@pytest.mark.anyio
async def test_run_single_attaches_observability_to_workflow_output(monkeypatch, tmp_path, caplog):
    trace_calls: list[tuple[str, str, dict]] = []

    class FakeResolver:
        def resolve_for_agent(self, spec):
            assert spec.id == "retrieval_planner"
            return SimpleNamespace(
                provider="openai",
                model_name="gpt-example",
                source="model_ref:openai_fast",
                extra={
                    "pricing": {
                        "currency": "USD",
                        "unit": "per_1m_tokens",
                        "input": "10",
                        "output": "20",
                    }
                },
            )

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings, **kwargs: SimpleNamespace(
            root_dir=tmp_path,
            trace_file=tmp_path / "trace.log",
            runtime=SimpleNamespace(build_server=lambda server_spec: server_spec),
            factory=SimpleNamespace(
                model_resolver=FakeResolver(),
                build_agent=lambda spec, active_servers: SimpleNamespace(id=spec.id),
            ),
            run_id="test-run-id",
        ),
    )

    async def _fake_run_agent_silently(agent, prompt: str) -> str:
        del agent, prompt
        pipeline_display._emit_stage_observability(
            "provider_usage",
            {"provider_usage": {"input_tokens": 8, "output_tokens": 4, "total_tokens": 12}},
        )
        return "single output"

    def _capture_trace(log_file, stage, content, **kwargs):
        del log_file
        trace_calls.append((stage, content, kwargs))

    monkeypatch.setattr(pipelines, "_run_agent_silently", _fake_run_agent_silently)
    monkeypatch.setattr(pipelines, "append_trace", _capture_trace)

    with caplog.at_level(logging.INFO, logger="crisai.cli.pipeline_engine"):
        result = await pipelines.run_single(
            "Find integration principles.",
            "retrieval_planner",
            settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
            server_specs={},
            agent_specs={"retrieval_planner": SimpleNamespace(id="retrieval_planner", allowed_servers=[])},
        )

    workflow_output = next(call for call in trace_calls if call[2].get("event_type") == "workflow_output")
    assert result == "single output"
    assert workflow_output[0] == "FINAL_OUTPUT"
    assert workflow_output[1] == "single output"
    assert workflow_output[2]["run_id"] == "test-run-id"
    assert workflow_output[2]["agent_id"] == "retrieval_planner"
    observability = workflow_output[2]["metadata"]["observability"]
    assert observability["schema_version"] == "ui_stage_observability_v1"
    assert observability["provider_usage"] == {"input_tokens": 8, "output_tokens": 4, "total_tokens": 12}
    assert observability["model"] == {
        "schema_version": "model_observability_v1",
        "provider": "openai",
        "model_name": "gpt-example",
        "source": "model_ref:openai_fast",
        "model_ref": "openai_fast",
    }
    assert observability["cost"] == {
        "schema_version": "usage_cost_v1",
        "currency": "USD",
        "estimated": True,
        "pricing_source": "model_ref:openai_fast",
        "pricing_unit": "per_1m_tokens",
        "input_cost_usd": 8e-05,
        "output_cost_usd": 8e-05,
        "total_cost_usd": 0.00016,
    }
    assert observability["execution_time"]["started_at"]
    assert observability["execution_time"]["ended_at"]
    assert observability["execution_time"]["duration_ms"] >= 0
    log_record = next(
        record for record in caplog.records if getattr(record, "event_type", None) == "agent_stage_observability"
    )
    assert log_record.run_id == "test-run-id"
    assert log_record.agent_id == "retrieval_planner"
    assert log_record.stage == "retrieval_planner"
    assert log_record.trace_label == "FINAL_OUTPUT"
    assert log_record.provider_usage == {"input_tokens": 8, "output_tokens": 4, "total_tokens": 12}
    assert log_record.usage_cost == observability["cost"]
    assert log_record.model == observability["model"]
    assert log_record.execution_time == observability["execution_time"]
    assert "single output" not in log_record.getMessage()


@pytest.mark.anyio
async def test_run_single_attaches_execution_time_to_stage_error(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str, dict]] = []

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings, **kwargs: SimpleNamespace(
            root_dir=tmp_path,
            trace_file=tmp_path / "trace.log",
            runtime=SimpleNamespace(build_server=lambda server_spec: server_spec),
            factory=SimpleNamespace(build_agent=lambda spec, active_servers: SimpleNamespace(id=spec.id)),
            run_id="test-run-id",
        ),
    )

    async def _fake_run_agent_silently(agent, prompt: str) -> str:
        del agent, prompt
        raise RuntimeError("provider failed")

    def _capture_trace(log_file, stage, content, **kwargs):
        del log_file
        trace_calls.append((stage, content, kwargs))

    monkeypatch.setattr(pipelines, "_run_agent_silently", _fake_run_agent_silently)
    monkeypatch.setattr(pipelines, "append_trace", _capture_trace)

    with pytest.raises(RuntimeError, match="provider failed"):
        await pipelines.run_single(
            "Find integration principles.",
            "retrieval_planner",
            settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
            server_specs={},
            agent_specs={"retrieval_planner": SimpleNamespace(id="retrieval_planner", allowed_servers=[])},
        )

    stage_error = next(call for call in trace_calls if call[2].get("event_type") == "stage_error")
    assert stage_error[0] == "RETRIEVAL_PLANNER OUTPUT_ERROR"
    assert stage_error[1] == "Stage retrieval_planner failed: RuntimeError: provider failed"
    assert stage_error[2]["run_id"] == "test-run-id"
    assert stage_error[2]["agent_id"] == "retrieval_planner"
    assert stage_error[2]["metadata"]["error_type"] == "RuntimeError"
    observability = stage_error[2]["metadata"]["observability"]
    assert observability["schema_version"] == "ui_stage_observability_v1"
    assert observability["execution_time"]["started_at"]
    assert observability["execution_time"]["ended_at"]
    assert observability["execution_time"]["duration_ms"] >= 0


@pytest.mark.anyio
async def test_run_single_rejects_source_inventory_titles_that_miss_required_phrase(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str, dict]] = []

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings, **kwargs: SimpleNamespace(
            root_dir=tmp_path,
            trace_file=tmp_path / "trace.log",
            runtime=SimpleNamespace(build_server=lambda server_spec: server_spec),
            factory=SimpleNamespace(build_agent=lambda spec, active_servers: SimpleNamespace(id=spec.id)),
            run_id="test-run-id",
        ),
    )

    async def _fake_run_agent_silently(agent, prompt: str) -> str:
        del agent, prompt
        return (
            "| File | Location |\n"
            "|---|---|\n"
            "| [STOP - InfinityFinanceIntegrationDesign.docx]"
            "(https://liveuclac-my.sharepoint.com/personal/user/doc.aspx) | OneDrive |\n"
        )

    def _capture_trace(log_file, stage, content, **kwargs):
        del log_file
        trace_calls.append((stage, content, kwargs))

    monkeypatch.setattr(pipelines, "_run_agent_silently", _fake_run_agent_silently)
    monkeypatch.setattr(pipelines, "append_trace", _capture_trace)

    with pytest.raises(pipelines.WorkflowPolicyViolation, match="Rejected source title"):
        await pipelines.run_single(
            "Find all the documents on my onedrive with Integration Strategy in the title and list the best 3.",
            "retrieval_planner",
            settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path, registry_dir=REGISTRY_DIR),
            server_specs={},
            agent_specs={"retrieval_planner": SimpleNamespace(id="retrieval_planner", allowed_servers=[])},
        )

    stage_error = next(call for call in trace_calls if call[2].get("event_type") == "stage_error")
    assert stage_error[0] == "RETRIEVAL_PLANNER OUTPUT_ERROR"
    assert "Required title phrase(s): Integration Strategy." in stage_error[1]
    assert "STOP - InfinityFinanceIntegrationDesign.docx" in stage_error[1]
    assert stage_error[2]["metadata"]["error_type"] == "SourceFitConstraintViolation"


@pytest.mark.anyio
async def test_run_single_policy_uses_latest_user_intent_not_history_wrapper(monkeypatch, tmp_path):
    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings, **kwargs: SimpleNamespace(
            root_dir=tmp_path,
            trace_file=tmp_path / "trace.log",
            runtime=SimpleNamespace(build_server=lambda server_spec: server_spec),
            factory=SimpleNamespace(build_agent=lambda spec, active_servers: SimpleNamespace(id=spec.id)),
            run_id="test-run-id",
        ),
    )

    async def _fake_run_agent_silently(agent, prompt: str) -> str:
        del agent, prompt
        return "option paper prose"

    monkeypatch.setattr(pipelines, "_run_agent_silently", _fake_run_agent_silently)
    history_wrapped_prompt = (
        "Conversation so far:\n"
        "Active task workspace:\n"
        "- Artefacts: workspace/tasks/Power-BI_CB_dashboard/artefacts\n\n"
        "Latest user message:\n"
        "Please generate an option paper."
    )

    result = await pipelines.run_single(
        history_wrapped_prompt,
        "design",
        settings=SimpleNamespace(openai_api_key="key", log_dir=tmp_path),
        server_specs={},
        agent_specs={"design": SimpleNamespace(id="design", allowed_servers=[])},
        user_intent_message="Please generate an option paper.",
    )

    assert result == "option paper prose"


@pytest.mark.anyio
async def test_run_pipeline_enforces_intranet_fetch_policy(monkeypatch, tmp_path):
    trace_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []

    class WorkspaceEvidenceWorkflowSession(FakeWorkflowSession):
        async def run_stage(self, *, ui_agent_id: str, prompt: str, **kwargs) -> str:
            self._stage_calls.append((ui_agent_id, prompt))
            result = (
                _workspace_retrieval_handoff(request="Use intranet site pages only and produce grounded output.")
                if ui_agent_id == "context_retrieval"
                else f"{ui_agent_id}-output"
            )
            output_processor = kwargs.get("output_processor")
            if output_processor is not None:
                output_processor(result)
            return result

    session = WorkspaceEvidenceWorkflowSession(trace_calls, stage_calls, "orchestrator-output")
    engine = FakeWorkflowEngine(session)

    monkeypatch.setattr(pipelines, "ensure_openai_api_key", lambda settings: None)
    monkeypatch.setattr(
        pipelines,
        "create_workflow_environment",
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
    author_kwargs = capture["author_kwargs"]
    assert isinstance(author_kwargs, dict)
    assert "deterministic_context" in author_kwargs


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
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
            "Write with write_workspace_file under workspace/knowledge_staging/patterns/",
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
        lambda settings, **kwargs: SimpleNamespace(trace_file=tmp_path / "trace.log"),
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
            "workspace/knowledge_staging/patterns/producer-pattern-1-system-to-enterprise-api-ondemand-synchronous.md"
        ],
    )

    def _fake_verify(*, root_dir, contract, final_text, changed_paths):
        del root_dir, contract, changed_paths
        verify_calls.append(final_text)
        if len(verify_calls) == 1:
            raise pipelines.PeerVerificationViolation(
                "Peer verifier gate failed:\n- Referenced output file does not exist: "
                "workspace/knowledge_staging/patterns/producer-pattern-1-system-to-enterprise-api-synchronous.md"
            )
        return SimpleNamespace(
            checked_files=(
                "workspace/knowledge_staging/patterns/producer-pattern-1-system-to-enterprise-api-ondemand-synchronous.md",
            ),
            violations=(),
        )

    monkeypatch.setattr(pipelines, "enforce_peer_final_deliverable_verification", _fake_verify)

    result = await pipelines.run_peer_pipeline(
        "Write with write_workspace_file under workspace/knowledge_staging/patterns/",
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
