from __future__ import annotations


class WorkflowValidationError(RuntimeError):
    """Raised when pipeline input fails validation before execution begins."""
