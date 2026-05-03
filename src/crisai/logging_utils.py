from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_CONFIGURED = False

# Default MCP framework logger names routed to per-server log files.
_DEFAULT_MCP_FRAMEWORK_LOGGERS: list[str] = [
    "mcp",
    "mcp.server",
    "mcp.server.fastmcp",
    "mcp.server.lowlevel",
    "mcp.server.lowlevel.server",
]

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
    """Formats log records as JSON lines using ECS-inspired field names.

    Aligns with common log aggregation expectations (Elastic ECS ``log.*``,
    ``message``, ``timestamp`` / ``@timestamp``, ``error.stack_trace``) so
    files under ``CRISAI_LOG_DIR`` share one structure across the CLI and MCP
    servers.
    """

    def __init__(
        self,
        *,
        service_name: str = "crisai",
        service_component: str | None = None,
    ) -> None:
        super().__init__()
        self._service_name = service_name
        self._service_component = service_component

    def format(self, record: logging.LogRecord) -> str:
        service: dict[str, str] = {"name": self._service_name}
        if self._service_component:
            service["component"] = self._service_component

        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "log": {"level": record.levelname, "logger": record.name},
            "message": record.getMessage(),
            "service": service,
        }

        if record.exc_info:
            payload["error"] = {"stack_trace": self.formatException(record.exc_info)}

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
    file_handler.setFormatter(JsonFormatter(service_component="application"))
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


def append_json_log_line(
    log_file: Path,
    message: str,
    *,
    logger_name: str,
    level: str = "INFO",
    service_component: str | None = None,
    **extra: Any,
) -> None:
    """Append one structured JSON log line (same schema as :class:`JsonFormatter`).

    Use for MCP tool audit lines and other events that bypass the stdlib logger.

    Args:
        log_file: Destination file (JSON Lines, one object per line).
        message: Human-readable log body.
        logger_name: Logical logger identifier (e.g. ``crisai.mcp.workspace``).
        level: Severity label, typically ``INFO`` or ``WARNING``.
        service_component: Optional ``service.component`` for routing in dashboards.
        **extra: Additional top-level JSON fields (ECS custom fields pattern).
    """
    service: dict[str, str] = {"name": "crisai"}
    if service_component:
        service["component"] = service_component

    payload: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "log": {"level": level, "logger": logger_name},
        "message": message,
        "service": service,
    }
    if extra:
        payload.update(extra)

    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as file_obj:
        file_obj.write(json.dumps(payload, ensure_ascii=False) + "\n")


def configure_mcp_framework_logging(
    log_file: Path,
    *,
    service_component: str,
    logger_names: list[str] | None = None,
    handler_level: int = logging.WARNING,
) -> None:
    """Attach JSON file logging to MCP framework loggers for one server process.

    Mirrors the main app's structured file logs so ``*_mcp.log`` can be parsed
    with the same schema as ``crisai.log``.

    Args:
        log_file: MCP server log path (shared by the listed framework loggers).
        service_component: ``service.component`` value (e.g. ``workspace_mcp``).
        logger_names: Loggers to capture; defaults to FastMCP-related loggers.
        handler_level: Minimum level written to the file (default: warnings+).
    """
    names = logger_names or _DEFAULT_MCP_FRAMEWORK_LOGGERS
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = JsonFormatter(service_component=service_component)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(handler_level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(DropListToolsRequestFilter())

    for name in names:
        logger = logging.getLogger(name)
        logger.setLevel(handler_level)
        logger.handlers.clear()
        logger.addHandler(file_handler)
        logger.propagate = False
