"""Tests for workspace text search behaviour."""

from __future__ import annotations

import sys

import pytest


def test_search_workspace_text_token_fallback_on_long_query(tmp_path, monkeypatch) -> None:
    """Long queries that match no single line still find files via token fallback."""
    fake_workspace = tmp_path / "ws"
    fake_workspace.mkdir()
    ctx = fake_workspace / "knowledge"
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
    hits = workspace_server.search_workspace_text(long_query, subdir="knowledge", max_hits=10)
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


def test_workspace_write_policy_allows_task_markdown(tmp_path, monkeypatch) -> None:
    fake_workspace = tmp_path / "ws"
    fake_workspace.mkdir()

    monkeypatch.setattr(sys, "argv", ["crisai-test-workspace", str(fake_workspace)])
    for name in list(sys.modules):
        if name == "crisai.servers.workspace_server" or name.startswith("crisai.servers.workspace_server."):
            del sys.modules[name]

    import crisai.servers.workspace_server as workspace_server

    written = workspace_server.write_workspace_file("tasks/demo/artefacts/a.md", "# A\n")

    assert written == "tasks/demo/artefacts/a.md"
    assert (fake_workspace / "tasks/demo/artefacts/a.md").read_text(encoding="utf-8") == "# A\n"


def test_workspace_write_policy_blocks_unapproved_subdir(tmp_path, monkeypatch) -> None:
    fake_workspace = tmp_path / "ws"
    fake_workspace.mkdir()

    monkeypatch.setattr(sys, "argv", ["crisai-test-workspace", str(fake_workspace)])
    for name in list(sys.modules):
        if name == "crisai.servers.workspace_server" or name.startswith("crisai.servers.workspace_server."):
            del sys.modules[name]

    import crisai.servers.workspace_server as workspace_server

    with pytest.raises(ValueError, match="restricted to these subdirectories"):
        workspace_server.write_workspace_file("knowledge/canonical.md", "# No\n")


def test_workspace_write_policy_allows_exact_authorized_knowledge_path(tmp_path, monkeypatch) -> None:
    fake_workspace = tmp_path / "ws"
    fake_workspace.mkdir()
    monkeypatch.setenv(
        "CRISAI_WORKSPACE_AUTHORIZED_WRITE_PATHS",
        "knowledge/reference/template/hld_generic.md",
    )

    monkeypatch.setattr(sys, "argv", ["crisai-test-workspace", str(fake_workspace)])
    for name in list(sys.modules):
        if name == "crisai.servers.workspace_server" or name.startswith("crisai.servers.workspace_server."):
            del sys.modules[name]

    import crisai.servers.workspace_server as workspace_server

    written = workspace_server.write_workspace_file(
        "workspace/knowledge/reference/template/hld_generic.md",
        "# HLD\n",
    )

    assert written == "knowledge/reference/template/hld_generic.md"
    assert (fake_workspace / "knowledge/reference/template/hld_generic.md").read_text(encoding="utf-8") == "# HLD\n"


def test_workspace_write_policy_blocks_neighboring_knowledge_path(tmp_path, monkeypatch) -> None:
    fake_workspace = tmp_path / "ws"
    fake_workspace.mkdir()
    monkeypatch.setenv(
        "CRISAI_WORKSPACE_AUTHORIZED_WRITE_PATHS",
        "knowledge/reference/template/hld_generic.md",
    )

    monkeypatch.setattr(sys, "argv", ["crisai-test-workspace", str(fake_workspace)])
    for name in list(sys.modules):
        if name == "crisai.servers.workspace_server" or name.startswith("crisai.servers.workspace_server."):
            del sys.modules[name]

    import crisai.servers.workspace_server as workspace_server

    with pytest.raises(ValueError, match="restricted to these subdirectories"):
        workspace_server.write_workspace_file("knowledge/reference/template/other.md", "# No\n")


def test_workspace_write_policy_blocks_unapproved_extension(tmp_path, monkeypatch) -> None:
    fake_workspace = tmp_path / "ws"
    fake_workspace.mkdir()

    monkeypatch.setattr(sys, "argv", ["crisai-test-workspace", str(fake_workspace)])
    for name in list(sys.modules):
        if name == "crisai.servers.workspace_server" or name.startswith("crisai.servers.workspace_server."):
            del sys.modules[name]

    import crisai.servers.workspace_server as workspace_server

    with pytest.raises(ValueError, match="restricted to these file extensions"):
        workspace_server.write_workspace_file("outputs/script.py", "print('no')\n")


def test_workspace_write_policy_blocks_oversized_content(tmp_path, monkeypatch) -> None:
    fake_workspace = tmp_path / "ws"
    fake_workspace.mkdir()
    monkeypatch.setenv("CRISAI_WORKSPACE_MAX_WRITE_BYTES", "1024")

    monkeypatch.setattr(sys, "argv", ["crisai-test-workspace", str(fake_workspace)])
    for name in list(sys.modules):
        if name == "crisai.servers.workspace_server" or name.startswith("crisai.servers.workspace_server."):
            del sys.modules[name]

    import crisai.servers.workspace_server as workspace_server

    with pytest.raises(ValueError, match="exceeds maximum size"):
        workspace_server.write_workspace_file("outputs/large.md", "x" * 2048)


