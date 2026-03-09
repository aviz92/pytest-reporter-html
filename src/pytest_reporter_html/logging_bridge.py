"""
Bridge between Python's standard ``logging`` module and report events.

Attaches a ``logging.Handler`` that captures all log records (from any logger,
including ``custom-python-logger``) and forwards them as events to the active
test's report.

This means any library that uses Python's standard logging — including
``custom_python_logger.build_logger()`` — will have its output captured
in the JSON report automatically.
"""
from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Optional

from .types import ReportEvent, _now_millis

if TYPE_CHECKING:
    from .reporter import TestReporter

# Modules to skip — we don't want to capture logs from the reporter itself
# or from pytest internals.
_SKIP_LOGGERS = (
    "pytest_reporter_html",
    "_pytest",
    "pluggy",
)


class ReportLoggingHandler(logging.Handler):
    """
    A ``logging.Handler`` that forwards log records to the active
    ``TestReporter`` as ``ReportEvent`` instances.

    Attach to the root logger so *all* loggers are captured, including
    those created by ``custom-python-logger`` or plain ``logging.getLogger()``.
    """

    def __init__(self, reporter: TestReporter):
        super().__init__()
        self._reporter = reporter
        self._extra_skip: tuple[str, ...] = ()

    def emit(self, record: logging.LogRecord) -> None:
        skip = _SKIP_LOGGERS + self._extra_skip
        if any(record.name.startswith(prefix) for prefix in skip):
            return

        level = self._map_level(record)
        message = self.format(record) if self.formatter else record.getMessage()

        if record.exc_info and record.exc_info[1] is not None:
            import traceback as tb_mod
            exc_lines = tb_mod.format_exception(*record.exc_info)
            message = message + "\n" + "".join(exc_lines)

        event_type = getattr(record, "report_event_type", None) or self._detect_json(message)

        source_file = os.path.basename(record.pathname) if record.pathname else None
        source_line = record.lineno if record.lineno else None

        event = ReportEvent(
            startTime=_now_millis(),
            level=level,
            event=message,
            type=event_type,
            sourceFileName=source_file,
            sourceLineNumber=source_line,
        )
        self._reporter.add_event(event)

    @staticmethod
    def _map_level(record: logging.LogRecord) -> str:
        """Map Python log levels to report levels."""
        if record.levelno >= logging.ERROR:
            return "ERROR"
        if record.levelno >= logging.WARNING:
            return "WARN"
        if record.levelno >= logging.INFO:
            return "INFO"
        if record.levelno >= logging.DEBUG:
            return "DEBUG"
        return "TRACE"

    @staticmethod
    def _detect_json(message: str) -> Optional[str]:
        stripped = message.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or (
            stripped.startswith("[") and stripped.endswith("]")
        ):
            try:
                json.loads(stripped)
                return "json"
            except (json.JSONDecodeError, ValueError):
                pass
        return None


_LEVEL_MAP = {
    "TRACE": 1,
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARN": logging.WARNING,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


def attach_logging_bridge(
    reporter: TestReporter,
    *,
    log_level: str = "DEBUG",
    exclude_loggers: list[str] | None = None,
) -> ReportLoggingHandler:
    """
    Attach a ``ReportLoggingHandler`` to the root logger.
    Returns the handler so it can be removed later.
    """
    handler = ReportLoggingHandler(reporter)
    numeric_level = _LEVEL_MAP.get(log_level.upper(), logging.DEBUG)
    handler.setLevel(numeric_level)

    if exclude_loggers:
        handler._extra_skip = tuple(exclude_loggers)

    logging.getLogger().addHandler(handler)
    return handler


def detach_logging_bridge(handler: ReportLoggingHandler) -> None:
    """Remove the handler from the root logger."""
    logging.getLogger().removeHandler(handler)
