"""Registry-driven Markdown validation under ``workspace/context*``.

Profiles are declared in ``registry/workspace_artifact_profiles.yaml``. The verifier
computes canonical ``type`` values from front matter plus optional aliases, resolves
the first matching profile, then applies structural checks (YAML fields, headings).
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import yaml

_ARTEFACT_REGISTRY_NAME = "workspace_artifact_profiles.yaml"
_INTEGRATION_PATTERN_SLUG = re.compile(
    r"^(?P<fam>consumer|producer|ingestion)-pattern-(?P<num>\d+)-",
    re.IGNORECASE,
)


def _norm_path_sep(rel: str) -> str:
    return rel.replace("\\", "/")


def _path_has_prefix(rel_posix: str, prefix: str) -> bool:
    """True when ``rel_posix`` is exactly the prefix path or a child of it.

    Uses path segments so ``workspace/context`` does not match
    ``workspace/context_staging``.
    """
    prefix_norm = _norm_path_sep(prefix.strip().strip("/"))
    path_norm = _norm_path_sep(rel_posix.strip().strip("/"))
    p_parts = [p for p in path_norm.split("/") if p]
    pre_parts = [p for p in prefix_norm.split("/") if p]
    if not pre_parts:
        return True
    if len(p_parts) < len(pre_parts):
        return False
    return p_parts[: len(pre_parts)] == pre_parts


def _parse_front_matter(raw: str) -> tuple[dict[str, Any], str]:
    """Split YAML front matter from markdown body.

    Args:
        raw: Full file text.

    Returns:
        Tuple of (metadata dict, body text). Malformed front matter yields ({}, raw).
    """
    if not raw.startswith("---"):
        return {}, raw
    close = raw.find("\n---\n", 3)
    if close == -1:
        return {}, raw
    block = raw[3:close]
    body = raw[close + 5 :]
    try:
        meta = yaml.safe_load(block) or {}
    except yaml.YAMLError:
        return {}, raw
    if not isinstance(meta, dict):
        return {}, raw
    return meta, body


def _h2_titles(body: str) -> list[str]:
    titles: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("### "):
            titles.append(stripped[3:].strip())
    return titles


def _has_h2_section(body: str, title: str) -> bool:
    want = title.strip().lower()
    for t in _h2_titles(body):
        if t.lower() == want:
            return True
    return False


def _non_empty_scalar(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _glob_match(rel_posix: str, pattern: str) -> bool:
    rel_posix = _norm_path_sep(rel_posix)
    pattern = _norm_path_sep(pattern)
    return fnmatch.fnmatch(rel_posix, pattern) or fnmatch.fnmatch(
        rel_posix.lower(), pattern.lower()
    )


def _canonical_type(raw_type: str | None, aliases: Mapping[str, list[str]]) -> str:
    if not raw_type or not isinstance(raw_type, str):
        return ""
    direct = raw_type.strip().lower().replace(" ", "_").replace("-", "_")
    if not direct:
        return ""
    for canonical, forms in aliases.items():
        bucket = {canonical.lower()}
        for form in forms:
            bucket.add(
                str(form).strip().lower().replace(" ", "_").replace("-", "_")
            )
        if direct in bucket:
            return canonical.lower()
    return direct


@dataclass(frozen=True)
class ArtefactProfileConfig:
    """Loaded representation of ``workspace_artifact_profiles.yaml``."""

    validate_path_prefixes: tuple[str, ...]
    defaults: dict[str, Any]
    type_aliases: dict[str, list[str]]
    profiles: tuple[dict[str, Any], ...]


@dataclass
class ArtefactValidationResult:
    """Aggregate validation outcome for a set of paths."""

    violations: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


def load_artefact_profiles(registry_dir: Path) -> ArtefactProfileConfig:
    """Load and parse artefact profile registry.

    Args:
        registry_dir: Directory containing ``workspace_artifact_profiles.yaml``.

    Returns:
        Parsed configuration.

    Raises:
        FileNotFoundError: When the registry file is missing.
        ValueError: When required top-level keys are absent.
    """
    path = registry_dir / _ARTEFACT_REGISTRY_NAME
    if not path.is_file():
        raise FileNotFoundError(f"Missing artefact profile registry: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("Artefact profile registry must be a mapping.")
    prefixes = data.get("validate_path_prefixes") or []
    if not isinstance(prefixes, list) or not prefixes:
        raise ValueError("validate_path_prefixes must be a non-empty list.")
    defaults = data.get("defaults") or {}
    if not isinstance(defaults, dict):
        raise ValueError("defaults must be a mapping.")
    aliases = data.get("type_aliases") or {}
    if not isinstance(aliases, dict):
        raise ValueError("type_aliases must be a mapping.")
    profiles = data.get("profiles") or []
    if not isinstance(profiles, list):
        raise ValueError("profiles must be a list.")
    return ArtefactProfileConfig(
        validate_path_prefixes=tuple(str(p) for p in prefixes),
        defaults=defaults,
        type_aliases={str(k): list(v or []) for k, v in aliases.items()},
        profiles=tuple(p for p in profiles if isinstance(p, dict)),
    )


def _base_rules_from_config(cfg: ArtefactProfileConfig) -> dict[str, Any]:
    """Return default rule mapping from registry ``defaults``."""
    block = cfg.defaults.get("rules")
    return dict(block) if isinstance(block, dict) else {}


def _match_clause(
    rel_posix: str,
    meta: Mapping[str, Any],
    canonical_type: str,
    clause: dict[str, Any],
    aliases: Mapping[str, list[str]],
) -> bool:
    """Evaluate a single match mapping (AND of its fields)."""
    if "path_globs" in clause:
        globs = clause["path_globs"]
        if isinstance(globs, str):
            globs = [globs]
        if not isinstance(globs, list) or not any(
            _glob_match(rel_posix, g) for g in globs
        ):
            return False
    if "type_equals" in clause:
        want = str(clause["type_equals"]).strip().lower().replace(" ", "_").replace(
            "-", "_"
        )
        if canonical_type != want:
            return False
    if "all_of" in clause:
        parts = clause["all_of"]
        if not isinstance(parts, list):
            return False
        for part in parts:
            if not isinstance(part, dict):
                return False
            if not _match_clause(rel_posix, meta, canonical_type, part, aliases):
                return False
    return True


def _profile_applies(
    profile: dict[str, Any],
    rel_posix: str,
    meta: Mapping[str, Any],
    canonical_type: str,
    aliases: Mapping[str, list[str]],
) -> bool:
    match_block = profile.get("match")
    if not match_block:
        return True
    if not isinstance(match_block, dict):
        return False
    return _match_clause(rel_posix, meta, canonical_type, match_block, aliases)


def _resolve_profile_rules(
    cfg: ArtefactProfileConfig,
    rel_posix: str,
    meta: Mapping[str, Any],
    canonical_type: str,
) -> tuple[str | None, dict[str, Any]]:
    default_rules = _base_rules_from_config(cfg)
    for profile in cfg.profiles:
        pid = str(profile.get("id", "") or "").strip()
        if _profile_applies(profile, rel_posix, meta, canonical_type, cfg.type_aliases):
            overlay = profile.get("rules")
            overlay = overlay if isinstance(overlay, dict) else {}
            return (pid or None, {**default_rules, **overlay})
    return None, default_rules


def _check_integration_pattern_slug_dedup(scope_paths: list[str]) -> list[str]:
    """At most one leaf file per (family, pattern number) slug prefix."""
    buckets: dict[tuple[str, str], list[str]] = {}
    for rel in scope_paths:
        name = PurePosixPath(rel).name
        m = _INTEGRATION_PATTERN_SLUG.match(name)
        if not m:
            continue
        key = (m.group("fam").lower(), m.group("num"))
        buckets.setdefault(key, []).append(rel)
    out: list[str] = []
    for (fam, num), paths in sorted(buckets.items()):
        if len(paths) <= 1:
            continue
        out.append(
            "integration_pattern_slug_dedup: multiple files for "
            f"{fam.capitalize()} Pattern {num}: "
            + ", ".join(sorted(paths))
        )
    return out


def validate_workspace_artefact_paths(
    *,
    root_dir: Path,
    relative_paths: list[str],
    registry_dir: Path | None = None,
) -> ArtefactValidationResult:
    """Validate markdown/text artefacts using registry profiles.

    Only paths sharing a configured prefix under ``workspace/context`` roots are checked.
    Other paths are skipped without violation.

    Args:
        root_dir: Repository root (parent of ``workspace/``).
        relative_paths: Changed or candidate paths relative to ``root_dir``.
        registry_dir: Optional override for the ``registry`` directory.

    Returns:
        Aggregate ``ArtefactValidationResult`` listing human-readable violations.
    """
    rdir = registry_dir or (root_dir / "registry")
    try:
        cfg = load_artefact_profiles(rdir)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return ArtefactValidationResult(violations=[f"Artefact profile load failed: {exc}"])

    result = ArtefactValidationResult()
    prefix_roots = tuple(_norm_path_sep(p).strip().strip("/") for p in cfg.validate_path_prefixes)
    markdown_paths = [
        _norm_path_sep(p).lstrip("./")
        for p in relative_paths
        if p.lower().endswith(".md")
    ]
    in_scope = [p for p in markdown_paths if any(_path_has_prefix(p, root) for root in prefix_roots)]
    builtin_scope = list(in_scope)

    slug_violations = _check_integration_pattern_slug_dedup(builtin_scope)

    for rel in in_scope:
        abs_path = (root_dir / rel).resolve()
        if not abs_path.is_file():
            continue
        try:
            raw = abs_path.read_text(encoding="utf-8")
        except OSError as exc:
            result.violations.append(f"{rel}: could not read file ({exc}).")
            continue

        meta, body = _parse_front_matter(raw)
        ctype = ""
        raw_type_val = meta.get("type") if isinstance(meta.get("type"), str) else None
        ctype = _canonical_type(raw_type_val, cfg.type_aliases)

        profile_id, rules = _resolve_profile_rules(cfg, rel, meta, ctype)

        if rules.get("skip_front_matter"):
            required_fm: list[str] = []
        else:
            req = rules.get("required_front_matter")
            inherited = cfg.defaults.get("rules", {}).get("required_front_matter", [])
            required_fm = list(req) if isinstance(req, list) else list(inherited or [])

        for key in required_fm:
            key_s = str(key).strip()
            if not key_s:
                continue
            if key_s not in meta or not _non_empty_scalar(meta.get(key_s)):
                result.violations.append(
                    f"{rel}: missing or empty front matter field '{key_s}' "
                    f"(profile={profile_id or 'defaults'})."
                )

        min_h2 = rules.get(
            "min_h2_headings",
            cfg.defaults.get("rules", {}).get("min_h2_headings", 1),
        )
        h2_count = sum(
            1
            for line in body.splitlines()
            if line.strip().startswith("## ") and not line.strip().startswith("### ")
        )
        try:
            need_h2 = int(min_h2)
        except (TypeError, ValueError):
            need_h2 = 1
        if h2_count < need_h2:
            result.violations.append(
                f"{rel}: expected at least {need_h2} level-2 headings; found {h2_count} "
                f"(profile={profile_id or 'defaults'})."
            )

        sections = rules.get("required_h2_sections")
        if isinstance(sections, list):
            for heading in sections:
                h = str(heading).strip()
                if h and not _has_h2_section(body, h):
                    result.violations.append(
                        f"{rel}: missing required '## {h}' section "
                        f"(profile={profile_id or 'defaults'})."
                    )

        require_src = rules.get(
            "require_source_section",
            cfg.defaults.get("rules", {}).get("require_source_section", False),
        )
        if require_src and "## Source" not in body:
            result.violations.append(
                f"{rel}: missing required '## Source' section "
                f"(profile={profile_id or 'defaults'})."
            )

    # One dedup scan per invocation (covers all slug files).
    result.violations.extend(slug_violations)

    return result


__all__ = [
    "ArtefactValidationResult",
    "load_artefact_profiles",
    "validate_workspace_artefact_paths",
]
