from __future__ import annotations

from types import SimpleNamespace

import pytest

from crisai.cli import session_store
from crisai.servers import session_memory_server


def _settings(tmp_path):
    return SimpleNamespace(workspace_dir=tmp_path / "workspace", log_dir=tmp_path / "logs", registry_dir=tmp_path / "registry")


def test_session_memory_mcp_is_active_session_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(session_store, "load_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr(session_memory_server, "load_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr("crisai.cli.chat_context.load_settings", lambda: _settings(tmp_path))
    monkeypatch.setenv("CRISAI_SESSION_MEMORY_SESSION", "demo")
    session_store.save_session_memory("demo", session_store.SessionMemory(task_goal="Demo goal."))
    session_store.save_session_memory("sibling", session_store.SessionMemory(task_goal="Sibling secret."))

    context = session_memory_server.get_session_context()

    assert context["session"] == "demo"
    assert "Demo goal" in context["baseline_brief"]
    assert "Sibling secret" not in context["baseline_brief"]
    with pytest.raises(PermissionError):
        session_memory_server._enforce_active_session("sibling")


def test_session_memory_mcp_read_only_tools_do_not_mutate_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(session_store, "load_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr(session_memory_server, "load_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr("crisai.cli.chat_context.load_settings", lambda: _settings(tmp_path))
    monkeypatch.setenv("CRISAI_SESSION_MEMORY_SESSION", "demo")
    session_store.save_session_memory(
        "demo",
        session_store.SessionMemory(task_goal="Recall certified datasets.", source_findings=["Certified datasets are required."]),
    )
    before = session_store.session_memory_file("demo").read_text(encoding="utf-8")

    results = session_memory_server.recall_session_context("certified datasets")
    active = session_memory_server.get_active_session_name()
    after = session_store.session_memory_file("demo").read_text(encoding="utf-8")

    assert active == {"session": "demo"}
    assert results
    assert after == before
