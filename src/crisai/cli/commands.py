from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CommandAction = Literal[
    "exit",
    "help",
    "clear",
    "history",
    "switch_session",
    "set_mode",
    "set_review",
    "set_agent",
    "invalid",
    "noop",
]


@dataclass
class CommandResult:
    handled: bool
    action: CommandAction = "noop"
    message: str | None = None
    value: str | bool | None = None


def parse_chat_command(user_input: str) -> CommandResult:
    text = user_input.strip()
    if not text.startswith("/"):
        return CommandResult(handled=False)

    if text in {"/exit", "/quit"}:
        return CommandResult(handled=True, action="exit")

    if text == "/help":
        return CommandResult(handled=True, action="help")

    if text == "/clear":
        return CommandResult(handled=True, action="clear")

    if text == "/history":
        return CommandResult(handled=True, action="history")

    if text.startswith("/session "):
        value = text.split(maxsplit=1)[1].strip()
        if not value:
            return CommandResult(handled=True, action="invalid", message="Please provide a session name.")
        return CommandResult(handled=True, action="switch_session", value=value)

    if text.startswith("/mode "):
        value = text.split(maxsplit=1)[1].strip().lower()
        if value not in {"single", "pipeline", "peer"}:
            return CommandResult(
                handled=True,
                action="invalid",
                message="Invalid mode. Use single, pipeline, or peer.",
            )
        return CommandResult(handled=True, action="set_mode", value=value)

    if text.startswith("/review "):
        value = text.split(maxsplit=1)[1].strip().lower()
        if value in {"on", "true", "yes"}:
            return CommandResult(handled=True, action="set_review", value=True)
        if value in {"off", "false", "no"}:
            return CommandResult(handled=True, action="set_review", value=False)
        return CommandResult(
            handled=True,
            action="invalid",
            message="Invalid review setting. Use /review on or /review off.",
        )

    if text.startswith("/agent "):
        value = text.split(maxsplit=1)[1].strip()
        if not value:
            return CommandResult(handled=True, action="invalid", message="Please provide an agent id.")
        return CommandResult(handled=True, action="set_agent", value=value)

    return CommandResult(handled=True, action="invalid", message="Unknown command. Type /help for commands.")
