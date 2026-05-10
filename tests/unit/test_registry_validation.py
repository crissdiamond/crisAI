from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

import yaml

from crisai.registry_validation import (
    DoctorIssue,
    _validate_registry_cross_references,
    run_doctor,
)


def _make_sse_servers_yaml(url: str | None = "https://mcp.example.com/sse", transport: str = "sse") -> dict:
    entry: dict = {
        "id": "remote_test",
        "name": "Remote Test",
        "enabled": True,
        "transport": transport,
        "tags": [],
        "tools": {"allow": []},
    }
    if url is not None:
        entry["url"] = url
    return {"version": 1, "servers": [entry]}


def test_doctor_passes_current_registry() -> None:
    root = Path(__file__).resolve().parents[2]

    result = run_doctor(root_dir=root, registry_dir=root / "registry")

    assert result.ok is True
    assert result.errors == ()


def test_doctor_model_dry_build_passes_current_registry(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[2]

    class FakeLitellmModel:
        def __init__(self, model, api_key=None, base_url=None, should_replay_reasoning_content=None):
            del model, api_key, base_url, should_replay_reasoning_content

    class FakeAgent:
        def __init__(self, **kwargs):
            del kwargs

    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr("crisai.agents.factory.Agent", FakeAgent)
    monkeypatch.setitem(
        __import__("sys").modules,
        "agents.extensions.models.litellm_model",
        SimpleNamespace(LitellmModel=FakeLitellmModel),
    )

    result = run_doctor(root_dir=root, registry_dir=root / "registry", validate_models=True)

    assert result.ok is True
    assert result.errors == ()


def test_doctor_model_dry_build_reports_runtime_model_constructor_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = Path(__file__).resolve().parents[2]
    registry_dir = tmp_path / "registry"
    shutil.copytree(root / "registry", registry_dir)
    models_path = registry_dir / "models.yaml"
    models_payload = yaml.safe_load(models_path.read_text(encoding="utf-8"))
    models_payload["models"].append(
        {
            "id": "bad_deepseek",
            "provider": "deepseek",
            "model_name": "deepseek/deepseek-v4-flash",
            "api_key_env": "DEEPSEEK_API_KEY",
            "unsupported": "value",
        }
    )
    models_path.write_text(yaml.safe_dump(models_payload, sort_keys=False), encoding="utf-8")
    agents_path = registry_dir / "agents.yaml"
    agents_payload = yaml.safe_load(agents_path.read_text(encoding="utf-8"))
    agents_payload["agents"][0]["model_ref"] = "bad_deepseek"
    agents_path.write_text(yaml.safe_dump(agents_payload, sort_keys=False), encoding="utf-8")

    class StrictLitellmModel:
        def __init__(self, model, api_key=None, base_url=None):
            del model, api_key, base_url
            raise TypeError("constructor mismatch")

    class FakeAgent:
        def __init__(self, **kwargs):
            del kwargs

    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr("crisai.agents.factory.Agent", FakeAgent)
    monkeypatch.setitem(
        __import__("sys").modules,
        "agents.extensions.models.litellm_model",
        SimpleNamespace(LitellmModel=StrictLitellmModel),
    )

    result = run_doctor(root_dir=root, registry_dir=registry_dir, validate_models=True)

    assert result.ok is False
    assert any("Agent 'orchestrator' model dry-build failed" in e.message for e in result.errors)
    assert any("constructor mismatch" in e.message for e in result.errors)


def test_validation_warns_when_prompt_contract_tool_is_not_allowed(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    registry_dir = tmp_path / "registry"
    shutil.copytree(root / "registry", registry_dir)
    servers_path = registry_dir / "servers.yaml"
    payload = yaml.safe_load(servers_path.read_text(encoding="utf-8"))
    documents = next(server for server in payload["servers"] if server["id"] == "documents")
    documents["tools"]["allow"].remove("inspect_powerpoint_document")
    servers_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    _errors, warnings = _validate_registry_cross_references(root, registry_dir)

    assert any("inspect_powerpoint_document" in w.message for w in warnings)


def test_doctor_reports_unknown_model_ref(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    registry_dir = tmp_path / "registry"
    shutil.copytree(root / "registry", registry_dir)
    agents_path = registry_dir / "agents.yaml"
    payload = yaml.safe_load(agents_path.read_text(encoding="utf-8"))
    payload["agents"][0]["model_ref"] = "missing_model"
    agents_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    result = run_doctor(root_dir=root, registry_dir=registry_dir)

    assert result.ok is False
    assert any("unknown model_ref: missing_model" in e.message for e in result.errors)


def test_doctor_reports_missing_prompt_file(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    registry_dir = tmp_path / "registry"
    shutil.copytree(root / "registry", registry_dir)
    agents_path = registry_dir / "agents.yaml"
    payload = yaml.safe_load(agents_path.read_text(encoding="utf-8"))
    payload["agents"][0]["prompt_file"] = "prompts/does-not-exist.md"
    agents_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    result = run_doctor(root_dir=root, registry_dir=registry_dir)

    assert result.ok is False
    assert any("missing prompt file" in e.message for e in result.errors)


def test_doctor_rejects_standalone_function_word_graph_terms(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    registry_dir = tmp_path / "registry"
    shutil.copytree(root / "registry", registry_dir)
    graph_path = registry_dir / "semantic_graph.yaml"
    payload = yaml.safe_load(graph_path.read_text(encoding="utf-8"))
    payload["vertices"][0]["terms"].append("in")
    graph_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    result = run_doctor(root_dir=root, registry_dir=registry_dir)

    assert result.ok is False
    assert any("standalone function word" in e.message and "intent.summary" in e.message for e in result.errors)


def test_issue_str_returns_message() -> None:
    issue = DoctorIssue(message="something is wrong", hint="fix it like this")
    assert str(issue) == "something is wrong"


def test_issue_hint_is_none_by_default() -> None:
    issue = DoctorIssue(message="something is wrong")
    assert issue.hint is None


def test_doctor_warns_about_missing_env_file(tmp_path: Path) -> None:
    """Doctor raises an error when .env is absent from the project root."""
    root = Path(__file__).resolve().parents[2]
    registry_dir = tmp_path / "registry"
    shutil.copytree(root / "registry", registry_dir)
    # Use tmp_path as root so there is no .env there
    result = run_doctor(root_dir=tmp_path, registry_dir=registry_dir)

    assert any(".env file not found" in e.message for e in result.errors)
    matching = next(e for e in result.errors if ".env file not found" in e.message)
    assert matching.hint is not None
    assert ".env.example" in matching.hint


def test_issues_carry_hints_for_unknown_model_ref(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    registry_dir = tmp_path / "registry"
    shutil.copytree(root / "registry", registry_dir)
    agents_path = registry_dir / "agents.yaml"
    payload = yaml.safe_load(agents_path.read_text(encoding="utf-8"))
    payload["agents"][0]["model_ref"] = "missing_model"
    agents_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    result = run_doctor(root_dir=root, registry_dir=registry_dir)

    matching = next(e for e in result.errors if "unknown model_ref: missing_model" in e.message)
    assert matching.hint is not None
    assert "models.yaml" in matching.hint


def test_issues_carry_hints_for_missing_api_key(tmp_path: Path, monkeypatch) -> None:
    root = Path(__file__).resolve().parents[2]
    registry_dir = tmp_path / "registry"
    shutil.copytree(root / "registry", registry_dir)
    # Force GEMINI_API_KEY to be absent so the warning fires regardless of local .env
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    _errors, warnings = _validate_registry_cross_references(root, registry_dir)

    key_warnings = [w for w in warnings if "GEMINI_API_KEY" in w.message]
    assert key_warnings, "expected a warning for unset GEMINI_API_KEY"
    for w in key_warnings:
        assert w.hint is not None
        assert ".env" in w.hint


# --- Transport validation ---


def test_validation_accepts_sse_transport_with_url(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    registry_dir = tmp_path / "registry"
    shutil.copytree(root / "registry", registry_dir)
    servers_path = registry_dir / "servers.yaml"
    payload = yaml.safe_load(servers_path.read_text(encoding="utf-8"))
    payload["servers"].append(_make_sse_servers_yaml()["servers"][0])
    servers_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    errors, _ = _validate_registry_cross_references(root, registry_dir)

    assert not any("remote_test" in e.message and "unsupported transport" in e.message for e in errors)
    assert not any("remote_test" in e.message and "url" in e.message for e in errors)


def test_validation_accepts_streamable_http_transport_with_url(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    registry_dir = tmp_path / "registry"
    shutil.copytree(root / "registry", registry_dir)
    servers_path = registry_dir / "servers.yaml"
    payload = yaml.safe_load(servers_path.read_text(encoding="utf-8"))
    payload["servers"].append(
        _make_sse_servers_yaml(url="https://mcp.example.com/mcp", transport="streamable-http")["servers"][0]
    )
    servers_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    errors, _ = _validate_registry_cross_references(root, registry_dir)

    assert not any("remote_test" in e.message and "unsupported transport" in e.message for e in errors)
    assert not any("remote_test" in e.message and "url" in e.message for e in errors)


def test_validation_rejects_sse_without_url(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    registry_dir = tmp_path / "registry"
    shutil.copytree(root / "registry", registry_dir)
    servers_path = registry_dir / "servers.yaml"
    payload = yaml.safe_load(servers_path.read_text(encoding="utf-8"))
    payload["servers"].append(_make_sse_servers_yaml(url=None)["servers"][0])
    servers_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    errors, _ = _validate_registry_cross_references(root, registry_dir)

    assert any("remote_test" in e.message and "url" in e.message for e in errors)


def test_validation_rejects_unknown_transport(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    registry_dir = tmp_path / "registry"
    shutil.copytree(root / "registry", registry_dir)
    servers_path = registry_dir / "servers.yaml"
    payload = yaml.safe_load(servers_path.read_text(encoding="utf-8"))
    payload["servers"].append(
        _make_sse_servers_yaml(transport="websocket")["servers"][0]
    )
    servers_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    errors, _ = _validate_registry_cross_references(root, registry_dir)

    assert any("remote_test" in e.message and "unsupported transport" in e.message for e in errors)
