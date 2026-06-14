from __future__ import annotations

from crisai import openai_agents_trace_compat as compat_module

compat_module.apply_openai_agents_trace_export_patch()

import copy
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from crisai import logging_utils as logging_utils_module
from crisai import runtime as runtime_module
from crisai import tracing as tracing_module
from crisai.agents import factory as factory_module
from crisai.cli import artefact_lifecycle as lifecycle_module
from crisai.cli import chat_context as chat_context_module
from crisai.cli import peer_transcript as peer_transcript_module
from crisai.cli import pipeline_display as display_module
from crisai.cli import pipeline_engine as engine_module
from crisai.cli import session_store as session_store_module
from crisai.cli import workflow_policy as policy_module
from crisai.cli import workflow_support as support_module
from crisai.orchestration import evidence_contract as evidence_contract_module
from crisai.orchestration import exceptions as exceptions_module
from crisai.orchestration import peer_contract as peer_contract_module
from crisai.orchestration import peer_evidence as peer_evidence_module
from crisai.orchestration import peer_judge as peer_judge_module
from crisai.orchestration import peer_verifier as peer_verifier_module
from crisai.orchestration import prompt_generation as prompt_generation_module
from crisai.orchestration import request_contract as request_contract_module
from crisai.orchestration import retrieval_association_graph as graph_module
from crisai.orchestration import retrieval_checkpoint as checkpoint_module
from crisai.orchestration import session_anchors as session_anchors_module
from crisai.orchestration import source_constraints as constraints_module
from crisai.orchestration import source_materialisation as source_materialisation_module
from crisai.orchestration import source_resolution as resolution_module
from crisai.orchestration import task_contract as task_contract_module

AgentFactory = factory_module.AgentFactory
get_logger = logging_utils_module.get_logger

EvidenceBundle = evidence_contract_module.EvidenceBundle
EvidenceItem = evidence_contract_module.EvidenceItem
parse_evidence_bundle = evidence_contract_module.parse_evidence_bundle
request_requires_content_read = evidence_contract_module.request_requires_content_read

WorkflowValidationError = exceptions_module.WorkflowValidationError

infer_peer_run_contract = peer_contract_module.infer_peer_run_contract
render_peer_run_contract = peer_contract_module.render_peer_run_contract

_build_peer_filesystem_evidence = peer_evidence_module._build_peer_filesystem_evidence
_build_peer_final_repair_prompt = peer_evidence_module._build_peer_final_repair_prompt
_format_runtime_changed_files_manifest = peer_evidence_module._format_runtime_changed_files_manifest
_is_repairable_peer_verifier_failure = peer_evidence_module._is_repairable_peer_verifier_failure

_build_prompt_with_contract = peer_judge_module._build_prompt_with_contract
_extract_final_recommendation = peer_judge_module._extract_final_recommendation
_judge_reason_excerpt = peer_judge_module._judge_reason_excerpt
_resolve_peer_max_escalations = peer_judge_module._resolve_peer_max_escalations
_resolve_peer_max_refinement_rounds = peer_judge_module._resolve_peer_max_refinement_rounds
_run_judge_with_acceptance_audit = peer_judge_module._run_judge_with_acceptance_audit
_trace_peer_flow_event = peer_judge_module._trace_peer_flow_event

PeerVerificationViolation = peer_verifier_module.PeerVerificationViolation
enforce_peer_final_deliverable_verification = peer_verifier_module.enforce_peer_final_deliverable_verification

build_author_prompt = prompt_generation_module.build_author_prompt
build_challenger_prompt = prompt_generation_module.build_challenger_prompt
build_context_retrieval_prompt = prompt_generation_module.build_context_retrieval_prompt
build_context_retrieval_repair_prompt = prompt_generation_module.build_context_retrieval_repair_prompt
build_context_synthesizer_prompt = prompt_generation_module.build_context_synthesizer_prompt
build_design_prompt = prompt_generation_module.build_design_prompt
build_peer_final_prompt = prompt_generation_module.build_peer_final_prompt
build_pipeline_final_prompt = prompt_generation_module.build_pipeline_final_prompt
build_refiner_prompt = prompt_generation_module.build_refiner_prompt
build_retrieval_planner_prompt = prompt_generation_module.build_retrieval_planner_prompt
build_review_prompt = prompt_generation_module.build_review_prompt
build_single_retrieval_planner_prompt = prompt_generation_module.build_single_retrieval_planner_prompt
build_summary_prompt = prompt_generation_module.build_summary_prompt

RequestContract = request_contract_module.RequestContract
infer_request_contract = request_contract_module.infer_request_contract
render_request_contract_block = request_contract_module.render_request_contract_block

DeterministicRetrievalContext = graph_module.DeterministicRetrievalContext
deterministic_context_from_registry = graph_module.deterministic_context_from_registry
deterministic_context_trace_metadata = graph_module.deterministic_context_trace_metadata

RetrievalCheckpointHandler = checkpoint_module.RetrievalCheckpointHandler
RetrievalCheckpointSnapshot = checkpoint_module.RetrievalCheckpointSnapshot

SourceFitConstraints = constraints_module.SourceFitConstraints
evidence_bundle_satisfies_constraints = constraints_module.evidence_bundle_satisfies_constraints
evidence_item_satisfies_constraints = constraints_module.evidence_item_satisfies_constraints
infer_source_fit_constraints = constraints_module.infer_source_fit_constraints
source_fit_failure_message = constraints_module.source_fit_failure_message
source_inventory_failure_message = constraints_module.source_inventory_failure_message

latest_source_conflict_message = resolution_module.latest_source_conflict_message

TaskContract = task_contract_module.TaskContract
infer_task_contract = task_contract_module.infer_task_contract
render_task_contract_block = task_contract_module.render_task_contract_block

MultiServerContext = runtime_module.MultiServerContext
RuntimeManager = runtime_module.RuntimeManager

TRACE_FILE_NAME = tracing_module.TRACE_FILE_NAME
append_trace = tracing_module.append_trace

validate_task_artefacts_for_request = lifecycle_module.validate_task_artefacts_for_request
persist_session_source_candidates_from_output = chat_context_module.persist_session_source_candidates_from_output

PeerMessage = peer_transcript_module.PeerMessage
PeerRunResult = peer_transcript_module.PeerRunResult
append_peer_message = peer_transcript_module.append_peer_message

_run_agent_silently = display_module._run_agent_silently
_run_agent_with_progress = display_module._run_agent_with_progress
print_agent_output = display_module.print_agent_output
reset_stage_observability_agent_id = display_module.reset_stage_observability_agent_id
reset_stage_observability_callback = display_module.reset_stage_observability_callback
sanitize_user_visible_text = display_module.sanitize_user_visible_text
set_stage_observability_agent_id = display_module.set_stage_observability_agent_id
set_stage_observability_callback = display_module.set_stage_observability_callback

WorkflowEngine = engine_module.WorkflowEngine
_execution_time_metadata = engine_module._execution_time_metadata
_log_successful_agent_stage = engine_module._log_successful_agent_stage
_merge_stage_observability_metadata = engine_module._merge_stage_observability_metadata
_resolve_model_observability = engine_module._resolve_model_observability
_utc_now_iso = engine_module._utc_now_iso

load_session_anchors = session_store_module.load_session_anchors
load_session_memory = session_store_module.load_session_memory
register_task_artefacts = session_store_module.register_task_artefacts
sanitize_session_name = session_store_module.sanitize_session_name

WorkflowPolicyViolation = policy_module.WorkflowPolicyViolation
changed_paths = policy_module.changed_paths
enforce_intranet_fetch_policy = policy_module.enforce_intranet_fetch_policy
enforce_workspace_authorized_write_validation = policy_module.enforce_workspace_authorized_write_validation
enforce_workspace_write_policy = policy_module.enforce_workspace_write_policy
infer_workflow_policy = policy_module.infer_workflow_policy
snapshot_tree = policy_module.snapshot_tree
workspace_write_authorization_env = policy_module.workspace_write_authorization_env
workspace_write_authorization_from_contract = policy_module.workspace_write_authorization_from_contract

WorkflowEnvironment = support_module.WorkflowEnvironment
_get_run_id = support_module._get_run_id
collect_server_ids = support_module.collect_server_ids
ensure_openai_api_key = support_module.ensure_openai_api_key
resolve_required_agents = support_module.resolve_required_agents

logger = get_logger(__name__)


def _empty_deterministic_context() -> DeterministicRetrievalContext:
    return DeterministicRetrievalContext(
        schema_version="deterministic_context_v1",
        activated_topic_ids=frozenset(),
        suggested_terms=frozenset(),
        suggested_sources=frozenset(),
        graph_loaded=False,
        graph_version="unavailable",
    )


def _infer_runtime_request_contract(
    intent_message: str,
    *,
    registry_dir: Path | None,
    deterministic_context: DeterministicRetrievalContext,
    current_mode: str | None = None,
    session_name: str | None = None,
) -> RequestContract:
    """Infer request contract with the configured registry as fallback."""
    anchor_registry = load_session_anchors(session_name) if session_name else None
    source_candidates = tuple(load_session_memory(session_name).source_candidates) if session_name else ()
    try:
        return infer_request_contract(
            intent_message,
            current_mode=current_mode,
            registry_dir=registry_dir,
            deterministic_context=deterministic_context,
            anchor_registry=anchor_registry,
            source_candidates=source_candidates,
        )
    except FileNotFoundError:
        if registry_dir is None:
            raise
        return infer_request_contract(
            intent_message,
            current_mode=current_mode,
            registry_dir=None,
            deterministic_context=deterministic_context,
            anchor_registry=anchor_registry,
            source_candidates=source_candidates,
        )


def _deterministic_advisory_enabled() -> bool:
    return os.getenv("CRISAI_DETERMINISTIC_MCP_ADVISORY", "").strip().lower() in {"1", "true", "yes", "on"}


def _source_materialisation_enabled(settings: Any) -> bool:
    """Opt-in gate for checkpoint-time source materialisation (CRISAI-ADR-015 2b).

    Off by default: enable with ``CRISAI_MATERIALISE_SOURCES`` (or a settings
    ``materialise_sources_enabled``) so the live fetch lands behind a switch.
    """
    explicit = getattr(settings, "materialise_sources_enabled", None)
    if explicit is not None:
        return bool(explicit)
    return os.getenv("CRISAI_MATERIALISE_SOURCES", "").strip().lower() in {"1", "true", "yes", "on"}


