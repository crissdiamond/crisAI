from __future__ import annotations

import importlib
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from crisai import registry as registry_module
from crisai.agents import factory as factory_module
from crisai.cli import prompt_contracts as prompt_contracts_module
from crisai.orchestration import retrieval_association_graph as graph_module
from crisai.orchestration import semantic_catalog as catalog_module
from crisai.orchestration.usage_cost import ModelPricing

_PLACEHOLDER_ENV_VALUES = {
    "your-openai-api-key",
    "your-gemini-api-key",
    "your-anthropic-api-key",
    "your-deepseek-api-key",
    "<your-key>",
}
_BOOLEAN_ENV_VARS = {
    "CRISAI_RETRIEVAL_CHECKPOINT_ENABLED",
    "CRISAI_TERMINAL_TITLE_ENABLED",
    "CRISAI_DETERMINISTIC_MCP_ADVISORY",
    "CRISAI_SESSION_MEMORY_TASK_DRIFT_NUDGE",
}
_BOOLEAN_ENV_VALUES = {"1", "0", "true", "false", "yes", "no", "on", "off"}
_TOKEN_CACHE_PATH_ENV_VARS = ("MS_TOKEN_CACHE_PATH", "MS_TOKEN_INFO_PATH")
_EXPECTED_TOKEN_DIR_MODE = 0o700
_EXPECTED_TOKEN_FILE_MODE = 0o600

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DoctorIssue:
    """A single diagnostic issue with an optional remediation hint."""

    message: str
    hint: str | None = None

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class DoctorResult:
    """Result of a local crisAI configuration health check."""

    ok: bool
    errors: tuple[DoctorIssue, ...]
    warnings: tuple[DoctorIssue, ...]
    info: tuple[str, ...] = ()


@dataclass(frozen=True)
class EnvValueSpec:
    """Validation rule for a local operator environment variable."""

    value_type: str
    minimum: int | float
    description: str
    inclusive: bool = True


_NUMERIC_ENV_VARS = {
    "CRISAI_AGENT_MAX_TURNS": EnvValueSpec("int", 1, "a positive integer"),
    "CRISAI_AGENT_STAGE_TIMEOUT_SECONDS": EnvValueSpec("float", 0, "a positive number of seconds", inclusive=False),
    "CRISAI_RETRIEVAL_CHECKPOINT_MAX_REDIRECTS": EnvValueSpec("int", 0, "a non-negative integer"),
    "CRISAI_MCP_CLIENT_TIMEOUT_SECONDS": EnvValueSpec("float", 10, "a number of seconds >= 10"),
    "CRISAI_SESSION_MEMORY_MAX_RECENT_TURNS": EnvValueSpec("int", 0, "a non-negative integer"),
    "CRISAI_SESSION_MEMORY_MAX_RUNTIME_CHARS": EnvValueSpec("int", 1000, "an integer >= 1000"),
    "CRISAI_SESSION_MEMORY_MAX_MEMORY_CHARS": EnvValueSpec("int", 500, "an integer >= 500"),
    "CRISAI_WORKSPACE_MAX_WRITE_BYTES": EnvValueSpec("int", 1024, "an integer >= 1024"),
    "CRISAI_DIAGRAM_MAX_WRITE_BYTES": EnvValueSpec("int", 1024, "an integer >= 1024"),
    "INTRANET_PAGE_CACHE_TTL_HOURS": EnvValueSpec("int", 1, "a positive integer"),
    "CRISAI_PEER_MAX_REFINEMENT_ROUNDS": EnvValueSpec("int", 0, "a non-negative integer"),
    "CRISAI_PEER_MAX_ESCALATIONS": EnvValueSpec("int", 0, "a non-negative integer"),
    "CRISAI_RATE_LIMIT_RPM": EnvValueSpec("int", 0, "a non-negative integer"),
    "CRISAI_PDF_VISION_MAX_PAGES": EnvValueSpec("int", 0, "a non-negative integer"),
}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required registry file: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _is_placeholder_env_value(value: str) -> bool:
    """Return True for values copied directly from .env.example."""
    stripped = value.strip().lower()
    return stripped in _PLACEHOLDER_ENV_VALUES or (
        stripped.startswith("your-") and stripped.endswith("-api-key")
    )


