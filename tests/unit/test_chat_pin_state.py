from crisai.cli.commands import parse_chat_command
from crisai.cli.main import _agent_status, _mode_status


def test_parse_mode_auto_command():
    result = parse_chat_command("/mode auto")
    assert result.handled is True
    assert result.action == "set_mode"
    assert result.value == "auto"


def test_parse_agent_auto_command():
    result = parse_chat_command("/agent auto")
    assert result.handled is True
    assert result.action == "set_agent"
    assert result.value == "auto"


def test_mode_status_auto():
    assert _mode_status("single", False) == "auto"


def test_mode_status_pinned():
    assert _mode_status("peer", True) == "pinned:peer"


def test_agent_status_auto():
    assert _agent_status("orchestrator", False) == "auto"


def test_agent_status_pinned():
    assert _agent_status("design", True) == "pinned:design"
