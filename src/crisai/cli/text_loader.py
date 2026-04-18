from __future__ import annotations

from pathlib import Path


def cli_text_dir() -> Path:
    return Path(__file__).resolve().parent / "text"


def load_cli_text(relative_path: str) -> str:
    path = cli_text_dir() / relative_path
    return path.read_text(encoding="utf-8")


def render_cli_text(relative_path: str, **context: str) -> str:
    template = load_cli_text(relative_path)
    return template.format(**context)
