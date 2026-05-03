from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from crisai.logging_utils import JsonFormatter, append_json_log_line, configure_mcp_framework_logging


def test_json_formatter_ecs_like_shape() -> None:
    formatter = JsonFormatter(service_component="test")
    record = logging.LogRecord(
        name="crisai.test",
        level=logging.INFO,
        pathname="x.py",
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    line = formatter.format(record)
    data = json.loads(line)
    assert data["message"] == "hello world"
    assert data["log"] == {"level": "INFO", "logger": "crisai.test"}
    assert data["service"] == {"name": "crisai", "component": "test"}
    assert "timestamp" in data


def test_json_formatter_includes_error_stack_trace() -> None:
    formatter = JsonFormatter()

    try:
        raise ValueError("boom")
    except ValueError:
        exc_tuple = sys.exc_info()
        record = logging.LogRecord(
            name="crisai.test",
            level=logging.ERROR,
            pathname="x.py",
            lineno=1,
            msg="failed",
            args=(),
            exc_info=exc_tuple,
        )

    line = formatter.format(record)
    data = json.loads(line)
    assert "error" in data
    assert "stack_trace" in data["error"]
    assert "ValueError: boom" in data["error"]["stack_trace"]


def test_append_json_log_line_writes_valid_json(tmp_path: Path) -> None:
    log_file = tmp_path / "out.log"
    append_json_log_line(
        log_file,
        "started",
        logger_name="crisai.mcp.test",
        service_component="test_mcp",
        custom_field=1,
    )
    line = log_file.read_text(encoding="utf-8").strip()
    data = json.loads(line)
    assert data["message"] == "started"
    assert data["log"]["logger"] == "crisai.mcp.test"
    assert data["service"]["component"] == "test_mcp"
    assert data["custom_field"] == 1


def test_configure_mcp_framework_logging_writes_json(tmp_path: Path) -> None:
    log_file = tmp_path / "mcp.log"
    test_logger = logging.getLogger("crisai_mcp_framework_test_logger")
    configure_mcp_framework_logging(
        log_file,
        service_component="unit_test_mcp",
        logger_names=["crisai_mcp_framework_test_logger"],
        handler_level=logging.INFO,
    )
    test_logger.warning("framework noise")
    line = log_file.read_text(encoding="utf-8").strip()
    data = json.loads(line)
    assert data["message"] == "framework noise"
    assert data["log"]["level"] == "WARNING"
    assert data["service"]["component"] == "unit_test_mcp"

    # Detach handler so other tests are not affected.
    test_logger.handlers.clear()
    test_logger.propagate = True
