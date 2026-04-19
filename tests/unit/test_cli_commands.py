import pytest

from crisai.cli.commands import parse_chat_command


@pytest.mark.parametrize(
    ("user_input", "expected_action", "expected_value"),
    [
        ("hello", "noop", None),
        ("/exit", "exit", None),
        ("/quit", "exit", None),
        ("/help", "help", None),
        ("/clear", "clear", None),
        ("/history", "history", None),
        ("/list-servers", "list_servers", None),
        ("/list servers", "list_servers", None),
        ("/list-agents", "list_agents", None),
        ("/list agents", "list_agents", None),
        ("/session design-review", "switch_session", "design-review"),
        ("/mode single", "set_mode", "single"),
        ("/mode pipeline", "set_mode", "pipeline"),
        ("/mode peer", "set_mode", "peer"),
        ("/review on", "set_review", True),
        ("/review off", "set_review", False),
        ("/verbose on", "set_verbose", True),
        ("/verbose off", "set_verbose", False),
        ("/agent discovery", "set_agent", "discovery"),
    ],
)
def test_parse_chat_command_supported_inputs(user_input, expected_action, expected_value):
    result = parse_chat_command(user_input)

    expected_handled = user_input.startswith("/")
    assert result.handled is expected_handled
    assert result.action == expected_action
    assert result.value == expected_value


@pytest.mark.parametrize(
    ("user_input", "expected_message"),
    [
        ("/mode invalid", "Invalid mode. Use single, pipeline, or peer."),
        ("/review maybe", "Invalid review setting. Use /review on or /review off."),
        ("/verbose maybe", "Invalid verbose setting. Use /verbose on or /verbose off."),
        ("/session ", "Please provide a session name."),
        ("/agent ", "Please provide an agent id."),
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
