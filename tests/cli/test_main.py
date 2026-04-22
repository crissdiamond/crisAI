from __future__ import annotations

import logging

from crisai.cli import main


def test_detect_explicit_mode_returns_peer_for_peer_instruction():
    user_input = (
        "Use peer mode. The author should propose. "
        "The challenger should identify weaknesses. "
        "The refiner should address them. The judge should decide."
    )

    assert main._detect_explicit_mode(user_input) == "peer"


def test_detect_explicit_mode_returns_none_when_no_explicit_instruction():
    assert main._detect_explicit_mode("Summarise this design proposal.") is None


def test_suppress_console_info_logs_preserves_file_handlers(tmp_path):
    logger = logging.getLogger("crisai.test.logging")
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    file_handler = logging.FileHandler(tmp_path / "test.log")
    file_handler.setLevel(logging.INFO)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    with main._suppress_console_info_logs():
        assert console_handler.level == logging.WARNING
        assert file_handler.level == logging.INFO

    assert console_handler.level == logging.INFO
    assert file_handler.level == logging.INFO
