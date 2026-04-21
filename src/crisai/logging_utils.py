from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_CONFIGURED = False

_NOISY_LOGGERS: dict[str, int] = {
    "mcp": logging.WARNING,
    "mcp.server": logging.WARNING,
    "mcp.client": logging.WARNING,
    "server": logging.WARNING,
    "httpx": logging.WARNING,
    "httpcore": logging.WARNING,
    "openai": logging.WARNING,
    "agents": logging.WARNING,
    "asyncio": logging.WARNING,
    "uvicorn": logging.WARNING,
}


class DropListToolsRequestFilter(logging.Filter):
    """Filters out repetitive MCP tool listing noise.

    This keeps operational logs readable without mutating logger state at
    runtime during individual agent executions.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return "Processing request of type ListToolsRequest" not in message


class JsonFormatter(logging.Formatter):
    """Formats log records as structured JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        for key, value in record.__dict__.items():
            if key.startswith("_") or key in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "asctime",
            }:
                continue
            payload[key] = value

        return json.dumps(payload, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """Formats concise human-readable console log lines."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        return f"[{timestamp}] {record.levelname:<8} {record.name}: {record.getMessage()}"



def configure_logging(settings) -> None:
    """Configure application logging once per process.

    Args:
        settings: Loaded application settings.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings.log_dir.mkdir(parents=True, exist_ok=True)
    log_file = settings.log_dir / "crisai.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    root_logger.handlers.clear()

    common_filter = DropListToolsRequestFilter()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ConsoleFormatter())
    console_handler.addFilter(common_filter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(root_logger.level)
    file_handler.setFormatter(JsonFormatter())
    file_handler.addFilter(common_filter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    for logger_name, logger_level in _NOISY_LOGGERS.items():
        logging.getLogger(logger_name).setLevel(logger_level)
        logging.getLogger(logger_name).propagate = True

    _CONFIGURED = True



def get_logger(name: str) -> logging.Logger:
    """Return an application logger."""
    return logging.getLogger(name)
