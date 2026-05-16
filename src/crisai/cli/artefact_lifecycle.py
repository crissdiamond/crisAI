from __future__ import annotations

import re
from pathlib import Path

from crisai.config import load_settings
from crisai.orchestration.semantic_catalog import load_semantic_catalog
from crisai.orchestration.task_contract import TaskContract, infer_task_contract

from .session_store import register_task_artefacts, sanitize_session_name, task_dir

_TASK_ARTEFACT_LINK_RE = re.compile(r"(?:file:///workspace/)?(tasks/[^)\s]+/artefacts/[^)\s]+\.md)")
_HEADING_RE = re.compile(r"(?m)^##\s+(.+?)\s*$")
_MERMAID_RE = re.compile(r"```mermaid\s+.+?```", re.DOTALL)

_HLD_REQUIRED_HEADINGS = (
    "Purpose",
    "Document control",
    "Executive summary",
    "Context",
    "Scope",
    "Requirements",
    "Current state",
    "Target architecture",
    "Architecture views",
    "Source inputs",
    "Data model, business rules, or processing logic",
    "Validation and quality controls",
    "Lineage and metadata",
    "Security, privacy, and access",
    "Governance and ownership",
    "Key decisions",
    "Options considered",
    "Risks, assumptions, issues, and dependencies",
    "Delivery approach",
    "Testing and acceptance",
    "Operations and support",
    "Open questions",
    "Approvals",
    "Source",
)


def final_output_references_task_artefacts(final_output: str, session_name: str) -> list[str]:
    """Return task artefact paths linked by a final answer."""
    safe = sanitize_session_name(session_name)
    paths: list[str] = []
    for match in _TASK_ARTEFACT_LINK_RE.finditer(final_output or ""):
        path = match.group(1).strip()
        if path.startswith(f"tasks/{safe}/artefacts/"):
            paths.append(f"workspace/{path}")
    return sorted(dict.fromkeys(paths))


def persist_reusable_deliverable(
    *,
    session_name: str,
    user_input: str,
    final_output: str,
    registry_dir: Path | None = None,
) -> str:
    """Persist reusable chat deliverables as task artefacts and return final text."""
    if final_output_references_task_artefacts(final_output, session_name):
        return final_output
    content = (final_output or "").strip()
    if len(content) < 800 or "##" not in content:
        return final_output
    try:
        contract = infer_task_contract(user_input, registry_dir=registry_dir)
    except Exception:  # noqa: BLE001 - persistence is opportunistic and must not fail the user response.
        return final_output
    filename = _deliverable_filename(user_input, contract, registry_dir=registry_dir)
    if not filename:
        return final_output
    target = task_dir(session_name) / "artefacts" / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content + "\n", encoding="utf-8")
    rel = f"workspace/tasks/{sanitize_session_name(session_name)}/artefacts/{filename}"
    register_task_artefacts(
        session_name,
        [rel],
        request=user_input,
        deliverable_type=contract.deliverable_type,
        root_dir=Path(getattr(load_settings(), "root_dir", Path.cwd())),
    )
    return final_output.rstrip() + f"\n\nSaved artefact: [{filename}](file:///{rel})"


def validate_hld_artefacts_for_request(
    *,
    user_input: str,
    paths: list[str],
    root_dir: Path,
) -> list[str]:
    """Return HLD conformance warnings for changed task artefacts."""
    contract = infer_task_contract(user_input)
    if not _is_hld_request(user_input, contract, registry_dir=getattr(load_settings(), "registry_dir", None)):
        return []
    warnings: list[str] = []
    for rel in paths:
        clean = rel.strip()
        if not clean.endswith(".md") or "/artefacts/" not in clean:
            continue
        path = (root_dir / clean).resolve()
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        headings = {heading.strip().lower() for heading in _HEADING_RE.findall(text)}
        missing = [heading for heading in _HLD_REQUIRED_HEADINGS if heading.lower() not in headings]
        if missing:
            warnings.append(f"{clean}: missing HLD template section(s): {', '.join(missing[:8])}")
        if not _MERMAID_RE.search(text):
            warnings.append(f"{clean}: missing Mermaid architecture diagram for full HLD request")
    return warnings


def _deliverable_filename(user_input: str, contract: TaskContract, *, registry_dir: Path | None = None) -> str:
    if _is_hld_request(user_input, contract, registry_dir=registry_dir):
        return "hld.md"
    try:
        catalog = load_semantic_catalog(str(registry_dir) if registry_dir is not None else None)
    except Exception:  # noqa: BLE001 - lifecycle persistence must fail open.
        return ""
    return catalog.artifact_lifecycle.persisted_deliverable_filenames.get(contract.deliverable_type, "")


def _is_hld_request(user_input: str, contract: TaskContract, *, registry_dir: Path | None = None) -> bool:
    try:
        catalog = load_semantic_catalog(str(registry_dir) if registry_dir is not None else None)
    except Exception:  # noqa: BLE001 - conformance checks must not block registry loading failures.
        return False
    text = (user_input or "").lower()
    return contract.deliverable_type == "architecture_design" and any(
        marker in text for marker in catalog.artifact_lifecycle.hld_markers
    )
