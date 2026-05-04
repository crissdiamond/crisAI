import pytest

from crisai.cli.commands import parse_chat_command


@pytest.mark.parametrize(
    ("user_input", "expected_action", "expected_value", "expected_message"),
    [
        ("hello", "noop", None, None),
        ("/exit", "exit", None, None),
        ("/quit", "exit", None, None),
        ("/help", "help", None, None),
        ("/clear", "clear", None, None),
        ("/clear-session", "clear_session", None, None),
        ("/clear-session design-review", "clear_session", "design-review", None),
        ("/history", "history", None, None),
        ("/status", "noop", None, "status"),
        ("/list-servers", "list_servers", None, None),
        ("/list servers", "list_servers", None, None),
        ("/list-agents", "list_agents", None, None),
        ("/list agents", "list_agents", None, None),
        ("/session design-review", "switch_session", "design-review", None),
        ("/mode auto", "set_mode", "auto", None),
        ("/mode single", "set_mode", "single", None),
        ("/mode pipeline", "set_mode", "pipeline", None),
        ("/mode peer", "set_mode", "peer", None),
        ("/review on", "set_review", True, None),
        ("/review off", "set_review", False, None),
        ("/verbose on", "set_verbose", True, None),
        ("/verbose off", "set_verbose", False, None),
        ("/agent auto", "set_agent", "auto", None),
        ("/agent discovery", "set_agent", "discovery", None),
    ],
)
def test_parse_chat_command_supported_inputs(user_input, expected_action, expected_value, expected_message):
    result = parse_chat_command(user_input)

    expected_handled = user_input.startswith("/")
    assert result.handled is expected_handled
    assert result.action == expected_action
    assert result.value == expected_value
    assert result.message == expected_message


@pytest.mark.parametrize(
    ("user_input", "expected_message"),
    [
        ("/mode invalid", "Invalid mode. Use /mode auto, /mode single, /mode pipeline, or /mode peer."),
        ("/review maybe", "Invalid review setting. Use /review on or /review off."),
        ("/verbose maybe", "Invalid verbose setting. Use /verbose on or /verbose off."),
        ("/session ", "Please provide a session name."),
        ("/agent ", "Please provide an agent id, or use /agent auto."),
        ("/unknown", "Unknown command. Type /help for commands."),
    ],
)
def test_parse_chat_command_invalid_inputs(user_input, expected_message):
    result = parse_chat_command(user_input)

    assert result.handled is True
    assert result.action == "invalid"
    assert result.message == expected_message


def test_parse_chat_command_verbose_without_value_returns_message():
    result = parse_chat_command("/verbose")

    assert result.handled is True
    assert result.action == "noop"
    assert result.message == "Verbose command requires a value. Use /verbose on or /verbose off."


def test_parse_chat_command_trims_whitespace_in_values():
    result = parse_chat_command("  /session   architecture_workshop   ")

    assert result.handled is True
    assert result.action == "switch_session"
    assert result.value == "architecture_workshop"
