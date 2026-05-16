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
class KnowledgeCorpus:
    """A named knowledge corpus exposed to retrieval and write policy."""

    id: str
    label: str
    root: str
    role: str = "approved"
    access: str = "read"
    aliases: tuple[str, ...] = ()
    staging_root: str | None = None
    promotion_target: str | None = None
    retrieval_priority: int = 100
    validation_profile: str = "default"


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
    knowledge_corpora: tuple[KnowledgeCorpus, ...] = ()

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
        roots = (
            self.knowledge_root,
            self.knowledge_staging_root,
            self.tasks_root,
            *self.legacy_knowledge_roots,
            *self.legacy_knowledge_staging_roots,
        )
        for corpus in self.effective_knowledge_corpora():
            roots = (*roots, corpus.root, *corpus.aliases)
        return tuple(dict.fromkeys(root for root in roots if root))

    def effective_knowledge_corpora(self) -> tuple[KnowledgeCorpus, ...]:
        """Return configured corpora or defaults derived from root settings."""
        if self.knowledge_corpora:
            return self.knowledge_corpora
        return (
            KnowledgeCorpus(
                id="approved_knowledge",
                label="Approved knowledge corpus",
                root=self.knowledge_root,
                role="approved",
                access="read",
                aliases=self.legacy_knowledge_roots,
                staging_root=self.knowledge_staging_root,
                retrieval_priority=10,
            ),
            KnowledgeCorpus(
                id="staged_knowledge",
                label="Knowledge staging area",
                root=self.knowledge_staging_root,
                role="staging",
                access="read_write",
                aliases=self.legacy_knowledge_staging_roots,
                promotion_target=self.knowledge_root,
                retrieval_priority=50,
            ),
        )

    def canonical_root_for(self, root: str) -> str:
        """Return the current root for a root or legacy alias."""
        clean = str(root or "").strip().strip("/")
        if not clean:
            return clean
        for corpus in self.effective_knowledge_corpora():
            if clean == corpus.root or clean in corpus.aliases:
                return corpus.root
        if clean == self.knowledge_root or clean in self.legacy_knowledge_roots:
            return self.knowledge_root
        if clean == self.knowledge_staging_root or clean in self.legacy_knowledge_staging_roots:
            return self.knowledge_staging_root
        return clean

    def canonicalize_workspace_path(self, path: str) -> str:
        """Normalize a workspace-relative path to current configured roots."""
        clean = str(path or "").strip().strip("`").strip("/")
        if clean.startswith("workspace/"):
            clean = clean[len("workspace/") :]
        root, sep, tail = clean.partition("/")
        canonical_root = self.canonical_root_for(root)
        if not canonical_root:
            return clean
        return canonical_root + (sep + tail if sep else "")

    def prompt_path_guidance(self) -> str:
        """Return concise user-facing guidance for current knowledge paths."""
        return (
            f"Approved knowledge corpus: workspace/{self.knowledge_root}/. "
            f"Draft knowledge staging area: workspace/{self.knowledge_staging_root}/. "
            f"Task artefacts: workspace/{self.tasks_root}/<task>/artefacts/."
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


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _knowledge_corpora(value: Any) -> tuple[KnowledgeCorpus, ...]:
    if not isinstance(value, list):
        return ()
    corpora: list[KnowledgeCorpus] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        root = str(item.get("root") or "").strip().strip("/")
        corpus_id = str(item.get("id") or root).strip()
        if not root or not corpus_id:
            continue
        corpora.append(
            KnowledgeCorpus(
                id=corpus_id,
                label=str(item.get("label") or corpus_id).strip(),
                root=root,
                role=str(item.get("role") or "approved").strip(),
                access=str(item.get("access") or "read").strip(),
                aliases=_strings(item.get("aliases")),
                staging_root=str(item.get("staging_root")).strip().strip("/")
                if item.get("staging_root")
                else None,
                promotion_target=str(item.get("promotion_target")).strip().strip("/")
                if item.get("promotion_target")
                else None,
                retrieval_priority=_int(item.get("retrieval_priority"), 100),
                validation_profile=str(item.get("validation_profile") or "default").strip(),
            )
        )
    return tuple(corpora)


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
    knowledge_root = str(block.get("knowledge_root") or defaults.knowledge_root).strip().strip("/")
    knowledge_staging_root = str(block.get("knowledge_staging_root") or defaults.knowledge_staging_root).strip().strip("/")
    tasks_root = str(block.get("tasks_root") or defaults.tasks_root).strip().strip("/")
    writable = _strings(block.get("writable_roots")) or ("outputs", "scratch", knowledge_staging_root, tasks_root)
    return WorkspaceSpaces(
        knowledge_root=knowledge_root,
        knowledge_staging_root=knowledge_staging_root,
        tasks_root=tasks_root,
        legacy_knowledge_roots=_strings(block.get("legacy_knowledge_roots")) or defaults.legacy_knowledge_roots,
        legacy_knowledge_staging_roots=_strings(block.get("legacy_knowledge_staging_roots"))
        or defaults.legacy_knowledge_staging_roots,
        task_subdirs=task_subdirs,
        writable_roots=writable,
        knowledge_categories=_strings(block.get("knowledge_categories")),
        task_artefact_categories=_strings(block.get("task_artefact_categories")),
        enterprise_architecture_terms=_strings(block.get("enterprise_architecture_terms")),
        knowledge_corpora=_knowledge_corpora(block.get("knowledge_corpora")),
    )
