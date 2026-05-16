from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from crisai.cli.chat_context import (
    build_runtime_context_package,
    render_session_memory,
    update_session_memory,
)
from crisai.cli.commands import parse_chat_command
from crisai.cli.display import print_final_answer, print_status_message
from crisai.cli.session_store import (
    HistoryEntry,
    clear_cli_history,
    clear_history,
    clear_session_memory,
    load_history,
    save_history,
)
from crisai.cli.status_views import (
    print_agents_table,
    print_chat_state,
    print_servers_table,
    print_session_history,
)
from crisai.cli.text_loader import load_cli_text
from crisai.config import Settings, load_settings
from crisai.orchestration.router import normalize_agent_id


@dataclass
class ChatRuntimeState:
    """Mutable runtime state for an interactive chat session."""

    current_session: str
    history: list[HistoryEntry]
    current_mode: str
    current_agent: str
    current_review: bool
    current_verbose: bool
    current_retrieval_checkpoint: bool
    mode_pinned: bool
    agent_pinned: bool
    settings: Settings = field(default_factory=load_settings)


def _print_hierarchical_settings(settings: Settings) -> None:
    lines = []
    for section_name in ["general", "ui", "model", "workflow"]:
        section = getattr(settings, section_name)
        lines.append(f"[bold cyan]{section_name.capitalize()}[/bold cyan]")
        for f in section.__dataclass_fields__:
            val = getattr(section, f)
            lines.append(f"  [dim]{f}:[/dim] {val}")
    print_status_message("\n".join(lines), title="⚙ Settings")


def _update_setting(settings: Settings, path: str, value: str) -> str:
    parts = path.split(".")
    if len(parts) != 2:
        return f"Invalid path '{path}'. Use <section>.<key> (e.g. ui.verbose)."

    section_name, key = parts
    if not hasattr(settings, section_name):
        return f"Invalid section '{section_name}'."

    section = getattr(settings, section_name)
    if not hasattr(section, key):
        return f"Invalid key '{key}' in section '{section_name}'."

    current_val = getattr(section, key)
    new_val: Any = value
    if isinstance(current_val, bool):
        if value.lower() in {"on", "true", "yes", "1"}:
            new_val = True
        elif value.lower() in {"off", "false", "no", "0"}:
            new_val = False
        else:
            return f"Invalid boolean value '{value}'."
    elif isinstance(current_val, int):
        try:
            new_val = int(value)
        except ValueError:
            return f"Invalid integer value '{value}'."
    elif isinstance(current_val, Path):
        new_val = Path(value)

    setattr(section, key, new_val)
    return f"Updated [bold]{path}[/bold] to {new_val}."