def test_workspace_read_blocks_sensitive_auth_folder(tmp_path, monkeypatch) -> None:
    fake_workspace = tmp_path / "ws"
    (fake_workspace / ".auth").mkdir(parents=True)
    (fake_workspace / ".auth" / "msal_token_cache.json").write_text("secret", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["crisai-test-workspace", str(fake_workspace)])
    for name in list(sys.modules):
        if name == "crisai.servers.workspace_server" or name.startswith("crisai.servers.workspace_server."):
            del sys.modules[name]

    import crisai.servers.workspace_server as workspace_server

    with pytest.raises(ValueError, match="restricted"):
        workspace_server.read_workspace_file(".auth/msal_token_cache.json")


def test_workspace_listing_omits_sensitive_and_hidden_paths(tmp_path, monkeypatch) -> None:
    fake_workspace = tmp_path / "ws"
    (fake_workspace / "knowledge").mkdir(parents=True)
    (fake_workspace / "knowledge" / "standard.md").write_text("# Standard\n", encoding="utf-8")
    # A non-hidden dir whose name merely shares a prefix with a sensitive name
    # must stay visible: prefix matching must not over-block.
    (fake_workspace / "authentication").mkdir()
    (fake_workspace / "authentication" / "guide.md").write_text("ok", encoding="utf-8")
    # Sensitive dirs remain blocked.
    (fake_workspace / ".auth").mkdir()
    (fake_workspace / ".auth" / "msal_token_cache.json").write_text("secret", encoding="utf-8")
    (fake_workspace / ".cache").mkdir()
    (fake_workspace / ".cache" / "runtime.json").write_text("cache", encoding="utf-8")
    # Any other hidden (dot) dir or file is excluded from the agent-visible
    # surface, not just the explicitly sensitive ones.
    (fake_workspace / "knowledge" / ".drafts").mkdir()
    (fake_workspace / "knowledge" / ".drafts" / "wip.md").write_text("wip", encoding="utf-8")
    (fake_workspace / ".env").write_text("SECRET=1\n", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["crisai-test-workspace", str(fake_workspace)])
    for name in list(sys.modules):
        if name == "crisai.servers.workspace_server" or name.startswith("crisai.servers.workspace_server."):
            del sys.modules[name]

    import crisai.servers.workspace_server as workspace_server

    listed = workspace_server.list_workspace_files(".")

    assert "knowledge/standard.md" in listed
    assert "authentication/guide.md" in listed
    assert ".auth/msal_token_cache.json" not in listed
    assert ".cache/runtime.json" not in listed
    assert "knowledge/.drafts/wip.md" not in listed
    assert ".env" not in listed


def test_iter_visible_workspace_files_skips_hidden_entries(tmp_path) -> None:
    """The shared visible-files walk excludes hidden dotfiles and dot-dirs.

    Both the workspace and document MCP servers list and read through
    iter_visible_workspace_files, so hiding hidden entries here keeps them out
    of the agent-visible retrieval surface as well as the UI browser.
    """
    from crisai.workspace.safety import iter_visible_workspace_files

    root = tmp_path
    (root / "docs").mkdir()
    (root / "docs" / "note.md").write_text("note", encoding="utf-8")
    (root / "docs" / ".secret.md").write_text("hidden file", encoding="utf-8")
    (root / ".config").mkdir()
    (root / ".config" / "settings.json").write_text("{}", encoding="utf-8")

    visible = {path.relative_to(root).as_posix() for path in iter_visible_workspace_files(root, root)}

    assert "docs/note.md" in visible
    assert "docs/.secret.md" not in visible
    assert ".config/settings.json" not in visible


def test_workspace_search_omits_sensitive_dirs(tmp_path, monkeypatch) -> None:
    fake_workspace = tmp_path / "ws"
    (fake_workspace / "knowledge").mkdir(parents=True)
    (fake_workspace / "knowledge" / "public.txt").write_text("needle public\n", encoding="utf-8")
    (fake_workspace / ".tokens").mkdir()
    (fake_workspace / ".tokens" / "secret.txt").write_text("needle secret\n", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["crisai-test-workspace", str(fake_workspace)])
    for name in list(sys.modules):
        if name == "crisai.servers.workspace_server" or name.startswith("crisai.servers.workspace_server."):
            del sys.modules[name]

    import crisai.servers.workspace_server as workspace_server

    hits = workspace_server.search_workspace_text("needle", max_hits=10)

    assert [hit["path"] for hit in hits] == ["knowledge/public.txt"]


def test_workspace_read_blocks_normalized_sensitive_path(tmp_path, monkeypatch) -> None:
    fake_workspace = tmp_path / "ws"
    (fake_workspace / ".auth").mkdir(parents=True)
    (fake_workspace / ".auth" / "token.json").write_text("secret", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["crisai-test-workspace", str(fake_workspace)])
    for name in list(sys.modules):
        if name == "crisai.servers.workspace_server" or name.startswith("crisai.servers.workspace_server."):
            del sys.modules[name]

    import crisai.servers.workspace_server as workspace_server

    with pytest.raises(ValueError, match="restricted"):
        workspace_server.read_workspace_file("knowledge/../.auth/token.json")
