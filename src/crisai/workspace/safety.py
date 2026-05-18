from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from pathlib import Path

from crisai.config import load_settings
from crisai.workspace.spaces import WorkspaceSpaces, load_workspace_spaces

SENSITIVE_PATH_PARTS = {
    ".auth",
    ".cache",
    ".crisai",
    ".secrets",
    ".tokens",
    "chat_sessions",
    "logs",
}
SENSITIVE_FILE_NAMES = {
    ".cli_history",
    ".env",
    ".env.local",
    ".envrc",
    "msal_token_cache.json",
    "msal_token_info.json",
}
SENSITIVE_PATH_ENV_VARS = (
    "MS_TOKEN_CACHE_PATH",
    "MS_TOKEN_INFO_PATH",
)


class WorkspacePathError(ValueError):
    """Base error for rejected workspace path resolution."""


class WorkspacePathEscapeError(WorkspacePathError):
    """Raised when a requested path resolves outside the workspace root."""


class SensitiveWorkspacePathError(WorkspacePathError):
    """Raised when a path points to sensitive local runtime state."""


def canonical_workspace_path(relative_path: str, *, spaces: WorkspaceSpaces | None = None) -> str:
    """Normalize workspace aliases without resolving against a filesystem root."""
    raw = (relative_path or ".").strip()
    if raw.startswith("/"):
        raw = raw.lstrip("/")
    active_spaces = spaces or load_workspace_spaces()
    return active_spaces.canonicalize_workspace_path(raw)


def resolve_workspace_path(
    root: Path,
    relative_path: str,
    *,
    spaces: WorkspaceSpaces | None = None,
) -> Path:
    """Resolve a workspace-relative path and enforce visibility restrictions."""
    raw = canonical_workspace_path(relative_path, spaces=spaces)
    root_resolved = root.resolve()
    candidate = (root_resolved / raw).resolve()

    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise WorkspacePathEscapeError(
            f"Path escapes the workspace root. root={root_resolved} requested={relative_path} resolved={candidate}"
        )

    assert_workspace_path_visible(candidate, root_resolved)
    return candidate


def assert_workspace_path_visible(path: Path, root: Path) -> None:
    """Reject workspace paths that expose local auth, cache, secret, or runtime state."""
    if is_sensitive_workspace_path(path, root):
        rel = _relative_to_root(path, root)
        raise SensitiveWorkspacePathError(f"Path is restricted because it points to sensitive workspace state: {rel}")


def is_sensitive_workspace_path(
    path: Path,
    root: Path,
    sensitive_paths: tuple[Path, ...] | None = None,
) -> bool:
    """Return whether a path is inside a sensitive workspace area."""
    root_resolved = root.resolve()
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path.absolute()

    if resolved != root_resolved and root_resolved not in resolved.parents:
        return True

    try:
        relative = resolved.relative_to(root_resolved)
    except ValueError:
        return True

    if any(part in SENSITIVE_PATH_PARTS for part in relative.parts):
        return True
    if relative.name in SENSITIVE_FILE_NAMES:
        return True

    configured_paths = sensitive_paths if sensitive_paths is not None else _configured_sensitive_paths(root_resolved)
    return any(_is_same_or_child(resolved, configured) for configured in configured_paths)


def iter_visible_workspace_files(
    base: Path,
    root: Path,
    *,
    predicate: Callable[[Path], bool] | None = None,
) -> Iterable[Path]:
    """Yield visible files under *base*, pruning restricted directories."""
    root_resolved = root.resolve()
    assert_workspace_path_visible(base, root_resolved)
    if not base.exists():
        return
    if base.is_file():
        if not is_sensitive_workspace_path(base, root_resolved) and (predicate is None or predicate(base)):
            yield base
        return

    for current_root, dirnames, filenames in os.walk(base):
        current = Path(current_root)
        if is_sensitive_workspace_path(current, root_resolved):
            dirnames[:] = []
            continue
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if not is_sensitive_workspace_path(current / dirname, root_resolved)
        ]
        for filename in filenames:
            file_path = current / filename
            if is_sensitive_workspace_path(file_path, root_resolved):
                continue
            if predicate is not None and not predicate(file_path):
                continue
            yield file_path


def _configured_sensitive_paths(root: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    try:
        settings = load_settings()
    except Exception:  # noqa: BLE001
        settings = None

    if settings is not None:
        paths.extend(_path_if_under_root(settings.log_dir, root))

    for env_name in SENSITIVE_PATH_ENV_VARS:
        raw = os.getenv(env_name)
        if raw:
            paths.extend(_path_if_under_root(Path(raw), root))

    return tuple(paths)


def _path_if_under_root(path: Path, root: Path) -> tuple[Path, ...]:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path.absolute()
    if resolved == root or root in resolved.parents:
        return (resolved,)
    return ()


def _is_same_or_child(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
