from __future__ import annotations

from contextlib import AsyncExitStack
from pathlib import Path

from agents.mcp import MCPServerStdio, create_static_tool_filter

from .registry import ServerSpec


class RuntimeManager:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    def build_server(self, spec: ServerSpec):
        if spec.transport == "stdio":
            command = spec.raw["command"]
            args = spec.raw.get("args", [])
            allowed_tools = spec.raw.get("tools", {}).get("allow", [])
            return MCPServerStdio(
                name=spec.name,
                params={
                    "command": command,
                    "args": args,
                    "cwd": str(self.root_dir),
                },
                tool_filter=create_static_tool_filter(allowed_tool_names=allowed_tools),
            )
        raise NotImplementedError(f"Transport not yet supported: {spec.transport}")


class MultiServerContext:
    def __init__(self, servers: list) -> None:
        self.servers = servers
        self.stack = AsyncExitStack()

    async def __aenter__(self):
        active = []
        for server in self.servers:
            active.append(await self.stack.enter_async_context(server))
        return active

    async def __aexit__(self, exc_type, exc, tb):
        return await self.stack.__aexit__(exc_type, exc, tb)
