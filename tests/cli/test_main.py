from __future__ import annotations

import asyncio
import logging
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


def test_should_keep_peer_retrieval_for_intranet_file_backed_peer_request():
    prompt = (
        "Use peer mode. Create files under workspace/knowledge_staging/patterns grounded on "
        "SharePoint intranet SitePages integration-patterns.aspx and leaf pages."
    )
    decision = SimpleNamespace(mode="peer", needs_retrieval=True)

    assert main._should_disable_peer_retrieval(prompt, "peer", decision) is False


def test_should_force_peer_retrieval_for_intranet_file_backed_peer_request():
    prompt = (
        "Create files under workspace/knowledge_staging/patterns grounded on "
        "SharePoint intranet Site Pages integration-patterns.aspx and leaf pages."
    )
    decision = SimpleNamespace(mode="peer", needs_retrieval=False)

    assert main._should_force_peer_retrieval(prompt, decision) is True


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


def test_apply_decision_overrides_forces_retrieval_for_intranet_peer_request():
    prompt = (
        "Use peer mode and create files in workspace/knowledge_staging based on "
        "intranet Site Pages and SharePoint sources."
    )
    decision = SimpleNamespace(mode="peer", needs_retrieval=False, needs_review=False)

    updated = main._apply_decision_overrides(prompt, "peer", decision)

    assert updated.mode == "peer"
    assert updated.needs_retrieval is True


def test_suppress_console_info_and_warning_logs_preserves_file_handler(tmp_path):
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
            assert console_handler.level == logging.ERROR
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


def test_web_react_command_delegates_to_ui_workspace_script(monkeypatch, tmp_path):
    calls = []
    ui_dir = tmp_path / "ui"
    ui_dir.mkdir()
    (ui_dir / "package.json").write_text("{}", encoding="utf-8")
    (ui_dir / "node_modules").mkdir()
    monkeypatch.setattr(main, "_UI_WORKSPACE", ui_dir)
    monkeypatch.setattr(
        main.subprocess,
        "run",
        lambda args, check=False, env=None: calls.append((args, check, env)) or SimpleNamespace(returncode=0),
    )

    main.web_react()

    assert calls[0][0:2] == (["npm", "--prefix", str(ui_dir), "run", "dev:web"], False)
    assert isinstance(calls[0][2], dict)


def test_gem_ink_command_delegates_to_ui_workspace_script(monkeypatch, tmp_path):
    calls = []
    ui_dir = tmp_path / "ui"
    ui_dir.mkdir()
    (ui_dir / "package.json").write_text("{}", encoding="utf-8")
    (ui_dir / "node_modules").mkdir()
    monkeypatch.setattr(main, "_UI_WORKSPACE", ui_dir)
    monkeypatch.setattr(
        main.subprocess,
        "run",
        lambda args, check=False, env=None: calls.append((args, check, env)) or SimpleNamespace(returncode=0),
    )

    main.gem_ink()

    assert calls[0][0:2] == (["npm", "--prefix", str(ui_dir), "run", "dev:gem"], False)
    assert isinstance(calls[0][2], dict)


def test_web_react_command_bridges_runtime_env_for_vite(monkeypatch, tmp_path):
    calls = []
    ui_dir = tmp_path / "ui"
    ui_dir.mkdir()
    (ui_dir / "package.json").write_text("{}", encoding="utf-8")
    (ui_dir / "node_modules").mkdir()
    monkeypatch.setattr(main, "_UI_WORKSPACE", ui_dir)
    monkeypatch.setenv("CRISAI_API_KEY", "token-123")
    monkeypatch.setenv("CRISAI_RUNTIME_URL", "http://127.0.0.1:9000")
    monkeypatch.delenv("CRISAI_API_TOKEN", raising=False)
    monkeypatch.delenv("VITE_CRISAI_API_KEY", raising=False)
    monkeypatch.delenv("VITE_CRISAI_API_TOKEN", raising=False)
    monkeypatch.delenv("VITE_CRISAI_RUNTIME_URL", raising=False)
    monkeypatch.setattr(
        main.subprocess,
        "run",
        lambda args, check=False, env=None: calls.append((args, check, env)) or SimpleNamespace(returncode=0),
    )

    main.web_react()

    assert calls[0][0:2] == (["npm", "--prefix", str(ui_dir), "run", "dev:web"], False)
    assert calls[0][2]["VITE_CRISAI_API_KEY"] == "token-123"
    assert calls[0][2]["VITE_CRISAI_API_TOKEN"] == "token-123"
    assert calls[0][2]["VITE_CRISAI_RUNTIME_URL"] == "http://127.0.0.1:9000"


