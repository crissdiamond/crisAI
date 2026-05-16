from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GemPalette:
    """Terminal theme tokens mapped from the web UCL design palette."""

    primary_dark: str = "#361a54"
    background: str = "#1f102f"
    transcript_background: str = "#fafafa"
    composer_background: str = "#ffffff"
    accent_bright: str = "#993bff"
    accent_mid: str = "#ba82ff"
    surface_light: str = "#ddbdff"
    surface_pale: str = "#eedeff"
    accent_blue: str = "#30d6ff"
    text: str = "#1f1f2e"
    border: str = "#c9b7dd"
    vibrant_purple: str = "#500778"
    success: str = "#52C152"
    error: str = "#D50032"
    warning: str = "#FFCA36"


UCL_PALETTE = GemPalette()

GEM_CSS = f"""
Screen {{
    background: {UCL_PALETTE.background};
    color: {UCL_PALETTE.transcript_background};
}}

#header {{
    background: {UCL_PALETTE.primary_dark};
    color: {UCL_PALETTE.background};
    height: 3;
    padding: 0 2;
    border-bottom: tall {UCL_PALETTE.accent_mid};
}}

#workspace {{
    layout: horizontal;
    background: {UCL_PALETTE.background};
}}

#stages {{
    width: 31;
    min-width: 24;
    background: {UCL_PALETTE.surface_pale};
    border-right: solid {UCL_PALETTE.border};
    padding: 1;
}}

#transcript {{
    background: {UCL_PALETTE.transcript_background};
    color: {UCL_PALETTE.text};
    border: solid {UCL_PALETTE.accent_bright};
    padding: 1 2;
}}

#composer {{
    height: 3;
    border-top: solid {UCL_PALETTE.accent_bright};
    background: {UCL_PALETTE.composer_background};
    color: {UCL_PALETTE.text};
    padding: 0 1;
}}

#footer {{
    height: 1;
    background: {UCL_PALETTE.primary_dark};
    color: {UCL_PALETTE.accent_mid};
}}

.stage-active {{
    color: {UCL_PALETTE.accent_blue};
    text-style: bold;
}}

.stage-complete {{
    color: {UCL_PALETTE.success};
}}

.stage-pending {{
    color: {UCL_PALETTE.text};
}}

.stage-warning {{
    color: {UCL_PALETTE.warning};
}}

.stage-error {{
    color: {UCL_PALETTE.error};
}}
"""


def gem_palette_as_dict() -> dict[str, str]:
    """Return Gem palette tokens for tests and future diagnostics."""
    return {
        "primary_dark": UCL_PALETTE.primary_dark,
        "background": UCL_PALETTE.background,
        "transcript_background": UCL_PALETTE.transcript_background,
        "composer_background": UCL_PALETTE.composer_background,
        "accent_bright": UCL_PALETTE.accent_bright,
        "accent_mid": UCL_PALETTE.accent_mid,
        "surface_light": UCL_PALETTE.surface_light,
        "surface_pale": UCL_PALETTE.surface_pale,
        "accent_blue": UCL_PALETTE.accent_blue,
        "text": UCL_PALETTE.text,
        "border": UCL_PALETTE.border,
        "vibrant_purple": UCL_PALETTE.vibrant_purple,
        "success": UCL_PALETTE.success,
        "error": UCL_PALETTE.error,
        "warning": UCL_PALETTE.warning,
    }
