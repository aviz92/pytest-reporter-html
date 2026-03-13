"""Tests for pytest_reporter_html.helpers."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from pytest_reporter_html.helpers import (
    _extract_failure,
    _module_label,
    _now_millis,
    _worse,
)


class TestNowMillis:
    def test_returns_int(self) -> None:
        result = _now_millis()
        assert isinstance(result, int), f"Expected int, got {type(result)}"

    def test_is_close_to_current_time(self) -> None:
        before = int(time.time() * 1000)
        result = _now_millis()
        after = int(time.time() * 1000)
        assert before <= result <= after, f"_now_millis() {result} is not between {before} and {after}"

    def test_monotonically_increases(self) -> None:
        t1 = _now_millis()
        t2 = _now_millis()
        assert t2 >= t1, f"Second call {t2} should be >= first call {t1}"


class TestWorse:
    @pytest.mark.parametrize(
        "a,b,expected",
        [
            ("PASSED", "FAILED", "FAILED"),
            ("FAILED", "PASSED", "FAILED"),
            ("PASSED", "SKIPPED", "SKIPPED"),
            ("SKIPPED", "PASSED", "SKIPPED"),
            ("FAILED", "ERROR", "ERROR"),
            ("ERROR", "FAILED", "ERROR"),
            ("PASSED", "PASSED", "PASSED"),
            ("ERROR", "ERROR", "ERROR"),
            ("PASSED", "ERROR", "ERROR"),
        ],
    )
    def test_returns_more_severe_status(self, a: str, b: str, expected: str) -> None:
        result = _worse(a, b)
        assert result == expected, f"_worse({a!r}, {b!r}) should be {expected!r}, got {result!r}"


class TestExtractFailure:
    def test_extracts_from_repr_crash(self) -> None:
        mock_crash = MagicMock()
        mock_crash.message = "AssertionError: expected True"
        longrepr = MagicMock()
        longrepr.reprcrash = mock_crash

        report = MagicMock(spec=pytest.TestReport)
        report.longrepr = longrepr

        msg, trace = _extract_failure(report)
        assert msg == "AssertionError: expected True", f"Expected crash message, got {msg!r}"
        assert trace == str(longrepr), f"Expected str(longrepr) as trace, got {trace!r}"

    def test_extracts_from_string_longrepr(self) -> None:
        report = MagicMock(spec=pytest.TestReport)
        report.longrepr = "plain string traceback"

        msg, trace = _extract_failure(report)
        assert msg == "plain string traceback", f"Expected string repr, got {msg!r}"
        assert trace == "plain string traceback", f"Expected string repr as trace, got {trace!r}"

    def test_returns_tuple_of_two_strings(self) -> None:
        report = MagicMock(spec=pytest.TestReport)
        report.longrepr = "some error"
        result = _extract_failure(report)
        assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
        assert len(result) == 2, f"Expected 2-tuple, got length {len(result)}"
        assert all(isinstance(s, str) for s in result), "Both elements must be strings"


class TestModuleLabel:
    def test_returns_class_label_when_cls_is_set(self) -> None:
        item = MagicMock()
        item.cls = MagicMock()
        item.cls.__name__ = "MyTestClass"
        item.module.__name__ = "tests.test_module"

        result = _module_label(item)
        assert result == "tests.test_module.MyTestClass", f"Expected 'tests.test_module.MyTestClass', got {result!r}"

    def test_returns_module_name_when_no_cls(self) -> None:
        item = MagicMock()
        item.cls = None
        item.module.__name__ = "tests.test_module"

        result = _module_label(item)
        assert result == "tests.test_module", f"Expected 'tests.test_module', got {result!r}"

    def test_returns_none_when_module_has_no_name(self) -> None:
        item = MagicMock()
        item.cls = None
        # Use a spec-constrained mock with no __name__ attribute
        item.module = MagicMock(spec=[])

        result = _module_label(item)
        assert result is None, f"Expected None when module has no __name__, got {result!r}"
