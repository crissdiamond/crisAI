from __future__ import annotations

from crisai.openai_agents_trace_compat import apply_openai_agents_trace_export_patch

apply_openai_agents_trace_export_patch()

import io
import inspect
import os
import re
from contextlib import asynccontextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from uuid import uuid4

import typer
from agents import Runner

from crisai.agents.factory import AgentFactory
from crisai.logging_utils import get_logger
from crisai.runtime import MultiServerContext, RuntimeManager
from crisai.tracing import TRACE_FILE_NAME, append_trace
from crisai.orchestration.peer_contract import infer_peer_run_contract, render_peer_run_contract
from crisai.orchestration.retrieval_association_graph import (
    DeterministicRetrievalContext,
    deterministic_context_from_registry,
    deterministic_context_trace_metadata,
)
from crisai.orchestration.peer_verifier import (
    PeerVerificationViolation,
    enforce_peer_final_deliverable_verification,
)

from .display import create_agent_live, print_agent_output
from .peer_transcript import PeerRunResult, append_peer_message
from .prompt_builders import (
    build_author_prompt,
    build_challenger_prompt,
    build_design_prompt,
    build_retrieval_planner_prompt,
    build_single_retrieval_planner_prompt,
    build_context_retrieval_prompt,
    build_judge_prompt,
    build_judge_quality_gate_prompt,
    build_peer_final_prompt,
    build_pipeline_final_prompt,
    build_refiner_prompt,
    build_review_prompt,
)
from .workflow_policy import (
    WorkflowPolicyViolation,
    changed_paths,
    enforce_intranet_fetch_policy,
    enforce_workspace_write_policy,
    infer_workflow_policy,
    snapshot_tree,
)
from .pipeline_engine import WorkflowEngine
from .workflow_support import (
    WorkflowEnvironment,
    collect_server_ids,
    ensure_openai_api_key,
    resolve_required_agents,
)

logger = get_logger(__name__)
_DEFAULT_AGENT_MAX_TURNS = 30