def test_ui_workspace_script_guides_when_node_modules_missing(monkeypatch, tmp_path):
    notices = []
    ui_dir = tmp_path / "ui"
    ui_dir.mkdir()
    (ui_dir / "package.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(main, "_UI_WORKSPACE", ui_dir)
    monkeypatch.setattr(main, "print_status_message", lambda body, title=None: notices.append((title, body)))

    try:
        main.web_react()
    except main.typer.Exit as exc:
        assert exc.exit_code == 1
    else:
        raise AssertionError("web_react should exit when UI dependencies are missing")

    assert notices[-1][0] == "🧪 Experimental UI"
    assert "npm --prefix ui install" in notices[-1][1]


def test_run_async_cancels_pending_background_tasks():
    observed: dict[str, bool] = {"cancelled": False}

    async def _background() -> None:
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            observed["cancelled"] = True
            raise

    async def _runner() -> str:
        asyncio.create_task(_background())
        await asyncio.sleep(0)
        return "ok"

    assert main._run_async(_runner()) == "ok"
    assert observed["cancelled"] is True


def test_clear_session_command_clears_target_and_prints_notice(monkeypatch):
    cleared = []
    cleared_cli = []
    notices = []
    monkeypatch.setattr(main, "clear_history", lambda session: cleared.append(session))
    monkeypatch.setattr(main, "clear_cli_history", lambda session: cleared_cli.append(session))
    monkeypatch.setattr(
        main,
        "print_status_message",
        lambda body, title=None: notices.append((title, body)),
    )

    main.clear_session(session="architecture-review")

    assert cleared == ["architecture-review"]
    assert cleared_cli == ["architecture-review"]
    assert notices[-1][0] == "🧹 Session cleared"
    assert "architecture-review" in notices[-1][1]


def test_ask_uses_session_history_for_continuation_intent(monkeypatch):
    captured: dict[str, object] = {}
    decision = SimpleNamespace(
        intent="discovery",
        mode="single",
        agent="retrieval_planner",
        needs_retrieval=True,
        needs_review=False,
        confidence=0.85,
        reason="test",
    )
    history = [
        ("user", "Find all documents in my OneDrive with integration strategy in the title."),
        ("assistant", "I found 10 OneDrive documents."),
    ]

    monkeypatch.setattr(main, "load_history", lambda session_name: history)
    monkeypatch.setattr(main, "print_status_message", lambda body, title=None: None)
    monkeypatch.setattr(main, "update_terminal_title", lambda title: None)
    monkeypatch.setattr(main, "_render_final_output", lambda decision, text: None)

    def fake_resolve_route(message, **kwargs):
        captured["route_message"] = message
        return decision

    async def fake_run_with_routing(message, verbose, review, route_decision, **kwargs):
        captured["agent_message"] = message
        captured["intent_message"] = kwargs["user_intent_message"]
        captured["session_name"] = kwargs["session_name"]
        return "ok"

    monkeypatch.setattr(main, "_resolve_route", fake_resolve_route)
    monkeypatch.setattr(main, "_apply_decision_overrides", lambda message, explicit_mode, route_decision: route_decision)
    monkeypatch.setattr(main, "_run_with_routing", fake_run_with_routing)

    main.ask(
        message="continua",
        agent_id="orchestrator",
        session="architecture",
        pipeline=False,
        peer=False,
        review=False,
        verbose=False,
        retrieval_checkpoint=False,
        no_retrieval_checkpoint=False,
    )

    assert "Previous user request:" in str(captured["route_message"])
    assert "Find all documents in my OneDrive" in str(captured["intent_message"])
    assert "Relevant recent turns:" in str(captured["agent_message"])
    assert captured["session_name"] == "architecture"