def _confirmed_source_identity(source: Any) -> str:
    """Stable id for a confirmed source, consistent with anchor identity."""
    content_id = (getattr(source, "content_id", "") or "").strip()
    if content_id:
        return content_id.lower()
    guid = session_anchors_module._sourcedoc_identity(getattr(source, "open_url", "") or "")
    if guid:
        return guid
    return (getattr(source, "open_url", "") or "").strip().lower()


async def _materialise_confirmed_sources(
    bundle: Any,
    *,
    environment: Any,
    server_specs: Any,
    session_name: str | None,
    settings: Any,
    workflow: Any,
) -> None:
    """Materialise confirmed content-read sources into the per-task evidence cache.

    Best-effort and opt-in: a source read during this turn is fetched once and
    cached, so later turns read a stable copy rather than re-querying live
    OneDrive/SharePoint (CRISAI-ADR-015 Phase 2b). Workspace-local and handle-less
    sources are skipped; failures are traced and never abort the run.
    """
    if not _source_materialisation_enabled(settings) or bundle is None or not session_name:
        return
    sharepoint_spec = server_specs.get("sharepoint_docs") if isinstance(server_specs, dict) else None
    if sharepoint_spec is None:
        return
    # Cache under a visible, readable per-task `sources/` directory (the task root,
    # not the sensitive `.crisai/` tree) so the agent can read the cached copy via
    # the workspace tools and the user can see and delete it (ADR-015 2b).
    task_state_dir = session_store_module.task_dir(session_name)
    workspace_root = Path(getattr(settings, "workspace_dir", "."))
    for item in getattr(bundle, "items", ()) or ():
        source = getattr(item, "source", None)
        if source is None or getattr(item, "evidence_level", "") != "content_read":
            continue
        if (getattr(source, "source_type", "") or "").startswith("workspace"):
            continue
        read_handle = (getattr(source, "read_handle", "") or "").strip()
        if not read_handle:
            continue
        source_id = _confirmed_source_identity(source)
        if not source_id:
            continue
        try:
            outcome = await source_materialisation_module.materialise_source(
                source_id=source_id,
                read_handle=read_handle,
                server_spec=sharepoint_spec,
                runtime=environment.runtime,
                task_state_dir=task_state_dir,
                workspace_root=workspace_root,
            )
        except Exception as exc:  # noqa: BLE001 - never break the run on materialisation
            _trace_workflow_policy_event(
                workflow, "SOURCE_MATERIALISE_ERROR", f"{source_id}: {exc}", event_type="source_signal",
            )
            continue
        record = outcome.record
        if record is not None:
            # Stamp the session candidate with the cache pointer so a later turn
            # can ground on the cached copy (ADR-015 2b read-through).
            chat_context_module.record_materialised_source(
                session_name,
                source_id=source_id,
                materialised_path=record.raw_path,
                revision=record.revision,
            )
            _trace_workflow_policy_event(
                workflow,
                "SOURCE_CACHE_HIT" if outcome.cache_hit else "SOURCE_MATERIALISED",
                f"{record.title or source_id} ({record.revision})",
                event_type="source_signal",
                metadata={
                    "source_id": source_id,
                    "revision": record.revision,
                    "cache_hit": outcome.cache_hit,
                    "bytes": record.byte_size,
                    "workspace_path": record.raw_path,
                },
            )
        elif outcome.error:
            _trace_workflow_policy_event(
                workflow, "SOURCE_MATERIALISE_SKIPPED", f"{source_id}: {outcome.error}",
                event_type="source_signal",
            )


def _is_empty_stage_output_error(exc: Exception, *, agent_id: str) -> bool:
    """Return whether an exception is the workflow engine's empty-output failure."""
    return f"Stage {agent_id} returned empty output" in str(exc)


def _build_retrieval_planner_fallback(
    message: str,
    *,
    deterministic_context: DeterministicRetrievalContext,
    task_contract: TaskContract,
    request_contract: RequestContract | None = None,
) -> str:
    """Build a deterministic retrieval handoff when the planner emits no text."""
    del message
    terms = ", ".join(sorted(deterministic_context.suggested_terms)[:24]) or "(none)"
    sources = ", ".join(sorted(deterministic_context.suggested_sources)) or "(none)"
    topics = ", ".join(sorted(deterministic_context.activated_topic_ids)) or "(none)"
    resolved_sources = (
        ", ".join(reference.source.title for reference in request_contract.resolved_sources)
        if request_contract is not None and request_contract.resolved_sources
        else "(none)"
    )
    return (
        "Retrieval planner returned empty output; continuing with deterministic fallback handoff.\n"
        "- Retrieval focus: use the user request as the authoritative retrieval brief and search/read local workspace "
        "context when the request asks for local documents or workspace context.\n"
        "- Resolved prior-turn sources: "
        f"{resolved_sources}. Prefer these source identities when present and re-search/refetch/read with current tools.\n"
        f"- Deliverable to support: {task_contract.deliverable_type}; primary intent: {task_contract.primary_intent}.\n"
        "- Open explicit workspace-relative paths first when present; otherwise list/search likely workspace knowledge, "
        "standards, patterns, notes, templates, and prior designs relevant to the request.\n"
        f"- Activated topics: {topics}.\n"
        f"- Query terms: {terms}.\n"
        f"- Source priority: {sources}.\n"
        "- Retrieval gaps to resolve: identify missing local evidence, unreadable files, or unavailable expected sources."
    )


