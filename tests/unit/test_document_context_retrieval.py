from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCUMENT_SERVER_CANDIDATES = [
    REPO_ROOT / "src" / "crisai" / "servers" / "document_server.py",
    REPO_ROOT / "src" / "crisai" / "mcp" / "document_server.py",
    REPO_ROOT / "servers" / "document_server.py",
    REPO_ROOT / "document_server.py",
]


def _find_document_server() -> Path:
    """Find the document MCP server without assuming one exact repo layout."""
    for candidate in DOCUMENT_SERVER_CANDIDATES:
        if candidate.exists():
            return candidate

    searched = "\n".join(str(path) for path in DOCUMENT_SERVER_CANDIDATES)
    raise FileNotFoundError(f"Could not find document_server.py. Searched:\n{searched}")


@pytest.fixture()
def document_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load document_server.py with ROOT pointing at a temporary workspace."""
    server_path = _find_document_server()
    module_name = f"document_server_under_test_{id(tmp_path)}"

    monkeypatch.setattr(sys, "argv", [str(server_path), str(tmp_path)])

    spec = importlib.util.spec_from_file_location(module_name, server_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write_context_file(workspace: Path, relative_path: str, content: str) -> None:
    path = workspace / "context" / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_context_index_creates_chunks_across_context_folders(
    document_server: ModuleType,
    tmp_path: Path,
) -> None:
    _write_context_file(
        tmp_path,
        "standards/source-control.txt",
        "Recurring reports must define ownership, lineage, access, and data quality checks. "
        "Critical transformation logic must not live only in Power BI.",
    )
    _write_context_file(
        tmp_path,
        "patterns/file-route.txt",
        "For recurring Excel reporting, land the file unchanged, validate fields, stage the data, "
        "curate it, and expose Power BI from the governed dataset.",
    )
    _write_context_file(
        tmp_path,
        "notes/session-capture.txt",
        "Stakeholders want a quick dashboard from spreadsheets, but they expect monthly refreshes "
        "and consistent figures for operational decisions.",
    )

    summary = document_server.build_context_index(
        context_subdir="context",
        max_chars=220,
        overlap_chars=40,
    )

    assert summary["documents_indexed"] == 3
    assert summary["chunks_indexed"] >= 3
    assert set(summary["folder_counts"]).issuperset({"standards", "patterns", "notes"})
    assert (tmp_path / ".crisai" / "context_index.json").exists()

    index_summary = document_server.get_context_index_summary()

    assert index_summary["context_subdir"] == "context"
    assert index_summary["documents_indexed"] == 3
    assert index_summary["chunking"] == {"max_chars": 220, "overlap_chars": 40}


def test_search_context_chunks_returns_ranked_cross_folder_results(
    document_server: ModuleType,
    tmp_path: Path,
) -> None:
    _write_context_file(
        tmp_path,
        "reference/background.txt",
        "Local Excel files often become operational reporting sources. The architecture must clarify "
        "whether the dashboard is ad hoc analysis or a recurring reporting product.",
    )
    _write_context_file(
        tmp_path,
        "standards/assurance.txt",
        "Recurring reports require documented ownership, lineage, access model, retention expectations, "
        "and known data quality limitations.",
    )
    _write_context_file(
        tmp_path,
        "patterns/controlled-ingestion.txt",
        "The preferred pattern for recurring Excel dashboards is controlled ingestion: land the file, "
        "validate structure, curate a dataset, then present the result in Power BI.",
    )
    _write_context_file(
        tmp_path,
        "designs/previous-example.txt",
        "A previous benefits dashboard used Excel as a source but ingested the file into the data platform "
        "before Power BI because monthly refresh and assurance were required.",
    )
    _write_context_file(
        tmp_path,
        "notes/current-discovery.txt",
        "The current team wants speed, but the report will refresh monthly and influence operational decisions. "
        "The source spreadsheet has no formal owner yet.",
    )

    results = document_server.search_context_chunks(
        "recurring Excel Power BI dashboard ownership lineage data quality monthly refresh",
        max_results=8,
        rebuild=True,
        context_subdir="context",
    )

    assert results
    assert results == sorted(results, key=lambda item: item["score"], reverse=True)

    folders = {result["folder"] for result in results}
    assert len(folders) >= 3
    assert {"standards", "patterns"}.issubset(folders)

    combined_text = "\n".join(result["text"].lower() for result in results)
    assert "ownership" in combined_text
    assert "lineage" in combined_text
    assert "power bi" in combined_text

    for result in results:
        assert result["score"] > 0
        assert result["path"].startswith("context/")
        assert result["chunk_id"].startswith("chunk-")


def test_context_search_returns_empty_list_for_non_matching_query(
    document_server: ModuleType,
    tmp_path: Path,
) -> None:
    _write_context_file(
        tmp_path,
        "patterns/reporting.txt",
        "Power BI reporting over curated datasets should avoid hidden transformation logic.",
    )

    results = document_server.search_context_chunks(
        "kubernetes gpu model serving ollama condenser",
        max_results=5,
        rebuild=True,
        context_subdir="context",
    )

    assert results == []


def test_chunk_text_validates_chunk_settings(document_server: ModuleType) -> None:
    with pytest.raises(ValueError, match="max_chars"):
        document_server._chunk_text("example", max_chars=0, overlap_chars=0)

    with pytest.raises(ValueError, match="overlap_chars"):
        document_server._chunk_text("example", max_chars=100, overlap_chars=100)