def _empty_deterministic_context() -> DeterministicRetrievalContext:
    return DeterministicRetrievalContext(
        activated_topic_ids=frozenset(),
        suggested_terms=frozenset(),
        suggested_sources=frozenset(),
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


def _get_run_id(environment: WorkflowEnvironment | object) -> str | None:
    """Return the workflow run id when available.

    This keeps pipeline logging and tracing compatible with older tests that
    monkeypatch create_workflow_environment with lightweight objects.
    """
    return getattr(environment, "run_id", None)


def _append_trace_compat(path: Path, stage: str, content: str, **kwargs: Any) -> None:
    """Call append_trace with backward-compatible fallback.

    Some existing tests monkeypatch append_trace with the historical
    three-argument signature. Production code uses structured keyword
    arguments. This helper preserves both call styles.
    """
    try:
        append_trace(path, stage, content, **kwargs)
    except TypeError:
        append_trace(path, stage, content)


def _append_trace_entry_compat(
    environment: WorkflowEnvironment,
    stage: str,
    content: str,
    *,
    event_type: str = "workflow_event",
    agent_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Call append_trace_entry with backward-compatible fallback.

    Some existing tests monkeypatch append_trace_entry with the historical
    three-argument signature. This helper allows the richer structured call in
    production while preserving those tests.
    """
    try:
        append_trace_entry(
            environment,
            stage,
            content,
            event_type=event_type,
            agent_id=agent_id,
            metadata=metadata,
        )
    except TypeError:
        append_trace_entry(environment, stage, content)


def _resolve_agent_max_turns() -> int:
    """Return the max turns used for each agent run.

    The OpenAI Agents SDK defaults to 10 turns, which can interrupt longer
    multi-step prompts. This resolver provides a safer default while allowing
    environment overrides.

    Returns:
        A positive integer max-turn value.
    """
    raw_value = os.getenv("CRISAI_AGENT_MAX_TURNS", str(_DEFAULT_AGENT_MAX_TURNS))
    try:
        parsed = int(raw_value)
    except ValueError:
        return _DEFAULT_AGENT_MAX_TURNS
    return parsed if parsed > 0 else _DEFAULT_AGENT_MAX_TURNS


async def _run_agent_silently(agent, prompt: str) -> str:
    """Run an agent while suppressing direct stdout/stderr noise only.

    Logging is handled centrally by the application logging configuration.
    """
    result = None
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = await Runner.run(
                agent,
                prompt,
                max_turns=_resolve_agent_max_turns(),
            )
    except Exception:
        logger.exception("Agent execution failed.")
        raise
    return str(result.final_output)


async def _run_agent_with_transient_box(agent_id: str, agent, prompt: str) -> str:
    """Run an agent and render its transient progress box."""
    live = create_agent_live(agent_id)
    with live:
        result = await _run_agent_silently(agent, prompt)
    return result


def _build_agent_factory(root_dir: Path, settings, model_specs=None):
    """Build an agent factory with compatibility for lightweight test doubles."""
    kwargs: dict[str, Any] = {}
    signature = inspect.signature(AgentFactory)
    if model_specs is not None and "model_specs" in signature.parameters:
        kwargs["model_specs"] = model_specs
    if "settings" in signature.parameters:
        kwargs["settings"] = settings
    return AgentFactory(root_dir, **kwargs)



def build_context_synthesizer_prompt(message: str, discovery_text: str) -> str:
    """Build a grounded prompt for the context synthesizer agent.

    The context_synthesizer stage is intentionally separate from both the retrieval
    planner and design: context_retrieval fetches sources from the planner handoff, while
    context_synthesizer converts that material into an evidence-led brief that a
    downstream design agent can use.

    Args:
        message: Original user request.
        discovery_text: Output produced by the **context_retrieval** stage (parameter
            name retained for call-site compatibility).

    Returns:
        A structured prompt that asks the context_synthesizer agent to extract
        relevant information, preserve source references, identify uncertainty,
        and avoid drafting the final solution design.
    """
    return f"""You are the Context Synthesizer agent in the crisAI workflow.

Your job is to transform retrieved source material into a concise, grounded context brief for a downstream solution design agent.

## Original user request

```text
{message}
```

## Context retrieval output

```text
{discovery_text}
```

## Task

Create a context brief that helps the design agent draft a solution design using only the information available in the context retrieval output.

## Rules

- Use only facts supported by the context retrieval output.
- Preserve file names, paths, document titles, sections, links, citations, or other source references when they are available.
- Separate confirmed facts from assumptions and uncertainties.
- Remove irrelevant findings, duplication, and low-value noise.
- Do not invent missing details.
- Do not draft, recommend, or optimise the solution design.
- If the context retrieval output is empty, weak, or not relevant, say so clearly and explain what is missing.

## Output format

```markdown
## Context Summary
A short paragraph explaining what relevant context was found and how strong the source basis is.

## Relevant Facts
- Fact: ...
  Source: ...

## Constraints and Dependencies
- Constraint/dependency: ...
  Source: ...

## Assumptions
- Assumption: ...
  Basis: ...

## Gaps and Uncertainties
- Gap/uncertainty: ...
  Why it matters: ...

## Source Notes
- Source: ...
  Relevance: ...
```
"""


def create_workflow_environment(settings, model_specs=None) -> WorkflowEnvironment:
    """Create workflow runtime objects using local module dependencies.

    This wrapper intentionally lives in pipelines.py so existing tests that
    monkeypatch RuntimeManager or AgentFactory on this module continue to work.
    """
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
    servers = [
        environment.runtime.build_server(server_specs[server_id])
        for server_id in server_ids
        if server_id in server_specs
    ]
    async with MultiServerContext(servers) as active_servers:
        yield active_servers


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
    _append_trace_compat(
        environment.trace_file,
        stage,
        content,
        run_id=_get_run_id(environment),
        event_type=event_type,
        agent_id=agent_id,
        metadata=metadata,
    )


_FINAL_RECOMMENDATION_PATTERNS = [
    r"(?:^|\n)(#+\s*Final recommendation\s*\n+.*)$",
    r"(?:^|\n)(\*\*Final recommendation\*\*\s*\n+.*)$",
    r"(?:^|\n)(Final recommendation\s*\n+.*)$",
]


_PEER_ACCEPT_MARKERS = {"accept", "approved", "ship"}
_PEER_REVISE_MARKERS = {"revise", "revision", "reject", "rejected", "not acceptable", "not approved"}
_DEFAULT_PEER_MAX_REFINEMENT_ROUNDS = 2
_DEFAULT_PEER_MAX_ESCALATIONS = 1


def _extract_final_recommendation(text: str) -> str:
    stripped = text.strip()
    for pattern in _FINAL_RECOMMENDATION_PATTERNS:
        match = re.search(pattern, stripped, flags=re.IGNORECASE | re.DOTALL)
        if match:
            extracted = match.group(1).strip()
            if extracted:
                return extracted
    return stripped


def _parse_judge_decision(text: str) -> str:
    """Parse judge output into ``accept``/``revise``/``unknown``."""
    raw = (text or "").strip()
    if not raw:
        return "unknown"
    clean = raw.lower()

    # Strict contract-first parse:
    # first non-empty line should be "Decision: accept|revise".
    first_line = next((line.strip() for line in raw.splitlines() if line.strip()), "")
    strict = re.match(r"^decision\s*[:\-]\s*(accept|revise)\b", first_line, flags=re.IGNORECASE)
    if strict:
        return strict.group(1).lower()

    decision_match = re.search(r"\bdecision\s*[:\-]?\s*([a-z ]{3,80})\b", clean)
    if decision_match:
        decision_blob = decision_match.group(1).strip()
        # Revise/reject semantics must win over accept in ambiguous phrases.
        if any(marker in decision_blob for marker in _PEER_REVISE_MARKERS):
            return "revise"
        if any(marker in decision_blob for marker in _PEER_ACCEPT_MARKERS):
            return "accept"
    if any(marker in clean for marker in _PEER_REVISE_MARKERS):
        return "revise"
    if any(marker in clean for marker in _PEER_ACCEPT_MARKERS):
        return "accept"
    return "unknown"


def _judge_reason_excerpt(text: str, max_chars: int = 240) -> str:
    """Return a compact reason excerpt from judge output."""
    raw = (text or "").strip()
    if not raw:
        return ""
    match = re.search(r"(?:^|\n)\s*reason\s*:\s*(.+)", raw, flags=re.IGNORECASE)
    if match:
        reason = " ".join(match.group(1).strip().split())
    else:
        # Fallback: first non-empty non-decision line.
        reason = ""
        for line in raw.splitlines():
            clean = line.strip()
            if not clean:
                continue
            if re.match(r"^decision\s*[:\-]", clean, flags=re.IGNORECASE):
                continue
            reason = " ".join(clean.split())
            break
    if len(reason) <= max_chars:
        return reason
    return reason[: max_chars - 3].rstrip() + "..."


def _trace_peer_flow_event(
    workflow: Any,
    stage: str,
    content: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit structured peer timeline events to the trace log."""
    _trace_workflow_policy_event(
        workflow,
        stage,
        content,
        event_type="peer_timeline",
        metadata=metadata,
    )


def _resolve_peer_max_refinement_rounds() -> int:
    """Return max extra refiner/judge rounds after the first judge pass."""
    raw = os.getenv(
        "CRISAI_PEER_MAX_REFINEMENT_ROUNDS",
        str(_DEFAULT_PEER_MAX_REFINEMENT_ROUNDS),
    )
    try:
        parsed = int(raw)
    except ValueError:
        return _DEFAULT_PEER_MAX_REFINEMENT_ROUNDS
    return max(0, parsed)


def _resolve_peer_max_escalations() -> int:
    """Return max author/challenger escalation attempts after revise loops."""
    raw = os.getenv(
        "CRISAI_PEER_MAX_ESCALATIONS",
        str(_DEFAULT_PEER_MAX_ESCALATIONS),
    )
    try:
        parsed = int(raw)
    except ValueError:
        return _DEFAULT_PEER_MAX_ESCALATIONS
    return max(0, parsed)


def _build_peer_filesystem_evidence(
    *,
    root_dir: Path,
    before_snapshot: dict[str, int],
    target_subdir: str | None,
    max_files: int = 20,
) -> str:
    """Return compact runtime evidence about changed workspace artefacts."""
    def _extract_excerpt_lines(rel_path: str, text: str, *, max_lines: int = 8) -> list[str]:
        """Return a compact, content-bearing excerpt for judge verification."""
        body = text.strip()
        if not body:
            return []
        lines = [line.rstrip() for line in body.splitlines()]
        # Prefer meaningful markdown structure and facts over raw front matter.
        candidates: list[str] = []
        body_lines: list[str] = []
        in_front_matter = False
        front_matter_delims_seen = 0
        for line in lines:
            stripped = line.strip()
            if stripped == "---":
                front_matter_delims_seen += 1
                in_front_matter = front_matter_delims_seen == 1
                if front_matter_delims_seen >= 2:
                    in_front_matter = False
                continue
            if in_front_matter or not stripped:
                continue
            body_lines.append(stripped)
        if not body_lines:
            return []

        lower_path = rel_path.lower()

        # For index-style artefacts, include the Design overview section slice so
        # judge can see grouped lists and representative pattern entries.
        if "index" in lower_path:
            for idx, line in enumerate(body_lines):
                if line.lower() == "## design overview":
                    return body_lines[idx : idx + min(max_lines, 20)]

        # For gap-style artefacts, include the Retrieval gaps section directly.
        if "gap" in lower_path or "retrieval-gaps" in lower_path:
            for idx, line in enumerate(body_lines):
                if line.lower() == "## retrieval gaps":
                    return body_lines[idx : idx + min(max_lines, 14)]

        for stripped in body_lines:
            if stripped.startswith("## ") or stripped.startswith("- "):
                candidates.append(stripped)
            elif not candidates:
                # Fallback to the first non-empty body lines if headings/bullets
                # are not yet available.
                candidates.append(stripped)
            if len(candidates) >= max_lines:
                break
        return candidates[:max_lines]

    after_snapshot = snapshot_tree(root_dir, target_subdir)
    changed = changed_paths(before_snapshot, after_snapshot)
    changed_md = [
        p
        for p in changed
        if p.startswith("workspace/") and Path(p).suffix.lower() in {".md", ".txt"}
    ]
    if not changed_md:
        return "No changed workspace markdown/txt files detected yet in this run."

    lines = [f"Changed markdown/txt files ({len(changed_md)}):"]
    for rel_path in changed_md[:max_files]:
        abs_path = (root_dir / rel_path).resolve()
        if not abs_path.exists():
            lines.append(f"- {rel_path} | exists: no")
            continue
        text = abs_path.read_text(encoding="utf-8", errors="ignore")
        has_front_matter = text.startswith("---") and "\n---" in text[3:]
        has_source = "## Source" in text
        header_count = sum(1 for line in text.splitlines() if line.strip().startswith("## "))
        lines.append(
            "- "
            + rel_path
            + f" | exists: yes | front_matter: {'yes' if has_front_matter else 'no'}"
            + f" | has_source: {'yes' if has_source else 'no'} | h2_sections: {header_count}"
        )
        excerpt_lines = _extract_excerpt_lines(rel_path, text, max_lines=8)
        if excerpt_lines:
            lines.append("  excerpt:")
            for excerpt_line in excerpt_lines:
                lines.append(f"    - {excerpt_line}")
    omitted = len(changed_md) - min(len(changed_md), max_files)
    if omitted > 0:
        lines.append(f"- ... {omitted} additional changed files omitted from evidence summary")
    return "\n".join(lines)


async def _run_judge_with_acceptance_audit(
    *,
    workflow: Any,
    specs: dict[str, Any],
    message: str,
    discovery_basis: str,
    challenger_text: str,
    refiner_text: str,
    verbose: bool,
    trace_label: str,
    quality_trace_label: str,
    run_contract_text: str = "",
    filesystem_evidence_text: str = "",
) -> tuple[str, str]:
    """Run judge stage and validate accepts with a second-pass quality audit.

    Returns:
        Tuple of (judge_text, parsed_decision).
    """
    effective_refiner_text = refiner_text
    if filesystem_evidence_text.strip():
        effective_refiner_text = (
            refiner_text.rstrip()
            + "\n\n## Filesystem evidence (runtime)\n"
            + filesystem_evidence_text.strip()
        )

    judge_prompt = _build_prompt_with_contract(
        build_judge_prompt,
        message,
        discovery_basis,
        challenger_text,
        effective_refiner_text,
        run_contract_text=run_contract_text,
    )
    judge_text = await workflow.run_stage(
        spec=specs["judge"],
        ui_agent_id="judge",
        prompt=judge_prompt,
        trace_label=trace_label,
        verbose=verbose,
    )
    judge_decision = _parse_judge_decision(judge_text)
    _trace_peer_flow_event(
        workflow,
        "PEER_JUDGE_DECISION",
        judge_text,
        metadata={
            "trace_label": trace_label,
            "decision": judge_decision,
            "reason_excerpt": _judge_reason_excerpt(judge_text),
        },
    )
    if judge_decision != "accept":
        return judge_text, judge_decision

    quality_gate_prompt = _build_prompt_with_contract(
        build_judge_quality_gate_prompt,
        message,
        discovery_basis,
        challenger_text,
        effective_refiner_text,
        judge_text,
        run_contract_text=run_contract_text,
    )
    quality_gate_text = await workflow.run_stage(
        spec=specs["judge"],
        ui_agent_id="judge",
        prompt=quality_gate_prompt,
        trace_label=quality_trace_label,
        verbose=verbose,
    )
    quality_decision = _parse_judge_decision(quality_gate_text)
    _trace_peer_flow_event(
        workflow,
        "PEER_QUALITY_GATE_DECISION",
        quality_gate_text,
        metadata={
            "trace_label": quality_trace_label,
            "decision": quality_decision,
            "reason_excerpt": _judge_reason_excerpt(quality_gate_text),
        },
    )
    if quality_decision == "revise":
        combined = (
            judge_text.strip()
            + "\n\nQuality gate override:\n"
            + quality_gate_text.strip()
        )
        return combined, "revise"
    return judge_text, "accept"


def _create_environment(settings, model_specs=None) -> WorkflowEnvironment:
    """Create a workflow environment while preserving older monkeypatch seams."""
    signature = inspect.signature(create_workflow_environment)
    if model_specs is not None and "model_specs" in signature.parameters:
        return create_workflow_environment(settings, model_specs=model_specs)
    return create_workflow_environment(settings)


def _build_prompt_with_contract(builder, *args, run_contract_text: str, **extra_kwargs: Any) -> str:
    """Call prompt builders with optional run_contract support.

    Some tests monkeypatch legacy builder signatures that do not accept
    ``run_contract_text``. Fallback preserves compatibility.
    """
    try:
        return builder(*args, run_contract_text=run_contract_text, **extra_kwargs)
    except TypeError:
        return builder(*args)


def _format_runtime_changed_files_manifest(paths: list[str]) -> str:
    """Render a stable, verbatim manifest of changed workspace artefact paths."""
    normalized = [
        path
        for path in sorted(set(paths or []))
        if path.startswith("workspace/") and Path(path).suffix.lower() in {".md", ".txt"}
    ]
    if not normalized:
        return "None."
    return "\n".join(f"- {path}" for path in normalized)


def _prompt_section(title: str, body: str) -> str:
    """Render a stable prompt section with trimmed content."""
    clean = (body or "").strip() or "None."
    return f"{title}:\n{clean}"


def _is_repairable_peer_verifier_failure(message: str) -> bool:
    """Return whether verifier failures are repairable via final-text rewrite."""
    lower = (message or "").lower()
    repairable_markers = (
        "referenced output file does not exist",
        "final output close-out omitted changed files",
        "final output did not reference any concrete workspace files",
    )
    return any(marker in lower for marker in repairable_markers)


def _build_peer_final_repair_prompt(
    *,
    message: str,
    discovery_basis: str,
    run_contract_text: str,
    judge_text: str,
    prior_final_text: str,
    runtime_changed_manifest: str,
    verifier_failures: str,
) -> str:
    """Build a bounded repair prompt for verifier mismatch classes."""
    return "\n\n".join(
        [
            _prompt_section("User request", message),
            _prompt_section("Discovery findings", discovery_basis),
            _prompt_section("Run contract", run_contract_text),
            _prompt_section("Judge decision", judge_text),
            _prompt_section("Previous final output", prior_final_text),
            _prompt_section("Runtime changed files", runtime_changed_manifest),
            _prompt_section("Verifier failures", verifier_failures),
            "Task:\nRepair the final output so verifier checks pass without changing on-disk artefacts.",
            "Repair rules:\n"
            "- Do not claim files that do not exist.\n"
            "- Use runtime changed file paths verbatim.\n"
            "- Ensure close-out file list exactly covers changed markdown/txt files.\n"
            "- Keep source mappings aligned to those exact file paths.\n"
            "- Do not introduce new file paths, aliases, or renamed variants.\n"
            "- Keep the response concise and user-facing.",
        ]
    )


def _create_workflow_engine(environment: WorkflowEnvironment, server_specs) -> WorkflowEngine:
    """Create a workflow engine wired to the local compatibility helpers.

    Keeping this wiring in ``pipelines.py`` preserves existing monkeypatch
    seams for tests that patch runtime, tracing, or agent execution helpers on
    this module.
    """

    def trace_writer(stage: str, content: str, **kwargs: Any) -> None:
        """Forward structured workflow events through the compatibility layer."""
        _append_trace_entry_compat(environment, stage, content, **kwargs)

    return WorkflowEngine(
        environment=environment,
        server_specs=server_specs,
        server_context_factory=workflow_server_context,
        stage_runner=_run_agent_with_transient_box,
        trace_writer=trace_writer,
        output_printer=print_agent_output,
    )


async def run_single(message: str, agent_id: str, *, settings, server_specs, agent_specs, model_specs=None) -> str:
    """Run a single agent directly."""
    ensure_openai_api_key(settings)

    if agent_id not in agent_specs:
        raise typer.BadParameter(f"Unknown agent_id: {agent_id}")

    environment = _create_environment(settings, model_specs=model_specs)
    agent_spec = agent_specs[agent_id]

    logger.info("Running single agent request.", extra={"agent_id": agent_id, "run_id": _get_run_id(environment)})

    registry_dir = getattr(settings, "registry_dir", None)
    deterministic_context = _empty_deterministic_context()
    graph_loaded = False
    if registry_dir is not None:
        deterministic_context, graph_loaded = deterministic_context_from_registry(message, Path(registry_dir))

    async with workflow_server_context(environment, [agent_spec], server_specs) as active_servers:
        _append_trace_entry_compat(
            environment,
            "USER_INPUT",
            message,
            event_type="workflow_input",
            metadata={"mode": "single", "agent_id": agent_id},
        )
        if graph_loaded:
            _append_trace_entry_compat(
                environment,
                "DETERMINISTIC_RETRIEVAL_CONTEXT",
                "Deterministic retrieval context computed.",
                event_type="policy_signal",
                metadata=deterministic_context_trace_metadata(deterministic_context),
            )
        agent = environment.factory.build_agent(agent_spec, active_servers)
        prompt = (
            build_single_retrieval_planner_prompt(
                message,
                deterministic_context=deterministic_context,
                registry_dir=Path(registry_dir) if registry_dir is not None else None,
            )
            if agent_id == "retrieval_planner"
            else message
        )
        result = await _run_agent_silently(agent, prompt)
        _append_trace_compat(
            environment.trace_file,
            "FINAL_OUTPUT",
            result,
            run_id=_get_run_id(environment),
            event_type="workflow_output",
            agent_id=agent_id,
        )
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
) -> str:
    """Run the standard retrieval_planner → context_retrieval → context_synthesizer → design pipeline."""
    ensure_openai_api_key(settings)
    environment = _create_environment(settings, model_specs=model_specs)
    intent_message = user_intent_message or message
    registry_dir = getattr(settings, "registry_dir", None)
    deterministic_context = _empty_deterministic_context()
    graph_loaded = False
    if registry_dir is not None:
        deterministic_context, graph_loaded = deterministic_context_from_registry(
            intent_message,
            Path(registry_dir),
        )
    policy = infer_workflow_policy(
        intent_message,
        registry_dir=Path(registry_dir) if registry_dir is not None else None,
        deterministic_context=deterministic_context,
    )
    root_dir = Path(getattr(environment, "root_dir", Path.cwd()))
    write_before = snapshot_tree(root_dir, policy.write_target_subdir)

    logger.info("Running pipeline workflow.", extra={"run_id": _get_run_id(environment), "review": review})

    specs = resolve_required_agents(
        agent_specs,
        ["retrieval_planner", "context_retrieval", "context_synthesizer", "design", "review", "orchestrator"],
        mode_name="Pipeline mode",
    )

    engine = _create_workflow_engine(environment, server_specs)

    async with engine.session(specs.values()) as workflow:
        workflow.start_workflow(
            "Starting pipeline workflow.",
            metadata={"mode": "pipeline", "review": review},
        )
        workflow.trace_user_input(message)
        if graph_loaded:
            _trace_workflow_policy_event(
                workflow,
                "DETERMINISTIC_RETRIEVAL_CONTEXT",
                "Deterministic retrieval context computed.",
                event_type="policy_signal",
                metadata=deterministic_context_trace_metadata(deterministic_context),
            )

        retrieval_plan_text = await workflow.run_stage(
            spec=specs["retrieval_planner"],
            ui_agent_id="retrieval_planner",
            prompt=build_retrieval_planner_prompt(
                message,
                deterministic_context=deterministic_context,
                registry_dir=Path(registry_dir) if registry_dir is not None else None,
            ),
            trace_label="RETRIEVAL_PLANNER OUTPUT",
            verbose=verbose,
        )

        context_retrieval_text = await workflow.run_stage(
            spec=specs["context_retrieval"],
            ui_agent_id="context_retrieval",
            prompt=build_context_retrieval_prompt(
                message,
                retrieval_plan_text,
                deterministic_context=deterministic_context,
                registry_dir=Path(registry_dir) if registry_dir is not None else None,
            ),
            trace_label="CONTEXT RETRIEVAL OUTPUT",
            verbose=verbose,
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
            raise typer.BadParameter(str(exc)) from exc

        context_text = await workflow.run_stage(
            spec=specs["context_synthesizer"],
            ui_agent_id="context_synthesizer",
            prompt=build_context_synthesizer_prompt(message, context_retrieval_text),
            trace_label="CONTEXT OUTPUT",
            verbose=verbose,
        )

        design_text = await workflow.run_stage(
            spec=specs["design"],
            ui_agent_id="design",
            prompt=build_design_prompt(message, context_text),
            trace_label="DESIGN OUTPUT",
            verbose=verbose,
        )

        if review:
            review_text = await workflow.run_stage(
                spec=specs["review"],
                ui_agent_id="review",
                prompt=build_review_prompt(message, context_text, design_text),
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
            prompt=build_pipeline_final_prompt(message, context_text, design_text, review_text),
            trace_label="FINAL OUTPUT",
            verbose=verbose,
            print_output=False,
        )
        try:
            changed = enforce_workspace_write_policy(
                policy,
                root_dir,
                write_before,
            )
            if changed:
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
            raise typer.BadParameter(str(exc)) from exc
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
) -> str:
    """Run the peer workflow with optional retrieval and final recommendation."""
    del review  # Unused in peer mode today; kept for API compatibility.
    ensure_openai_api_key(settings)
    environment = _create_environment(settings, model_specs=model_specs)
    intent_message = user_intent_message or message
    registry_dir = getattr(settings, "registry_dir", None)
    deterministic_context = _empty_deterministic_context()
    if registry_dir is not None:
        deterministic_context, _ = deterministic_context_from_registry(intent_message, Path(registry_dir))
    policy = infer_workflow_policy(
        intent_message,
        registry_dir=Path(registry_dir) if registry_dir is not None else None,
        deterministic_context=deterministic_context,
    )
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

        retrieval_plan_text = ""
        context_retrieval_text = ""
        context_text = ""
        if needs_retrieval:
            retrieval_plan_text = await workflow.run_stage(
                spec=specs["retrieval_planner"],
                ui_agent_id="retrieval_planner",
                prompt=build_retrieval_planner_prompt(
                    message,
                    deterministic_context=deterministic_context,
                    registry_dir=Path(registry_dir) if registry_dir is not None else None,
                ),
                trace_label="RETRIEVAL_PLANNER OUTPUT",
                verbose=verbose,
            )
            if use_context_retrieval:
                context_retrieval_text = await workflow.run_stage(
                    spec=specs["context_retrieval"],
                    ui_agent_id="context_retrieval",
                    prompt=build_context_retrieval_prompt(
                        message,
                        retrieval_plan_text,
                        deterministic_context=deterministic_context,
                        registry_dir=Path(registry_dir) if registry_dir is not None else None,
                    ),
                    trace_label="CONTEXT RETRIEVAL OUTPUT",
                    verbose=verbose,
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
                    raise typer.BadParameter(str(exc)) from exc
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
        )
        previous_refiner_text = refiner_text
        stagnation_detected = False
        rounds_executed = 0
        escalations_executed = 0

        # Judge-gated refinement loop. If the judge says "revise", feed the
        # judge feedback back into the refiner and ask for another judgement.
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
            )

        # Escalation path: if revise loop cannot reach accept, rerun
        # author/challenger/refiner with explicit judge feedback.
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
            )

        if rounds_executed > 0 and judge_decision != "accept":
            unresolved_reason = (
                "Peer refinement reached convergence with no material changes."
                if stagnation_detected
                else f"Peer refinement reached max rounds ({max_refinement_rounds}) without an explicit accept decision."
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
            raise typer.BadParameter(
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
            changed = enforce_workspace_write_policy(
                policy,
                root_dir,
                write_before,
            )
            if changed:
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
                    raise typer.BadParameter(str(repair_exc)) from repair_exc
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
            raise typer.BadParameter(str(exc)) from exc
        except WorkflowPolicyViolation as exc:
            _trace_workflow_policy_event(
                workflow,
                "POLICY_VIOLATION",
                str(exc),
                event_type="policy_violation",
            )
            raise typer.BadParameter(str(exc)) from exc
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
    transcript = []
    append_peer_message(transcript, "retrieval_planner", discovery_text)
    append_peer_message(transcript, "design_author", author_text)
    append_peer_message(transcript, "design_challenger", challenger_text)
    append_peer_message(transcript, "design_refiner", refiner_text)
    append_peer_message(transcript, "judge", judge_text)
    append_peer_message(transcript, "orchestrator", final_text)
    return PeerRunResult(final_text=final_text, transcript=transcript)
