from crisai.cli.workflow_policy import snapshot_tree
from crisai.orchestration.peer_evidence import _build_peer_filesystem_evidence


def test_build_peer_filesystem_evidence_reports_changed_markdown_files(tmp_path):
    root = tmp_path
    target = root / "workspace/knowledge_staging/patterns"
    target.mkdir(parents=True, exist_ok=True)
    before = snapshot_tree(root, "workspace/knowledge_staging")
    sample = target / "consumer-pattern-1.md"
    sample.write_text(
        "---\nid: PATT-1\n---\n\n## Source\n- x\n\n## Design overview\n- y\n",
        encoding="utf-8",
    )

    evidence = _build_peer_filesystem_evidence(
        root_dir=root,
        before_snapshot=before,
        target_subdir="workspace/knowledge_staging",
    )

    assert "Changed markdown/txt files (1):" in evidence
    assert "workspace/knowledge_staging/patterns/consumer-pattern-1.md" in evidence
    assert "front_matter: yes" in evidence
    assert "has_source: yes" in evidence
    assert "excerpt:" in evidence
    assert "## Source" in evidence


def test_build_peer_filesystem_evidence_prioritizes_index_section_content(tmp_path):
    root = tmp_path
    target = root / "workspace/knowledge_staging/patterns"
    target.mkdir(parents=True, exist_ok=True)
    before = snapshot_tree(root, "workspace/knowledge_staging")
    sample = target / "integration-patterns-index.md"
    sample.write_text(
        (
            "---\nid: PATT-INT-001\n---\n\n"
            "## Source\n- x\n\n"
            "## Design overview\n"
            "- Consumer patterns listed on the catalogue:\n"
            "  - Pattern 0 — Direct\n"
            "- Producer patterns listed on the catalogue:\n"
            "  - Pattern 1 — System to Enterprise API\n"
            "- Ingestion patterns listed on the catalogue:\n"
            "  - Pattern 1 — Database to Ingestion API\n"
        ),
        encoding="utf-8",
    )

    evidence = _build_peer_filesystem_evidence(
        root_dir=root,
        before_snapshot=before,
        target_subdir="workspace/knowledge_staging",
    )

    assert "integration-patterns-index.md" in evidence
    assert "## Design overview" in evidence
    assert "Pattern 0 — Direct" in evidence
    assert "Ingestion patterns listed on the catalogue" in evidence
