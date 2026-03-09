"""Tests for pytest_reporter_html.logging_bridge — log capture."""
from __future__ import annotations

import logging
import sys

from pytest_reporter_html.logging_bridge import (
    ReportLoggingHandler,
    attach_logging_bridge,
    detach_logging_bridge,
)
from pytest_reporter_html.types import _now_millis

stdlog = logging.getLogger(__name__)
stdlog.setLevel(logging.DEBUG)


class TestReportLoggingHandler:
    def test_captures_info(self, reporter):
        stdlog.info("Emit INFO LogRecord via handler — verify event is captured")
        reporter.begin_phase("test")
        handler = ReportLoggingHandler(reporter)
        handler.setLevel(1)

        record = logging.LogRecord(
            name="myapp",
            level=logging.INFO,
            pathname="app.py",
            lineno=10,
            msg="hello from app",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        reporter.end_phase(None)

        events = reporter._report.steps[0].events
        stdlog.debug(f"Captured event: level={events[0].level}, msg='{events[0].event}', file={events[0].sourceFileName}")
        assert len(events) == 1
        assert events[0].level == "INFO"
        assert events[0].event == "hello from app"
        assert events[0].sourceFileName == "app.py"
        assert events[0].sourceLineNumber == 10

    def test_skips_internal_loggers(self, reporter):
        stdlog.info("Emit from internal loggers (pytest_reporter_html, _pytest, pluggy) — should be skipped")
        reporter.begin_phase("test_body")
        handler = ReportLoggingHandler(reporter)

        for name in ("pytest_reporter_html.plugin", "_pytest.config", "pluggy"):
            record = logging.LogRecord(
                name=name, level=logging.INFO,
                pathname="x.py", lineno=1,
                msg="internal", args=(), exc_info=None,
            )
            handler.emit(record)

        reporter.end_phase(None)
        stdlog.debug(f"Events captured: {len(reporter._report.steps[0].events)} (expected 0)")
        assert len(reporter._report.steps) == 1
        assert len(reporter._report.steps[0].events) == 0

    def test_extra_skip_loggers(self, reporter):
        stdlog.info("Configure extra skip loggers (urllib3, botocore) — messages should be ignored")
        reporter.begin_phase("test_body")
        handler = ReportLoggingHandler(reporter)
        handler._extra_skip = ("urllib3", "botocore")

        record = logging.LogRecord(
            name="urllib3.connectionpool",
            level=logging.DEBUG,
            pathname="pool.py", lineno=5,
            msg="request", args=(), exc_info=None,
        )
        handler.emit(record)
        reporter.end_phase(None)

        stdlog.debug(f"Events captured: {len(reporter._report.steps[0].events)} (expected 0)")
        assert len(reporter._report.steps) == 1
        assert len(reporter._report.steps[0].events) == 0


class TestLevelMapping:
    def _emit_at_level(self, reporter, level):
        reporter.begin_phase("test")
        handler = ReportLoggingHandler(reporter)
        handler.setLevel(1)
        record = logging.LogRecord(
            name="app", level=level,
            pathname="a.py", lineno=1,
            msg="msg", args=(), exc_info=None,
        )
        handler.emit(record)
        reporter.end_phase(None)
        return reporter._report.steps[0].events[0].level

    def test_error_level(self, reporter):
        stdlog.info("Map logging.ERROR → report 'ERROR'")
        result = self._emit_at_level(reporter, logging.ERROR)
        stdlog.debug(f"Mapped level: {result}")
        assert result == "ERROR"

    def test_warning_level(self, reporter):
        stdlog.info("Map logging.WARNING → report 'WARN'")
        result = self._emit_at_level(reporter, logging.WARNING)
        stdlog.debug(f"Mapped level: {result}")
        assert result == "WARN"

    def test_info_level(self, reporter):
        stdlog.info("Map logging.INFO → report 'INFO'")
        result = self._emit_at_level(reporter, logging.INFO)
        stdlog.debug(f"Mapped level: {result}")
        assert result == "INFO"

    def test_debug_level(self, reporter):
        stdlog.info("Map logging.DEBUG → report 'DEBUG'")
        result = self._emit_at_level(reporter, logging.DEBUG)
        stdlog.debug(f"Mapped level: {result}")
        assert result == "DEBUG"

    def test_trace_level(self, reporter):
        stdlog.info("Map level=5 (TRACE) → report 'TRACE'")
        result = self._emit_at_level(reporter, 5)
        stdlog.debug(f"Mapped level: {result}")
        assert result == "TRACE"


class TestExceptionCapture:
    def test_captures_traceback(self, reporter):
        stdlog.info("Emit LogRecord with exc_info — verify traceback is appended to event text")
        reporter.begin_phase("test")
        handler = ReportLoggingHandler(reporter)
        handler.setLevel(1)

        try:
            raise ValueError("test error")
        except ValueError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="myapp", level=logging.ERROR,
            pathname="app.py", lineno=50,
            msg="something failed", args=(),
            exc_info=exc_info,
        )
        handler.emit(record)
        reporter.end_phase(None)

        event = reporter._report.steps[0].events[0]
        stdlog.debug(f"Event text contains traceback: {'Traceback' in event.event}")
        assert "something failed" in event.event
        assert "Traceback (most recent call last):" in event.event
        assert "ValueError: test error" in event.event

    def test_no_traceback_without_exc_info(self, reporter):
        stdlog.info("Emit LogRecord without exc_info — no traceback appended")
        reporter.begin_phase("test")
        handler = ReportLoggingHandler(reporter)
        handler.setLevel(1)

        record = logging.LogRecord(
            name="myapp", level=logging.ERROR,
            pathname="app.py", lineno=50,
            msg="plain error", args=(),
            exc_info=None,
        )
        handler.emit(record)
        reporter.end_phase(None)

        event = reporter._report.steps[0].events[0]
        stdlog.debug(f"Event text: '{event.event}'")
        assert event.event == "plain error"
        assert "Traceback" not in event.event


