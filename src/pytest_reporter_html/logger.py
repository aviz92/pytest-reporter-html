"""
Report logger for pytest.

Provides ``log.info()``, ``log.debug()``, ``log.warn()``, ``log.error()``
that capture events into the active step of the current test report.

Source file name and line number are captured automatically via
``inspect.stack()``.
"""
from __future__ import annotations

import inspect
import json
import os
from typing import TYPE_CHECKING, Optional

from .types import ReportEvent, _now_millis

if TYPE_CHECKING:
    from .reporter import TestReporter

# Packages to skip when walking the stack to find the real caller.
_SKIP_PACKAGES = (
    "pytest_reporter_html",
    "pluggy",
    "_pytest",
    "pytest",
)


class ReportLogger:
    """
    Logger bound to a test's report.

    Created per-test by the plugin and injected as the ``log`` fixture.
    Events are routed to the reporter's current step.
    """

    def __init__(self, reporter: TestReporter):
        self._reporter = reporter

    # ---- public API (matches JUnit reporter) ----

    def info(self, message: str) -> None:
        self._log("INFO", message)

    def debug(self, message: str) -> None:
        self._log("DEBUG", message)

    def warn(self, message: str) -> None:
        self._log("WARN", message)

    def warning(self, message: str) -> None:
        self._log("WARN", message)

    def error(self, message: str) -> None:
        self._log("ERROR", message)

    def trace(self, message: str) -> None:
        self._log("DEBUG", message)

    # ---- internals ----

    def _log(self, level: str, message: str) -> None:
        source = self._capture_source()
        event_type = self._detect_json(message)

        event = ReportEvent(
            startTime=_now_millis(),
            level=level,
            event=message,
            type=event_type,
            sourceFileName=source[0],
            sourceLineNumber=source[1],
        )
        self._reporter.add_event(event)

    @staticmethod
    def _capture_source() -> tuple[Optional[str], Optional[int]]:
        """Walk the stack to find the caller outside this package."""
        try:
            for frame_info in inspect.stack():
                module = frame_info.frame.f_globals.get("__name__", "")
                if any(module.startswith(pkg) for pkg in _SKIP_PACKAGES):
                    continue
                filename = os.path.basename(frame_info.filename)
                return filename, frame_info.lineno
        except Exception:
            pass
        return None, None

    @staticmethod
    def _detect_json(message: str) -> Optional[str]:
        """Return ``'json'`` if a message looks like JSON, else ``None``."""
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