def handle_chat_command(user_input: str, state: ChatRuntimeState) -> bool:
    """Handles slash commands for the interactive chat loop.

    Args:
        user_input: Raw user input.
        state: Mutable interactive session state.

    Returns:
        True if the input was handled as a command, otherwise False.

    Raises:
        EOFError: If the command requests session exit.
    """
    command = parse_chat_command(user_input)

    if not command.handled:
        return False

    action = command.action

    if action == "exit":
        raise EOFError

    if action == "help":
        print_final_answer(load_cli_text("help.md"), title="📘 CLI help")
    elif action in {"clear", "clear_session"}:
        target_session = str(command.value) if action == "clear_session" and command.value else state.current_session
        clear_history(target_session)
        clear_cli_history(target_session)
        clear_session_memory(target_session)
        if target_session == state.current_session:
            state.history.clear()
        print_status_message(
            f"Conversation history cleared for session '{target_session}'.",
            title="🧹 Session cleared",
        )
    elif action == "list_servers":
        print_servers_table()
    elif action == "list_agents":
        print_agents_table()
    elif action == "history":
        print_session_history(state.history)
    elif action == "context_show":
        package = build_runtime_context_package("(preview)", state.history, session_name=state.current_session)
        memory_text = render_session_memory(package.memory) or "No compact memory for this session yet."
        print_status_message(
            "\n".join(
                [
                    memory_text,
                    "",
                    f"Recent entries included: {package.included_recent_entries}",
                    f"Truncated: {'yes' if package.truncated else 'no'}",
                ]
            ),
            title="🧠 Runtime context",
        )
    elif action == "context_reset":
        clear_session_memory(state.current_session)
        print_status_message(
            f"Compact memory cleared for session '{state.current_session}'. Raw history was kept.",
            title="🧠 Context reset",
        )
    elif action == "switch_session":
        state.current_session = str(command.value)
        state.history = load_history(state.current_session)
        # Persist/touch the target session immediately so CLI startup can
        # reliably resume the most recently selected session, even before the
        # next user/assistant exchange is saved.
        save_history(state.current_session, state.history)
        print_status_message(
            f"Switched to session '{state.current_session}'.\nLoaded history entries: {len(state.history)}",
            title="🔁 Session switched",
        )
    elif action == "session_new":
        state.current_session = str(command.value)
        state.history = []
        save_history(state.current_session, state.history)
        clear_cli_history(state.current_session)
        clear_session_memory(state.current_session)
        print_status_message(
            f"Created and switched to clean session '{state.current_session}'.",
            title="🆕 Session created",
        )
    elif action == "session_compact":
        memory = update_session_memory(state.current_session, state.history)
        print_status_message(
            render_session_memory(memory) or "No history available to compact.",
            title="🧠 Session compacted",
        )
    elif action == "set_mode":
        value = str(command.value)
        if value == "auto":
            state.current_mode = "single"
            state.mode_pinned = False
            print_status_message(
                "Mode pin cleared. Router is back to auto mode selection.",
                title="🧭 Routing mode",
            )
        else:
            state.current_mode = value
            state.mode_pinned = True
            print_status_message(f"Mode pinned to {state.current_mode}", title="🧭 Routing mode")
    elif action == "set_review":
        state.current_review = bool(command.value)
        print_status_message(
            f"Review preference {'enabled' if state.current_review else 'disabled'}.",
            title="🛡 Review preference",
        )
    elif action == "set_retrieval_checkpoint":
        state.current_retrieval_checkpoint = bool(command.value)
        print_status_message(
            f"Retrieval checkpoint {'enabled' if state.current_retrieval_checkpoint else 'disabled'}.",
            title="⏸ Retrieval checkpoint",
        )
    elif action == "set_verbose":
        state.current_verbose = bool(command.value)
        print_status_message(
            f"Verbose {'enabled' if state.current_verbose else 'disabled'}.",
            title="📝 Verbose output",
        )
    elif action == "set_agent":
        value = str(command.value)
        if value.lower() == "auto":
            state.current_agent = "orchestrator"
            state.agent_pinned = False
            print_status_message(
                "Agent pin cleared. Router is back to auto agent selection.",
                title="🤖 Agent selection",
            )
        else:
            state.current_agent = normalize_agent_id(value) or value
            state.agent_pinned = True
            print_status_message(
                f"Single-agent target pinned to {state.current_agent}",
                title="🤖 Agent selection",
            )
    elif action == "settings":
        if not command.value:
            _print_hierarchical_settings(state.settings)
        else:
            val = str(command.value)
            if " " in val:
                path, new_val = val.split(maxsplit=1)
                msg = _update_setting(state.settings, path, new_val)
                # Sync back to top-level state if applicable
                if path == "ui.verbose":
                    state.current_verbose = state.settings.ui.verbose
                elif path == "ui.retrieval_checkpoint_enabled":
                    state.current_retrieval_checkpoint = state.settings.ui.retrieval_checkpoint_enabled
                print_status_message(msg, title="⚙ Settings")
            else:
                # Show single setting
                try:
                    current = getattr(getattr(state.settings, val.split(".")[0]), val.split(".")[1])
                    print_status_message(f"[dim]{val}:[/dim] {current}", title="⚙ Settings")
                except (AttributeError, IndexError):
                    print_status_message(f"Invalid setting path '{val}'.", title="⚠ Settings")
    elif action == "noop" and command.message == "status":
        print_chat_state(
            current_session=state.current_session,
            history_count=len(state.history),
        )
    elif action in {"invalid", "noop"} and command.message:
        print_status_message(command.message, title="⚠ Command notice")

    return True
