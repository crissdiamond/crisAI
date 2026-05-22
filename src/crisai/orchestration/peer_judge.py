"""Judge parsing, decision audit, and peer round-limit resolution for peer workflows."""

from __future__ import annotations

import os
import re
from typing import Any

from crisai.orchestration import prompt_generation as prompt_module
from crisai.orchestration import retrieval_association_graph as graph_module
from crisai.orchestration import semantic_catalog as catalog_module

_FINAL_RECOMMENDATION_PATTERNS = [
    r"(?:^|\n)(#+\s*Final recommendation\s*\n+.*)$",
    r"(?:^|\n)(\*\*Final recommendation\*\*\s*\n+.*)$",
    r"(?:^|\n)(Final recommendation\s*\n+.*)$",
]

_DEFAULT_PEER_MAX_REFINEMENT_ROUNDS = 2
_DEFAULT_PEER_MAX_ESCALATIONS = 1


def _extract_final_recommendation(text: str) -> str:
    """Extract final recommendation section from the text if present.

    Args:
        text: The raw output text.

    Returns:
        The extracted final recommendation or the original text.
    """
    stripped = text.strip()
    for pattern in _FINAL_RECOMMENDATION_PATTERNS:
        match = re.search(pattern, stripped, flags=re.IGNORECASE | re.DOTALL)
        if match:
            extracted = match.group(1).strip()
            if extracted:
                return extracted
    return stripped


def _parse_judge_decision(text: str) -> str:
    """Parse judge output into ``accept``/``revise``/``rework``/``unknown``.

    Args:
        text: The raw judge output text.

    Returns:
        A string decision representing the parsed decision status.
    """
    raw = (text or "").strip()
    if not raw:
        return "unknown"
    clean = raw.lower()
    markers = catalog_module.load_semantic_catalog().peer_judge

    # Strict contract-first parse:
    # first non-empty line should be "Decision: accept|revise|rework".
    first_line = next((line.strip() for line in raw.splitlines() if line.strip()), "")
    strict = re.match(r"^decision\s*[:\-]\s*(accept|revise|rework|refine)\b", first_line, flags=re.IGNORECASE)
    if strict:
        decision = strict.group(1).lower()
        if decision in {"revise", "refine"} and any(marker in first_line.lower() for marker in markers.rework_markers):
            return "rework"
        return "revise" if decision == "refine" else decision

    decision_match = re.search(r"\bdecision\s*[:\-]?\s*([a-z ]{3,80})\b", clean)
    if decision_match:
        decision_blob = decision_match.group(1).strip()
        # Structural rework must win over revise/accept in ambiguous phrases.
        if any(marker in decision_blob for marker in markers.rework_markers):
            return "rework"
        # Revise/reject semantics must win over accept in ambiguous phrases.
        if any(marker in decision_blob for marker in markers.revise_markers):
            return "revise"
        if any(marker in decision_blob for marker in markers.accept_markers):
            return "accept"
    if any(marker in clean for marker in markers.rework_markers):
        return "rework"
    if any(marker in clean for marker in markers.revise_markers):
        return "revise"
    if any(marker in clean for marker in markers.accept_markers):
        return "accept"
    return "unknown"


def _judge_reason_excerpt(text: str, max_chars: int = 240) -> str:
    """Return a compact reason excerpt from judge output.

    Args:
        text: The raw judge output text.
        max_chars: The maximum character length of the excerpt.

    Returns:
        A compact snippet string representing the reason.
    """
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


def _resolve_peer_max_refinement_rounds() -> int:
    """Return max extra refiner/judge rounds after the first judge pass.

    Returns:
        The maximum refinement rounds as an integer.
    """
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
    """Return max author/challenger escalation attempts after rework/revise loops.

    Returns:
        The maximum escalations as an integer.
    """
    raw = os.getenv(
        "CRISAI_PEER_MAX_ESCALATIONS",
        str(_DEFAULT_PEER_MAX_ESCALATIONS),
    )
    try:
        parsed = int(raw)
    except ValueError:
        return _DEFAULT_PEER_MAX_ESCALATIONS
    return max(0, parsed)


def _trace_peer_flow_event(
    workflow: Any,
    stage: str,
    content: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit structured peer timeline events to the trace log.

    Args:
        workflow: The workflow object executing the pipeline.
        stage: The stage name of the workflow.
        content: The description or payload of the event.
        metadata: Optional dictionary with extra metadata.
    """
    tracer = getattr(workflow, "trace_event", None)
    if callable(tracer):
        tracer(stage, content, event_type="peer_timeline", metadata=metadata)


def _build_prompt_with_contract(
    builder: Any,
    *args: Any,
    run_contract_text: str,
    **extra_kwargs: Any,
) -> str:
    """Call prompt builders with optional run_contract support.

    Some tests monkeypatch legacy builder signatures that do not accept
    ``run_contract_text``. Fallback preserves compatibility.

    Args:
        builder: The prompt builder callable.
        *args: Positional arguments for the builder.
        run_contract_text: The run contract string to pass.
        **extra_kwargs: Additional keyword arguments for the builder.

    Returns:
        The generated prompt string.
    """
    try:
        return builder(*args, run_contract_text=run_contract_text, **extra_kwargs)
    except TypeError:
        return builder(*args)


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
    deterministic_context: graph_module.DeterministicRetrievalContext | None = None,
    deterministic_advisory_enabled: bool = False,
) -> tuple[str, str]:
    """Run judge stage and validate accepts with a second-pass quality audit.

    Args:
        workflow: The workflow object executing the pipeline.
        specs: Dictionary mapping stages to their agent/model specifications.
        message: The current user message.
        discovery_basis: The discovery foundation text.
        challenger_text: The challenger prompt or output.
        refiner_text: The refiner output.
        verbose: Whether to print verbose output.
        trace_label: Trace identifier for the first judge pass.
        quality_trace_label: Trace identifier for the quality gate.
        run_contract_text: The run contract context.
        filesystem_evidence_text: Dynamic filesystem evidence.
        deterministic_context: The canonical retrieval context.
        deterministic_advisory_enabled: Whether deterministic advisory is enabled.

    Returns:
        A tuple containing:
            - judge_text: The judge output.
            - parsed_decision: The final resolved decision ("accept", "revise", "rework").
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
        deterministic_context=deterministic_context,
        deterministic_advisory_enabled=deterministic_advisory_enabled,
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
        deterministic_context=deterministic_context,
        deterministic_advisory_enabled=deterministic_advisory_enabled,
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
    if quality_decision in {"revise", "rework"}:
        combined = (
            judge_text.strip()
            + "\n\nQuality gate override:\n"
            + quality_gate_text.strip()
        )
        return combined, quality_decision
    return judge_text, "accept"


# Expose prompt builders at module level for compatibility with unit test monkeypatching
build_judge_prompt = prompt_module.build_judge_prompt
build_judge_quality_gate_prompt = prompt_module.build_judge_quality_gate_prompt


