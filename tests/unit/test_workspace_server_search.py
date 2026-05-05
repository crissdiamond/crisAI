"""Tests for workspace text search behaviour."""

from __future__ import annotations

import sys


def test_search_workspace_text_token_fallback_on_long_query(tmp_path, monkeypatch) -> None:
    """Long queries that match no single line still find files via token fallback."""
    fake_workspace = tmp_path / "ws"
    fake_workspace.mkdir()
    ctx = fake_workspace / "context"
    ctx.mkdir()
    (ctx / "reporting-patterns.txt").write_text(
        "Use a staging layer before Power BI connects to curated sources.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(sys, "argv", ["crisai-test-workspace", str(fake_workspace)])
    for name in list(sys.modules):
        if name == "crisai.servers.workspace_server" or name.startswith("crisai.servers.workspace_server."):
            del sys.modules[name]

    import crisai.servers.workspace_server as workspace_server

    long_query = (
        "Challenge a speed-first approach and find governance patterns for "
        "Power BI connecting to Excel in a monthly reporting scenario"
    )
    hits = workspace_server.search_workspace_text(long_query, subdir="context", max_hits=10)
    assert hits, "expected token fallback to match a distinctive word on a line"
    assert any("reporting-patterns.txt" in str(h["path"]) for h in hits)


def test_expand_associations_returns_advisory_payload(tmp_path, monkeypatch) -> None:
    fake_workspace = tmp_path / "ws"
    fake_workspace.mkdir()

    monkeypatch.setattr(sys, "argv", ["crisai-test-workspace", str(fake_workspace)])
    for name in list(sys.modules):
        if name == "crisai.servers.workspace_server" or name.startswith("crisai.servers.workspace_server."):
            del sys.modules[name]

    import crisai.servers.workspace_server as workspace_server

    class _Ctx:
        schema_version = "deterministic_context_v1"
        graph_version = "abc123"
        activated_topic_ids = frozenset({"integration_principles_corpus"})
        suggested_terms = frozenset({"integration principles", "producer flows"})
        suggested_sources = frozenset({"intranet"})

    monkeypatch.setattr(
        workspace_server,
        "deterministic_context_from_registry",
        lambda message, registry_dir: (_Ctx(), True),
    )
    payload = workspace_server.expand_associations("integration principles", max_terms=2)
    assert payload["advisory"] is True
    assert payload["graph_loaded"] is True
    assert payload["schema_version"] == "deterministic_context_v1"
    assert payload["activated_topics"] == ["integration_principles_corpus"]
