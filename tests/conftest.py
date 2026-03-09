"""Shared fixtures for pytest-reporter-html tests."""
from __future__ import annotations

import pytest

from pytest_reporter_html.reporter import TestReporter
from pytest_reporter_html.types import ReportEvent, ReportStep, _now_millis


@pytest.fixture(autouse=True)
def _pytester_default_mode(request):
    """Ensure pytester sub-processes have report_mode=all unless overridden."""
    if "pytester" not in request.fixturenames:
        return
    pytester = request.getfixturevalue("pytester")
    pytester.makeini("[pytest]\nreport_mode = all\n")


@pytest.fixture
def reporter(tmp_path):
    """A TestReporter writing to a temp directory."""
    return TestReporter(
        test_name="test_example",
        class_name="TestSample",
        all_test_methods=["test_example", "test_other"],
        output_dir=str(tmp_path),
    )


@pytest.fixture
def sample_event():
    """A minimal ReportEvent."""
    return ReportEvent(
        startTime=_now_millis(),
        level="INFO",
        event="Something happened",
        sourceFileName="test_file.py",
        sourceLineNumber=42,
    )


@pytest.fixture
def sample_step(sample_event):
    """A ReportStep with one event."""
    return ReportStep(
        startTime=_now_millis(),
        endTime=_now_millis() + 100,
        name="Step 01: Do thing",
        status="PASSED",
        events=[sample_event],
    )
