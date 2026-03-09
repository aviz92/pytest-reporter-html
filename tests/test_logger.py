"""Tests for pytest_reporter_html.logger — ReportLogger."""
from __future__ import annotations

import logging

from pytest_reporter_html.logger import ReportLogger

stdlog = logging.getLogger(__name__)
stdlog.setLevel(logging.DEBUG)


class TestLogMethods:
    def test_info(self, reporter):
        stdlog.info("ReportLogger.info() creates an INFO-level event")
        rlog = ReportLogger(reporter)
        reporter.begin_step("s")
        rlog.info("hello")
        reporter.end_step(None)

        events = reporter._report.steps[0].events
        stdlog.debug(f"Event count: {len(events)}, level={events[0].level}, msg='{events[0].event}'")
        assert len(events) == 1
        assert events[0].level == "INFO"
        assert events[0].event == "hello"

    def test_debug(self, reporter):
        stdlog.info("ReportLogger.debug() creates a DEBUG-level event")
        rlog = ReportLogger(reporter)
        reporter.begin_step("s")
        rlog.debug("detail")
        reporter.end_step(None)

        stdlog.debug(f"Event level: {reporter._report.steps[0].events[0].level}")
        assert reporter._report.steps[0].events[0].level == "DEBUG"

    def test_warn(self, reporter):
        stdlog.info("ReportLogger.warn() creates a WARN-level event")
        rlog = ReportLogger(reporter)
        reporter.begin_step("s")
        rlog.warn("careful")
        reporter.end_step(None)

        stdlog.debug(f"Event level: {reporter._report.steps[0].events[0].level}")
        assert reporter._report.steps[0].events[0].level == "WARN"

    def test_warning_alias(self, reporter):
        stdlog.info("ReportLogger.warning() is an alias for warn()")
        rlog = ReportLogger(reporter)
        reporter.begin_step("s")
        rlog.warning("careful")
        reporter.end_step(None)

        stdlog.debug(f"Event level: {reporter._report.steps[0].events[0].level}")
        assert reporter._report.steps[0].events[0].level == "WARN"

    def test_error(self, reporter):
        stdlog.info("ReportLogger.error() creates an ERROR-level event")
        rlog = ReportLogger(reporter)
        reporter.begin_step("s")
        rlog.error("broken")
        reporter.end_step(None)

        stdlog.debug(f"Event level: {reporter._report.steps[0].events[0].level}")
        assert reporter._report.steps[0].events[0].level == "ERROR"

    def test_trace(self, reporter):
        stdlog.info("ReportLogger.trace() maps to DEBUG level")
        rlog = ReportLogger(reporter)
        reporter.begin_step("s")
        rlog.trace("very detailed")
        reporter.end_step(None)

        stdlog.debug(f"Event level: {reporter._report.steps[0].events[0].level}")
        assert reporter._report.steps[0].events[0].level == "DEBUG"


class TestSourceCapture:
    def test_captures_source_file_and_line(self, reporter):
        stdlog.info("Verify ReportLogger captures the caller's source file and line number")
        rlog = ReportLogger(reporter)
        reporter.begin_step("s")
        rlog.info("here")
        reporter.end_step(None)

        ev = reporter._report.steps[0].events[0]
        stdlog.debug(f"Source file='{ev.sourceFileName}', line={ev.sourceLineNumber}")
        assert ev.sourceFileName == "test_logger.py"
        assert isinstance(ev.sourceLineNumber, int)
        assert ev.sourceLineNumber > 0


class TestJsonDetection:
    def test_detects_json_object(self, reporter):
        stdlog.info("Log a JSON object string — type should be 'json'")
        rlog = ReportLogger(reporter)
        reporter.begin_step("s")
        rlog.info('{"key": "value"}')
        reporter.end_step(None)

        stdlog.debug(f"Detected type: {reporter._report.steps[0].events[0].type}")
        assert reporter._report.steps[0].events[0].type == "json"

    def test_detects_json_array(self, reporter):
        stdlog.info("Log a JSON array string — type should be 'json'")
        rlog = ReportLogger(reporter)
        reporter.begin_step("s")
        rlog.info('[1, 2, 3]')
        reporter.end_step(None)

        stdlog.debug(f"Detected type: {reporter._report.steps[0].events[0].type}")
        assert reporter._report.steps[0].events[0].type == "json"

    def test_non_json_has_no_type(self, reporter):
        stdlog.info("Log plain text — type should be None")
        rlog = ReportLogger(reporter)
        reporter.begin_step("s")
        rlog.info("plain text")
        reporter.end_step(None)

        stdlog.debug(f"Detected type: {reporter._report.steps[0].events[0].type}")
        assert reporter._report.steps[0].events[0].type is None

    def test_invalid_json_not_detected(self, reporter):
        stdlog.info("Log invalid JSON string — type should be None")
        rlog = ReportLogger(reporter)
        reporter.begin_step("s")
        rlog.info("{not valid json}")
        reporter.end_step(None)

        stdlog.debug(f"Detected type: {reporter._report.steps[0].events[0].type}")
        assert reporter._report.steps[0].events[0].type is None


class TestMultipleEvents:
    def test_events_ordered(self, reporter):
        stdlog.info("Log three messages sequentially — verify order is preserved")
        rlog = ReportLogger(reporter)
        reporter.begin_step("s")
        rlog.info("first")
        rlog.info("second")
        rlog.info("third")
        reporter.end_step(None)

        events = reporter._report.steps[0].events
        stdlog.debug(f"Event messages: {[e.event for e in events]}")
        assert len(events) == 3
        assert [e.event for e in events] == ["first", "second", "third"]
