from __future__ import annotations

import io
from pathlib import Path

import pytest

from crisai.workspace import source_cache


def _materialise(tmp_path: Path, *, source_id: str, revision: str, data: bytes = b"raw-bytes"):
    state = tmp_path / ".crisai"
    return source_cache.materialise_source(
        task_state_dir=state,
        workspace_root=tmp_path,
        source_id=source_id,
        revision=revision,
        raw_bytes=data,
        suffix=".pptx",
        extracted={"format": "pptx", "slide_count": 2},
        title="UCL Integration Strategy v2.pptx",
        source_family="sharepoint_docs",
        source_type="sharepoint_document",
        materialised_at="2026-06-14T08:00:00Z",
    )


def test_materialise_then_lookup_hit(tmp_path: Path) -> None:
    record = _materialise(tmp_path, source_id="{DD876D07-GUID}", revision="2026-06-12T10:00:00Z")

    assert record.byte_size == len(b"raw-bytes")
    assert (tmp_path / record.raw_path).read_bytes() == b"raw-bytes"
    assert (tmp_path / record.extracted_path).is_file()
    assert record.raw_path.endswith("raw.pptx")

    hit = source_cache.lookup_materialised(
        task_state_dir=tmp_path / ".crisai",
        source_id="{DD876D07-GUID}",
        revision="2026-06-12T10:00:00Z",
    )
    assert hit is not None
    assert hit.title == "UCL Integration Strategy v2.pptx"
    assert hit.source_family == "sharepoint_docs"


def test_lookup_is_a_miss_for_a_different_revision(tmp_path: Path) -> None:
    # Revision invalidation: an upstream change means the new revision was never
    # cached, so the caller must re-materialise.
    _materialise(tmp_path, source_id="src-1", revision="rev-old")

    miss = source_cache.lookup_materialised(
        task_state_dir=tmp_path / ".crisai",
        source_id="src-1",
        revision="rev-new",
    )
    assert miss is None


def test_read_extracted_returns_sidecar(tmp_path: Path) -> None:
    record = _materialise(tmp_path, source_id="src-1", revision="rev-1")
    extracted = source_cache.read_extracted(workspace_root=tmp_path, record=record)
    assert extracted == {"format": "pptx", "slide_count": 2}


def test_prune_keeps_only_the_current_revision(tmp_path: Path) -> None:
    _materialise(tmp_path, source_id="src-1", revision="rev-1")
    _materialise(tmp_path, source_id="src-1", revision="rev-2")
    _materialise(tmp_path, source_id="src-1", revision="rev-3")

    removed = source_cache.prune_stale_revisions(
        task_state_dir=tmp_path / ".crisai",
        source_id="src-1",
        keep_revision="rev-3",
    )

    assert sorted(removed) == ["rev-1", "rev-2"]
    assert source_cache.lookup_materialised(
        task_state_dir=tmp_path / ".crisai", source_id="src-1", revision="rev-3"
    ) is not None
    assert source_cache.lookup_materialised(
        task_state_dir=tmp_path / ".crisai", source_id="src-1", revision="rev-1"
    ) is None


def test_safe_segment_sanitises_provider_guids(tmp_path: Path) -> None:
    # A braced GUID with separators must not escape the cache directory.
    record = _materialise(tmp_path, source_id="{7D59EB57-57D2-5E3E}", revision="2026/06/14 08:00")
    raw = tmp_path / record.raw_path
    assert ".crisai/sources/" in record.raw_path
    assert raw.is_file()
    assert ".." not in record.raw_path


def test_materialise_requires_identity_and_revision(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        source_cache.materialise_source(
            task_state_dir=tmp_path / ".crisai",
            workspace_root=tmp_path,
            source_id="   ",
            revision="rev-1",
            raw_bytes=b"x",
            suffix=".pptx",
            extracted={},
        )
    with pytest.raises(ValueError):
        source_cache.materialise_source(
            task_state_dir=tmp_path / ".crisai",
            workspace_root=tmp_path,
            source_id="src-1",
            revision="  ",
            raw_bytes=b"x",
            suffix=".pptx",
            extracted={},
        )


def test_extract_pptx_evidence_builds_slide_level_sidecar(tmp_path: Path) -> None:
    pptx = pytest.importorskip("pptx")
    prs = pptx.Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Integration Strategy"
    slide.placeholders[1].text = "Event driven and API first"
    buffer = io.BytesIO()
    prs.save(buffer)

    sidecar = source_cache.extract_pptx_evidence(buffer.getvalue())

    assert sidecar["slide_count"] == 1
    assert "Integration Strategy" in str(sidecar)

    # End-to-end: a real deck materialises with its extracted sidecar.
    record = source_cache.materialise_source(
        task_state_dir=tmp_path / ".crisai",
        workspace_root=tmp_path,
        source_id="deck-1",
        revision="rev-1",
        raw_bytes=buffer.getvalue(),
        suffix=".pptx",
        extracted=sidecar,
    )
    reloaded = source_cache.read_extracted(workspace_root=tmp_path, record=record)
    assert reloaded["slide_count"] == 1