def _env_keys(path: Path, *, include_commented: bool = True) -> set[str]:
    """Extract active and commented dotenv-style assignment keys."""
    if not path.is_file():
        return set()
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            if not include_commented:
                continue
            stripped = stripped[1:].strip()
        if "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key and key.replace("_", "").isalnum() and not key[0].isdigit():
            keys.add(key)
    return keys


def _env_value_is_valid(raw: str, spec: EnvValueSpec) -> bool:
    """Return whether an environment value satisfies a numeric spec."""
    try:
        if spec.value_type == "int":
            value: int | float = int(raw)
        else:
            value = float(raw)
    except ValueError:
        return False
    if not spec.inclusive:
        return value > spec.minimum
    return value >= spec.minimum


def _operator_env_value_warnings() -> list[DoctorIssue]:
    """Validate first-run operator environment overrides."""
    warnings: list[DoctorIssue] = []
    for name in sorted(_BOOLEAN_ENV_VARS):
        raw = os.getenv(name)
        if raw is None or raw.strip().lower() in _BOOLEAN_ENV_VALUES:
            continue
        warnings.append(DoctorIssue(
            message=f"{name} should be true or false.",
            hint=f"Update `{name}` in `.env`, or remove it to use the default.",
        ))

    for name, spec in sorted(_NUMERIC_ENV_VARS.items()):
        raw = os.getenv(name)
        if raw is None or _env_value_is_valid(raw.strip(), spec):
            continue
        warnings.append(DoctorIssue(
            message=f"{name} should be {spec.description}.",
            hint=f"Update `{name}` in `.env`, or remove it to use the default.",
        ))
    return warnings


# ---------------------------------------------------------------------------
# Cross-reference validation
# ---------------------------------------------------------------------------


def _validate_unique_ids(
    items: list[Any],
    *,
    label: str,
    errors: list[DoctorIssue],
    registry_file: str,
) -> None:
    seen: set[str] = set()
    for item in items:
        item_id = getattr(item, "id", "")
        if not item_id:
            errors.append(DoctorIssue(
                message=f"{label} entry is missing id.",
                hint=f"Add an `id` field to the entry in `registry/{registry_file}`.",
            ))
            continue
        if item_id in seen:
            errors.append(DoctorIssue(
                message=f"Duplicate {label} id: {item_id}",
                hint=f"Rename one of the duplicate `{item_id}` entries in `registry/{registry_file}`.",
            ))
        seen.add(item_id)


def _validate_source_capability(
    server: registry_module.ServerSpec,
    allowed_tools: list[str],
    errors: list[DoctorIssue],
    warnings: list[DoctorIssue],
) -> None:
    """Validate the source capability contract (CRISAI-ADR-013) for one server."""
    if server.kind not in {"source", "tool"}:
        errors.append(DoctorIssue(
            message=f"Server '{server.id}' has invalid kind '{server.kind}'.",
            hint="Set `kind: source` or `kind: tool` in `registry/servers.yaml`.",
        ))
        return
    if server.kind == "tool":
        if server.capabilities is not None:
            warnings.append(DoctorIssue(
                message=f"Server '{server.id}' is kind 'tool' but declares a capabilities block.",
                hint="Remove `capabilities` from a tool server, or set `kind: source`.",
            ))
        return

    cap = server.capabilities
    if cap is None:
        errors.append(DoctorIssue(
            message=f"Source server '{server.id}' is missing a capabilities block.",
            hint="Add a `capabilities` block (see CRISAI-ADR-013) for source servers.",
        ))
        return

    allow = set(allowed_tools)
    sid = server.id
    if not cap.source_families:
        errors.append(DoctorIssue(
            message=f"Source server '{sid}' declares no source_families.",
            hint="List at least one source family this server serves.",
        ))
    for fam in cap.source_families:
        if fam not in registry_module.KNOWN_SOURCE_FAMILIES:
            errors.append(DoctorIssue(
                message=f"Server '{sid}' capability source_family '{fam}' is not recognised.",
                hint=f"Use one of: {', '.join(sorted(registry_module.KNOWN_SOURCE_FAMILIES))}.",
            ))
    for stype in cap.source_types:
        if stype not in registry_module.KNOWN_SOURCE_TYPES:
            errors.append(DoctorIssue(
                message=f"Server '{sid}' capability source_type '{stype}' is not recognised.",
                hint=f"Use one of: {', '.join(sorted(registry_module.KNOWN_SOURCE_TYPES))}.",
            ))
    for operation, tools in cap.operations.items():
        if operation not in registry_module.KNOWN_OPERATIONS:
            errors.append(DoctorIssue(
                message=f"Server '{sid}' capability operation '{operation}' is not recognised.",
                hint=f"Use one of: {', '.join(sorted(registry_module.KNOWN_OPERATIONS))}.",
            ))
        for tool in tools:
            if tool not in allow:
                errors.append(DoctorIssue(
                    message=f"Server '{sid}' capability operation '{operation}' references tool '{tool}' not in tools.allow.",
                    hint=f"Add `{tool}` to `tools.allow` for `{sid}`, or correct the capability.",
                ))
    for level in cap.evidence_levels:
        if level not in registry_module.KNOWN_EVIDENCE_LEVELS:
            errors.append(DoctorIssue(
                message=f"Server '{sid}' capability evidence_level '{level}' is not recognised.",
                hint=f"Use one of: {', '.join(sorted(registry_module.KNOWN_EVIDENCE_LEVELS))}.",
            ))
    if cap.reference_handle and cap.reference_handle not in registry_module.KNOWN_REFERENCE_HANDLES:
        errors.append(DoctorIssue(
            message=f"Server '{sid}' capability reference.handle '{cap.reference_handle}' is not recognised.",
            hint=f"Use one of: {', '.join(sorted(registry_module.KNOWN_REFERENCE_HANDLES))}.",
        ))
    if cap.reference_stability and cap.reference_stability not in registry_module.KNOWN_REFERENCE_STABILITY:
        errors.append(DoctorIssue(
            message=f"Server '{sid}' capability reference.stability '{cap.reference_stability}' is not recognised.",
            hint="Use `stable` or `session`.",
        ))
    for auth_tool in (cap.auth_login_tool, cap.auth_status_tool):
        if auth_tool and auth_tool not in allow:
            errors.append(DoctorIssue(
                message=f"Server '{sid}' capability auth tool '{auth_tool}' is not in tools.allow.",
                hint=f"Add `{auth_tool}` to `tools.allow` for `{sid}`.",
            ))


