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

    assert path == tmp_path / "chat_sessions" / ".cli_history_test-11"
    assert path.parent.exists()


def test_session_file_sanitises_session_name(tmp_path, monkeypatch):
    monkeypatch.setattr(
        session_store,
        "load_settings",
        lambda: SimpleNamespace(workspace_dir=tmp_path),
    )

    path = session_store.session_file(" my/session:*name ")

    assert path == tmp_path / "chat_sessions" / "my_session__name.json"


def test_session_file_defaults_to_default_when_name_is_blank(tmp_path, monkeypatch):
    monkeypatch.setattr(
        session_store,
        "load_settings",
        lambda: SimpleNamespace(workspace_dir=tmp_path),
    )

    path = session_store.session_file("   ")

    assert path == tmp_path / "chat_sessions" / "default.json"


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
