from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True)
class Settings:
    openai_api_key: str
    default_model: str
    workspace_dir: Path
    log_dir: Path
    registry_dir: Path


def load_settings() -> Settings:
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
    )
