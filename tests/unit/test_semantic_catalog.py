from pathlib import Path

from crisai.orchestration.semantic_catalog import load_semantic_catalog


def test_load_semantic_catalog_reads_registry_overrides(tmp_path: Path):
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir(parents=True)
    (registry_dir / "semantic_catalog.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "router:",
                "  discovery_terms: [discover-me]",
                "  source_markers: [discover-me]",
                "peer_verifier:",
                "  pattern_gap_line: '^\\\\s*-\\\\s*(Pattern)\\\\s+(\\\\d+)\\\\s*:'",
                "  leaf_file_pattern: 'workspace/context_staging/patterns/custom-(\\\\d+)\\\\.md$'",
                "  leaf_file_terms: [high level design, playbook]",
                "  data_architecture_terms: [data mesh]",
            ]
        ),
        encoding="utf-8",
    )

    catalog = load_semantic_catalog(str(registry_dir))

    assert "discover-me" in catalog.router.discovery_terms
    assert "discover-me" in catalog.router.source_markers
    assert "design" in catalog.router.design_terms  # default retained
    assert "high accuracy" in catalog.router.criticality_terms  # default retained
    assert "custom" in catalog.peer_verifier.leaf_file_pattern
    assert "high level design" in catalog.peer_verifier.leaf_file_terms
    assert "playbook" in catalog.peer_verifier.leaf_file_terms
    assert "data mesh" in catalog.peer_verifier.data_architecture_terms


def test_load_semantic_catalog_peer_contract_markers_override(tmp_path: Path):
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir(parents=True)
    (registry_dir / "semantic_catalog.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "peer_contract:",
                "  file_write_markers: [my-custom-write-marker]",
            ]
        ),
        encoding="utf-8",
    )

    catalog = load_semantic_catalog(str(registry_dir))

    assert "my-custom-write-marker" in catalog.peer_contract.file_write_markers
    assert "write_workspace_file" not in catalog.peer_contract.file_write_markers
    assert "implement" in catalog.peer_contract.code_change_markers
