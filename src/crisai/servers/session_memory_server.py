from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from crisai.cli.chat_context import (
    build_session_context_package,
    recall_session_memory,
    serialize_session_context,
)
from crisai.cli.session_store import sanitize_session_name
from crisai.config import load_settings
from crisai.logging_utils import append_json_log_line, configure_mcp_framework_logging

mcp = FastMCP("crisai-session-memory")
ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
ACTIVE_SESSION_ENV = "CRISAI_SESSION_MEMORY_SESSION"


def _log_file() -> Path:
    return load_settings().log_dir / "session_memory_mcp.log"


def _configure_mcp_logging() -> None:
    configure_mcp_framework_logging(_log_file(), service_component="session_memory_mcp")


def log_event(message: str) -> None:
    append_json_log_line(
        _log_file(),
        message,
        logger_name="crisai.mcp.session_memory",
        service_component="session_memory_mcp",
    )


def _active_session() -> str:
    raw = os.getenv(ACTIVE_SESSION_ENV, "")
    if not raw.strip():
        raise PermissionError("Session memory MCP requires an active session scope.")
    return sanitize_session_name(raw)


def _enforce_active_session(session_name: str | None = None) -> str:
    active = _active_session()
    requested = sanitize_session_name(session_name or active)
    if requested != active:
        raise PermissionError("Session memory MCP is scoped to the active session only.")
    return active


@mcp.tool()
def get_session_context(query: str = "", max_results: int = 5) -> dict[str, Any]:
    """Return the active session baseline brief and optional deterministic recall."""
    session = _enforce_active_session()
    log_event(f"get_session_context session={session} query_chars={len(query or '')}")
    package = build_session_context_package(
        session,
        query=query,
        limit=max_results,
        registry_dir=ROOT / "registry",
    )
    return serialize_session_context(package)


@mcp.tool()
def recall_session_context(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Return relevant read-only recall hits from the active session memory."""
    session = _enforce_active_session()
    log_event(f"recall_session_context session={session} query_chars={len(query or '')}")
    results = recall_session_memory(
        session,
        query,
        limit=max_results,
        registry_dir=ROOT / "registry",
    )
    return [
        {
            "field": result.field,
            "content": result.content,
            "score": result.score,
            "provenance": result.provenance,
            "matched_terms": result.matched_terms,
        }
        for result in results
    ]


@mcp.tool()
def get_active_session_name() -> dict[str, str]:
    """Return the active session name for this scoped MCP process."""
    session = _active_session()
    log_event(f"get_active_session_name session={session}")
    return {"session": session}


if __name__ == "__main__":
    _configure_mcp_logging()
    log_event(f"session_memory_server_started root={ROOT}")
    mcp.run()
