from __future__ import annotations

import logging
import os
import time
from types import SimpleNamespace

from crisai.cli import main


def test_detect_explicit_mode_returns_peer_for_peer_prompt():
    prompt = (
        "Use peer mode. The author should propose. "
        "The challenger should identify three weaknesses. "
        "The refiner should respond. The judge should decide."
    )

    assert main._detect_explicit_mode(prompt) == "peer"


def test_should_disable_peer_retrieval_for_explicit_generative_peer_request():
    prompt = (
        "Use peer mode. Propose a simple design for improving crisAI command handling in the CLI. "
        "The author should propose. The challenger should identify at least three weaknesses. "
        "The refiner should address those weaknesses. The judge should decide whether the refined version is acceptable."
    )
    decision = SimpleNamespace(mode="peer", needs_retrieval=True)

    assert main._should_disable_peer_retrieval(prompt, "peer", decision) is True


def test_should_keep_peer_retrieval_when_prompt_requests_existing_sources():
    prompt = (
        "Use peer mode. Review the existing document in the workspace and propose improvements based on it. "
        "Show the peer conversation and final recommendation."
    )
    decision = SimpleNamespace(mode="peer", needs_retrieval=True)

    assert main._should_disable_peer_retrieval(prompt, "peer", decision) is False


def test_apply_decision_overrides_turns_off_retrieval_for_generative_peer_request():
    prompt = (
        "Use peer mode. Propose a simple design for improving crisAI command handling in the CLI. "
        "The author should propose. The challenger should identify at least three weaknesses."
    )
    decision = SimpleNamespace(mode="peer", needs_retrieval=True, needs_review=True)

    updated = main._apply_decision_overrides(prompt, "peer", decision)

    assert updated.mode == "peer"
    assert updated.needs_retrieval is False
    assert updated.needs_review is True


def test_suppress_console_info_logs_preserves_file_handler(tmp_path):
    logger = logging.getLogger("crisai.test.console_suppression")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    file_handler = logging.FileHandler(tmp_path / "app.log")
    file_handler.setLevel(logging.INFO)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    try:
        with main._suppress_console_info_logs():
            assert console_handler.level == logging.WARNING
            assert file_handler.level == logging.INFO
        assert console_handler.level == logging.INFO
        assert file_handler.level == logging.INFO
    finally:
        logger.handlers.clear()
        file_handler.close()


def test_is_benign_ssl_shutdown_context_detects_transport_message():
    context = {"message": "Fatal error on SSL transport"}
    assert main._is_benign_ssl_shutdown_context(context) is True


def test_is_benign_ssl_shutdown_context_detects_close_notify_sslerror():
    context = {"exception": OSError("[SSL: APPLICATION_DATA_AFTER_CLOSE_NOTIFY] application data after close notify")}
    # non-SSLError should not match
    assert main._is_benign_ssl_shutdown_context(context) is False

    import ssl

    ssl_context = {"exception": ssl.SSLError("application data after close notify")}
    assert main._is_benign_ssl_shutdown_context(ssl_context) is True


def test_resolve_initial_chat_session_prefers_newest_when_default(tmp_path, monkeypatch):
    older = tmp_path / "older.json"
    newer = tmp_path / "newer.json"
    older.write_text("[]", encoding="utf-8")
    newer.write_text("[]", encoding="utf-8")
    base = time.time()
    os.utime(older, (base - 100, base - 100))
    os.utime(newer, (base, base))
    monkeypatch.setattr(main, "session_dir", lambda: tmp_path)

    assert main._resolve_initial_chat_session("default") == "newer"


def test_resolve_initial_chat_session_preserves_explicit_session(monkeypatch):
    monkeypatch.setattr(main, "_session_name_newest_by_mtime", lambda: "newer")
    assert main._resolve_initial_chat_session("team_review") == "team_review"
