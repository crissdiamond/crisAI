from __future__ import annotations

import re
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from crisai.config import load_settings
from crisai.logging_utils import append_json_log_line, configure_mcp_framework_logging

mcp = FastMCP("crisai-workspace")
ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
ROOT.mkdir(parents=True, exist_ok=True)
LOG_FILE = load_settings().log_dir / "workspace_mcp.log"




def _configure_mcp_logging() -> None:
    """Keep MCP framework INFO logs out of the interactive CLI.

    Warnings and errors are still written to this server log file.
    """
    configure_mcp_framework_logging(LOG_FILE, service_component="workspace_mcp")


def log_event(message: str) -> None:
    append_json_log_line(
        LOG_FILE,
        message,
        logger_name="crisai.mcp.workspace",
        service_component="workspace_mcp",
    )


#def _safe_path(relative_path: str) -> Path:
#    candidate = (ROOT / relative_path).resolve()
#    if ROOT not in candidate.parents and candidate != ROOT:
#        raise ValueError("Path escapes the workspace root.")
#    return candidate


def _safe_path(relative_path: str) -> Path:
    raw = (relative_path or ".").strip()

    # normalise common model mistakes
    if raw.startswith("/"):
        raw = raw.lstrip("/")
    if raw.startswith("workspace/"):
        raw = raw[len("workspace/"):]

    candidate = (ROOT / raw).resolve()
    root = ROOT.resolve()

    if candidate != root and root not in candidate.parents:
        raise ValueError(
            f"Path escapes the workspace root. root={root} requested={relative_path} resolved={candidate}"
        )

    return candidate

_configure_mcp_logging()

log_event(f"workspace_server_started root={ROOT}")
log_event(f"server_started root={ROOT.resolve()}")

@mcp.tool()
def list_workspace_files(subdir: str = ".") -> list[str]:
    log_event(f"list_workspace_files subdir={subdir}")
    base = _safe_path(subdir)
    if not base.exists():
        return []
    return sorted(str(file_path.relative_to(ROOT)) for file_path in base.rglob("*") if file_path.is_file())


@mcp.tool()
def read_workspace_file(path: str) -> str:
    log_event(f"read_workspace_file path={path}")
    file_path = _safe_path(path)
    return file_path.read_text(encoding="utf-8")


@mcp.tool()
def write_workspace_file(path: str, content: str) -> str:
    log_event(f"write_workspace_file path={path} chars={len(content)}")
    file_path = _safe_path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return str(file_path.relative_to(ROOT))


@mcp.tool()
def append_workspace_file(path: str, content: str) -> str:
    log_event(f"append_workspace_file path={path} chars={len(content)}")
    file_path = _safe_path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as f:
        f.write(content)
    return str(file_path.relative_to(ROOT))


@mcp.tool()
def search_workspace_text(query: str, subdir: str = ".", max_hits: int = 20) -> list[dict[str, str | int]]:
    log_event(f"search_workspace_text query={query!r} subdir={subdir} max_hits={max_hits}")
    base = _safe_path(subdir)
    if not base.exists():
        return []
    results: list[dict[str, str | int]] = []
    pattern = re.compile(re.escape(query), flags=re.IGNORECASE)
    for file_path in base.rglob("*"):
        if not file_path.is_file():
            continue
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for idx, line in enumerate(lines, start=1):
            if pattern.search(line):
                results.append(
                    {
                        "path": str(file_path.relative_to(ROOT)),
                        "line": idx,
                        "text": line.strip(),
                        "file_uri": file_path.resolve().as_uri(),
                    }
                )
                if len(results) >= max_hits:
                    return results
    return results


@mcp.tool()
def workspace_file_link(path: str) -> dict[str, str]:
    """Return paths and a file:// URI so the user can open a workspace file locally.

    In user-facing markdown, use ``[basename](file_uri)`` so only the file name
    shows as link text and the URI appears only in the href (not as duplicated
    raw text).
    """
    log_event(f"workspace_file_link path={path}")
    file_path = _safe_path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"No such file: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"Not a file (directories are not supported): {file_path}")
    resolved = file_path.resolve()
    root_resolved = ROOT.resolve()
    return {
        "relative_path": str(resolved.relative_to(root_resolved)),
        "absolute_path": str(resolved),
        "file_uri": resolved.as_uri(),
    }


@mcp.tool()
def make_note_path(kind: str, slug: str) -> str:
    log_event(f"make_note_path kind={kind} slug={slug}")
    safe_slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", slug.strip()).strip("-").lower()
    safe_kind = re.sub(r"[^a-zA-Z0-9._-]+", "-", kind.strip()).strip("-").lower()
    return str(Path("outputs") / safe_kind / f"{safe_slug}.md")


if __name__ == "__main__":
    mcp.run()
