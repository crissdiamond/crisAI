from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

CheckpointAction = Literal["continue", "redirect", "stop"]


@dataclass(frozen=True, slots=True)
class RetrievalCheckpointSnapshot:
    """Human-reviewable checkpoint shown after retrieval and before drafting."""

    request: str
    retrieval_plan: str
    evidence_brief: str
    retrieval_prose: str
    attempt: int
    max_redirects: int
    evidence_bundle: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable representation for trace and web state."""
        payload: dict[str, object] = {
            "request": self.request,
            "retrieval_plan": self.retrieval_plan,
            "evidence_brief": self.evidence_brief,
            "retrieval_prose": self.retrieval_prose,
            "attempt": self.attempt,
            "max_redirects": self.max_redirects,
            "remaining_redirects": max(self.max_redirects - self.attempt, 0),
        }
        if self.evidence_bundle is not None:
            payload["evidence_bundle"] = self.evidence_bundle
        return payload


@dataclass(frozen=True, slots=True)
class RetrievalCheckpointDecision:
    """User decision captured at the retrieval checkpoint."""

    action: CheckpointAction
    redirect_instruction: str = ""

    @classmethod
    def continue_(cls) -> RetrievalCheckpointDecision:
        """Return a continue decision."""
        return cls(action="continue")

    @classmethod
    def stop(cls) -> RetrievalCheckpointDecision:
        """Return a stop decision."""
        return cls(action="stop")

    @classmethod
    def redirect(cls, instruction: str) -> RetrievalCheckpointDecision:
        """Return a redirect decision with user guidance."""
        return cls(action="redirect", redirect_instruction=instruction.strip())

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serialisable representation for tracing."""
        return {
            "action": self.action,
            "redirect_instruction": self.redirect_instruction,
        }


RetrievalCheckpointHandler = Callable[
    [RetrievalCheckpointSnapshot],
    Awaitable[RetrievalCheckpointDecision],
]


class RetrievalCheckpointStopped(RuntimeError):
    """Raised internally when the user stops after retrieval."""