class TestJsonDetection:
    def _emit_message(self, reporter, msg):
        reporter.begin_phase("test")
        handler = ReportLoggingHandler(reporter)
        handler.setLevel(1)
        record = logging.LogRecord(
            name="app", level=logging.INFO,
            pathname="a.py", lineno=1,
            msg=msg, args=(), exc_info=None,
        )
        handler.emit(record)
        reporter.end_phase(None)
        return reporter._report.steps[0].events[0].type

    def test_detects_json_object(self, reporter):
        stdlog.info("Log JSON object string via bridge — type should be 'json'")
        result = self._emit_message(reporter, '{"a": 1}')
        stdlog.debug(f"Detected type: {result}")
        assert result == "json"

    def test_detects_json_array(self, reporter):
        stdlog.info("Log JSON array string via bridge — type should be 'json'")
        result = self._emit_message(reporter, '[1, 2]')
        stdlog.debug(f"Detected type: {result}")
        assert result == "json"

    def test_plain_text_no_type(self, reporter):
        stdlog.info("Log plain text via bridge — type should be None")
        result = self._emit_message(reporter, "hello")
        stdlog.debug(f"Detected type: {result}")
        assert result is None


class TestAttachDetach:
    def test_attach_adds_handler_to_root(self, reporter):
        stdlog.info("attach_logging_bridge() adds handler to root logger")
        root = logging.getLogger()
        before = len(root.handlers)

        handler = attach_logging_bridge(reporter)
        after = len(root.handlers)
        stdlog.debug(f"Handlers before={before}, after={after}")
        assert after == before + 1

        detach_logging_bridge(handler)
        stdlog.debug(f"Handlers after detach: {len(root.handlers)}")
        assert len(root.handlers) == before

    def test_attach_with_log_level(self, reporter):
        stdlog.info("Attach with log_level='ERROR' — handler level should be ERROR")
        handler = attach_logging_bridge(reporter, log_level="ERROR")
        stdlog.debug(f"Handler level: {handler.level} (expected {logging.ERROR})")
        assert handler.level == logging.ERROR
        detach_logging_bridge(handler)

    def test_attach_with_trace_level(self, reporter):
        stdlog.info("Attach with log_level='TRACE' — handler level should be 1")
        handler = attach_logging_bridge(reporter, log_level="TRACE")
        stdlog.debug(f"Handler level: {handler.level}")
        assert handler.level == 1
        detach_logging_bridge(handler)

    def test_attach_with_exclude_loggers(self, reporter):
        stdlog.info("Attach with exclude_loggers=['noisy', 'spam'] — stored in _extra_skip")
        handler = attach_logging_bridge(
            reporter, exclude_loggers=["noisy", "spam"]
        )
        stdlog.debug(f"_extra_skip: {handler._extra_skip}")
        assert handler._extra_skip == ("noisy", "spam")
        detach_logging_bridge(handler)

    def test_integration_with_real_logger(self, reporter):
        stdlog.info("End-to-end: attach bridge, emit via real logger, verify capture")
        reporter.begin_phase("test")
        handler = attach_logging_bridge(reporter)

        app_logger = logging.getLogger("test_app_integration")
        app_logger.setLevel(logging.DEBUG)
        app_logger.info("captured message")

        detach_logging_bridge(handler)
        reporter.end_phase(None)

        events = reporter._report.steps[0].events
        captured = [e.event for e in events]
        stdlog.debug(f"Captured messages: {captured}")
        assert any(e.event == "captured message" for e in events)
