from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True)
class GeneralSettings:
    log_level: str = "INFO"
    workspace_dir: Path = Path("workspace")
    log_dir: Path = Path("logs")
    registry_dir: Path = Path("registry")
    root_dir: Path = Path(".")


@dataclass(slots=True)
class UISettings:
    verbose: bool = False
    retrieval_checkpoint_enabled: bool = True
    theme: str = "default"
    cli_experience: str = "fullscreen"


@dataclass(slots=True)
class ModelSettings:
    openai_api_key: str = ""
    default_model: str = "gpt-5.4-mini"


@dataclass(slots=True)
class WorkflowSettings:
    retrieval_checkpoint_max_redirects: int = 2


@dataclass(slots=True)
class Settings:
    """Application settings with hierarchical structure and backward compatibility."""
    general: GeneralSettings = field(default_factory=GeneralSettings)
    ui: UISettings = field(default_factory=UISettings)
    model: ModelSettings = field(default_factory=ModelSettings)
    workflow: WorkflowSettings = field(default_factory=WorkflowSettings)

    @property
    def openai_api_key(self) -> str:
        return self.model.openai_api_key

    @property
    def default_model(self) -> str:
        return self.model.default_model

    @property
    def workspace_dir(self) -> Path:
        return self.general.workspace_dir

    @property
    def log_dir(self) -> Path:
        return self.general.log_dir

    @property
    def registry_dir(self) -> Path:
        return self.general.registry_dir

    @property
    def root_dir(self) -> Path:
        return self.general.root_dir

    @property
    def log_level(self) -> str:
        return self.general.log_level

    @property
    def retrieval_checkpoint_enabled(self) -> bool:
        return self.ui.retrieval_checkpoint_enabled

    @property
    def retrieval_checkpoint_max_redirects(self) -> int:
        return self.workflow.retrieval_checkpoint_max_redirects


def _env_bool(name: str, default: bool) -> bool:
    """Return a boolean environment setting using common truthy/falsy values."""
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _env_positive_int(name: str, default: int) -> int:
    """Return a positive integer environment setting, or the default."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _load_from_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


SettingsData = dict[str, dict[str, Any]]


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> None:
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _merge_dict(base[k], v)
        else:
            base[k] = v


def load_settings() -> Settings:
    """Load settings from multiple sources with hierarchical precedence.

    Precedence (highest first):
    1. Environment variables (e.g. ``CRISAI_LOG_LEVEL``, ``OPENAI_API_KEY``)
    2. Local project settings (``./.crisai/settings.json``)
    3. Global user settings (``~/.crisai/settings.json``)
    4. Defaults
    """
    root = Path(__file__).resolve().parents[2]

    # Start with defaults
    data: SettingsData = {
        "general": {
            "log_level": "INFO",
            "workspace_dir": str(root / "workspace"),
            "log_dir": str(root / "logs"),
            "registry_dir": str(root / "registry"),
            "root_dir": str(root),
        },
        "ui": {
            "verbose": False,
            "retrieval_checkpoint_enabled": True,
            "theme": "default",
            "cli_experience": "fullscreen",
        },
        "model": {
            "openai_api_key": "",
            "default_model": "gpt-5.4-mini",
        },
        "workflow": {
            "retrieval_checkpoint_max_redirects": 2,
        },
    }

    # Load global settings
    global_path = Path.home() / ".crisai" / "settings.json"
    _merge_dict(data, _load_from_json(global_path))

    # Load project settings
    project_path = root / ".crisai" / "settings.json"
    _merge_dict(data, _load_from_json(project_path))

    # Apply environment overrides (highest precedence)
    env_map = {
        "CRISAI_LOG_LEVEL": ("general", "log_level"),
        "CRISAI_WORKSPACE_DIR": ("general", "workspace_dir"),
        "CRISAI_LOG_DIR": ("general", "log_dir"),
        "CRISAI_REGISTRY_DIR": ("general", "registry_dir"),
        "OPENAI_API_KEY": ("model", "openai_api_key"),
        "CRISAI_DEFAULT_MODEL": ("model", "default_model"),
        "CRISAI_RETRIEVAL_CHECKPOINT_ENABLED": ("ui", "retrieval_checkpoint_enabled"),
        "CRISAI_RETRIEVAL_CHECKPOINT_MAX_REDIRECTS": ("workflow", "retrieval_checkpoint_max_redirects"),
        "CRISAI_VERBOSE": ("ui", "verbose"),
        "CRISAI_THEME": ("ui", "theme"),
        "CRISAI_CLI_EXPERIENCE": ("ui", "cli_experience"),
    }

    for env_var, (section, key) in env_map.items():
        val = os.getenv(env_var)
        if val is not None:
            if isinstance(data[section][key], bool):
                data[section][key] = _env_bool(env_var, data[section][key])
            elif isinstance(data[section][key], int):
                data[section][key] = _env_positive_int(env_var, data[section][key])
            else:
                data[section][key] = val

    # Finalize directories and create them
    workspace_dir = Path(data["general"]["workspace_dir"]).resolve()
    log_dir = Path(data["general"]["log_dir"]).resolve()
    registry_dir = Path(data["general"]["registry_dir"]).resolve()

    workspace_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    registry_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        general=GeneralSettings(
            log_level=data["general"]["log_level"],
            workspace_dir=workspace_dir,
            log_dir=log_dir,
            registry_dir=registry_dir,
            root_dir=root,
        ),
        ui=UISettings(
            verbose=data["ui"]["verbose"],
            retrieval_checkpoint_enabled=data["ui"]["retrieval_checkpoint_enabled"],
            theme=data["ui"]["theme"],
            cli_experience=data["ui"].get("cli_experience", "fullscreen"),
        ),
        model=ModelSettings(
            openai_api_key=data["model"]["openai_api_key"],
            default_model=data["model"]["default_model"],
        ),
        workflow=WorkflowSettings(
            retrieval_checkpoint_max_redirects=data["workflow"]["retrieval_checkpoint_max_redirects"],
        ),
    )
