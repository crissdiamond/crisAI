from __future__ import annotations

from dataclasses import dataclass

from crisai.cli.commands import parse_chat_command
from crisai.cli.display import print_final_answer, print_status_message
from crisai.cli.session_store import HistoryEntry, load_history, save_history
from crisai.cli.status_views import (
    print_agents_table,
    print_chat_state,
    print_servers_table,
    print_session_history,
)
from crisai.cli.text_loader import load_cli_text
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
    mode_pinned: bool
    agent_pinned: bool


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
    elif action == "clear":
        state.history.clear()
        save_history(state.current_session, state.history)
        print_status_message(
            f"Conversation history cleared for session '{state.current_session}'.",
            title="🧹 Session cleared",
        )
    elif action == "list_servers":
        print_servers_table()
    elif action == "list_agents":
        print_agents_table()
    elif action == "history":
        print_session_history(state.history)
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
    elif action == "noop" and command.message == "status":
        print_chat_state(
            current_session=state.current_session,
            current_mode=state.current_mode,
            current_agent=state.current_agent,
            current_review=state.current_review,
            current_verbose=state.current_verbose,
            mode_pinned=state.mode_pinned,
            agent_pinned=state.agent_pinned,
            history_count=len(state.history),
        )
    elif action in {"invalid", "noop"} and command.message:
        print_status_message(command.message, title="⚠ Command notice")

    return True