def _trace_workflow_policy_event(
    workflow: Any,
    stage: str,
    content: str,
    *,
    event_type: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Trace policy events when the workflow session exposes trace_event."""
    tracer = getattr(workflow, "trace_event", None)
    if callable(tracer):
        tracer(stage, content, event_type=event_type, metadata=metadata)


def _enforce_workspace_write_and_validation(
    policy,
    authorization,
    root_dir: Path,
    write_before,
    registry_dir: Path | None,
) -> list[str]:
    """Enforce workspace side effects and validate explicit knowledge writes."""
    changed = enforce_workspace_write_policy(policy, root_dir, write_before)
    enforce_workspace_authorized_write_validation(
        authorization,
        root_dir=root_dir,
        changed=changed,
        registry_dir=registry_dir,
    )
    return changed


def _apply_mcp_env_overrides(environment: Any, overrides: dict[str, str]) -> None:
    """Attach MCP subprocess environment overrides to the workflow environment."""
    if not overrides:
        return
    current = getattr(environment, "mcp_env_overrides", None)
    if current is None:
        setattr(environment, "mcp_env_overrides", dict(overrides))
        return
    current.update(overrides)


def _session_memory_env(session_name: str | None) -> dict[str, str]:
    """Return MCP env that scopes session-memory tools to the active session."""
    if not session_name:
        return {}
    return {"CRISAI_SESSION_MEMORY_SESSION": session_name}


def _write_target_subdir_from_contract(contract: RequestContract) -> str | None:
    """Return the subtree to monitor when a contract requires artefact publication."""
    if contract.output_target_subdir:
        return contract.output_target_subdir
    if "publish_artifact" in contract.actions:
        return "workspace/tasks"
    return None


def _register_and_validate_task_artefacts(
    *,
    workflow: Any | None,
    session_name: str | None,
    changed: list[str],
    root_dir: Path,
    user_input: str,
    deliverable_type: str = "",
    request_contract: RequestContract | None = None,
) -> None:
    """Register changed task artefacts and enforce template checks when relevant."""
    if not session_name or not changed:
        return
    safe = sanitize_session_name(session_name)
    task_artefacts = [
        path
        for path in changed
        if path.startswith(f"workspace/tasks/{safe}/artefacts/") and path.endswith(".md")
    ]
    if not task_artefacts:
        return
    warnings = validate_task_artefacts_for_request(
        user_input=user_input,
        paths=task_artefacts,
        root_dir=root_dir,
        referenced_anchors=request_contract.referenced_anchors if request_contract is not None else (),
    )
    if warnings:
        message = "Task artefact conformance failed. " + " ".join(warnings)
        if workflow is not None:
            _trace_workflow_policy_event(
                workflow,
                "POLICY_VIOLATION",
                message,
                event_type="policy_violation",
            )
        raise WorkflowPolicyViolation(message)
    register_task_artefacts(
        session_name,
        task_artefacts,
        request=user_input,
        deliverable_type=deliverable_type,
        root_dir=root_dir,
    )
    if workflow is not None:
        _trace_workflow_policy_event(
            workflow,
            "TASK_ARTEFACTS_REGISTERED",
            "\n".join(task_artefacts),
            event_type="policy_signal",
            metadata={"changed_count": len(task_artefacts)},
        )


@dataclass(frozen=True, slots=True)
class ValidatedEvidenceTransport:
    """Clean prose plus typed evidence carried between retrieval stages."""

    prose: str
    bundle: EvidenceBundle | None
    evidence_brief: str

    @property
    def prompt_text(self) -> str:
        """Return readable retrieval context for downstream prompts."""
        if not self.evidence_brief:
            return self.prose
        sections = [self.prose.strip(), "## Validated Evidence Summary", self.evidence_brief.strip()]
        return "\n\n".join(section for section in sections if section)

    @property
    def trace_metadata(self) -> dict[str, Any] | None:
        """Return structured trace metadata for machine evidence artifacts."""
        if self.bundle is None:
            return None
        return {
            "artifacts": {
                "evidence_bundle_v1": self.bundle.to_sanitized_dict(),
            },
            "evidence_summary": self.evidence_brief,
        }


@dataclass(slots=True)
class EvidenceValidationCapture:
    """Capture parsed evidence transport from a retrieval stage output."""

    intent_message: str
    require_evidence_bundle: bool = False
    require_retrieval_structure: bool = False
    transport: ValidatedEvidenceTransport | None = None
    error: WorkflowPolicyViolation | None = None

    def process(self, raw_text: str) -> tuple[str, dict[str, Any] | None]:
        """Parse evidence output and keep validation failures available to callers."""
        try:
            self.transport = _validated_evidence_transport(
                self.intent_message,
                raw_text,
                require_evidence_bundle=self.require_evidence_bundle,
                require_retrieval_structure=self.require_retrieval_structure,
            )
        except WorkflowPolicyViolation as exc:
            self.error = exc
            self.transport = ValidatedEvidenceTransport(
                prose=sanitize_user_visible_text(raw_text),
                bundle=None,
                evidence_brief="",
            )
            return self.transport.prose, {"evidence_validation_error": str(exc)}
        self.error = None
        return self.transport.prose, self.transport.trace_metadata


def _evidence_brief(bundle: EvidenceBundle) -> str:
    """Render a human-readable evidence summary for downstream agents."""
    lines = [f"- Request covered: {bundle.request}"]
    for item in bundle.items:
        source = item.source
        source_bits = [source.title]
        if source.location:
            source_bits.append(source.location)
        if source.source_type:
            source_bits.append(source.source_type)
        metadata_bits = []
        for key in ("createdDateTime", "lastModifiedDateTime", "mimeType"):
            value = source.metadata.get(key)
            if value:
                metadata_bits.append(f"{key}: {value}")
        detail = "; ".join(source_bits)
        if metadata_bits:
            detail = f"{detail}; " + "; ".join(metadata_bits)
        line = f"- {item.evidence_level} / {item.read_status}: {detail}"
        if item.evidence_role == "supplemental":
            line = "- supplemental " + line[2:]
        if item.read_tool:
            line += f" via {item.read_tool}"
        lines.append(line)
        if item.content_excerpt.strip():
            lines.append(f"  Evidence excerpt: {item.content_excerpt.strip()}")
        if item.raw_error.strip():
            lines.append(f"  Retrieval error: {item.raw_error.strip()}")
    if bundle.gaps:
        lines.append("- Gaps: " + "; ".join(gap for gap in bundle.gaps if gap))
    return "\n".join(lines)


def _requires_retrieval_evidence_contract(request_contract: RequestContract) -> bool:
    """Return whether the retrieval stage must provide structured evidence."""
    return bool(request_contract.source_required or "source_evidence" in request_contract.quality_gates)


def _validate_retrieval_output_structure(retrieval_text: str) -> None:
    """Require the context retrieval prose sections promised by the prompt."""
    lowered = retrieval_text.lower()
    required_sections = ("## retrieval summary", "## retrieved sources")
    missing = [section for section in required_sections if section not in lowered]
    if not missing:
        return
    raise WorkflowPolicyViolation(
        "Policy gate failed: context retrieval must return retrieval handoff sections "
        "including `## Retrieval Summary` and `## Retrieved Sources`; it must not return "
        "the final user-facing answer in place of source evidence."
    )


def _validate_evidence_bundle(message: str, bundle: EvidenceBundle) -> None:
    """Apply workflow evidence policy gates to a parsed bundle."""
    must_read = request_requires_content_read(message)
    if must_read and not bundle.has_content_read():
        raise WorkflowPolicyViolation(
            "Policy gate failed: this request requires content-read evidence, "
            "but no source in the evidence bundle has evidence_level='content_read'."
        )
    if must_read:
        unresolved = _unresolved_required_read_failures(bundle)
        if unresolved:
            raise WorkflowPolicyViolation(
                "Policy gate failed: required source read failed and was not recovered by "
                "matching content-read evidence. Failed source(s): " + ", ".join(unresolved[:5]) + "."
            )
    constraints = infer_source_fit_constraints(message)
    if must_read and constraints.is_active:
        if any(item.evidence_level == "content_read" and item.evidence_role == "supplemental" for item in bundle.items):
            supplemental_violation = _supplemental_evidence_role_violation(bundle, constraints)
            if supplemental_violation:
                raise WorkflowPolicyViolation(supplemental_violation)
        if not evidence_bundle_satisfies_constraints(bundle, constraints):
            raise WorkflowPolicyViolation(source_fit_failure_message(bundle, constraints))
        supplemental_violation = _supplemental_evidence_role_violation(bundle, constraints)
        if supplemental_violation:
            raise WorkflowPolicyViolation(supplemental_violation)
    conflict_message = latest_source_conflict_message(message, bundle, constraints)
    if must_read and conflict_message:
        raise WorkflowPolicyViolation(conflict_message)


# Source-search servers a framing-only planner must not hold. In pipeline/peer
# mode the retrieval planner produces a search *handoff*; the actual lookup is
# Context Retrieval's job (see prompts/retrieval_planner_agent.md). Despite the
# prompt saying "do not retrieve", the model would still search OneDrive/SharePoint
# and return a separate (often wrong) file list that Context Retrieval then
# ignored. Removing these servers from the planner stage enforces the contract
# structurally. The single-agent planner keeps them (it retrieves directly).
_PLANNER_FRAMING_DENIED_SERVERS = frozenset({"sharepoint_docs", "documents", "intranet"})


def _framing_only_planner_spec(spec: Any) -> Any:
    """Return a copy of the planner spec with source-search servers removed.

    Falls back to the original spec if it cannot be copied/updated, so a malformed
    spec never breaks the run.
    """
    allowed = [
        server_id
        for server_id in getattr(spec, "allowed_servers", []) or []
        if server_id not in _PLANNER_FRAMING_DENIED_SERVERS
    ]
    try:
        framed = copy.copy(spec)
        framed.allowed_servers = allowed
    except (AttributeError, TypeError):
        return spec
    return framed


def _enforce_source_inventory_fit(
    result: str,
    *,
    deliverable_type: str,
    intent_message: str,
    registry_dir: str | Path | None,
) -> None:
    """Raise when a source-inventory output lists items outside the user's
    inferred title/scope constraints.

    The single-agent path enforces this inline (``run_single``), but an inventory
    ask that routes through the pipeline produced its final list without this
    check, so off-title files (e.g. a PDF missing the required title phrase) were
    presented as matches. This makes the gate mode-independent. A non-inventory
    deliverable is a no-op.
    """
    if deliverable_type != "source_inventory":
        return
    constraints = infer_source_fit_constraints(
        intent_message,
        registry_dir=Path(registry_dir) if registry_dir is not None else None,
    )
    violation = source_inventory_failure_message(result, constraints)
    if violation:
        raise WorkflowPolicyViolation(violation)


def _unresolved_required_read_failures(bundle: EvidenceBundle) -> list[str]:
    """Return non-workspace read failures not matched by a successful read."""
    read_identities = {
        _evidence_source_identity(item)
        for item in bundle.items
        if item.evidence_level == "content_read" and _evidence_source_identity(item)
    }
    unresolved: list[str] = []
    for item in bundle.items:
        if item.evidence_level != "read_failed":
            continue
        source_type = item.source.source_type.lower()
        if source_type.startswith("workspace"):
            continue
        identity = _evidence_source_identity(item)
        if identity and identity not in read_identities:
            unresolved.append(item.source.title or identity)
    return unresolved


def _evidence_source_identity(item: EvidenceItem) -> str:
    """Return a stable comparable identity for an evidence item source."""
    source = item.source
    for value in (source.read_handle, source.open_url, source.content_id, source.workspace_path, source.title):
        cleaned = (value or "").strip().lower()
        if cleaned:
            return cleaned
    return ""


def _supplemental_evidence_role_violation(bundle: EvidenceBundle, constraints: SourceFitConstraints) -> str:
    """Return a policy violation when off-target reads are not marked supplemental."""
    has_primary_match = False
    off_target_primary: list[str] = []
    for item in bundle.items:
        if item.evidence_level != "content_read":
            continue
        if evidence_item_satisfies_constraints(item, constraints):
            if item.evidence_role != "supplemental":
                has_primary_match = True
            continue
        if item.evidence_role != "supplemental":
            off_target_primary.append(item.source.title or _evidence_source_identity(item) or "unknown source")
    if not has_primary_match:
        return (
            "Policy gate failed: no primary content-read evidence item matches the user's requested source. "
            "Mark non-primary source variants as evidence_role='supplemental' only after reading the requested source."
        )
    if off_target_primary:
        return (
            "Policy gate failed: content-read source variant(s) do not match the user's requested source and must "
            "be marked evidence_role='supplemental': " + ", ".join(off_target_primary[:5]) + "."
        )
    return ""


def _validated_evidence_transport(
    message: str,
    retrieval_text: str,
    *,
    require_evidence_bundle: bool = False,
    require_retrieval_structure: bool = False,
) -> ValidatedEvidenceTransport:
    """Parse evidence once and keep machine transport separate from prose.

    For document-summary/source-read requests, the bundle is mandatory and must
    contain at least one content_read item. For other requests, plain markdown
    retrieval output is accepted.
    """
    prose = sanitize_user_visible_text(retrieval_text)
    if require_retrieval_structure:
        _validate_retrieval_output_structure(prose)
    must_read = request_requires_content_read(message)
    try:
        bundle = parse_evidence_bundle(retrieval_text)
    except ValueError as exc:
        if must_read or require_evidence_bundle:
            raise WorkflowPolicyViolation(
                "Policy gate failed: this request requires structured source evidence, "
                f"but context retrieval did not return a valid evidence bundle. {exc}"
            ) from exc
        return ValidatedEvidenceTransport(prose=prose, bundle=None, evidence_brief="")
    _validate_evidence_bundle(message, bundle)
    return ValidatedEvidenceTransport(
        prose=prose,
        bundle=bundle,
        evidence_brief=_evidence_brief(bundle),
    )


def _validated_evidence_text(message: str, retrieval_text: str) -> str:
    """Return readable retrieval context after evidence validation.

    Machine evidence is exposed through ``_validated_evidence_transport`` instead
    of embedded JSON.
    """
    return _validated_evidence_transport(message, retrieval_text).prompt_text


def _build_agent_factory(root_dir: Path, settings, model_specs=None):
    """Build a provider-aware agent factory."""
    return AgentFactory(root_dir, model_specs=model_specs, settings=settings)


def create_workflow_environment(settings, model_specs=None) -> WorkflowEnvironment:
    """Create workflow runtime objects using local module dependencies."""
    root_dir = Path.cwd()
    return WorkflowEnvironment(
        root_dir=root_dir,
        runtime=RuntimeManager(root_dir),
        factory=_build_agent_factory(root_dir, settings, model_specs=model_specs),
        trace_file=settings.log_dir / TRACE_FILE_NAME,
        run_id=uuid4().hex,
    )


@asynccontextmanager
async def workflow_server_context(environment: WorkflowEnvironment, agent_specs, server_specs):
    """Build and open the required MCP server context for a workflow."""
    server_ids = collect_server_ids(agent_specs)
    env_overrides = getattr(environment, "mcp_env_overrides", {}) or {}
    servers = [
        environment.runtime.build_server(server_specs[server_id], env_overrides=env_overrides)
        if env_overrides
        else environment.runtime.build_server(server_specs[server_id])
        for server_id in server_ids
        if server_id in server_specs
    ]
    async with MultiServerContext(servers) as active_servers:
        yield {
            server_id: server
            for server_id, server in zip((server_id for server_id in server_ids if server_id in server_specs), active_servers, strict=False)
        }


def append_trace_entry(
    environment: WorkflowEnvironment,
    stage: str,
    content: str,
    *,
    event_type: str = "workflow_event",
    agent_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Append a structured trace entry.

    This wrapper keeps append_trace patchable from tests through the pipelines
    module surface.
    """
    append_trace(
        environment.trace_file,
        stage,
        content,
        run_id=_get_run_id(environment),
        event_type=event_type,
        agent_id=agent_id,
        metadata=metadata,
    )


def _create_workflow_engine(environment: WorkflowEnvironment, server_specs) -> WorkflowEngine:
    """Create a workflow engine wired to the local runtime helpers."""

    def trace_writer(stage: str, content: str, **kwargs: Any) -> None:
        """Forward structured workflow events through the local trace wrapper."""
        append_trace_entry(environment, stage, content, **kwargs)

    return WorkflowEngine(
        environment=environment,
        server_specs=server_specs,
        server_context_factory=workflow_server_context,
        stage_runner=_run_agent_with_progress,
        trace_writer=trace_writer,
        output_printer=print_agent_output,
    )


async def run_single(
    message: str,
    agent_id: str,
    *,
    settings,
    server_specs,
    agent_specs,
    model_specs=None,
    user_intent_message: str | None = None,
    session_name: str | None = None,
) -> str:
    """Run a single agent directly."""
    ensure_openai_api_key(settings)

    if agent_id not in agent_specs:
        raise WorkflowValidationError(f"Unknown agent_id: {agent_id}")

    environment = create_workflow_environment(settings, model_specs=model_specs)
    _apply_mcp_env_overrides(environment, _session_memory_env(session_name))
    agent_spec = agent_specs[agent_id]

    logger.info("Running single agent request.", extra={"agent_id": agent_id, "run_id": _get_run_id(environment)})

    registry_dir = getattr(settings, "registry_dir", None)
    intent_message = user_intent_message or message
    deterministic_context = _empty_deterministic_context()
    graph_loaded = False
    if registry_dir is not None:
        deterministic_context, graph_loaded = deterministic_context_from_registry(intent_message, Path(registry_dir))
    request_contract = _infer_runtime_request_contract(
        intent_message,
        current_mode="single",
        registry_dir=Path(registry_dir) if registry_dir is not None else None,
        deterministic_context=deterministic_context,
        session_name=session_name,
    )
    policy = infer_workflow_policy(
        intent_message,
        registry_dir=Path(registry_dir) if registry_dir is not None else None,
        deterministic_context=deterministic_context,
        explicit_write_target_subdir=_write_target_subdir_from_contract(request_contract),
    )
    authorization = workspace_write_authorization_from_contract(
        request_contract,
        registry_dir=Path(registry_dir) if registry_dir is not None else None,
    )
    root_dir = Path(getattr(environment, "root_dir", Path.cwd()))
    write_before = snapshot_tree(root_dir, policy.write_target_subdir)

    with workspace_write_authorization_env(authorization):
        async with workflow_server_context(environment, [agent_spec], server_specs) as active_servers:
            append_trace_entry(
                environment,
                "USER_INPUT",
                message,
                event_type="workflow_input",
                metadata={"mode": "single", "agent_id": agent_id},
            )
            append_trace_entry(
                environment,
                "REQUEST_CONTRACT",
                render_request_contract_block(request_contract),
                event_type="policy_signal",
                metadata=request_contract.to_dict(),
            )
            append_trace_entry(
                environment,
                "WORKSPACE_WRITE_AUTHORIZATION",
                "Per-run workspace write authorization resolved.",
                event_type="policy_signal",
                metadata=authorization.to_dict(),
            )
            append_trace_entry(
                environment,
                "DETERMINISTIC_RETRIEVAL_CONTEXT",
                (
                    "Deterministic retrieval context computed from registry graph."
                    if graph_loaded
                    else "Deterministic retrieval graph unavailable; continuing in fail-open mode."
                ),
                event_type="policy_signal",
                metadata={
                    **deterministic_context_trace_metadata(deterministic_context),
                    "mode": "single",
                },
            )
            active_agent_servers = (
                [active_servers[server_id] for server_id in agent_spec.allowed_servers if server_id in active_servers]
                if isinstance(active_servers, dict)
                else active_servers
            )
            model_metadata, pricing = _resolve_model_observability(environment.factory, agent_spec)
            agent = environment.factory.build_agent(agent_spec, active_agent_servers)
            prompt = (
                build_single_retrieval_planner_prompt(
                    intent_message,
                    deterministic_context=deterministic_context,
                    registry_dir=Path(registry_dir) if registry_dir is not None else None,
                    resolved_sources=request_contract.resolved_sources,
                )
                if agent_id == "retrieval_planner"
                else message
            )
            append_trace_entry(
                environment,
                f"{agent_id.upper()} OUTPUT_START",
                f"Starting stage for {agent_id}.",
                event_type="stage_start",
                agent_id=agent_id,
            )
            observability_events: list[tuple[str, dict[str, object]]] = []

            def _record_observability(observed_agent_id: str, event_type: str, metadata: dict[str, object]) -> None:
                if observed_agent_id == agent_id and metadata:
                    observability_events.append((event_type, metadata))

            observability_agent_token = set_stage_observability_agent_id(agent_id)
            observability_callback_token = set_stage_observability_callback(_record_observability)
            started_at = _utc_now_iso()
            started_monotonic = time.perf_counter()
            try:
                result = await _run_agent_silently(agent, prompt)
            except Exception as exc:
                append_trace_entry(
                    environment,
                    f"{agent_id.upper()} OUTPUT_ERROR",
                    f"Stage {agent_id} failed: {type(exc).__name__}: {exc}",
                    event_type="stage_error",
                    agent_id=agent_id,
                    metadata=_merge_stage_observability_metadata(
                        {"error_type": type(exc).__name__},
                        observability_events,
                        execution_time=_execution_time_metadata(started_at, started_monotonic),
                        model_metadata=model_metadata,
                        pricing=pricing,
                    ),
                )
                raise
            finally:
                reset_stage_observability_callback(observability_callback_token)
                reset_stage_observability_agent_id(observability_agent_token)
            if request_contract.deliverable_type == "source_inventory":
                constraints = infer_source_fit_constraints(
                    intent_message,
                    registry_dir=Path(registry_dir) if registry_dir is not None else None,
                )
                inventory_violation = source_inventory_failure_message(result, constraints)
                if inventory_violation:
                    append_trace_entry(
                        environment,
                        f"{agent_id.upper()} OUTPUT_ERROR",
                        inventory_violation,
                        event_type="stage_error",
                        agent_id=agent_id,
                        metadata=_merge_stage_observability_metadata(
                            {"error_type": "SourceFitConstraintViolation"},
                            observability_events,
                            execution_time=_execution_time_metadata(started_at, started_monotonic),
                            model_metadata=model_metadata,
                            pricing=pricing,
                        ),
                    )
                    raise WorkflowPolicyViolation(inventory_violation)
            if session_name and agent_id == "retrieval_planner":
                persist_session_source_candidates_from_output(session_name, result)
            workflow_metadata = _merge_stage_observability_metadata(
                None,
                observability_events,
                execution_time=_execution_time_metadata(started_at, started_monotonic),
                model_metadata=model_metadata,
                pricing=pricing,
            )
            assert workflow_metadata is not None
            append_trace(
                environment.trace_file,
                "FINAL_OUTPUT",
                result,
                run_id=_get_run_id(environment),
                event_type="workflow_output",
                agent_id=agent_id,
                metadata=workflow_metadata,
            )
            _log_successful_agent_stage(
                run_id=_get_run_id(environment),
                agent_id=agent_id,
                stage=agent_id,
                trace_label="FINAL_OUTPUT",
                observability=workflow_metadata["observability"],
            )
            append_trace_entry(
                environment,
                f"{agent_id.upper()} OUTPUT_END",
                f"Completed stage for {agent_id}.",
                event_type="stage_end",
                agent_id=agent_id,
            )
            try:
                changed = _enforce_workspace_write_and_validation(
                    policy,
                    authorization,
                    root_dir,
                    write_before,
                    Path(registry_dir) if registry_dir is not None else None,
                )
                if changed:
                    _register_and_validate_task_artefacts(
                        workflow=None,
                        session_name=session_name,
                        changed=changed,
                        root_dir=root_dir,
                        user_input=intent_message,
                        deliverable_type=getattr(request_contract.task_contract, "deliverable_type", ""),
                        request_contract=request_contract,
                    )
                    append_trace_entry(
                        environment,
                        "POLICY_WRITE_CHANGES",
                        "\n".join(changed),
                        event_type="policy_signal",
                        metadata={"changed_count": len(changed)},
                    )
            except WorkflowPolicyViolation as exc:
                append_trace_entry(
                    environment,
                    "POLICY_VIOLATION",
                    str(exc),
                    event_type="policy_violation",
                )
                raise WorkflowValidationError(str(exc)) from exc
            return result


async def run_pipeline(
    message: str,
    verbose: bool,
    review: bool,
    *,
    settings,
    server_specs,
    agent_specs,
    model_specs=None,
    user_intent_message: str | None = None,
    session_name: str | None = None,
    retrieval_checkpoint_enabled: bool | None = None,
    retrieval_checkpoint_handler: RetrievalCheckpointHandler | None = None,
) -> str:
    """Run the standard retrieval/context pipeline with summary or design drafting."""
    ensure_openai_api_key(settings)
    environment = create_workflow_environment(settings, model_specs=model_specs)
    intent_message = user_intent_message or message
    registry_dir = getattr(settings, "registry_dir", None)
    deterministic_context = _empty_deterministic_context()
    graph_loaded = False
    if registry_dir is not None:
        deterministic_context, graph_loaded = deterministic_context_from_registry(
            intent_message,
            Path(registry_dir),
        )
    task_contract = infer_task_contract(
        intent_message,
        registry_dir=Path(registry_dir) if registry_dir is not None else None,
    )
    request_contract = _infer_runtime_request_contract(
        intent_message,
        registry_dir=Path(registry_dir) if registry_dir is not None else None,
        deterministic_context=deterministic_context,
        session_name=session_name,
    )
    policy = infer_workflow_policy(
        intent_message,
        registry_dir=Path(registry_dir) if registry_dir is not None else None,
        deterministic_context=deterministic_context,
        explicit_write_target_subdir=_write_target_subdir_from_contract(request_contract),
    )
    authorization = workspace_write_authorization_from_contract(
        request_contract,
        registry_dir=Path(registry_dir) if registry_dir is not None else None,
    )
    _apply_mcp_env_overrides(environment, _session_memory_env(session_name))
    _apply_mcp_env_overrides(environment, authorization.to_env())
    root_dir = Path(getattr(environment, "root_dir", Path.cwd()))
    write_before = snapshot_tree(root_dir, policy.write_target_subdir)

    logger.info("Running pipeline workflow.", extra={"run_id": _get_run_id(environment), "review": review})
    checkpoint_enabled = (
        bool(getattr(settings, "retrieval_checkpoint_enabled", False))
        if retrieval_checkpoint_enabled is None
        else retrieval_checkpoint_enabled
    )
    checkpoint_max_redirects = int(getattr(settings, "retrieval_checkpoint_max_redirects", 2) or 2)

    drafting_agent_id = "summary" if task_contract.is_summary else "design"
    required_agent_ids = ["retrieval_planner", "context_retrieval", drafting_agent_id]
    if not task_contract.is_summary:
        required_agent_ids.extend(["context_synthesizer", "review", "orchestrator"])
    specs = resolve_required_agents(
        agent_specs,
        required_agent_ids,
        mode_name="Pipeline mode",
    )

    engine = _create_workflow_engine(environment, server_specs)
    require_retrieval_evidence = _requires_retrieval_evidence_contract(request_contract)

    async with engine.session(specs.values()) as workflow:
        workflow.start_workflow(
            "Starting pipeline workflow.",
            metadata={"mode": "pipeline", "review": review},
        )
        workflow.trace_user_input(message)
        _trace_workflow_policy_event(
            workflow,
            "TASK_CONTRACT",
            render_task_contract_block(task_contract),
            event_type="policy_signal",
            metadata=task_contract.to_dict(),
        )
        _trace_workflow_policy_event(
            workflow,
            "REQUEST_CONTRACT",
            render_request_contract_block(request_contract),
            event_type="policy_signal",
            metadata=request_contract.to_dict(),
        )
        _trace_workflow_policy_event(
            workflow,
            "WORKSPACE_WRITE_AUTHORIZATION",
            "Per-run workspace write authorization resolved.",
            event_type="policy_signal",
            metadata=authorization.to_dict(),
        )
        _trace_workflow_policy_event(
            workflow,
            "DETERMINISTIC_RETRIEVAL_CONTEXT",
            (
                "Deterministic retrieval context computed from registry graph."
                if graph_loaded
                else "Deterministic retrieval graph unavailable; continuing in fail-open mode."
            ),
            event_type="policy_signal",
            metadata={
                **deterministic_context_trace_metadata(deterministic_context),
                "mode": "pipeline",
            },
        )

        retrieval_message = message
        retrieval_intent_message = intent_message
        redirect_count = 0
        retrieval_plan_text = ""
        context_retrieval_text = ""
        evidence_capture: EvidenceValidationCapture | None = None
        validated_context_retrieval_text = ""

        while True:
            try:
                retrieval_plan_text = await workflow.run_stage(
                    spec=_framing_only_planner_spec(specs["retrieval_planner"]),
                    ui_agent_id="retrieval_planner",
                    prompt=build_retrieval_planner_prompt(
                        retrieval_message,
                        deterministic_context=deterministic_context,
                        registry_dir=Path(registry_dir) if registry_dir is not None else None,
                        task_contract=task_contract,
                        resolved_sources=request_contract.resolved_sources,
                    ),
                    trace_label="RETRIEVAL_PLANNER OUTPUT",
                    verbose=verbose,
                )
            except RuntimeError as exc:
                if not _is_empty_stage_output_error(exc, agent_id="retrieval_planner"):
                    raise
                retrieval_plan_text = _build_retrieval_planner_fallback(
                    retrieval_message,
                    deterministic_context=deterministic_context,
                    task_contract=task_contract,
                    request_contract=request_contract,
                )
                workflow.trace_event(
                    "RETRIEVAL_PLANNER FALLBACK",
                    retrieval_plan_text,
                    event_type="stage_output",
                    agent_id="retrieval_planner",
                    metadata={"fallback_reason": "empty_output"},
                )

            evidence_capture = EvidenceValidationCapture(
                retrieval_intent_message,
                require_evidence_bundle=require_retrieval_evidence,
                require_retrieval_structure=require_retrieval_evidence,
            )

            context_retrieval_text = await workflow.run_stage(
                spec=specs["context_retrieval"],
                ui_agent_id="context_retrieval",
                prompt=build_context_retrieval_prompt(
                    retrieval_message,
                    retrieval_plan_text,
                    deterministic_context=deterministic_context,
                    registry_dir=Path(registry_dir) if registry_dir is not None else None,
                    task_contract=task_contract,
                    resolved_sources=request_contract.resolved_sources,
                ),
                trace_label="CONTEXT RETRIEVAL OUTPUT",
                verbose=verbose,
                output_processor=evidence_capture.process,
            )
            if evidence_capture.error is not None and (
                request_requires_content_read(retrieval_intent_message) or require_retrieval_evidence
            ):
                _trace_workflow_policy_event(
                    workflow,
                    "EVIDENCE_CONTRACT_REPAIR",
                    "Retrying context retrieval because required evidence transport failed validation.",
                    event_type="policy_signal",
                    metadata={"validation_error": str(evidence_capture.error)},
                )
                repair_capture = EvidenceValidationCapture(
                    retrieval_intent_message,
                    require_evidence_bundle=require_retrieval_evidence,
                    require_retrieval_structure=require_retrieval_evidence,
                )
                context_retrieval_text = await workflow.run_stage(
                    spec=specs["context_retrieval"],
                    ui_agent_id="context_retrieval",
                    prompt=build_context_retrieval_repair_prompt(
                        retrieval_message,
                        retrieval_plan_text,
                        context_retrieval_text,
                        str(evidence_capture.error),
                    ),
                    trace_label="CONTEXT RETRIEVAL REPAIR OUTPUT",
                    verbose=verbose,
                    output_processor=repair_capture.process,
                )
                evidence_capture = repair_capture
            if evidence_capture.error is not None:
                _trace_workflow_policy_event(
                    workflow,
                    "POLICY_VIOLATION",
                    str(evidence_capture.error),
                    event_type="policy_violation",
                )
                raise WorkflowValidationError(str(evidence_capture.error)) from evidence_capture.error
            validated_context_retrieval_text = (
                evidence_capture.transport.prompt_text
                if evidence_capture.transport is not None
                else sanitize_user_visible_text(context_retrieval_text)
            )
            try:
                enforce_intranet_fetch_policy(policy, validated_context_retrieval_text)
            except WorkflowPolicyViolation as exc:
                _trace_workflow_policy_event(
                    workflow,
                    "POLICY_VIOLATION",
                    str(exc),
                    event_type="policy_violation",
                )
                raise WorkflowValidationError(str(exc)) from exc

            if not checkpoint_enabled:
                break
            if retrieval_checkpoint_handler is None:
                raise WorkflowValidationError(
                    "Retrieval checkpoint is enabled, but this runtime has no checkpoint handler. "
                    "Disable it with --no-retrieval-checkpoint or CRISAI_RETRIEVAL_CHECKPOINT_ENABLED=false."
                )
            transport = evidence_capture.transport
            snapshot = RetrievalCheckpointSnapshot(
                request=intent_message,
                retrieval_plan=sanitize_user_visible_text(retrieval_plan_text),
                evidence_brief=transport.evidence_brief if transport is not None else "",
                retrieval_prose=transport.prose if transport is not None else sanitize_user_visible_text(context_retrieval_text),
                attempt=redirect_count,
                max_redirects=checkpoint_max_redirects,
                evidence_bundle=transport.bundle.to_sanitized_dict()
                if transport is not None and transport.bundle is not None
                else None,
            )
            _trace_workflow_policy_event(
                workflow,
                "RETRIEVAL_CHECKPOINT",
                "Retrieval checkpoint presented to user.",
                event_type="checkpoint",
                metadata=snapshot.to_dict(),
            )
            decision = await retrieval_checkpoint_handler(snapshot)
            _trace_workflow_policy_event(
                workflow,
                "RETRIEVAL_CHECKPOINT_DECISION",
                f"Retrieval checkpoint decision: {decision.action}.",
                event_type="checkpoint_decision",
                metadata=decision.to_dict(),
            )
            if decision.action == "continue":
                break
            if decision.action == "stop":
                workflow.finish_workflow("Pipeline workflow stopped after retrieval checkpoint.", metadata={"mode": "pipeline"})
                return "Run stopped after retrieval checkpoint. No summary or design stages were executed."
            if decision.action == "redirect":
                if redirect_count >= checkpoint_max_redirects:
                    raise WorkflowValidationError(
                        f"Retrieval checkpoint redirect limit reached ({checkpoint_max_redirects}). "
                        "Continue with current evidence or start a fresh request."
                    )
                if not decision.redirect_instruction.strip():
                    raise WorkflowValidationError("Retrieval checkpoint redirect requires non-empty guidance.")
                redirect_count += 1
                retrieval_message = (
                    f"{message}\n\nAdditional retrieval direction from checkpoint "
                    f"{redirect_count}: {decision.redirect_instruction.strip()}"
                )
                retrieval_intent_message = (
                    f"{intent_message}\n\nAdditional retrieval direction: "
                    f"{decision.redirect_instruction.strip()}"
                )
                continue
            raise WorkflowValidationError(f"Unknown retrieval checkpoint decision: {decision.action}")

        # Sources are confirmed (checkpoint continued): materialise them into the
        # per-task evidence cache so later turns read a stable copy (ADR-015 2b).
        await _materialise_confirmed_sources(
            getattr(evidence_capture.transport, "bundle", None)
            if getattr(evidence_capture, "transport", None) is not None
            else None,
            environment=environment,
            server_specs=server_specs,
            session_name=session_name,
            settings=settings,
            workflow=workflow,
        )

        if task_contract.is_summary:
            workflow.skip_stage(
                "CONTEXT OUTPUT",
                "Context synthesizer skipped for summary fast path; validated retrieval evidence passed directly to summary.",
                agent_id="context_synthesizer",
            )
            summary_text = await workflow.run_stage(
                spec=specs["summary"],
                ui_agent_id="summary",
                prompt=build_summary_prompt(message, validated_context_retrieval_text, task_contract),
                trace_label="SUMMARY OUTPUT",
                verbose=verbose,
            )
            if review:
                workflow.skip_stage(
                    "REVIEW OUTPUT",
                    "Review stage skipped for summary fast path.",
                    agent_id="review",
                )
            workflow.skip_stage(
                "FINAL OUTPUT",
                "Final orchestration skipped for summary fast path; summary output is the final answer.",
                agent_id="orchestrator",
            )
            try:
                changed = _enforce_workspace_write_and_validation(
                    policy,
                    authorization,
                    root_dir,
                    write_before,
                    Path(registry_dir) if registry_dir is not None else None,
                )
                if changed:
                    _register_and_validate_task_artefacts(
                        workflow=workflow,
                        session_name=session_name,
                        changed=changed,
                        root_dir=root_dir,
                        user_input=intent_message,
                        deliverable_type=task_contract.deliverable_type,
                        request_contract=request_contract,
                    )
                    _trace_workflow_policy_event(
                        workflow,
                        "POLICY_WRITE_CHANGES",
                        "\n".join(changed),
                        event_type="policy_signal",
                        metadata={"changed_count": len(changed)},
                    )
            except WorkflowPolicyViolation as exc:
                _trace_workflow_policy_event(
                    workflow,
                    "POLICY_VIOLATION",
                    str(exc),
                    event_type="policy_violation",
                )
                raise WorkflowValidationError(str(exc)) from exc
            workflow.finish_workflow("Pipeline workflow completed.", metadata={"mode": "pipeline"})
            return summary_text

        context_text = await workflow.run_stage(
            spec=specs["context_synthesizer"],
            ui_agent_id="context_synthesizer",
            prompt=build_context_synthesizer_prompt(
                message,
                validated_context_retrieval_text,
                task_contract=task_contract,
            ),
            trace_label="CONTEXT OUTPUT",
            verbose=verbose,
        )

        draft_prompt = (
            build_summary_prompt(message, context_text, task_contract)
            if task_contract.is_summary
            else build_design_prompt(message, context_text, task_contract=task_contract)
        )
        draft_trace_label = "SUMMARY OUTPUT" if task_contract.is_summary else "DESIGN OUTPUT"
        design_text = await workflow.run_stage(
            spec=specs[drafting_agent_id],
            ui_agent_id=drafting_agent_id,
            prompt=draft_prompt,
            trace_label=draft_trace_label,
            verbose=verbose,
        )

        if review:
            review_text = await workflow.run_stage(
                spec=specs["review"],
                ui_agent_id="review",
                prompt=build_review_prompt(message, context_text, design_text, task_contract=task_contract),
                trace_label="REVIEW OUTPUT",
                verbose=verbose,
            )
        else:
            review_text = workflow.skip_stage(
                "REVIEW OUTPUT",
                "Review stage skipped because review is disabled.",
                agent_id="review",
            )

        final_text = await workflow.run_stage(
            spec=specs["orchestrator"],
            ui_agent_id="orchestrator",
            prompt=build_pipeline_final_prompt(
                message,
                context_text,
                design_text,
                review_text,
                task_contract=task_contract,
            ),
            trace_label="FINAL OUTPUT",
            verbose=verbose,
            print_output=False,
        )
        try:
            _enforce_source_inventory_fit(
                final_text,
                deliverable_type=task_contract.deliverable_type,
                intent_message=intent_message,
                registry_dir=registry_dir,
            )
            changed = _enforce_workspace_write_and_validation(
                policy,
                authorization,
                root_dir,
                write_before,
                Path(registry_dir) if registry_dir is not None else None,
            )
            if changed:
                _register_and_validate_task_artefacts(
                    workflow=workflow,
                    session_name=session_name,
                    changed=changed,
                    root_dir=root_dir,
                    user_input=intent_message,
                    deliverable_type=task_contract.deliverable_type,
                    request_contract=request_contract,
                )
                _trace_workflow_policy_event(
                    workflow,
                    "POLICY_WRITE_CHANGES",
                    "\n".join(changed),
                    event_type="policy_signal",
                    metadata={"changed_count": len(changed)},
                )
        except WorkflowPolicyViolation as exc:
            _trace_workflow_policy_event(
                workflow,
                "POLICY_VIOLATION",
                str(exc),
                event_type="policy_violation",
            )
            raise WorkflowValidationError(str(exc)) from exc
        workflow.finish_workflow("Pipeline workflow completed.", metadata={"mode": "pipeline"})
        return final_text


async def run_peer_pipeline(
    message: str,
    verbose: bool,
    review: bool,
    *,
    settings,
    server_specs,
    agent_specs,
    model_specs=None,
    needs_retrieval: bool = True,
    user_intent_message: str | None = None,
    session_name: str | None = None,
) -> str:
    """Run the peer workflow with optional retrieval and final recommendation."""
    del review  # Unused in peer mode today; kept for API compatibility.
    ensure_openai_api_key(settings)
    environment = create_workflow_environment(settings, model_specs=model_specs)
    intent_message = user_intent_message or message
    registry_dir = getattr(settings, "registry_dir", None)
    deterministic_context = _empty_deterministic_context()
    graph_loaded = False
    if registry_dir is not None:
        deterministic_context, graph_loaded = deterministic_context_from_registry(intent_message, Path(registry_dir))
    deterministic_advisory_enabled = _deterministic_advisory_enabled()
    request_contract = _infer_runtime_request_contract(
        intent_message,
        current_mode="peer",
        registry_dir=Path(registry_dir) if registry_dir is not None else None,
        deterministic_context=deterministic_context,
        session_name=session_name,
    )
    policy = infer_workflow_policy(
        intent_message,
        registry_dir=Path(registry_dir) if registry_dir is not None else None,
        deterministic_context=deterministic_context,
        explicit_write_target_subdir=_write_target_subdir_from_contract(request_contract),
    )
    authorization = workspace_write_authorization_from_contract(
        request_contract,
        registry_dir=Path(registry_dir) if registry_dir is not None else None,
    )
    _apply_mcp_env_overrides(environment, _session_memory_env(session_name))
    _apply_mcp_env_overrides(environment, authorization.to_env())
    root_dir = Path(getattr(environment, "root_dir", Path.cwd()))
    write_before = snapshot_tree(root_dir, policy.write_target_subdir)
    max_refinement_rounds = _resolve_peer_max_refinement_rounds()
    max_escalations = _resolve_peer_max_escalations()
    run_contract = infer_peer_run_contract(intent_message)
    run_contract_text = render_peer_run_contract(run_contract)

    logger.info(
        "Running peer workflow.",
        extra={
            "run_id": _get_run_id(environment),
            "needs_retrieval": needs_retrieval,
            "max_refinement_rounds": max_refinement_rounds,
            "max_escalations": max_escalations,
        },
    )

    use_context_retrieval = needs_retrieval and "context_retrieval" in agent_specs
    use_context_synthesizer = needs_retrieval and "context_synthesizer" in agent_specs

    required_agents = [
        "design_author",
        "design_challenger",
        "design_refiner",
        "judge",
        "orchestrator",
    ]
    if needs_retrieval:
        required_agents.insert(0, "retrieval_planner")
    if use_context_retrieval:
        required_agents.insert(1, "context_retrieval")
    if use_context_synthesizer:
        required_agents.insert(2, "context_synthesizer")

    specs = resolve_required_agents(
        agent_specs,
        required_agents,
        mode_name="Peer mode",
    )

    engine = _create_workflow_engine(environment, server_specs)

    async with engine.session(specs.values()) as workflow:
        workflow.start_workflow(
            "Starting peer workflow.",
            metadata={"mode": "peer", "needs_retrieval": needs_retrieval},
        )
        workflow.trace_user_input(message)
        _trace_workflow_policy_event(
            workflow,
            "PEER_RUN_CONTRACT",
            run_contract_text,
            event_type="policy_signal",
            metadata={"expected_output_type": run_contract.expected_output_type},
        )
        _trace_workflow_policy_event(
            workflow,
            "REQUEST_CONTRACT",
            render_request_contract_block(request_contract),
            event_type="policy_signal",
            metadata=request_contract.to_dict(),
        )
        _trace_workflow_policy_event(
            workflow,
            "WORKSPACE_WRITE_AUTHORIZATION",
            "Per-run workspace write authorization resolved.",
            event_type="policy_signal",
            metadata=authorization.to_dict(),
        )
        _trace_workflow_policy_event(
            workflow,
            "DETERMINISTIC_RETRIEVAL_CONTEXT",
            (
                "Deterministic retrieval context computed from registry graph."
                if graph_loaded
                else "Deterministic retrieval graph unavailable; continuing in fail-open mode."
            ),
            event_type="policy_signal",
            metadata={
                **deterministic_context_trace_metadata(deterministic_context),
                "mode": "peer",
                "advisory_mcp_enabled": deterministic_advisory_enabled,
            },
        )

        retrieval_plan_text = ""
        context_retrieval_text = ""
        context_text = ""
        if needs_retrieval:
            try:
                retrieval_plan_text = await workflow.run_stage(
                    spec=specs["retrieval_planner"],
                    ui_agent_id="retrieval_planner",
                    prompt=build_retrieval_planner_prompt(
                        message,
                        deterministic_context=deterministic_context,
                        registry_dir=Path(registry_dir) if registry_dir is not None else None,
                        task_contract=request_contract.task_contract,
                        resolved_sources=request_contract.resolved_sources,
                    ),
                    trace_label="RETRIEVAL_PLANNER OUTPUT",
                    verbose=verbose,
                )
            except RuntimeError as exc:
                # The framing handoff is advisory — context retrieval does the real
                # lookup. An empty planner output (e.g. a reasoning model that emits
                # only reasoning) must not kill the peer run; fall back to a
                # deterministic handoff and continue, mirroring the pipeline path.
                if not _is_empty_stage_output_error(exc, agent_id="retrieval_planner"):
                    raise
                retrieval_plan_text = _build_retrieval_planner_fallback(
                    message,
                    deterministic_context=deterministic_context,
                    task_contract=request_contract.task_contract,
                    request_contract=request_contract,
                )
                workflow.trace_event(
                    "RETRIEVAL_PLANNER FALLBACK",
                    retrieval_plan_text,
                    event_type="stage_output",
                    agent_id="retrieval_planner",
                    metadata={"fallback_reason": "empty_output"},
                )
            if use_context_retrieval:
                evidence_capture = EvidenceValidationCapture(intent_message)

                context_retrieval_text = await workflow.run_stage(
                    spec=specs["context_retrieval"],
                    ui_agent_id="context_retrieval",
                    prompt=build_context_retrieval_prompt(
                        message,
                        retrieval_plan_text,
                        deterministic_context=deterministic_context,
                        registry_dir=Path(registry_dir) if registry_dir is not None else None,
                        task_contract=request_contract.task_contract,
                        resolved_sources=request_contract.resolved_sources,
                    ),
                    trace_label="CONTEXT RETRIEVAL OUTPUT",
                    verbose=verbose,
                    output_processor=evidence_capture.process,
                )
                if evidence_capture.error is not None and request_requires_content_read(intent_message):
                    _trace_workflow_policy_event(
                        workflow,
                        "EVIDENCE_CONTRACT_REPAIR",
                        "Retrying context retrieval because required evidence transport failed validation.",
                        event_type="policy_signal",
                        metadata={"validation_error": str(evidence_capture.error)},
                    )
                    repair_capture = EvidenceValidationCapture(intent_message)
                    context_retrieval_text = await workflow.run_stage(
                        spec=specs["context_retrieval"],
                        ui_agent_id="context_retrieval",
                        prompt=build_context_retrieval_repair_prompt(
                            message,
                            retrieval_plan_text,
                            context_retrieval_text,
                            str(evidence_capture.error),
                        ),
                        trace_label="CONTEXT RETRIEVAL REPAIR OUTPUT",
                        verbose=verbose,
                        output_processor=repair_capture.process,
                    )
                    evidence_capture = repair_capture
                if evidence_capture.error is not None:
                    _trace_workflow_policy_event(
                        workflow,
                        "POLICY_VIOLATION",
                        str(evidence_capture.error),
                        event_type="policy_violation",
                    )
                    raise WorkflowValidationError(str(evidence_capture.error)) from evidence_capture.error
                context_retrieval_text = (
                    evidence_capture.transport.prompt_text
                    if evidence_capture.transport is not None
                    else sanitize_user_visible_text(context_retrieval_text)
                )
                try:
                    enforce_intranet_fetch_policy(policy, context_retrieval_text)
                except WorkflowPolicyViolation as exc:
                    _trace_workflow_policy_event(
                        workflow,
                        "POLICY_VIOLATION",
                        str(exc),
                        event_type="policy_violation",
                    )
                    raise WorkflowValidationError(str(exc)) from exc
            else:
                workflow.skip_stage(
                    "CONTEXT RETRIEVAL OUTPUT",
                    "Context retrieval stage skipped in peer mode.",
                    agent_id="context_retrieval",
                )
            if use_context_synthesizer:
                context_text = await workflow.run_stage(
                    spec=specs["context_synthesizer"],
                    ui_agent_id="context_synthesizer",
                    prompt=build_context_synthesizer_prompt(message, context_retrieval_text),
                    trace_label="CONTEXT OUTPUT",
                    verbose=verbose,
                )
            else:
                workflow.skip_stage(
                    "CONTEXT OUTPUT",
                    "Context synthesizer skipped in peer mode (agent unavailable).",
                    agent_id="context_synthesizer",
                )
        else:
            workflow.skip_stage(
                "RETRIEVAL_PLANNER OUTPUT",
                "Retrieval planner skipped because this peer task does not require retrieval.",
                agent_id="retrieval_planner",
            )
            workflow.skip_stage(
                "CONTEXT RETRIEVAL OUTPUT",
                "Context retrieval skipped because this peer task does not require retrieval.",
                agent_id="context_retrieval",
            )
            workflow.skip_stage(
                "CONTEXT OUTPUT",
                "Context synthesizer skipped because this peer task does not require retrieval.",
                agent_id="context_synthesizer",
            )

        discovery_basis = context_text or context_retrieval_text or retrieval_plan_text or "None."

        author_text = await workflow.run_stage(
            spec=specs["design_author"],
            ui_agent_id="design_author",
            prompt=_build_prompt_with_contract(
                build_author_prompt,
                message,
                discovery_basis,
                run_contract_text=run_contract_text,
                deterministic_context=deterministic_context,
                deterministic_advisory_enabled=False,
            ),
            trace_label="AUTHOR OUTPUT",
            verbose=verbose,
        )

        challenger_text = await workflow.run_stage(
            spec=specs["design_challenger"],
            ui_agent_id="design_challenger",
            prompt=_build_prompt_with_contract(
                build_challenger_prompt,
                message,
                discovery_basis,
                author_text,
                run_contract_text=run_contract_text,
                deterministic_context=deterministic_context,
                deterministic_advisory_enabled=deterministic_advisory_enabled,
            ),
            trace_label="CHALLENGER OUTPUT",
            verbose=verbose,
        )

        refiner_text = await workflow.run_stage(
            spec=specs["design_refiner"],
            ui_agent_id="design_refiner",
            prompt=_build_prompt_with_contract(
                build_refiner_prompt,
                message,
                discovery_basis,
                author_text,
                challenger_text,
                run_contract_text=run_contract_text,
                deterministic_context=deterministic_context,
                deterministic_advisory_enabled=False,
            ),
            trace_label="REFINER OUTPUT",
            verbose=verbose,
        )
        filesystem_evidence = _build_peer_filesystem_evidence(
            root_dir=root_dir,
            before_snapshot=write_before,
            target_subdir=policy.write_target_subdir,
        )
        _trace_peer_flow_event(
            workflow,
            "PEER_FILESYSTEM_EVIDENCE",
            filesystem_evidence,
            metadata={"phase": "initial"},
        )

        judge_text, judge_decision = await _run_judge_with_acceptance_audit(
            workflow=workflow,
            specs=specs,
            message=message,
            discovery_basis=discovery_basis,
            challenger_text=challenger_text,
            refiner_text=refiner_text,
            verbose=verbose,
            trace_label="JUDGE OUTPUT",
            quality_trace_label="JUDGE QUALITY GATE",
            run_contract_text=run_contract_text,
            filesystem_evidence_text=filesystem_evidence,
            deterministic_context=deterministic_context,
            deterministic_advisory_enabled=deterministic_advisory_enabled,
        )
        previous_refiner_text = refiner_text
        stagnation_detected = False
        rounds_executed = 0
        escalations_executed = 0

        # Judge-gated refinement loop. If the judge says "revise", feed the
        # judge feedback back into the refiner and ask for another judgement.
        # "rework" skips this loop and enters the structural escalation path.
        for round_index in range(1, max_refinement_rounds + 1):
            if judge_decision != "revise":
                break
            _trace_peer_flow_event(
                workflow,
                "PEER_REFINEMENT_ROUND_START",
                judge_text,
                metadata={
                    "round_index": round_index,
                    "decision_before_round": judge_decision,
                    "reason_excerpt": _judge_reason_excerpt(judge_text),
                },
            )
            rounds_executed = round_index
            revision_challenge = "\n\n".join(
                [
                    challenger_text,
                    f"Judge feedback (round {round_index - 1}):\n{judge_text}",
                ]
            )
            refiner_text = await workflow.run_stage(
                spec=specs["design_refiner"],
                ui_agent_id="design_refiner",
                prompt=_build_prompt_with_contract(
                    build_refiner_prompt,
                    message,
                    discovery_basis,
                    author_text,
                    revision_challenge,
                    run_contract_text=run_contract_text,
                    deterministic_context=deterministic_context,
                    deterministic_advisory_enabled=False,
                ),
                trace_label=f"REFINER OUTPUT (ROUND {round_index})",
                verbose=verbose,
            )
            filesystem_evidence = _build_peer_filesystem_evidence(
                root_dir=root_dir,
                before_snapshot=write_before,
                target_subdir=policy.write_target_subdir,
            )
            _trace_peer_flow_event(
                workflow,
                "PEER_FILESYSTEM_EVIDENCE",
                filesystem_evidence,
                metadata={"phase": "refinement", "round_index": round_index},
            )
            if refiner_text.strip() == previous_refiner_text.strip():
                stagnation_detected = True
                judge_text = (
                    judge_text.strip()
                    + "\n\nDecision: revise\nReason: Refinement stalled; additional peer rounds produced no material change."
                )
                judge_decision = "revise"
                _trace_peer_flow_event(
                    workflow,
                    "PEER_REFINEMENT_STAGNATION",
                    judge_text,
                    metadata={"round_index": round_index},
                )
                break
            previous_refiner_text = refiner_text
            judge_text, judge_decision = await _run_judge_with_acceptance_audit(
                workflow=workflow,
                specs=specs,
                message=message,
                discovery_basis=discovery_basis,
                challenger_text=revision_challenge,
                refiner_text=refiner_text,
                verbose=verbose,
                trace_label=f"JUDGE OUTPUT (ROUND {round_index})",
                quality_trace_label=f"JUDGE QUALITY GATE (ROUND {round_index})",
                run_contract_text=run_contract_text,
                filesystem_evidence_text=filesystem_evidence,
                deterministic_context=deterministic_context,
                deterministic_advisory_enabled=deterministic_advisory_enabled,
            )

        # Escalation path: if the judge requests structural rework, or if the
        # revise loop cannot reach accept, rerun author/challenger/refiner with
        # explicit judge feedback.
        for escalation_index in range(1, max_escalations + 1):
            if judge_decision == "accept":
                break
            escalations_executed = escalation_index
            _trace_peer_flow_event(
                workflow,
                "PEER_ESCALATION_START",
                judge_text,
                metadata={
                    "escalation_index": escalation_index,
                    "decision_before_escalation": judge_decision,
                    "reason_excerpt": _judge_reason_excerpt(judge_text),
                },
            )
            escalation_context = "\n\n".join(
                [
                    discovery_basis,
                    f"Escalation judge feedback (attempt {escalation_index}):\n{judge_text}",
                ]
            )
            author_text = await workflow.run_stage(
                spec=specs["design_author"],
                ui_agent_id="design_author",
                prompt=_build_prompt_with_contract(
                    build_author_prompt,
                    message,
                    escalation_context,
                    run_contract_text=run_contract_text,
                    deterministic_context=deterministic_context,
                    deterministic_advisory_enabled=False,
                ),
                trace_label=f"AUTHOR OUTPUT (ESCALATION {escalation_index})",
                verbose=verbose,
            )
            challenger_text = await workflow.run_stage(
                spec=specs["design_challenger"],
                ui_agent_id="design_challenger",
                prompt=_build_prompt_with_contract(
                    build_challenger_prompt,
                    message,
                    escalation_context,
                    author_text,
                    run_contract_text=run_contract_text,
                    deterministic_context=deterministic_context,
                    deterministic_advisory_enabled=deterministic_advisory_enabled,
                ),
                trace_label=f"CHALLENGER OUTPUT (ESCALATION {escalation_index})",
                verbose=verbose,
            )
            refiner_text = await workflow.run_stage(
                spec=specs["design_refiner"],
                ui_agent_id="design_refiner",
                prompt=_build_prompt_with_contract(
                    build_refiner_prompt,
                    message,
                    escalation_context,
                    author_text,
                    challenger_text,
                    run_contract_text=run_contract_text,
                    deterministic_context=deterministic_context,
                    deterministic_advisory_enabled=False,
                ),
                trace_label=f"REFINER OUTPUT (ESCALATION {escalation_index})",
                verbose=verbose,
            )
            filesystem_evidence = _build_peer_filesystem_evidence(
                root_dir=root_dir,
                before_snapshot=write_before,
                target_subdir=policy.write_target_subdir,
            )
            _trace_peer_flow_event(
                workflow,
                "PEER_FILESYSTEM_EVIDENCE",
                filesystem_evidence,
                metadata={"phase": "escalation", "escalation_index": escalation_index},
            )
            judge_text, judge_decision = await _run_judge_with_acceptance_audit(
                workflow=workflow,
                specs=specs,
                message=message,
                discovery_basis=escalation_context,
                challenger_text=challenger_text,
                refiner_text=refiner_text,
                verbose=verbose,
                trace_label=f"JUDGE OUTPUT (ESCALATION {escalation_index})",
                quality_trace_label=f"JUDGE QUALITY GATE (ESCALATION {escalation_index})",
                run_contract_text=run_contract_text,
                filesystem_evidence_text=filesystem_evidence,
                deterministic_context=deterministic_context,
                deterministic_advisory_enabled=deterministic_advisory_enabled,
            )

        if rounds_executed > 0 and judge_decision != "accept":
            if judge_decision == "rework":
                unresolved_reason = "Judge requested structural rework after refinement."
            elif stagnation_detected:
                unresolved_reason = "Peer refinement reached convergence with no material changes."
            else:
                unresolved_reason = (
                    f"Peer refinement reached max rounds ({max_refinement_rounds}) without an explicit accept decision."
                )
            if escalations_executed > 0:
                unresolved_reason += (
                    f" Escalation attempts exhausted ({escalations_executed}/{max_escalations})"
                    " without an explicit accept decision."
                )
            judge_text = (
                judge_text.strip()
                + f"\n\nStatus: unresolved after peer refinement loop.\nReason: {unresolved_reason}"
            )
        elif escalations_executed > 0 and judge_decision != "accept":
            judge_text = (
                judge_text.strip()
                + "\n\nStatus: unresolved after peer escalation.\nReason: "
                f"Escalation attempts exhausted ({escalations_executed}/{max_escalations})"
                " without an explicit accept decision."
            )
        if judge_decision != "accept":
            _trace_peer_flow_event(
                workflow,
                "PEER_FINAL_DECISION",
                judge_text,
                metadata={
                    "decision": judge_decision,
                    "rounds_executed": rounds_executed,
                    "escalations_executed": escalations_executed,
                    "reason_excerpt": _judge_reason_excerpt(judge_text),
                },
            )
            _trace_workflow_policy_event(
                workflow,
                "POLICY_VIOLATION",
                "Peer run stopped before finalization because judge did not return accept.",
                event_type="policy_violation",
                metadata={"judge_decision": judge_decision},
            )
            raise WorkflowValidationError(
                "Peer quality gate failed: judge did not accept the refined draft. "
                "Run stopped before final recommendation."
            )
        _trace_peer_flow_event(
            workflow,
            "PEER_FINAL_DECISION",
            judge_text,
            metadata={
                "decision": judge_decision,
                "rounds_executed": rounds_executed,
                "escalations_executed": escalations_executed,
                "reason_excerpt": _judge_reason_excerpt(judge_text),
            },
        )

        runtime_changed_manifest = _format_runtime_changed_files_manifest(
            changed_paths(
                write_before,
                snapshot_tree(root_dir, policy.write_target_subdir),
            )
        )
        final_text = await workflow.run_stage(
            spec=specs["orchestrator"],
            ui_agent_id="orchestrator",
            prompt=_build_prompt_with_contract(
                build_peer_final_prompt,
                message,
                discovery_basis,
                author_text,
                challenger_text,
                refiner_text,
                judge_text,
                run_contract_text=run_contract_text,
                runtime_changed_files_text=runtime_changed_manifest,
            ),
            trace_label="FINAL OUTPUT",
            verbose=verbose,
            print_output=False,
        )
        try:
            changed = _enforce_workspace_write_and_validation(
                policy,
                authorization,
                root_dir,
                write_before,
                Path(registry_dir) if registry_dir is not None else None,
            )
            if changed:
                _register_and_validate_task_artefacts(
                    workflow=workflow,
                    session_name=session_name,
                    changed=changed,
                    root_dir=root_dir,
                    user_input=intent_message,
                    deliverable_type=request_contract.deliverable_type,
                    request_contract=request_contract,
                )
                _trace_workflow_policy_event(
                    workflow,
                    "POLICY_WRITE_CHANGES",
                    "\n".join(changed),
                    event_type="policy_signal",
                    metadata={"changed_count": len(changed)},
                )
            verifier_result = enforce_peer_final_deliverable_verification(
                root_dir=root_dir,
                contract=run_contract,
                final_text=final_text,
                changed_paths=changed,
            )
            if verifier_result.checked_files:
                _trace_workflow_policy_event(
                    workflow,
                    "PEER_VERIFIER",
                    "\n".join(verifier_result.checked_files),
                    event_type="policy_signal",
                    metadata={"checked_file_count": len(verifier_result.checked_files)},
                )
        except PeerVerificationViolation as exc:
            if _is_repairable_peer_verifier_failure(str(exc)):
                _trace_peer_flow_event(
                    workflow,
                    "PEER_FINAL_REPAIR_START",
                    str(exc),
                    metadata={"attempt": 1},
                )
                repair_prompt = _build_peer_final_repair_prompt(
                    message=message,
                    discovery_basis=discovery_basis,
                    run_contract_text=run_contract_text,
                    judge_text=judge_text,
                    prior_final_text=final_text,
                    runtime_changed_manifest=_format_runtime_changed_files_manifest(changed),
                    verifier_failures=str(exc),
                )
                repaired_final_text = await workflow.run_stage(
                    spec=specs["orchestrator"],
                    ui_agent_id="orchestrator",
                    prompt=repair_prompt,
                    trace_label="FINAL OUTPUT (REPAIR 1)",
                    verbose=verbose,
                    print_output=False,
                )
                try:
                    verifier_result = enforce_peer_final_deliverable_verification(
                        root_dir=root_dir,
                        contract=run_contract,
                        final_text=repaired_final_text,
                        changed_paths=changed,
                    )
                except PeerVerificationViolation as repair_exc:
                    _trace_workflow_policy_event(
                        workflow,
                        "POLICY_VIOLATION",
                        str(repair_exc),
                        event_type="policy_violation",
                        metadata={"after_repair_attempt": 1},
                    )
                    raise WorkflowValidationError(str(repair_exc)) from repair_exc
                final_text = repaired_final_text
                if verifier_result.checked_files:
                    _trace_workflow_policy_event(
                        workflow,
                        "PEER_VERIFIER",
                        "\n".join(verifier_result.checked_files),
                        event_type="policy_signal",
                        metadata={
                            "checked_file_count": len(verifier_result.checked_files),
                            "after_repair_attempt": 1,
                        },
                    )
                _trace_peer_flow_event(
                    workflow,
                    "PEER_FINAL_REPAIR_SUCCESS",
                    "Peer final output repaired and verifier checks passed.",
                    metadata={"attempt": 1},
                )
                workflow.finish_workflow(
                    "Peer workflow completed.",
                    metadata={
                        "mode": "peer",
                        "judge_decision": judge_decision,
                        "refinement_rounds_executed": rounds_executed,
                        "refinement_stagnation": stagnation_detected,
                        "escalation_rounds_executed": escalations_executed,
                    },
                )
                return _extract_final_recommendation(final_text)
            _trace_workflow_policy_event(
                workflow,
                "POLICY_VIOLATION",
                str(exc),
                event_type="policy_violation",
            )
            raise WorkflowValidationError(str(exc)) from exc
        except WorkflowPolicyViolation as exc:
            _trace_workflow_policy_event(
                workflow,
                "POLICY_VIOLATION",
                str(exc),
                event_type="policy_violation",
            )
            raise WorkflowValidationError(str(exc)) from exc
        workflow.finish_workflow(
            "Peer workflow completed.",
            metadata={
                "mode": "peer",
                "judge_decision": judge_decision,
                "refinement_rounds_executed": rounds_executed,
                "refinement_stagnation": stagnation_detected,
                "escalation_rounds_executed": escalations_executed,
            },
        )
        return _extract_final_recommendation(final_text)


def build_peer_run_result(
    discovery_text: str,
    author_text: str,
    challenger_text: str,
    refiner_text: str,
    judge_text: str,
    final_text: str,
) -> PeerRunResult:
    transcript: list[PeerMessage] = []
    append_peer_message(transcript, "retrieval_planner", discovery_text)
    append_peer_message(transcript, "design_author", author_text)
    append_peer_message(transcript, "design_challenger", challenger_text)
    append_peer_message(transcript, "design_refiner", refiner_text)
    append_peer_message(transcript, "judge", judge_text)
    append_peer_message(transcript, "orchestrator", final_text)
    return PeerRunResult(final_text=final_text, transcript=transcript)
