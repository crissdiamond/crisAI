from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

import yaml

from crisai.registry_validation import _validate_registry_cross_references, run_doctor


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
    assert any("Agent 'orchestrator' model dry-build failed" in error for error in result.errors)
    assert any("constructor mismatch" in error for error in result.errors)


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

    assert any("inspect_powerpoint_document" in warning for warning in warnings)


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
    assert any("unknown model_ref: missing_model" in error for error in result.errors)


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
    assert any("missing prompt file" in error for error in result.errors)


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
    assert any("standalone function word" in error and "intent.summary" in error for error in result.errors)


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

    assert not any("remote_test" in e and "unsupported transport" in e for e in errors)
    assert not any("remote_test" in e and "url" in e for e in errors)


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

    assert not any("remote_test" in e and "unsupported transport" in e for e in errors)
    assert not any("remote_test" in e and "url" in e for e in errors)


def test_validation_rejects_sse_without_url(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    registry_dir = tmp_path / "registry"
    shutil.copytree(root / "registry", registry_dir)
    servers_path = registry_dir / "servers.yaml"
    payload = yaml.safe_load(servers_path.read_text(encoding="utf-8"))
    payload["servers"].append(_make_sse_servers_yaml(url=None)["servers"][0])
    servers_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    errors, _ = _validate_registry_cross_references(root, registry_dir)

    assert any("remote_test" in e and "url" in e for e in errors)


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

    assert any("remote_test" in e and "unsupported transport" in e for e in errors)
