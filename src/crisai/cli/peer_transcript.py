from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(slots=True)
class PeerMessage:
    speaker: str
    role: str
    content: str
    step: str


@dataclass(slots=True)
class PeerRunResult:
    final_text: str
    transcript: list[PeerMessage] = field(default_factory=list)


def make_peer_message(speaker: str, content: str, *, role: str | None = None, step: str | None = None) -> PeerMessage:
    clean = (content or "").strip()
    return PeerMessage(
        speaker=speaker,
        role=role or speaker,
        step=step or speaker,
        content=clean,
    )


def append_peer_message(transcript: list[PeerMessage], speaker: str, content: str, *, role: str | None = None, step: str | None = None) -> None:
    msg = make_peer_message(speaker, content, role=role, step=step)
    if msg.content:
        transcript.append(msg)


def peer_speakers(messages: Iterable[PeerMessage]) -> list[str]:
    return [m.speaker for m in messages]
