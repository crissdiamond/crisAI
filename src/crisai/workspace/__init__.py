"""Workspace helpers (artefact validation, layout helpers).

This package is intentionally small — keep heavyweight imports inside modules.
"""

from crisai.workspace.artefact_validation import (
    ArtefactValidationResult,
    validate_workspace_artefact_paths,
)

__all__ = ["ArtefactValidationResult", "validate_workspace_artefact_paths"]
