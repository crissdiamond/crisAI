from __future__ import annotations

import os
from contextlib import AsyncExitStack
from pathlib import Path

from agents.mcp import (
    MCPServerSse,
    MCPServerStdio,
    MCPServerStreamableHttp,
    create_static_tool_filter,
)

from .registry import ServerSpec


def _mcp_client_session_timeout_seconds() -> float:
    """Return MCP ClientSession timeout for list_tools and tool calls (seconds).

    The OpenAI Agents SDK defaults to 5s, which is often too short for stdio
    servers that import heavy stacks (for example SharePoint + MSAL) before
    responding to the first ``list_tools`` request.
    """
    raw = os.getenv("CRISAI_MCP_CLIENT_TIMEOUT_SECONDS", "60")
    try:
        value = float(raw)
    except ValueError:
        return 60.0
    return max(value, 10.0)


def _resolve_client_session_timeout_seconds(server_raw: dict[str, object]) -> float:
    """Resolve MCP session timeout with optional per-server override.

    A global default works for fast MCP servers, but interactive auth flows
    (for example delegated Microsoft login) may legitimately exceed 60s while
    the user completes browser consent. Servers can opt into a longer timeout
    by setting ``client_timeout_seconds`` in ``registry/servers.yaml``.
    """
    default_timeout = _mcp_client_session_timeout_seconds()
    override = server_raw.get("client_timeout_seconds")
    if override is None:
        return default_timeout
    try:
        return max(float(str(override)), 10.0)
    except (TypeError, ValueError):
        return default_timeout


def _resolve_headers(raw: dict[str, object]) -> dict[str, str]:
    """Build HTTP headers for SSE/Streamable-HTTP servers.

    If ``api_key_env`` names an env var, its value is injected as
    ``Authorization: Bearer <value>``. Literal ``headers`` from the spec
    are merged on top and win on collision.
    """
    merged: dict[str, str] = {}
    api_key_env = raw.get("api_key_env")
    if api_key_env and isinstance(api_key_env, str):
        key_value = os.getenv(api_key_env, "")
        if key_value:
            merged["Authorization"] = f"Bearer {key_value}"
    literal = raw.get("headers") or {}
    if isinstance(literal, dict):
        merged.update({str(k): str(v) for k, v in literal.items()})
    return merged


class RuntimeManager:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    def build_server(self, spec: ServerSpec):
        allowed_tools = spec.raw.get("tools", {}).get("allow", [])
        timeout = _resolve_client_session_timeout_seconds(spec.raw)
        tool_filter = create_static_tool_filter(allowed_tool_names=allowed_tools)

        if spec.transport == "stdio":
            return MCPServerStdio(
                name=spec.name,
                params={
                    "command": spec.raw["command"],
                    "args": spec.raw.get("args", []),
                    "cwd": str(self.root_dir),
                },
                client_session_timeout_seconds=timeout,
                tool_filter=tool_filter,
            )

        if spec.transport == "sse":
            return MCPServerSse(
                name=spec.name,
                params={"url": spec.raw["url"], "headers": _resolve_headers(spec.raw)},
                client_session_timeout_seconds=timeout,
                tool_filter=tool_filter,
            )

        if spec.transport == "streamable-http":
            return MCPServerStreamableHttp(
                name=spec.name,
                params={"url": spec.raw["url"], "headers": _resolve_headers(spec.raw)},
                client_session_timeout_seconds=timeout,
                tool_filter=tool_filter,
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
