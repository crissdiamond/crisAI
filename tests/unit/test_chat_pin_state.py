from crisai.cli.commands import parse_chat_command
from crisai.cli.status_views import agent_status, mode_status


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
    assert mode_status("single", False) == "auto"


def test_mode_status_pinned():
    assert mode_status("peer", True) == "pinned:peer"


def test_agent_status_auto():
    assert agent_status("orchestrator", False) == "auto"


def test_agent_status_pinned():
    assert agent_status("design", True) == "pinned:design"
