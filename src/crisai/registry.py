from __future__ import annotations

from dataclasses import dataclass
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
class AgentSpec:
    id: str
    name: str
    model: str
    prompt_file: str
    allowed_servers: list[str]


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

    def load_agents(self) -> list[AgentSpec]:
        path = self.registry_dir / "agents.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return [
            AgentSpec(
                id=item["id"],
                name=item["name"],
                model=item["model"],
                prompt_file=item["prompt_file"],
                allowed_servers=item.get("allowed_servers", []),
            )
            for item in data.get("agents", [])
        ]
