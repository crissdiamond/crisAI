from __future__ import annotations

import json
from types import SimpleNamespace

from crisai.cli import session_store


def test_cli_history_file_uses_workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(
        session_store,
        "load_settings",
        lambda: SimpleNamespace(workspace_dir=tmp_path),
    )

    path = session_store.cli_history_file()

    assert path == tmp_path / ".cli_history"
    assert path.parent.exists()


def test_cli_history_file_is_session_scoped_when_name_is_provided(tmp_path, monkeypatch):
    monkeypatch.setattr(
        session_store,
        "load_settings",
        lambda: SimpleNamespace(workspace_dir=tmp_path),
    )

    path = session_store.cli_history_file(" test-11 ")

    assert path == tmp_path / "tasks" / "test-11" / ".crisai" / ".cli_history_test-11"
    assert path.parent.exists()


def test_session_file_sanitises_session_name(tmp_path, monkeypatch):
    monkeypatch.setattr(
        session_store,
        "load_settings",
        lambda: SimpleNamespace(workspace_dir=tmp_path),
    )

    path = session_store.session_file(" my/session:*name ")

    assert path == tmp_path / "tasks" / "my_session__name" / ".crisai" / "history.json"


def test_session_file_defaults_to_default_when_name_is_blank(tmp_path, monkeypatch):
    monkeypatch.setattr(
        session_store,
        "load_settings",
        lambda: SimpleNamespace(workspace_dir=tmp_path),
    )

    path = session_store.session_file("   ")

    assert path == tmp_path / "tasks" / "default" / ".crisai" / "history.json"


def test_session_memory_file_uses_sanitised_session_name(tmp_path, monkeypatch):
    monkeypatch.setattr(
        session_store,
        "load_settings",
        lambda: SimpleNamespace(workspace_dir=tmp_path),
    )

    path = session_store.session_memory_file(" my/session:*name ")

    assert path == tmp_path / "tasks" / "my_session__name" / ".crisai" / "memory.json"


def test_load_history_filters_invalid_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(
        session_store,
        "load_settings",
        lambda: SimpleNamespace(workspace_dir=tmp_path),
    )

    target = session_store.session_file("demo")
    target.write_text(
        json.dumps(
            [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
                {"role": "system", "content": "ignore me"},
                {"role": "user", "content": 123},
                {"role": "assistant"},
            ]
        ),
        encoding="utf-8",
    )

    assert session_store.load_history("demo") == [
        ("user", "hello"),
        ("assistant", "hi"),
    ]


def test_load_history_returns_empty_list_for_invalid_json(tmp_path, monkeypatch):
    monkeypatch.setattr(
        session_store,
        "load_settings",
        lambda: SimpleNamespace(workspace_dir=tmp_path),
    )

    target = session_store.session_file("broken")
    target.write_text("not-json", encoding="utf-8")

    assert session_store.load_history("broken") == []


def test_save_history_persists_expected_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(
        session_store,
        "load_settings",
        lambda: SimpleNamespace(workspace_dir=tmp_path),
    )

    history = [("user", "hello"), ("assistant", "hi")]

    session_store.save_history("demo", history)

    target = session_store.session_file("demo")
    payload = json.loads(target.read_text(encoding="utf-8"))

    assert [item["role"] for item in payload] == ["user", "assistant"]
    assert [item["content"] for item in payload] == ["hello", "hi"]
    assert all(item["saved_at"].endswith("Z") for item in payload)


def test_clear_history_rewrites_session_to_empty_json_array(tmp_path, monkeypatch):
    monkeypatch.setattr(
        session_store,
        "load_settings",
        lambda: SimpleNamespace(workspace_dir=tmp_path),
    )
    session_store.save_history("demo", [("user", "hello"), ("assistant", "hi")])

    session_store.clear_history("demo")

    target = session_store.session_file("demo")
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == []
    assert session_store.load_history("demo") == []


def test_clear_cli_history_rewrites_session_command_history(tmp_path, monkeypatch):
    monkeypatch.setattr(
        session_store,
        "load_settings",
        lambda: SimpleNamespace(workspace_dir=tmp_path),
    )
    target = session_store.cli_history_file("demo")
    target.write_text("+old-command\n+another-command\n", encoding="utf-8")

    session_store.clear_cli_history("demo")

    assert target.exists()
    assert target.read_text(encoding="utf-8") == ""


def test_save_and_load_session_memory_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        session_store,
        "load_settings",
        lambda: SimpleNamespace(workspace_dir=tmp_path),
    )
    memory = session_store.SessionMemory(
        task_goal="Summarise the Integration Strategy deck.",
        current_state="Summary complete.",
        known_sources=["workspace/knowledge/integration.md"],
    )

    session_store.save_session_memory("demo", memory)
    loaded = session_store.load_session_memory("demo")

    assert loaded.task_goal == "Summarise the Integration Strategy deck."
    assert loaded.current_state == "Summary complete."
    assert loaded.schema_version == "session_memory_v2"
    assert loaded.known_sources == ["workspace/knowledge/integration.md"]
    assert loaded.updated_at.endswith("Z")


def test_load_session_memory_does_not_create_session_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(
        session_store,
        "load_settings",
        lambda: SimpleNamespace(workspace_dir=tmp_path),
    )

    loaded = session_store.load_session_memory("missing")

    assert loaded == session_store.SessionMemory()
    assert not (tmp_path / "tasks" / "missing").exists()


def test_load_v1_session_memory_upgrades_to_v2_on_save(tmp_path, monkeypatch):
    monkeypatch.setattr(
        session_store,
        "load_settings",
        lambda: SimpleNamespace(workspace_dir=tmp_path),
    )
    path = session_store.session_memory_file("demo")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "session_memory_v1",
                "task_goal": "Summarise the strategy.",
                "current_state": "Drafted.",
                "important_decisions": ["Use option A."],
                "known_sources": ["knowledge/strategy.md"],
            }
        ),
        encoding="utf-8",
    )

    loaded = session_store.load_session_memory("demo")
    session_store.save_session_memory("demo", loaded)
    saved = json.loads(path.read_text(encoding="utf-8"))

    assert loaded.schema_version == "session_memory_v2"
    assert loaded.task_goal == "Summarise the strategy."
    assert saved["schema_version"] == "session_memory_v2"
    assert saved["scope"] == []
    assert saved["source_findings"] == []


def test_clear_session_memory_rewrites_empty_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(
        session_store,
        "load_settings",
        lambda: SimpleNamespace(workspace_dir=tmp_path),
    )
    session_store.save_session_memory("demo", session_store.SessionMemory(task_goal="old"))

    session_store.clear_session_memory("demo")

    loaded = session_store.load_session_memory("demo")
    assert loaded.task_goal == ""
    assert loaded.schema_version == "session_memory_v2"
