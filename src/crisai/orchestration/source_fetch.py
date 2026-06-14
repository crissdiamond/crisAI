"""Deterministic (non-agent) source fetch for workspace evidence materialisation.

Orchestration normally reaches MCP tools only through the agent loop. Materialising
a confirmed source (CRISAI-ADR-015 Phase 2b) needs to fetch its raw bytes itself,
without a model in the loop, so this module opens a short-lived MCP client session
to the source server and calls the internal ``read_binary`` download tool
(``download_source_bytes_by_handle``).

The download tool is in the server's ``tools.internal`` list, so it is invisible to
agents; this path builds the server with ``include_internal=True`` so it can call
it. The whole-file base64 returned by the tool is decoded here and never enters an
agent's context or a trace.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from crisai import registry

if TYPE_CHECKING:
    from crisai.runtime import RuntimeManager

DOWNLOAD_TOOL = "download_source_bytes_by_handle"


@dataclass(frozen=True, slots=True)
class FetchedSource:
    """Raw bytes and provider revision of a fetched source."""

    name: str
    suffix: str
    revision: str
    size: int
    raw_bytes: bytes

    @property
    def is_empty(self) -> bool:
        return not self.raw_bytes


class SourceFetchError(RuntimeError):
    """Raised when a deterministic source fetch fails."""


async def fetch_source_bytes(
    spec: registry.ServerSpec,
    read_handle: str,
    *,
    runtime: RuntimeManager,
    env_overrides: dict[str, str] | None = None,
) -> FetchedSource:
    """Fetch a source's raw bytes + revision via the internal download tool.

    Opens a short-lived MCP session to ``spec`` (with internal tools enabled),
    calls the download tool with ``read_handle``, and returns the decoded bytes.
    The session is closed before returning.
    """
    if not read_handle.strip():
        raise SourceFetchError("read_handle is required to fetch a source")
    server = runtime.build_server(spec, env_overrides=env_overrides, include_internal=True)
    try:
        async with server:
            result = await server.call_tool(DOWNLOAD_TOOL, {"read_handle": read_handle})
    except Exception as exc:  # noqa: BLE001 - surface a typed error to the caller
        raise SourceFetchError(f"source fetch failed for handle: {exc}") from exc

    if getattr(result, "isError", False):
        raise SourceFetchError(f"download tool reported an error for handle: {_result_text(result)[:200]}")

    payload = _result_payload(result)
    content_b64 = str(payload.get("content_base64") or "")
    try:
        raw = base64.b64decode(content_b64) if content_b64 else b""
    except (ValueError, TypeError) as exc:
        raise SourceFetchError(f"download tool returned undecodable content: {exc}") from exc

    return FetchedSource(
        name=str(payload.get("name") or ""),
        suffix=str(payload.get("suffix") or ""),
        revision=str(payload.get("revision") or ""),
        size=int(payload.get("size") or len(raw)),
        raw_bytes=raw,
    )


def _result_payload(result: Any) -> dict[str, Any]:
    """Extract the tool's dict payload from a CallToolResult.

    Prefers ``structuredContent`` (FastMCP serialises a dict return there); falls
    back to parsing the first JSON text content item.
    """
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    for item in getattr(result, "content", None) or []:
        text = getattr(item, "text", None)
        if not text:
            continue
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict):
            return data
    return {}


def _result_text(result: Any) -> str:
    parts = [getattr(item, "text", "") or "" for item in getattr(result, "content", None) or []]
    return " ".join(part for part in parts if part).strip()
