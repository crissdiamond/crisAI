from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Any

import yaml

REQUIRED_PALETTE_TOKENS = {
    "primary_dark",
    "background",
    "transcript_background",
    "composer_background",
    "accent_bright",
    "accent_mid",
    "surface_light",
    "surface_pale",
    "accent_blue",
    "text",
    "border",
    "vibrant_purple",
    "success",
    "error",
    "warning",
}


def default_gem_ui_config_path() -> Path:
    """Return the default Gem UI registry path."""
    return Path(__file__).resolve().parents[3] / "registry" / "ui.yaml"


def load_gem_ui_config(path: Path | None = None) -> dict[str, Any]:
    """Load Gem UI theme configuration from YAML."""
    config_path = path or default_gem_ui_config_path()
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Gem UI config must be a mapping: {config_path}")
    return data


def _theme_config(config: dict[str, Any]) -> dict[str, Any]:
    surfaces = config.get("surfaces")
    themes = config.get("themes")
    if isinstance(surfaces, dict) and isinstance(themes, dict):
        gem = surfaces.get("gem")
        if not isinstance(gem, dict):
            raise ValueError("UI config requires surfaces.gem mapping.")
        theme_name = str(gem.get("theme") or config.get("default_theme") or "")
        theme = themes.get(theme_name)
        if not isinstance(theme, dict):
            raise ValueError(f"UI config references unknown Gem theme: {theme_name}")
        return {"palette": theme.get("palette"), "css_template": gem.get("css_template")}

    theme = config.get("theme")
    if isinstance(theme, dict):
        return theme
    raise ValueError("Gem UI config requires a theme mapping.")


def gem_palette_as_dict(path: Path | None = None) -> dict[str, str]:
    """Return Gem palette tokens from registry configuration."""
    theme = _theme_config(load_gem_ui_config(path))
    palette = theme.get("palette")
    if not isinstance(palette, dict):
        raise ValueError("Gem UI theme requires a palette mapping.")
    missing = REQUIRED_PALETTE_TOKENS - set(palette)
    if missing:
        raise ValueError(f"Gem UI palette is missing token(s): {', '.join(sorted(missing))}")
    return {key: str(palette[key]) for key in sorted(REQUIRED_PALETTE_TOKENS)}


def _template_fields(template: str) -> set[str]:
    fields: set[str] = set()
    for match in Template.pattern.finditer(template):
        named = match.group("named") or match.group("braced")
        if named:
            fields.add(named)
    return fields


def render_gem_css(path: Path | None = None) -> str:
    """Render Gem Textual CSS from registry-backed theme tokens."""
    config = load_gem_ui_config(path)
    theme = _theme_config(config)
    template = theme.get("css_template")
    if not isinstance(template, str) or not template.strip():
        raise ValueError("Gem UI theme requires a non-empty css_template.")
    palette = gem_palette_as_dict(path)
    missing = _template_fields(template) - set(palette)
    if missing:
        raise ValueError(f"Gem UI css_template references unknown token(s): {', '.join(sorted(missing))}")
    return Template(template).substitute(**palette)


GEM_CSS = render_gem_css()
