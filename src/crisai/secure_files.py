"""Helpers for local files that may contain credentials or tokens."""

from __future__ import annotations

import os
from pathlib import Path

SECURE_DIR_MODE = 0o700
SECURE_FILE_MODE = 0o600
_DEDICATED_SECRET_DIR_NAMES = {".auth", ".tokens", "auth", "tokens"}


def _supports_posix_modes() -> bool:
    return os.name == "posix"


def _is_dedicated_secret_dir(path: Path) -> bool:
    return path.name in _DEDICATED_SECRET_DIR_NAMES


def ensure_secure_directory(path: Path, *, harden_existing: bool = False) -> None:
    """Create *path* and restrict it to the current user on POSIX systems."""
    path.mkdir(parents=True, exist_ok=True)
    if _supports_posix_modes() and (harden_existing or _is_dedicated_secret_dir(path)):
        path.chmod(SECURE_DIR_MODE)


def ensure_secure_parent_for_file(path: Path) -> None:
    """Create the parent directory for a sensitive file with safe permissions."""
    existed = path.parent.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not _supports_posix_modes():
        return
    if not existed or _is_dedicated_secret_dir(path.parent):
        path.parent.chmod(SECURE_DIR_MODE)


def write_secure_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Write a sensitive text file and restrict it to the current user."""
    ensure_secure_parent_for_file(path)
    path.write_text(content, encoding=encoding)
    if _supports_posix_modes():
        path.chmod(SECURE_FILE_MODE)
