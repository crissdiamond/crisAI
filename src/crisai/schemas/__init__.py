"""Schema and prompt-contract resources."""

from __future__ import annotations

from functools import cache
from importlib import resources


@cache
def load_schema_text(name: str) -> str:
    """Load a schema resource as UTF-8 text."""
    return resources.files(__package__).joinpath(name).read_text(encoding="utf-8")
