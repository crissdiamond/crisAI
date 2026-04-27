from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True)
class Settings:
    """Application settings loaded from environment variables and defaults.

    Attributes:
        openai_api_key: OpenAI API key.
        default_model: Default model identifier for LLM calls.
        workspace_dir: Directory for persistent workspace files.
        log_dir: Directory for log and trace output.
        registry_dir: Directory containing YAML agent/server/policy definitions.
        root_dir: Resolved project root directory (3 levels above this file).
        log_level: Logging level (e.g. DEBUG, INFO, WARNING).
    """
    openai_api_key: str
    default_model: str
    workspace_dir: Path
    log_dir: Path
    registry_dir: Path
    root_dir: Path
    log_level: str


def load_settings() -> Settings:
    """Load settings from environment variables with sensible defaults.

    The project root is resolved relative to this file's location
    (three directories up).  Default directories ``workspace`` (your files),
    ``logs`` (app trace, crisai.log, MCP server logs), and ``registry`` (YAML)
    can be overridden via environment variables and are created if they
    do not exist.

    Returns:
        A fully populated Settings instance.
    """
    root = Path(__file__).resolve().parents[2]
    workspace_dir = Path(os.getenv("CRISAI_WORKSPACE_DIR", root / "workspace")).resolve()
    log_dir = Path(os.getenv("CRISAI_LOG_DIR", root / "logs")).resolve()
    registry_dir = Path(os.getenv("CRISAI_REGISTRY_DIR", root / "registry")).resolve()

    workspace_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    registry_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        default_model=os.getenv("CRISAI_DEFAULT_MODEL", "gpt-5.4-mini"),
        workspace_dir=workspace_dir,
        log_dir=log_dir,
        registry_dir=registry_dir,
        root_dir=root,
        log_level=os.getenv("CRISAI_LOG_LEVEL", "INFO"),
    )
