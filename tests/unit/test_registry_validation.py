from __future__ import annotations

import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from crisai.registry_validation import (
    _BOOLEAN_ENV_VARS,
    _NUMERIC_ENV_VARS,
    DoctorIssue,
    _check_env_setup,
    _env_keys,
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


def test_doctor_reports_semantic_graph_vertex_count() -> None:
    root = Path(__file__).resolve().parents[2]

    result = run_doctor(root_dir=root, registry_dir=root / "registry")

    assert any("semantic_graph.yaml loaded" in line and "vertices" in line for line in result.info)


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


def test_validation_reports_invalid_model_pricing(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    registry_dir = tmp_path / "registry"
    shutil.copytree(root / "registry", registry_dir)
    models_path = registry_dir / "models.yaml"
    models_payload = yaml.safe_load(models_path.read_text(encoding="utf-8"))
    models_payload["models"][0]["pricing"] = {
        "currency": "USD",
        "unit": "per_1m_tokens",
        "input": -1,
        "output": 1,
    }
    models_path.write_text(yaml.safe_dump(models_payload), encoding="utf-8")

    errors, _warnings = _validate_registry_cross_references(root, registry_dir)

    assert any("Model 'openai_fast' has invalid pricing metadata" in error.message for error in errors)


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
    summary_vertex = next(vertex for vertex in payload["vertices"] if vertex["id"] == "intent.summary")
    summary_vertex["terms"].append("in")
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
    """Doctor keeps clean checkouts valid when .env is absent."""
    errors, warnings = _check_env_setup(tmp_path)

    assert errors == []
    assert any(".env file not found" in w.message for w in warnings)
    matching = next(w for w in warnings if ".env file not found" in w.message)
    assert matching.hint is not None
    assert ".env.example" in matching.hint


def test_env_keys_reads_active_and_commented_placeholders(tmp_path: Path) -> None:
    env = tmp_path / ".env.example"
    env.write_text(
        """
ACTIVE_KEY=value
# COMMENTED_KEY=value
# not an assignment
INVALID-KEY=value
""",
        encoding="utf-8",
    )

    assert _env_keys(env) == {"ACTIVE_KEY", "COMMENTED_KEY"}


def test_env_keys_can_ignore_commented_placeholders(tmp_path: Path) -> None:
    env = tmp_path / ".env.example"
    env.write_text(
        """
ACTIVE_KEY=value
# COMMENTED_KEY=value
""",
        encoding="utf-8",
    )

    assert _env_keys(env, include_commented=False) == {"ACTIVE_KEY"}


def test_doctor_warns_when_env_missing_example_keys(tmp_path: Path) -> None:
    (tmp_path / ".env.example").write_text(
        """
OPENAI_API_KEY=placeholder
CRISAI_AGENT_STAGE_TIMEOUT_SECONDS=300
""",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("OPENAI_API_KEY=real\n", encoding="utf-8")

    errors, warnings = _check_env_setup(tmp_path)

    assert errors == []
    matching = next(w for w in warnings if ".env is missing key" in w.message)
    assert "CRISAI_AGENT_STAGE_TIMEOUT_SECONDS" in matching.message
    assert matching.hint is not None


def test_doctor_ignores_missing_commented_example_keys(tmp_path: Path) -> None:
    (tmp_path / ".env.example").write_text(
        """
OPENAI_API_KEY=placeholder
# CRISAI_RUNTIME_URL=http://127.0.0.1:8000
""",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("OPENAI_API_KEY=real\n", encoding="utf-8")

    errors, warnings = _check_env_setup(tmp_path)

    assert errors == []
    assert not any("CRISAI_RUNTIME_URL" in w.message for w in warnings)


def test_env_example_covers_doctor_validated_operator_env_vars() -> None:
    root = Path(__file__).resolve().parents[2]
    example_keys = _env_keys(root / ".env.example")
    expected = _BOOLEAN_ENV_VARS | set(_NUMERIC_ENV_VARS)

    assert expected <= example_keys


def test_doctor_warns_about_invalid_session_memory_env(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("", encoding="utf-8")
    monkeypatch.setenv("CRISAI_AGENT_STAGE_TIMEOUT_SECONDS", "0")
    monkeypatch.setenv("CRISAI_SESSION_MEMORY_STRATEGY", "random")
    monkeypatch.setenv("CRISAI_SESSION_MEMORY_MAX_RECENT_TURNS", "-1")
    monkeypatch.setenv("CRISAI_SESSION_MEMORY_MAX_RUNTIME_CHARS", "small")
    monkeypatch.setenv("CRISAI_SESSION_MEMORY_MAX_MEMORY_CHARS", "400")
    monkeypatch.setenv("CRISAI_SESSION_MEMORY_TASK_DRIFT_NUDGE", "maybe")

    errors, warnings = _check_env_setup(tmp_path)

    assert errors == []
    messages = "\n".join(w.message for w in warnings)
    assert "CRISAI_AGENT_STAGE_TIMEOUT_SECONDS" in messages
    assert "CRISAI_SESSION_MEMORY_STRATEGY" in messages
    assert "CRISAI_SESSION_MEMORY_MAX_RECENT_TURNS" in messages
    assert "CRISAI_SESSION_MEMORY_MAX_RUNTIME_CHARS" in messages
    assert "CRISAI_SESSION_MEMORY_MAX_MEMORY_CHARS" in messages
    assert "CRISAI_SESSION_MEMORY_TASK_DRIFT_NUDGE" in messages


def test_doctor_warns_about_invalid_first_run_operator_env(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("", encoding="utf-8")
    monkeypatch.setenv("CRISAI_AGENT_MAX_TURNS", "0")
    monkeypatch.setenv("CRISAI_RETRIEVAL_CHECKPOINT_ENABLED", "sometimes")
    monkeypatch.setenv("CRISAI_RETRIEVAL_CHECKPOINT_MAX_REDIRECTS", "-1")
    monkeypatch.setenv("CRISAI_MCP_CLIENT_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("CRISAI_WORKSPACE_MAX_WRITE_BYTES", "512")
    monkeypatch.setenv("CRISAI_DIAGRAM_MAX_WRITE_BYTES", "tiny")
    monkeypatch.setenv("INTRANET_PAGE_CACHE_TTL_HOURS", "0")
    monkeypatch.setenv("CRISAI_DETERMINISTIC_MCP_ADVISORY", "maybe")
    monkeypatch.setenv("CRISAI_PEER_MAX_REFINEMENT_ROUNDS", "-1")
    monkeypatch.setenv("CRISAI_PEER_MAX_ESCALATIONS", "-1")

    errors, warnings = _check_env_setup(tmp_path)

    assert errors == []
    messages = "\n".join(w.message for w in warnings)
    assert "CRISAI_AGENT_MAX_TURNS" in messages
    assert "CRISAI_RETRIEVAL_CHECKPOINT_ENABLED" in messages
    assert "CRISAI_RETRIEVAL_CHECKPOINT_MAX_REDIRECTS" in messages
    assert "CRISAI_MCP_CLIENT_TIMEOUT_SECONDS" in messages
    assert "CRISAI_WORKSPACE_MAX_WRITE_BYTES" in messages
    assert "CRISAI_DIAGRAM_MAX_WRITE_BYTES" in messages
    assert "INTRANET_PAGE_CACHE_TTL_HOURS" in messages
    assert "CRISAI_DETERMINISTIC_MCP_ADVISORY" in messages
    assert "CRISAI_PEER_MAX_REFINEMENT_ROUNDS" in messages
    assert "CRISAI_PEER_MAX_ESCALATIONS" in messages


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


def test_validation_warns_about_placeholder_api_keys(tmp_path: Path, monkeypatch) -> None:
    root = Path(__file__).resolve().parents[2]
    registry_dir = tmp_path / "registry"
    shutil.copytree(root / "registry", registry_dir)
    monkeypatch.setenv("GEMINI_API_KEY", "your-gemini-api-key")

    _errors, warnings = _validate_registry_cross_references(root, registry_dir)

    assert any("GEMINI_API_KEY" in w.message and "placeholder" in w.message for w in warnings)


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


# --- CRISAI_API_KEY warning ---


def test_doctor_warns_when_api_key_not_set(tmp_path: Path, monkeypatch) -> None:
    """Doctor issues a warning when CRISAI_API_KEY is not configured."""
    monkeypatch.delenv("CRISAI_API_KEY", raising=False)
    # Include key in .env (empty value) so the missing-key check does not fire.
    (tmp_path / ".env").write_text("OPENAI_API_KEY=test\nCRISAI_API_KEY=\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("OPENAI_API_KEY=\nCRISAI_API_KEY=\n", encoding="utf-8")

    _errors, warnings = _check_env_setup(tmp_path)

    api_key_warning = next((w for w in warnings if "unprotected" in w.message), None)
    assert api_key_warning is not None, "expected an 'unprotected' warning for unset CRISAI_API_KEY"
    assert api_key_warning.hint is not None
    assert "localhost" in api_key_warning.hint


def test_doctor_does_not_warn_when_api_key_set(tmp_path: Path, monkeypatch) -> None:
    """No CRISAI_API_KEY warning when the key is configured."""
    monkeypatch.setenv("CRISAI_API_KEY", "a-real-secret-key")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=test\nCRISAI_API_KEY=a-real-secret-key\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("OPENAI_API_KEY=\nCRISAI_API_KEY=\n", encoding="utf-8")

    _errors, warnings = _check_env_setup(tmp_path)

    assert not any("CRISAI_API_KEY" in w.message and "unprotected" in w.message for w in warnings)


def test_doctor_warns_when_ms_token_cache_path_is_inside_workspace(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("CRISAI_WORKSPACE_DIR", str(workspace))
    monkeypatch.setenv("MS_TOKEN_CACHE_PATH", str(workspace / ".auth" / "msal_token_cache.json"))
    monkeypatch.delenv("MS_TOKEN_INFO_PATH", raising=False)

    result = run_doctor(root_dir=tmp_path, registry_dir=Path(__file__).resolve().parents[2] / "registry")

    assert any("MS_TOKEN_CACHE_PATH points inside the workspace" in warning.message for warning in result.warnings)


def test_doctor_allows_ms_token_cache_path_outside_workspace(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("CRISAI_WORKSPACE_DIR", str(workspace))
    monkeypatch.setenv("MS_TOKEN_CACHE_PATH", str(tmp_path / "auth" / "msal_token_cache.json"))
    monkeypatch.delenv("MS_TOKEN_INFO_PATH", raising=False)

    result = run_doctor(root_dir=tmp_path, registry_dir=Path(__file__).resolve().parents[2] / "registry")

    assert not any("MS_TOKEN_CACHE_PATH points inside the workspace" in warning.message for warning in result.warnings)


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes only")
def test_doctor_warns_when_token_cache_permissions_are_too_broad(tmp_path: Path, monkeypatch) -> None:
    cache_dir = tmp_path / ".auth"
    cache_dir.mkdir(mode=0o755)
    cache_file = cache_dir / "msal_token_cache.json"
    cache_file.write_text("{}", encoding="utf-8")
    cache_file.chmod(0o644)
    monkeypatch.delenv("MS_TOKEN_CACHE_PATH", raising=False)
    monkeypatch.delenv("MS_TOKEN_INFO_PATH", raising=False)

    result = run_doctor(root_dir=tmp_path, registry_dir=Path(__file__).resolve().parents[2] / "registry")

    messages = "\n".join(w.message for w in result.warnings)
    assert "Microsoft token cache directory is too permissive" in messages
    assert "Microsoft token cache file is too permissive" in messages


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes only")
def test_doctor_accepts_private_token_cache_permissions(tmp_path: Path, monkeypatch) -> None:
    cache_dir = tmp_path / ".auth"
    cache_dir.mkdir(mode=0o700)
    cache_dir.chmod(0o700)
    cache_file = cache_dir / "msal_token_cache.json"
    cache_file.write_text("{}", encoding="utf-8")
    cache_file.chmod(0o600)
    monkeypatch.delenv("MS_TOKEN_CACHE_PATH", raising=False)
    monkeypatch.delenv("MS_TOKEN_INFO_PATH", raising=False)

    result = run_doctor(root_dir=tmp_path, registry_dir=Path(__file__).resolve().parents[2] / "registry")

    assert not any("Microsoft token cache" in warning.message for warning in result.warnings)


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes only")
def test_doctor_warns_when_tokens_directory_permissions_are_too_broad(tmp_path: Path, monkeypatch) -> None:
    cache_dir = tmp_path / ".tokens"
    cache_dir.mkdir(mode=0o755)
    cache_file = cache_dir / "msal_token_cache.json"
    cache_file.write_text("{}", encoding="utf-8")
    cache_file.chmod(0o644)
    monkeypatch.delenv("MS_TOKEN_CACHE_PATH", raising=False)
    monkeypatch.delenv("MS_TOKEN_INFO_PATH", raising=False)

    result = run_doctor(root_dir=tmp_path, registry_dir=Path(__file__).resolve().parents[2] / "registry")

    messages = "\n".join(w.message for w in result.warnings)
    assert "Microsoft token cache directory is too permissive" in messages
    assert "Microsoft token cache file is too permissive" in messages


def test_doctor_resolves_relative_token_cache_paths(tmp_path: Path, monkeypatch) -> None:
    # Set relative token cache path
    monkeypatch.setenv("MS_TOKEN_CACHE_PATH", ".tokens/msal_token_cache.json")
    monkeypatch.delenv("MS_TOKEN_INFO_PATH", raising=False)

    # Place a permissive token cache file relative to tmp_path (which is root_dir)
    cache_dir = tmp_path / ".tokens"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "msal_token_cache.json"
    cache_file.write_text("{}", encoding="utf-8")

    if os.name == "posix":
        cache_dir.chmod(0o755)
        cache_file.chmod(0o644)

    result = run_doctor(root_dir=tmp_path, registry_dir=Path(__file__).resolve().parents[2] / "registry")

    if os.name == "posix":
        messages = "\n".join(w.message for w in result.warnings)
        assert "Microsoft token cache directory is too permissive" in messages
        assert "Microsoft token cache file is too permissive" in messages


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes only")
def test_doctor_deduplicates_relative_token_cache_permission_warnings(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MS_TOKEN_CACHE_PATH", ".tokens/msal_token_cache.json")
    monkeypatch.delenv("MS_TOKEN_INFO_PATH", raising=False)
    cache_dir = tmp_path / ".tokens"
    cache_dir.mkdir(mode=0o755)
    cache_file = cache_dir / "msal_token_cache.json"
    cache_file.write_text("{}", encoding="utf-8")
    cache_file.chmod(0o644)

    result = run_doctor(root_dir=tmp_path, registry_dir=Path(__file__).resolve().parents[2] / "registry")

    duplicate_file_warnings = [
        warning
        for warning in result.warnings
        if f"Microsoft token cache file is too permissive: {cache_file.resolve()}" in warning.message
    ]
    assert len(duplicate_file_warnings) == 1
