from __future__ import annotations

import shutil
from pathlib import Path

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
