from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from crisai.orchestration.retrieval_association_graph import (
    load_retrieval_association_graph,
)
from crisai.orchestration.semantic_catalog import load_semantic_catalog
from crisai.registry import Registry


@dataclass(frozen=True)
class DoctorResult:
    """Result of a local crisAI configuration health check."""

    ok: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def _read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required registry file: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _validate_unique_ids(items: list[Any], *, label: str, errors: list[str]) -> None:
    seen: set[str] = set()
    for item in items:
        item_id = getattr(item, "id", "")
        if not item_id:
            errors.append(f"{label} entry is missing id.")
            continue
        if item_id in seen:
            errors.append(f"Duplicate {label} id: {item_id}")
        seen.add(item_id)


def _validate_registry_cross_references(root_dir: Path, registry_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    registry = Registry(registry_dir)

    try:
        servers = registry.load_servers()
    except Exception as exc:  # noqa: BLE001
        return [f"Could not load servers.yaml: {exc}"], warnings
    try:
        agents = registry.load_agents()
    except Exception as exc:  # noqa: BLE001
        return [f"Could not load agents.yaml: {exc}"], warnings
    try:
        models = registry.load_models()
    except Exception as exc:  # noqa: BLE001
        return [f"Could not load models.yaml: {exc}"], warnings

    _validate_unique_ids(servers, label="server", errors=errors)
    _validate_unique_ids(agents, label="agent", errors=errors)
    _validate_unique_ids(models, label="model", errors=errors)

    server_ids = {server.id for server in servers}
    model_ids = {model.id for model in models}
    for server in servers:
        if server.transport != "stdio":
            errors.append(f"Server '{server.id}' uses unsupported transport '{server.transport}'.")
        command = server.raw.get("command")
        if not command:
            errors.append(f"Server '{server.id}' is missing command.")
        args = server.raw.get("args") or []
        if args:
            script_path = root_dir / str(args[0])
            if str(args[0]).endswith(".py") and not script_path.is_file():
                errors.append(f"Server '{server.id}' references missing script: {args[0]}")
        allowed_tools = server.raw.get("tools", {}).get("allow", [])
        if not isinstance(allowed_tools, list):
            errors.append(f"Server '{server.id}' tools.allow must be a list.")

    for agent in agents:
        prompt_path = root_dir / agent.prompt_file
        if not prompt_path.is_file():
            errors.append(f"Agent '{agent.id}' references missing prompt file: {agent.prompt_file}")
        if agent.model_ref and agent.model_ref not in model_ids:
            errors.append(f"Agent '{agent.id}' references unknown model_ref: {agent.model_ref}")
        if not agent.model_ref and not agent.model:
            errors.append(f"Agent '{agent.id}' must define model_ref or legacy model.")
        for server_id in agent.allowed_servers:
            if server_id not in server_ids:
                errors.append(f"Agent '{agent.id}' references unknown server: {server_id}")

    for model in models:
        if model.provider not in {"openai", "gemini", "anthropic"}:
            errors.append(f"Model '{model.id}' has unsupported provider: {model.provider}")
        if model.api_key_env and not os.getenv(model.api_key_env, ""):
            warnings.append(f"Model '{model.id}' expects unset environment variable: {model.api_key_env}")

    return errors, warnings


def _validate_registry_files(registry_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    required_files = (
        "agents.yaml",
        "servers.yaml",
        "models.yaml",
        "workflow_policy.yaml",
        "semantic_catalog.yaml",
        "retrieval_association_graph.yaml",
    )
    for filename in required_files:
        path = registry_dir / filename
        try:
            payload = _read_yaml(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
            continue
        if not isinstance(payload, dict):
            errors.append(f"{filename} must contain a YAML mapping.")

    try:
        load_semantic_catalog.cache_clear()
        load_semantic_catalog(str(registry_dir))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"semantic_catalog.yaml is invalid: {exc}")

    if load_retrieval_association_graph(registry_dir) is None:
        errors.append("retrieval_association_graph.yaml is missing or invalid.")

    workflow_policy = registry_dir / "workflow_policy.yaml"
    if workflow_policy.is_file():
        data = yaml.safe_load(workflow_policy.read_text(encoding="utf-8")) or {}
        if not isinstance(data.get("workflow_policy"), dict):
            errors.append("workflow_policy.yaml must contain top-level workflow_policy mapping.")
    return errors, warnings


def _tracked_secret_like_paths(root_dir: Path) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    if not (root_dir / ".git").exists():
        return errors, warnings
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=root_dir,
            check=True,
            text=True,
            capture_output=True,
        )
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Could not inspect tracked files for secret/cache hygiene: {exc}")
        return errors, warnings
    risky_prefixes = (".auth/", "workspace/.auth/", "logs/")
    risky_tokens = ("token_cache", ".token")
    for line in result.stdout.splitlines():
        if line == ".env" or line.startswith(risky_prefixes) or any(token in line for token in risky_tokens):
            errors.append(f"Sensitive or runtime path is tracked by git: {line}")
    return errors, warnings


def run_doctor(root_dir: Path, registry_dir: Path) -> DoctorResult:
    """Validate the local crisAI registry, prompts, env references, and hygiene."""
    errors: list[str] = []
    warnings: list[str] = []

    file_errors, file_warnings = _validate_registry_files(registry_dir)
    errors.extend(file_errors)
    warnings.extend(file_warnings)

    ref_errors, ref_warnings = _validate_registry_cross_references(root_dir, registry_dir)
    errors.extend(ref_errors)
    warnings.extend(ref_warnings)

    hygiene_errors, hygiene_warnings = _tracked_secret_like_paths(root_dir)
    errors.extend(hygiene_errors)
    warnings.extend(hygiene_warnings)

    return DoctorResult(
        ok=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
