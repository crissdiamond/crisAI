"""Declarative workspace space configuration.

The registry owns workspace semantics so runtime code does not hard-code where
knowledge, staged knowledge, and task artefacts live.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from crisai.config import load_settings

_REGISTRY_NAME = "workspace_spaces.yaml"


@dataclass(frozen=True, slots=True)
class WorkspaceSpaces:
    """Resolved workspace root names and task subdirectories."""

    knowledge_root: str = "knowledge"
    knowledge_staging_root: str = "knowledge_staging"
    tasks_root: str = "tasks"
    legacy_knowledge_roots: tuple[str, ...] = ("context",)
    legacy_knowledge_staging_roots: tuple[str, ...] = ("context_staging",)
    task_subdirs: dict[str, str] = field(
        default_factory=lambda: {
            "artefacts": "artefacts",
            "inputs": "inputs",
            "scratch": "scratch",
            "exports": "exports",
        }
    )
    writable_roots: tuple[str, ...] = ("outputs", "scratch", "knowledge_staging", "tasks")
    knowledge_categories: tuple[str, ...] = ()
    task_artefact_categories: tuple[str, ...] = ()
    enterprise_architecture_terms: tuple[str, ...] = ()

    @property
    def validation_roots(self) -> tuple[str, ...]:
        """Return repo-relative validation roots."""
        return (
            f"workspace/{self.knowledge_root}/",
            f"workspace/{self.knowledge_staging_root}/",
            f"workspace/{self.tasks_root}/",
        )

    def task_root(self, task_slug: str) -> str:
        """Return the workspace-relative root for a task."""
        return f"{self.tasks_root}/{task_slug}"

    def task_subdir(self, task_slug: str, key: str) -> str:
        """Return a workspace-relative task subdirectory."""
        subdir = self.task_subdirs.get(key, key)
        return f"{self.task_root(task_slug)}/{subdir}"

    def all_read_roots(self) -> tuple[str, ...]:
        """Return canonical and legacy roots that may contain retrievable text."""
        return (
            self.knowledge_root,
            self.knowledge_staging_root,
            self.tasks_root,
            *self.legacy_knowledge_roots,
            *self.legacy_knowledge_staging_roots,
        )


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip().strip("/") for item in value if str(item).strip())


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key).strip(): str(val).strip().strip("/")
        for key, val in value.items()
        if str(key).strip() and str(val).strip()
    }


def load_workspace_spaces(registry_dir: Path | None = None) -> WorkspaceSpaces:
    """Load workspace spaces from registry, falling back to sane defaults."""
    root = registry_dir or load_settings().registry_dir
    path = root / _REGISTRY_NAME
    if not path.is_file():
        return WorkspaceSpaces()
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return WorkspaceSpaces()
    block = payload.get("workspace_spaces") if isinstance(payload, dict) else {}
    if not isinstance(block, dict):
        return WorkspaceSpaces()
    defaults = WorkspaceSpaces()
    task_subdirs = dict(defaults.task_subdirs)
    task_subdirs.update(_string_map(block.get("task_subdirs")))
    writable = _strings(block.get("writable_roots")) or defaults.writable_roots
    return WorkspaceSpaces(
        knowledge_root=str(block.get("knowledge_root") or defaults.knowledge_root).strip().strip("/"),
        knowledge_staging_root=str(block.get("knowledge_staging_root") or defaults.knowledge_staging_root).strip().strip("/"),
        tasks_root=str(block.get("tasks_root") or defaults.tasks_root).strip().strip("/"),
        legacy_knowledge_roots=_strings(block.get("legacy_knowledge_roots")) or defaults.legacy_knowledge_roots,
        legacy_knowledge_staging_roots=_strings(block.get("legacy_knowledge_staging_roots"))
        or defaults.legacy_knowledge_staging_roots,
        task_subdirs=task_subdirs,
        writable_roots=writable,
        knowledge_categories=_strings(block.get("knowledge_categories")),
        task_artefact_categories=_strings(block.get("task_artefact_categories")),
        enterprise_architecture_terms=_strings(block.get("enterprise_architecture_terms")),
    )
