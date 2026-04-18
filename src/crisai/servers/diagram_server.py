from __future__ import annotations

import logging
import re
import sys
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("crisai-diagrams")
ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
ROOT.mkdir(parents=True, exist_ok=True)
LOG_FILE = ROOT / "diagram_mcp.log"




def _configure_mcp_logging() -> None:
    """Keep MCP framework INFO logs out of the interactive CLI.

    Warnings and errors are still written to this server log file.
    """
    logger_names = [
        "mcp",
        "mcp.server",
        "mcp.server.fastmcp",
        "mcp.server.lowlevel",
        "mcp.server.lowlevel.server",
    ]

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(formatter)

    for name in logger_names:
        logger = logging.getLogger(name)
        logger.setLevel(logging.WARNING)
        logger.handlers.clear()
        logger.addHandler(file_handler)
        logger.propagate = False

def log_event(message: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} {message}\n")


def _slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-").lower()


_configure_mcp_logging()

log_event(f"diagram_server_started root={ROOT}")


@mcp.tool()
def generate_mermaid(kind: str, subject: str, notes: str = "") -> str:
    log_event(f"generate_mermaid kind={kind} subject={subject}")
    label = subject.replace('"', "'")
    if kind.lower() in {"flow", "flowchart"}:
        return f"flowchart TD\n    A[Start] --> B[{label}]\n    B --> C[Outcome]"
    if kind.lower() in {"sequence"}:
        return f"sequenceDiagram\n    participant U as User\n    participant S as System\n    U->>S: Request about {label}\n    S-->>U: Response"
    return f"flowchart TD\n    A[{label}] --> B[Detail]\n    B --> C[Next step]\n"


@mcp.tool()
def validate_mermaid(content: str) -> dict[str, str | bool]:
    log_event(f"validate_mermaid chars={len(content)}")
    valid_prefixes = ("flowchart", "sequenceDiagram", "classDiagram", "graph")
    is_valid = content.strip().startswith(valid_prefixes)
    return {
        "valid": is_valid,
        "message": "Looks like Mermaid content." if is_valid else "Content does not start with a recognised Mermaid diagram keyword.",
    }


@mcp.tool()
def save_diagram(filename: str, content: str, subdir: str = "outputs/diagrams") -> str:
    log_event(f"save_diagram filename={filename} subdir={subdir} chars={len(content)}")
    safe_name = _slugify(filename)
    if not safe_name.endswith(".mmd"):
        safe_name += ".mmd"
    target_dir = (ROOT / subdir).resolve()
    if ROOT not in target_dir.parents and target_dir != ROOT:
        raise ValueError("Path escapes the workspace root.")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / safe_name
    target.write_text(content, encoding="utf-8")
    return str(target.relative_to(ROOT))


if __name__ == "__main__":
    mcp.run()
