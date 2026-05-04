from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CommandAction = Literal[
    "exit",
    "help",
    "clear",
    "clear_session",
    "history",
    "list_servers",
    "list_agents",
    "switch_session",
    "set_mode",
    "set_review",
    "set_verbose",
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
    raw = user_input.strip()
    if not raw.startswith("/"):
        return CommandResult(handled=False)

    if raw in {"/exit", "/quit"}:
        return CommandResult(handled=True, action="exit")

    if raw == "/help":
        return CommandResult(handled=True, action="help")

    if raw == "/clear":
        return CommandResult(handled=True, action="clear")

    if raw.startswith("/clear-session"):
        parts = raw.split(maxsplit=1)
        if len(parts) == 1 or not parts[1].strip():
            return CommandResult(handled=True, action="clear_session", value=None)
        return CommandResult(handled=True, action="clear_session", value=parts[1].strip())

    if raw in {"/list servers", "/list-servers"}:
        return CommandResult(handled=True, action="list_servers")

    if raw in {"/list agents", "/list-agents"}:
        return CommandResult(handled=True, action="list_agents")

    if raw == "/history":
        return CommandResult(handled=True, action="history")

    if raw == "/status":
        return CommandResult(handled=True, action="noop", message="status")

    if raw.startswith("/session"):
        parts = raw.split(maxsplit=1)
        if len(parts) == 1 or not parts[1].strip():
            return CommandResult(handled=True, action="invalid", message="Please provide a session name.")
        return CommandResult(handled=True, action="switch_session", value=parts[1].strip())

    if raw.startswith("/mode"):
        parts = raw.split(maxsplit=1)
        if len(parts) == 1 or not parts[1].strip():
            return CommandResult(
                handled=True,
                action="invalid",
                message="Invalid mode. Use /mode auto, /mode single, /mode pipeline, or /mode peer.",
            )
        value = parts[1].strip().lower()
        if value not in {"auto", "single", "pipeline", "peer"}:
            return CommandResult(
                handled=True,
                action="invalid",
                message="Invalid mode. Use /mode auto, /mode single, /mode pipeline, or /mode peer.",
            )
        return CommandResult(handled=True, action="set_mode", value=value)

    if raw == "/verbose":
        return CommandResult(
            handled=True,
            action="noop",
            message="Verbose command requires a value. Use /verbose on or /verbose off.",
        )

    if raw.startswith("/verbose"):
        parts = raw.split(maxsplit=1)
        if len(parts) == 1 or not parts[1].strip():
            return CommandResult(
                handled=True,
                action="invalid",
                message="Invalid verbose setting. Use /verbose on or /verbose off.",
            )
        value = parts[1].strip().lower()
        if value in {"on", "true", "yes"}:
            return CommandResult(handled=True, action="set_verbose", value=True)
        if value in {"off", "false", "no"}:
            return CommandResult(handled=True, action="set_verbose", value=False)
        return CommandResult(
            handled=True,
            action="invalid",
            message="Invalid verbose setting. Use /verbose on or /verbose off.",
        )

    if raw.startswith("/review"):
        parts = raw.split(maxsplit=1)
        if len(parts) == 1 or not parts[1].strip():
            return CommandResult(
                handled=True,
                action="invalid",
                message="Invalid review setting. Use /review on or /review off.",
            )
        value = parts[1].strip().lower()
        if value in {"on", "true", "yes"}:
            return CommandResult(handled=True, action="set_review", value=True)
        if value in {"off", "false", "no"}:
            return CommandResult(handled=True, action="set_review", value=False)
        return CommandResult(
            handled=True,
            action="invalid",
            message="Invalid review setting. Use /review on or /review off.",
        )

    if raw.startswith("/agent"):
        parts = raw.split(maxsplit=1)
        if len(parts) == 1 or not parts[1].strip():
            return CommandResult(handled=True, action="invalid", message="Please provide an agent id, or use /agent auto.")
        value = parts[1].strip()
        return CommandResult(handled=True, action="set_agent", value=value)

    return CommandResult(handled=True, action="invalid", message="Unknown command. Type /help for commands.")
