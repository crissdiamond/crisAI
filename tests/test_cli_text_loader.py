from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from crisai.cli.text_loader import cli_text_dir, load_cli_text, render_cli_text


def test_cli_text_dir_exists() -> None:
    path = cli_text_dir()
    assert path.exists()
    assert path.is_dir()


def test_load_cli_text_reads_history_wrapper() -> None:
    content = load_cli_text("chat/history_wrapper.md")
    assert "Conversation so far:" in content
    assert "{transcript}" in content
    assert "{user_input}" in content


def test_render_cli_text_renders_history_wrapper() -> None:
    rendered = render_cli_text(
        "chat/history_wrapper.md",
        transcript="User: hello",
        user_input="What next?",
    )
    assert "User: hello" in rendered
    assert "What next?" in rendered
    assert "{transcript}" not in rendered
    assert "{user_input}" not in rendered
