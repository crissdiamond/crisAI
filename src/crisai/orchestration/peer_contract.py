from __future__ import annotations

from dataclasses import dataclass

from crisai.orchestration.semantic_catalog import load_semantic_catalog


@dataclass(frozen=True)
class PeerRunContract:
    """Execution contract inferred from user intent for peer mode."""

    expected_output_type: str
    must_create_or_update_files: bool
    must_modify_code: bool
    must_ground_in_sources: bool
    acceptance_dimensions: tuple[str, ...]
    role_focus_author: str
    role_focus_challenger: str
    role_focus_refiner: str
    role_focus_judge: str


def infer_peer_run_contract(message: str) -> PeerRunContract:
    """Infer a generic peer contract from the user request."""
    markers = load_semantic_catalog().peer_contract
    text = (message or "").lower()
    must_write_files = any(marker in text for marker in markers.file_write_markers)
    must_modify_code = any(marker in text for marker in markers.code_change_markers)
    has_clear_code_targets = any(marker in text for marker in markers.code_target_markers)
    must_ground_in_sources = any(marker in text for marker in markers.grounding_markers)
    asks_assessment = any(marker in text for marker in markers.assessment_markers)

    # Prefer file-backed artefact classification unless explicit code targets
    # are present; this avoids over-classifying context-staging prompts as
    # code changes due to generic words like "implement".
    if must_write_files and not has_clear_code_targets:
        expected_output_type = "artifact_package"
    elif must_modify_code:
        expected_output_type = "code_change"
    elif asks_assessment:
        expected_output_type = "assessment"
    else:
        expected_output_type = "direct_answer"

    dimensions = ["instruction_alignment", "correctness", "completeness"]
    if must_ground_in_sources:
        dimensions.extend(["evidence_grounding", "traceability"])
    if must_write_files or must_modify_code:
        dimensions.append("execution_fidelity")

    author_focus = (
        "Produce the requested deliverable directly (not a process critique)."
        if expected_output_type in {"artifact_package", "code_change", "direct_answer"}
        else "Produce a decisive assessment aligned to the request."
    )
    challenger_focus = (
        "Challenge only against contract dimensions and missing deliverable outcomes; "
        "avoid semantics-only debate."
    )
    refiner_focus = (
        "Resolve only failed contract dimensions and preserve material evidence/detail."
    )
    judge_focus = (
        "Accept only when contract dimensions are met and output type matches the expected deliverable."
    )

    return PeerRunContract(
        expected_output_type=expected_output_type,
        must_create_or_update_files=must_write_files,
        must_modify_code=must_modify_code,
        must_ground_in_sources=must_ground_in_sources,
        acceptance_dimensions=tuple(dict.fromkeys(dimensions)),
        role_focus_author=author_focus,
        role_focus_challenger=challenger_focus,
        role_focus_refiner=refiner_focus,
        role_focus_judge=judge_focus,
    )


def render_peer_run_contract(contract: PeerRunContract) -> str:
    """Render contract as stable prompt text."""
    dimensions = ", ".join(contract.acceptance_dimensions)
    return "\n".join(
        [
            f"- Expected output type: {contract.expected_output_type}",
            f"- Must create/update files: {'yes' if contract.must_create_or_update_files else 'no'}",
            f"- Must modify code: {'yes' if contract.must_modify_code else 'no'}",
            f"- Must ground in sources: {'yes' if contract.must_ground_in_sources else 'no'}",
            f"- Acceptance dimensions: {dimensions}",
            f"- Author focus: {contract.role_focus_author}",
            f"- Challenger focus: {contract.role_focus_challenger}",
            f"- Refiner focus: {contract.role_focus_refiner}",
            f"- Judge focus: {contract.role_focus_judge}",
        ]
    )