def _validate_registry_cross_references(root_dir: Path, registry_dir: Path) -> tuple[list[DoctorIssue], list[DoctorIssue]]:
    errors: list[DoctorIssue] = []
    warnings: list[DoctorIssue] = []
    registry = registry_module.Registry(registry_dir)

    try:
        servers = registry.load_servers()
    except Exception as exc:  # noqa: BLE001
        return [DoctorIssue(
            message=f"Could not load servers.yaml: {exc}",
            hint="Check `registry/servers.yaml` for YAML syntax errors.",
        )], warnings
    try:
        agents = registry.load_agents()
    except Exception as exc:  # noqa: BLE001
        return [DoctorIssue(
            message=f"Could not load agents.yaml: {exc}",
            hint="Check `registry/agents.yaml` for YAML syntax errors.",
        )], warnings
    try:
        models = registry.load_models()
    except Exception as exc:  # noqa: BLE001
        return [DoctorIssue(
            message=f"Could not load models.yaml: {exc}",
            hint="Check `registry/models.yaml` for YAML syntax errors.",
        )], warnings

    _validate_unique_ids(servers, label="server", errors=errors, registry_file="servers.yaml")
    _validate_unique_ids(agents, label="agent", errors=errors, registry_file="agents.yaml")
    _validate_unique_ids(models, label="model", errors=errors, registry_file="models.yaml")

    server_ids = {server.id for server in servers}
    model_ids = {model.id for model in models}
    _supported_transports = {"stdio", "sse", "streamable-http"}
    for server in servers:
        if server.transport not in _supported_transports:
            errors.append(DoctorIssue(
                message=f"Server '{server.id}' uses unsupported transport '{server.transport}'.",
                hint="Valid transports are `stdio`, `sse`, and `streamable-http`. Update `registry/servers.yaml`.",
            ))
        elif server.transport == "stdio":
            command = server.raw.get("command")
            if not command:
                errors.append(DoctorIssue(
                    message=f"Server '{server.id}' is missing command.",
                    hint=f"Add a `command` field to server `{server.id}` in `registry/servers.yaml`.",
                ))
            args = server.raw.get("args") or []
            if args:
                script_path = root_dir / str(args[0])
                if str(args[0]).endswith(".py") and not script_path.is_file():
                    errors.append(DoctorIssue(
                        message=f"Server '{server.id}' references missing script: {args[0]}",
                        hint=f"Ensure the script exists at `{args[0]}` or update `args` in `registry/servers.yaml`.",
                    ))
        else:
            url = server.raw.get("url")
            if not url or not isinstance(url, str) or not url.strip():
                errors.append(DoctorIssue(
                    message=f"Server '{server.id}' ({server.transport}) requires a non-empty 'url' field.",
                    hint=f"Add a `url` field to server `{server.id}` in `registry/servers.yaml`.",
                ))
            api_key_env = server.raw.get("api_key_env")
            if api_key_env and isinstance(api_key_env, str):
                key_value = os.getenv(api_key_env, "")
                if key_value and not _is_placeholder_env_value(key_value):
                    continue
                warnings.append(DoctorIssue(
                    message=f"Server '{server.id}' expects environment variable '{api_key_env}' to be set, but it is currently unset or a placeholder.",
                    hint=f"Add a real `{api_key_env}=<your-key>` value to your `.env` file.",
                ))
        tools_block = server.raw.get("tools", {}) or {}
        allowed_tools = tools_block.get("allow", [])
        if not isinstance(allowed_tools, list):
            errors.append(DoctorIssue(
                message=f"Server '{server.id}' tools.allow must be a list.",
                hint=f"Change `tools.allow` for server `{server.id}` in `registry/servers.yaml` to a YAML list.",
            ))
            continue
        # Internal tools are part of the capability contract but excluded from the
        # agent tool surface (they are not in tools.allow, so the static tool
        # filter hides them). Used by the deterministic materialisation path only.
        internal_tools = tools_block.get("internal", [])
        if not isinstance(internal_tools, list):
            errors.append(DoctorIssue(
                message=f"Server '{server.id}' tools.internal must be a list.",
                hint=f"Change `tools.internal` for server `{server.id}` in `registry/servers.yaml` to a YAML list.",
            ))
            continue
        overlap = sorted(set(allowed_tools) & set(internal_tools))
        if overlap:
            errors.append(DoctorIssue(
                message=(
                    f"Server '{server.id}' lists tool(s) in both tools.allow and tools.internal: "
                    f"{', '.join(overlap)}. An internal tool must not be agent-exposed."
                ),
                hint=f"Remove the tool(s) from one of the lists for server `{server.id}`.",
            ))
        for tool_name in sorted(prompt_contracts_module.PROMPT_CONTRACT_TOOL_REFERENCES.get(server.id, frozenset())):
            if tool_name not in allowed_tools:
                warnings.append(DoctorIssue(
                    message=(
                        f"Server '{server.id}' prompt contract references tool '{tool_name}' "
                        "but tools.allow does not expose it."
                    ),
                    hint=f"Add `{tool_name}` to `tools.allow` for server `{server.id}` in `registry/servers.yaml`.",
                ))
        if server.enabled:
            # Capability operations may reference agent-facing (allow) or internal tools.
            _validate_source_capability(server, allowed_tools + internal_tools, errors, warnings)

    for agent in agents:
        prompt_path = root_dir / agent.prompt_file
        if not prompt_path.is_file():
            errors.append(DoctorIssue(
                message=f"Agent '{agent.id}' references missing prompt file: {agent.prompt_file}",
                hint=f"Create `{agent.prompt_file}` or update `prompt_file` for agent `{agent.id}` in `registry/agents.yaml`.",
            ))
        if agent.model_ref and agent.model_ref not in model_ids:
            errors.append(DoctorIssue(
                message=f"Agent '{agent.id}' references unknown model_ref: {agent.model_ref}",
                hint=f"Add a model with `id: {agent.model_ref}` to `registry/models.yaml`, or correct the `model_ref` in `registry/agents.yaml`.",
            ))
        if not agent.model_ref and not agent.model:
            errors.append(DoctorIssue(
                message=f"Agent '{agent.id}' must define model_ref or legacy model.",
                hint=f"Add a `model_ref` pointing to a model id in `registry/models.yaml` for agent `{agent.id}` in `registry/agents.yaml`.",
            ))
        for server_id in agent.allowed_servers:
            if server_id not in server_ids:
                errors.append(DoctorIssue(
                    message=f"Agent '{agent.id}' references unknown server: {server_id}",
                    hint=f"Define server `{server_id}` in `registry/servers.yaml` or remove it from agent `{agent.id}` in `registry/agents.yaml`.",
                ))

    for model in models:
        if model.provider not in {"openai", "gemini", "anthropic", "deepseek"}:
            errors.append(DoctorIssue(
                message=f"Model '{model.id}' has unsupported provider: {model.provider}",
                hint="Valid providers are `openai`, `gemini`, `anthropic`, and `deepseek`. Update `registry/models.yaml`.",
            ))
        if model.api_key_env:
            key_value = os.getenv(model.api_key_env, "")
            if not key_value or _is_placeholder_env_value(key_value):
                warnings.append(DoctorIssue(
                    message=f"Model '{model.id}' expects environment variable '{model.api_key_env}' to be set, but it is currently unset or a placeholder.",
                    hint=f"Add a real `{model.api_key_env}=<your-key>` value to your `.env` file.",
                ))
        try:
            ModelPricing.from_mapping(model.extra.get("pricing"))
        except ValueError as exc:
            errors.append(DoctorIssue(
                message=f"Model '{model.id}' has invalid pricing metadata: {exc}",
                hint=(
                    "Use `pricing: {currency: USD, unit: per_1m_tokens, input: <rate>, output: <rate>}` "
                    "with optional non-negative `cached_input` and `reasoning` rates, or remove the pricing block."
                ),
            ))

    return errors, warnings


