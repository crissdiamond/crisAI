from __future__ import annotations

from pathlib import Path

from agents import Agent

from crisai.registry import AgentSpec


class AgentFactory:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    def load_prompt(self, relative_path: str) -> str:
        return (self.root_dir / relative_path).read_text(encoding="utf-8")

    def build_agent(self, spec: AgentSpec, mcp_servers: list) -> Agent:
        return Agent(
            name=spec.name,
            instructions=self.load_prompt(spec.prompt_file),
            model=spec.model,
            mcp_servers=mcp_servers,
        )
