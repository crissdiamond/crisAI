from pathlib import Path

import pytest

from crisai.orchestration.peer_contract import infer_peer_run_contract
from crisai.orchestration.peer_verifier import (
    PeerVerificationViolation,
    enforce_peer_final_deliverable_verification,
    verify_peer_final_deliverable,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_verify_peer_final_deliverable_flags_missing_referenced_file(tmp_path: Path):
    contract = infer_peer_run_contract("Create files under workspace/context_staging/patterns.")
    result = verify_peer_final_deliverable(
        root_dir=tmp_path,
        contract=contract,
        final_text="Updated workspace/context_staging/patterns/missing.md",
        changed_paths=["workspace/context_staging/patterns/missing.md"],
    )
    assert any("does not exist" in violation for violation in result.violations)


def test_verify_peer_final_deliverable_flags_duplicate_front_matter_ids(tmp_path: Path):
    contract = infer_peer_run_contract("Create files under workspace/context_staging/patterns.")
    file_a = tmp_path / "workspace/context_staging/patterns/a.md"
    file_b = tmp_path / "workspace/context_staging/patterns/b.md"
    _write(
        file_a,
        "---\nid: PATT-001\n---\n\n## Source\n- x\n",
    )
    _write(
        file_b,
        "---\nid: PATT-001\n---\n\n## Source\n- y\n",
    )
    result = verify_peer_final_deliverable(
        root_dir=tmp_path,
        contract=contract,
        final_text=(
            "Updated workspace/context_staging/patterns/a.md and "
            "workspace/context_staging/patterns/b.md"
        ),
        changed_paths=[
            "workspace/context_staging/patterns/a.md",
            "workspace/context_staging/patterns/b.md",
        ],
    )
    assert any("Duplicate front-matter id" in violation for violation in result.violations)


def test_enforce_peer_final_deliverable_verification_detects_unbacked_mismatch_claim(tmp_path: Path):
    contract = infer_peer_run_contract("Create files under workspace/context_staging/patterns.")
    file_a = tmp_path / "workspace/context_staging/patterns/a.md"
    _write(
        file_a,
        "---\nid: PATT-001\n---\n\n## Source\n- x\n## Design overview\n- fine\n",
    )
    with pytest.raises(PeerVerificationViolation) as exc:
        enforce_peer_final_deliverable_verification(
            root_dir=tmp_path,
            contract=contract,
            final_text=(
                "Updated workspace/context_staging/patterns/a.md. "
                "Mismatch was documented in-file."
            ),
            changed_paths=["workspace/context_staging/patterns/a.md"],
        )
    assert "mismatch/inconsistency was documented in files" in str(exc.value)


def test_verify_peer_final_deliverable_flags_closeout_omitting_changed_files(tmp_path: Path):
    contract = infer_peer_run_contract("Create files under workspace/context_staging/patterns.")
    file_a = tmp_path / "workspace/context_staging/patterns/a.md"
    file_b = tmp_path / "workspace/context_staging/patterns/b.md"
    _write(file_a, "---\nid: P1\n---\n\n## Source\n- a\n")
    _write(file_b, "---\nid: P2\n---\n\n## Source\n- b\n")
    result = verify_peer_final_deliverable(
        root_dir=tmp_path,
        contract=contract,
        final_text="Updated workspace/context_staging/patterns/a.md",
        changed_paths=[
            "workspace/context_staging/patterns/a.md",
            "workspace/context_staging/patterns/b.md",
        ],
    )
    assert any("close-out omitted changed files" in violation for violation in result.violations)


def test_verify_peer_final_deliverable_flags_gap_and_leaf_inconsistency(tmp_path: Path):
    contract = infer_peer_run_contract("Create files under workspace/context_staging/patterns.")
    gaps = tmp_path / "workspace/context_staging/patterns/integration-retrieval-gaps.md"
    leaf = tmp_path / "workspace/context_staging/patterns/consumer-pattern-1.md"
    _write(
        gaps,
        (
            "---\nid: G1\n---\n\n## Source\n- x\n\n## Retrieval gaps\n"
            "- Consumer Pattern 1: no grounded leaf content available in this run\n"
        ),
    )
    _write(
        leaf,
        (
            "---\nid: P1\n---\n\n## Source\n- y\n\n## Design overview\n"
            "- Name: Consumer Pattern 1\n- Description: grounded details\n"
        ),
    )
    result = verify_peer_final_deliverable(
        root_dir=tmp_path,
        contract=contract,
        final_text=(
            "Updated workspace/context_staging/patterns/integration-retrieval-gaps.md and "
            "workspace/context_staging/patterns/consumer-pattern-1.md"
        ),
        changed_paths=[
            "workspace/context_staging/patterns/integration-retrieval-gaps.md",
            "workspace/context_staging/patterns/consumer-pattern-1.md",
        ],
    )
    assert any("Gap inconsistency" in violation for violation in result.violations)
