from __future__ import annotations


def test_import_cli_main() -> None:
    import crisai.cli.main  # noqa: F401


def test_import_cli_display() -> None:
    import crisai.cli.display  # noqa: F401


def test_import_cli_pipelines() -> None:
    import crisai.cli.pipelines  # noqa: F401


def test_import_cli_peer_transcript() -> None:
    import crisai.cli.peer_transcript  # noqa: F401


def test_import_cli_session_store() -> None:
    import crisai.cli.session_store  # noqa: F401


def test_import_cli_chat_context() -> None:
    import crisai.cli.chat_context  # noqa: F401


def test_import_cli_status_views() -> None:
    import crisai.cli.status_views  # noqa: F401


def test_import_cli_chat_controller() -> None:
    import crisai.cli.chat_controller  # noqa: F401


def test_import_orchestration_router() -> None:
    import crisai.orchestration.router  # noqa: F401