# ---------------------------------------------------------------------------
# File structure and semantic graph validation
# ---------------------------------------------------------------------------


def _validate_registry_files(registry_dir: Path) -> tuple[list[DoctorIssue], list[DoctorIssue], list[str]]:
    errors: list[DoctorIssue] = []
    warnings: list[DoctorIssue] = []
    info: list[str] = []
    required_files = (
        "agents.yaml",
        "servers.yaml",
        "models.yaml",
        "workflow_policy.yaml",
        "session_memory.yaml",
        "semantic_catalog.yaml",
        "semantic_graph.yaml",
    )
    for filename in required_files:
        path = registry_dir / filename
        try:
            payload = _read_yaml(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(DoctorIssue(
                message=str(exc),
                hint=f"Restore the file with `git checkout HEAD -- registry/{filename}` or recreate it from scratch.",
            ))
            continue
        if not isinstance(payload, dict):
            errors.append(DoctorIssue(
                message=f"{filename} must contain a YAML mapping.",
                hint=f"Open `registry/{filename}` and ensure the top-level value is a YAML mapping (`key: value`), not a list or scalar.",
            ))

    catalog = None
    try:
        catalog_module.load_semantic_catalog.cache_clear()
        catalog = catalog_module.load_semantic_catalog(str(registry_dir))
    except Exception as exc:  # noqa: BLE001
        errors.append(DoctorIssue(
            message=f"semantic_catalog.yaml is invalid: {exc}",
            hint="Check `registry/semantic_catalog.yaml` for YAML syntax errors and re-run `uv run crisai doctor`.",
        ))

    graph_path = registry_dir / "semantic_graph.yaml"
    graph = graph_module.load_retrieval_association_graph(registry_dir)
    if graph is None:
        if not graph_path.is_file():
            errors.append(DoctorIssue(
                message="semantic_graph.yaml is missing.",
                hint="Ensure `registry/semantic_graph.yaml` exists, then re-run `uv run crisai doctor`.",
            ))
        else:
            errors.append(DoctorIssue(
                message="semantic_graph.yaml is invalid (failed to parse or produced no vertices).",
                hint="Check `registry/semantic_graph.yaml` for YAML syntax errors and re-run `uv run crisai doctor`.",
            ))
    else:
        info.append(f"semantic_graph.yaml loaded ({len(graph.vertex_terms)} vertices)")
        if catalog is not None:
            function_words = catalog.lexicon.all_function_words
            for vertex_id, terms in sorted(graph.vertex_terms.items()):
                leaked_terms = sorted(term for term in terms if term in function_words)
                if leaked_terms:
                    errors.append(DoctorIssue(
                        message=(
                            "semantic_graph.yaml vertex "
                            f"'{vertex_id}' contains standalone function word term(s): "
                            + ", ".join(leaked_terms)
                        ),
                        hint=f"Remove {', '.join(f'`{t}`' for t in leaked_terms)} from the `terms` list of vertex `{vertex_id}` in `registry/semantic_graph.yaml`.",
                    ))

    workflow_policy = registry_dir / "workflow_policy.yaml"
    if workflow_policy.is_file():
        data = yaml.safe_load(workflow_policy.read_text(encoding="utf-8")) or {}
        if not isinstance(data.get("workflow_policy"), dict):
            errors.append(DoctorIssue(
                message="workflow_policy.yaml must contain top-level workflow_policy mapping.",
                hint="Add a top-level `workflow_policy:` mapping to `registry/workflow_policy.yaml`.",
            ))
    session_memory = registry_dir / "session_memory.yaml"
    if session_memory.is_file():
        data = yaml.safe_load(session_memory.read_text(encoding="utf-8")) or {}
        block = data.get("session_memory")
        if not isinstance(block, dict):
            errors.append(DoctorIssue(
                message="session_memory.yaml must contain top-level session_memory mapping.",
                hint="Add a top-level `session_memory:` mapping to `registry/session_memory.yaml`.",
            ))
        elif str(block.get("strategy") or "deterministic") not in {"deterministic", "agentic"}:
            errors.append(DoctorIssue(
                message="session_memory.strategy must be deterministic or agentic.",
                hint="Set `strategy: deterministic` or `strategy: agentic` in `registry/session_memory.yaml`.",
            ))
    return errors, warnings, info


# ---------------------------------------------------------------------------
# Environment and security hygiene
# ---------------------------------------------------------------------------


def _tracked_secret_like_paths(root_dir: Path) -> tuple[list[DoctorIssue], list[DoctorIssue]]:
    warnings: list[DoctorIssue] = []
    errors: list[DoctorIssue] = []
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
        warnings.append(DoctorIssue(
            message=f"Could not inspect tracked files for secret/cache hygiene: {exc}",
            hint="Ensure `git` is available and this directory is a valid git repository.",
        ))
        return errors, warnings
    risky_prefixes = (".auth/", ".tokens/", "workspace/.auth/", "workspace/.tokens/", "logs/")
    risky_tokens = ("token_cache", ".token")
    for line in result.stdout.splitlines():
        if line == ".env" or line.startswith(risky_prefixes) or any(token in line for token in risky_tokens):
            errors.append(DoctorIssue(
                message=f"Sensitive or runtime path is tracked by git: {line}",
                hint=f"Run `git rm --cached {line}` and add `{line}` to `.gitignore`.",
            ))
    return errors, warnings


def _configured_token_cache_path_warnings(root_dir: Path) -> list[DoctorIssue]:
    """Warn when explicit token-cache paths are placed under the workspace."""
    warnings: list[DoctorIssue] = []
    workspace_dir = Path(os.getenv("CRISAI_WORKSPACE_DIR", str(root_dir / "workspace"))).expanduser().resolve()
    for env_name in _TOKEN_CACHE_PATH_ENV_VARS:
        raw = os.getenv(env_name, "").strip()
        if not raw:
            continue
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = root_dir / path
        path = path.resolve()
        if path == workspace_dir or workspace_dir in path.parents:
            warnings.append(DoctorIssue(
                message=f"{env_name} points inside the workspace: {path}",
                hint=(
                    "Move Microsoft token cache files outside `workspace/`, or rely on the "
                    "agent/web sensitive-path deny policy until the cache path is relocated."
                ),
            ))
    return warnings


def _token_cache_candidate_paths(root_dir: Path) -> set[Path]:
    """Return token cache paths that doctor can inspect when they exist."""
    raw_candidates = {
        root_dir / ".auth" / "msal_token_cache.json",
        root_dir / ".auth" / "msal_token_info.json",
        root_dir / ".auth" / "sharepoint_token_cache.json",
        root_dir / ".auth" / "sharepoint_token_info.json",
        root_dir / ".auth" / "intranet_token_cache.json",
        root_dir / ".auth" / "intranet_token_info.json",
        root_dir / ".tokens" / "msal_token_cache.json",
        root_dir / ".tokens" / "msal_token_info.json",
        root_dir / ".tokens" / "sharepoint_token_cache.json",
        root_dir / ".tokens" / "sharepoint_token_info.json",
        root_dir / ".tokens" / "intranet_token_cache.json",
        root_dir / ".tokens" / "intranet_token_info.json",
    }
    for env_name in _TOKEN_CACHE_PATH_ENV_VARS:
        raw = os.getenv(env_name, "").strip()
        if raw:
            raw_candidates.add(Path(raw).expanduser())
    candidates: set[Path] = set()
    for raw_path in raw_candidates:
        path = raw_path.expanduser()
        if not path.is_absolute():
            path = root_dir / path
        candidates.add(path.resolve())
    return candidates


def _mode_too_broad(path: Path, expected_mode: int) -> bool:
    mode = stat.S_IMODE(path.stat().st_mode)
    return bool(mode & ~expected_mode)


def _token_cache_permission_warnings(root_dir: Path) -> list[DoctorIssue]:
    """Warn when existing Microsoft token cache files are group/world readable."""
    if os.name != "posix":
        return []

    warnings: list[DoctorIssue] = []
    checked_dirs: set[Path] = set()
    for path in _token_cache_candidate_paths(root_dir):
        if path.parent.exists() and path.parent not in checked_dirs:
            checked_dirs.add(path.parent)
            try:
                if _mode_too_broad(path.parent, _EXPECTED_TOKEN_DIR_MODE):
                    warnings.append(DoctorIssue(
                        message=f"Microsoft token cache directory is too permissive: {path.parent}",
                        hint=f"Restrict it with `chmod 700 {path.parent}`.",
                    ))
            except OSError as exc:
                warnings.append(DoctorIssue(
                    message=f"Could not inspect token cache directory permissions: {path.parent} ({exc})",
                    hint="Check local filesystem permissions and re-run `uv run crisai doctor`.",
                ))
        if not path.exists():
            continue
        try:
            if _mode_too_broad(path, _EXPECTED_TOKEN_FILE_MODE):
                warnings.append(DoctorIssue(
                    message=f"Microsoft token cache file is too permissive: {path}",
                    hint=f"Restrict it with `chmod 600 {path}`.",
                ))
        except OSError as exc:
            warnings.append(DoctorIssue(
                message=f"Could not inspect token cache file permissions: {path} ({exc})",
                hint="Check local filesystem permissions and re-run `uv run crisai doctor`.",
            ))
    return warnings


# ---------------------------------------------------------------------------
# Model dry-build validation
# ---------------------------------------------------------------------------


def _validate_model_dry_build(root_dir: Path, registry_dir: Path) -> tuple[list[DoctorIssue], list[DoctorIssue]]:
    """Dry-build configured agent models without opening tools or calling APIs."""
    errors: list[DoctorIssue] = []
    warnings: list[DoctorIssue] = []
    registry = registry_module.Registry(registry_dir)
    try:
        agents = registry.load_agents()
        models = registry.load_models()
    except Exception as exc:  # noqa: BLE001
        return [DoctorIssue(
            message=f"Could not load registry models/agents for model dry-build: {exc}",
            hint="Ensure `registry/agents.yaml` and `registry/models.yaml` are valid before running `--models`.",
        )], warnings

    try:
        factory = factory_module.AgentFactory(root_dir, model_specs=models)
    except Exception as exc:  # noqa: BLE001
        return [DoctorIssue(
            message=f"Could not initialise agent factory for model dry-build: {exc}",
            hint="Ensure all required packages are installed: `uv sync --extra litellm`.",
        )], warnings

    for agent in agents:
        if not (root_dir / agent.prompt_file).is_file():
            continue
        try:
            factory.build_agent(agent, mcp_servers=[])
        except Exception as exc:  # noqa: BLE001
            errors.append(DoctorIssue(
                message=f"Agent '{agent.id}' model dry-build failed: {exc}",
                hint=f"Check that the model constructor for agent `{agent.id}` is compatible with the SDK. Verify model fields in `registry/models.yaml`.",
            ))
    return errors, warnings


def _check_env_setup(root_dir: Path) -> tuple[list[DoctorIssue], list[DoctorIssue]]:
    """Check optional local environment setup."""
    errors: list[DoctorIssue] = []
    warnings: list[DoctorIssue] = []

    env_file = root_dir / ".env"
    env_example = root_dir / ".env.example"
    if not env_file.is_file():
        warnings.append(DoctorIssue(
            message=".env file not found; local dotenv values will not be loaded.",
            hint=(
                "Create one from the example if you rely on dotenv configuration: "
                "`cp .env.example .env`"
            ),
        ))
    else:
        expected_keys = _env_keys(env_example, include_commented=False)
        local_keys = _env_keys(env_file, include_commented=False)
        missing_keys = sorted(expected_keys - local_keys)
        if missing_keys:
            warnings.append(DoctorIssue(
                message=".env is missing key(s) present in .env.example: " + ", ".join(missing_keys),
                hint=(
                    "Add the missing key placeholders to `.env` without changing existing secrets, "
                    "or refresh from `.env.example`."
                ),
            ))

    if not os.getenv("CRISAI_API_KEY", "").strip():
        warnings.append(DoctorIssue(
            message="CRISAI_API_KEY is not set. All API endpoints are unprotected.",
            hint=(
                "Set `CRISAI_API_KEY=<random-secret>` in your `.env` file "
                "before exposing the server beyond localhost."
            ),
        ))

    strategy = os.getenv("CRISAI_SESSION_MEMORY_STRATEGY")
    if strategy and strategy.strip().lower() not in {"deterministic", "agentic"}:
        warnings.append(DoctorIssue(
            message="CRISAI_SESSION_MEMORY_STRATEGY has an unsupported value.",
            hint="Use `CRISAI_SESSION_MEMORY_STRATEGY=deterministic` or `CRISAI_SESSION_MEMORY_STRATEGY=agentic` in `.env`.",
        ))

    warnings.extend(_operator_env_value_warnings())

    return errors, warnings


def _read_pinned_python_version(path: Path) -> tuple[int, int] | None:
    """Return the (major, minor) pin from a `.python-version` file when parseable."""
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    # `.python-version` may hold entries like "3.13", "3.13.13", or
    # "cpython-3.13"; take the first dotted numeric major.minor pair.
    match = re.search(r"(\d+)\.(\d+)", raw)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _check_runtime_environment(root_dir: Path) -> tuple[list[DoctorIssue], list[DoctorIssue]]:
    """Check that the active interpreter and async backend are usable.

    A stale virtualenv whose Python no longer matches `.python-version` can carry
    a broken `anyio` install whose async backend fails to import. Because the web
    app's auth and rate-limit middleware are Starlette `BaseHTTPMiddleware`, which
    creates an `anyio` synchronisation primitive per request, that failure surfaces
    as a 500 on every request instead of at startup. Catch both signals here.
    """
    errors: list[DoctorIssue] = []
    warnings: list[DoctorIssue] = []

    active = (sys.version_info.major, sys.version_info.minor)
    pinned = _read_pinned_python_version(root_dir / ".python-version")
    if pinned and pinned != active:
        warnings.append(DoctorIssue(
            message=(
                f"Active interpreter is Python {active[0]}.{active[1]} but "
                f".python-version pins {pinned[0]}.{pinned[1]}; the virtualenv may be stale."
            ),
            hint="Rebuild the environment with `uv sync` so the venv matches `.python-version`.",
        ))

    try:
        importlib.import_module("anyio._backends._asyncio")
    except Exception as exc:  # noqa: BLE001 - report any import failure to the operator
        errors.append(DoctorIssue(
            message=(
                f"anyio asyncio backend failed to import ({type(exc).__name__}); the web server "
                "would return 500 on every request through its middleware."
            ),
            hint=(
                "Rebuild the virtualenv with `uv sync`. If the venv is stale, align it with "
                "`.python-version` first; do not run the server under an unsupported Python."
            ),
        ))

    return errors, warnings


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_doctor(root_dir: Path, registry_dir: Path, *, validate_models: bool = False) -> DoctorResult:
    """Validate the local crisAI registry, prompts, env references, and hygiene."""
    errors: list[DoctorIssue] = []
    warnings: list[DoctorIssue] = []
    info: list[str] = []

    setup_errors, setup_warnings = _check_env_setup(root_dir)
    errors.extend(setup_errors)
    warnings.extend(setup_warnings)

    runtime_errors, runtime_warnings = _check_runtime_environment(root_dir)
    errors.extend(runtime_errors)
    warnings.extend(runtime_warnings)

    file_errors, file_warnings, file_info = _validate_registry_files(registry_dir)
    errors.extend(file_errors)
    warnings.extend(file_warnings)
    info.extend(file_info)

    ref_errors, ref_warnings = _validate_registry_cross_references(root_dir, registry_dir)
    errors.extend(ref_errors)
    warnings.extend(ref_warnings)

    hygiene_errors, hygiene_warnings = _tracked_secret_like_paths(root_dir)
    errors.extend(hygiene_errors)
    warnings.extend(hygiene_warnings)
    warnings.extend(_configured_token_cache_path_warnings(root_dir))
    warnings.extend(_token_cache_permission_warnings(root_dir))

    if validate_models:
        model_errors, model_warnings = _validate_model_dry_build(root_dir, registry_dir)
        errors.extend(model_errors)
        warnings.extend(model_warnings)

    return DoctorResult(
        ok=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
        info=tuple(info),
    )
