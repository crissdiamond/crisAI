from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UIConfig:
    """Static UI tuning values for the web interface."""

    history_max_lines: int = 8


UI_CONFIG = UIConfig()

