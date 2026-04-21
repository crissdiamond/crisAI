from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class ServerSpec:
    id: str
    name: str
    enabled: bool
    transport: str
    tags: list[str]
    raw: dict[str, Any]


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
