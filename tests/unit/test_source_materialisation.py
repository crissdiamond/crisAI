from __future__ import annotations

from pathlib import Path

import pytest

from crisai.orchestration import source_fetch, source_materialisation
from crisai.orchestration.source_materialisation import materialise_source
from crisai.workspace import source_cache


def _fetched(raw: bytes = b"raw-deck", *, suffix: str = ".pptx", revision: str = "rev-1") -> source_fetch.FetchedSource:
    return source_fetch.FetchedSource(
        name="UCL Integration Strategy v2.pptx",
        suffix=suffix,
        revision=revision,
        size=len(raw),
        raw_bytes=raw,
    )


def _patch_fetch(monkeypatch, *, result=None, error: str | None = None):
    calls = {"count": 0}

    async def _fake_fetch(server_spec, read_handle, *, runtime, env_overrides=None):
        calls["count"] += 1
        if error is not None:
            raise source_fetch.SourceFetchError(error)
        return result

    monkeypatch.setattr(source_materialisation.source_fetch, "fetch_source_bytes", _fake_fetch)
    # Avoid pptx extraction here (raw bytes are not a real deck): use a stub sidecar.
    monkeypatch.setattr(
        source_materialisation.source_cache, "extract_pptx_evidence",
        lambda raw: {"format": "pptx", "slide_count": 1},
    )
    return calls


@pytest.mark.anyio
async def test_materialise_fetches_and_caches(monkeypatch, tmp_path: Path):
    calls = _patch_fetch(monkeypatch, result=_fetched())

    outcome = await materialise_source(
        source_id="{DD876D07}",
        read_handle="spdoc-abc",
        server_spec=object(),
        runtime=object(),
        task_state_dir=tmp_path / ".crisai",
        workspace_root=tmp_path,
    )

    assert outcome.ok and not outcome.cache_hit
    assert outcome.record.revision == "rev-1"
    assert calls["count"] == 1
    # The cache now holds the source at that revision.
    assert source_cache.lookup_materialised(
        task_state_dir=tmp_path / ".crisai", source_id="{DD876D07}", revision="rev-1"
    ) is not None


@pytest.mark.anyio
async def test_known_revision_cache_hit_skips_fetch(monkeypatch, tmp_path: Path):
    calls = _patch_fetch(monkeypatch, result=_fetched())
    # Prime the cache with rev-1.
    await materialise_source(
        source_id="src-1", read_handle="spdoc-x", server_spec=object(), runtime=object(),
        task_state_dir=tmp_path / ".crisai", workspace_root=tmp_path,
    )
    assert calls["count"] == 1

    # A second call that already knows rev-1 must not fetch again.
    outcome = await materialise_source(
        source_id="src-1", read_handle="spdoc-x", server_spec=object(), runtime=object(),
        task_state_dir=tmp_path / ".crisai", workspace_root=tmp_path, known_revision="rev-1",
    )
    assert outcome.cache_hit is True
    assert calls["count"] == 1  # no extra fetch


@pytest.mark.anyio
async def test_fetched_revision_already_cached_is_a_hit(monkeypatch, tmp_path: Path):
    calls = _patch_fetch(monkeypatch, result=_fetched(revision="rev-9"))
    await materialise_source(
        source_id="src-1", read_handle="spdoc-x", server_spec=object(), runtime=object(),
        task_state_dir=tmp_path / ".crisai", workspace_root=tmp_path,
    )
    # Second call without known_revision: it fetches (learns rev-9) then finds it cached.
    outcome = await materialise_source(
        source_id="src-1", read_handle="spdoc-x", server_spec=object(), runtime=object(),
        task_state_dir=tmp_path / ".crisai", workspace_root=tmp_path,
    )
    assert outcome.cache_hit is True
    assert calls["count"] == 2  # fetched both times, but the second reused the cache entry


@pytest.mark.anyio
async def test_fetch_error_is_returned_not_raised(monkeypatch, tmp_path: Path):
    _patch_fetch(monkeypatch, error="graph 404")

    outcome = await materialise_source(
        source_id="src-1", read_handle="spdoc-x", server_spec=object(), runtime=object(),
        task_state_dir=tmp_path / ".crisai", workspace_root=tmp_path,
    )

    assert not outcome.ok
    assert outcome.record is None
    assert "graph 404" in outcome.error


@pytest.mark.anyio
async def test_missing_identifiers_short_circuit(monkeypatch, tmp_path: Path):
    calls = _patch_fetch(monkeypatch, result=_fetched())
    outcome = await materialise_source(
        source_id="  ", read_handle="spdoc-x", server_spec=object(), runtime=object(),
        task_state_dir=tmp_path / ".crisai", workspace_root=tmp_path,
    )
    assert not outcome.ok
    assert calls["count"] == 0
