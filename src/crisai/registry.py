from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Source capability contract (CRISAI-ADR-013). Enforced enums for the v1 subset.
KNOWN_SOURCE_FAMILIES = frozenset({"personal_onedrive", "sharepoint", "intranet", "workspace"})
KNOWN_SOURCE_TYPES = frozenset({"file", "document", "slide", "page", "record"})
KNOWN_OPERATIONS = frozenset({"search", "list", "fetch", "read_binary"})
# Canonical source of evidence levels a source can declare as its ceiling.
# evidence_contract.ALLOWED_EVIDENCE_LEVELS is derived from this (plus read_failed).
KNOWN_EVIDENCE_LEVELS = frozenset({"search_hit_only", "metadata_read", "content_read"})
KNOWN_REFERENCE_HANDLES = frozenset({"workspace_path", "read_handle", "content_id", "open_url"})
KNOWN_REFERENCE_STABILITY = frozenset({"stable", "session"})


@dataclass(slots=True, frozen=True)
class SourceCapability:
    """Declared capabilities of a retrieval-source MCP server (servers.yaml)."""

    source_families: tuple[str, ...]
    source_types: tuple[str, ...]
    operations: dict[str, tuple[str, ...]]  # operation -> tools that perform it
    evidence_levels: tuple[str, ...]
    reference_handle: str
    reference_stability: str
    auth_login_tool: str
    auth_status_tool: str
    pagination: str
    freshness: str

    def all_operation_tools(self) -> tuple[str, ...]:
        """Every tool referenced by any operation, de-duplicated in order."""
        seen: list[str] = []
        for tools in self.operations.values():
            for tool in tools:
                if tool not in seen:
                    seen.append(tool)
        return tuple(seen)


def _parse_source_capability(item: dict[str, Any]) -> SourceCapability | None:
    cap = item.get("capabilities")
    if not isinstance(cap, dict):
        return None
    operations = {
        str(op): tuple(str(tool) for tool in (tools or []))
        for op, tools in (cap.get("operations") or {}).items()
    }
    reference = cap.get("reference") or {}
    auth = cap.get("auth") or {}
    return SourceCapability(
        source_families=tuple(str(x) for x in (cap.get("source_families") or [])),
        source_types=tuple(str(x) for x in (cap.get("source_types") or [])),
        operations=operations,
        evidence_levels=tuple(str(x) for x in (cap.get("evidence_levels") or [])),
        reference_handle=str(reference.get("handle") or ""),
        reference_stability=str(reference.get("stability") or ""),
        auth_login_tool=str(auth.get("interactive_login_tool") or ""),
        auth_status_tool=str(auth.get("status_tool") or ""),
        pagination=str(cap.get("pagination") or "none"),
        freshness=str(cap.get("freshness") or "none"),
    )


@dataclass(slots=True)
class ServerSpec:
    id: str
    name: str
    enabled: bool
    transport: str
    tags: list[str]
    raw: dict[str, Any]
    kind: str = "tool"  # "source" (retrieval adapter) or "tool" (utility)
    capabilities: SourceCapability | None = None


@dataclass(slots=True)
class ModelSpec:
    """Model catalogue entry loaded from registry/models.yaml."""

    id: str
    provider: str
    model_name: str
    api_key_env: str | None = None
    base_url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentSpec:
    id: str
    name: str
    prompt_file: str
    allowed_servers: list[str]
    model_ref: str | None = None
    model: str | None = None

    @property
    def display_model(self) -> str:
        """Returns the user-facing model label for CLI views."""
        return self.model_ref or self.model or "-"


class Registry:
    def __init__(self, registry_dir: Path) -> None:
        self.registry_dir = registry_dir

    def load_servers(self) -> list[ServerSpec]:
        path = self.registry_dir / "servers.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return [
            ServerSpec(
                id=item["id"],
                name=item["name"],
                enabled=item.get("enabled", True),
                transport=item["transport"],
                tags=item.get("tags", []),
                raw=item,
                kind=str(item.get("kind", "tool")),
                capabilities=_parse_source_capability(item),
            )
            for item in data.get("servers", [])
        ]

    def load_models(self) -> list[ModelSpec]:
        path = self.registry_dir / "models.yaml"
        if not path.exists():
            return []

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return [
            ModelSpec(
                id=item["id"],
                provider=item["provider"],
                model_name=item["model_name"],
                api_key_env=item.get("api_key_env"),
                base_url=item.get("base_url"),
                extra={
                    key: value
                    for key, value in item.items()
                    if key not in {"id", "provider", "model_name", "api_key_env", "base_url"}
                },
            )
            for item in data.get("models", [])
        ]

    def load_agents(self) -> list[AgentSpec]:
        path = self.registry_dir / "agents.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return [
            AgentSpec(
                id=item["id"],
                name=item["name"],
                prompt_file=item["prompt_file"],
                allowed_servers=item.get("allowed_servers", []),
                model_ref=item.get("model_ref"),
                model=item.get("model"),
            )
            for item in data.get("agents", [])
        ]
