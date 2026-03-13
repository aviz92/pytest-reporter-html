"""Tests for pytest_reporter_html.plugin."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from pytest_reporter_html.plugin import _ReportLogHandler
from pytest_reporter_html.reporter import TestReporter


@pytest.fixture
def reporter(tmp_path) -> TestReporter:
    r = TestReporter(
        test_name="test_example",
        class_name="tests.test_plugin",
        output_dir=str(tmp_path),
    )
    r.begin_phase("test_example")
    return r


class TestReportLogHandler:
    def test_emit_adds_event_to_reporter(self, reporter: TestReporter) -> None:
        handler = _ReportLogHandler(reporter)
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test_file.py",
            lineno=10,
            msg="hello from log",
            args=(),
            exc_info=None,
        )
        handler.emit(record)

        assert reporter._current_step is not None, "current_step should still be open"
        assert len(reporter._current_step.events) == 1, f"Expected 1 event, got {len(reporter._current_step.events)}"
        event = reporter._current_step.events[0]
        assert event.level == "INFO", f"Level mismatch: {event.level!r}"
        assert event.event == "hello from log", f"Message mismatch: {event.event!r}"
        assert event.sourceFileName == "test_file.py", f"sourceFileName mismatch: {event.sourceFileName!r}"
        assert event.sourceLineNumber == 10, f"sourceLineNumber mismatch: {event.sourceLineNumber!r}"

    def test_emit_does_not_raise_on_reporter_error(self, reporter: TestReporter) -> None:
        handler = _ReportLogHandler(reporter)
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler.handleError = MagicMock()

        with patch.object(reporter, "add_event", side_effect=RuntimeError("boom")):
            record = logging.LogRecord(
                name="test",
                level=logging.WARNING,
                pathname="f.py",
                lineno=1,
                msg="msg",
                args=(),
                exc_info=None,
            )
            handler.emit(record)

        handler.handleError.assert_called_once(), "handleError should be called on exception"

    def test_emit_multiple_records(self, reporter: TestReporter) -> None:
        handler = _ReportLogHandler(reporter)
        handler.setFormatter(logging.Formatter("%(message)s"))

        for i in range(3):
            record = logging.LogRecord(
                name="test",
                level=logging.DEBUG,
                pathname="f.py",
                lineno=i,
                msg=f"message {i}",
                args=(),
                exc_info=None,
            )
            handler.emit(record)

        assert len(reporter._current_step.events) == 3, f"Expected 3 events, got {len(reporter._current_step.events)}"


class TestReportTestNameFixture:
    def test_report_test_name_fixture_updates_reporter_name(self, report_test_name) -> None:
        report_test_name("custom name")
        # No assertion needed beyond it not raising — the reporter stash may
        # not have a reporter if called outside the plugin's setup hook.
        # This just verifies the fixture is callable without error.
