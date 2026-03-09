"""Tests for pytest_reporter_html.reporter — TestReporter lifecycle."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

from pytest_reporter_html.reporter import TestReporter
from pytest_reporter_html.types import ReportEvent, _now_millis

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class TestReporterInit:
    def test_stores_attributes(self, tmp_path):
        log.info("Create TestReporter with test_name='test_foo', class_name='TestBar'")
        r = TestReporter(
            test_name="test_foo",
            class_name="TestBar",
            all_test_methods=["test_foo"],
            output_dir=str(tmp_path),
        )
        log.debug(f"Stored test_name={r.test_name}, class_name={r.class_name}")
        assert r.test_name == "test_foo"
        assert r.class_name == "TestBar"

    def test_default_report_status(self, reporter):
        log.info("Verify fresh reporter defaults to PASSED status")
        log.debug(f"Initial status: {reporter._report.testStatus}")
        assert reporter._report.testStatus == "PASSED"

    def test_class_name_stored_in_report(self, reporter):
        log.info("Verify className is stored in the internal report object")
        log.debug(f"className: {reporter._report.className}")
        assert reporter._report.className == "TestSample"


class TestStepLifecycle:
    def test_begin_end_step_creates_passed_step(self, reporter):
        log.info("Begin and end a step — verify PASSED step is created")
        reporter.begin_step("do thing")
        reporter.end_step(None)

        step = reporter._report.steps[0]
        log.debug(f"Step name='{step.name}', status={step.status}, duration={step.endTime - step.startTime}ms")
        assert len(reporter._report.steps) == 1
        assert step.name == "Step 01: do thing"
        assert step.status == "PASSED"
        assert step.endTime >= step.startTime

    def test_step_counter_increments(self, reporter):
        log.info("Create two sequential steps — verify counter increments 01, 02")
        reporter.begin_step("first")
        reporter.end_step(None)
        reporter.begin_step("second")
        reporter.end_step(None)

        log.debug(f"Step names: {[s.name for s in reporter._report.steps]}")
        assert reporter._report.steps[0].name == "Step 01: first"
        assert reporter._report.steps[1].name == "Step 02: second"

    def test_begin_step_closes_previous(self, reporter):
        log.info("Begin a new step without ending the previous — auto-close behavior")
        reporter.begin_step("one")
        reporter.begin_step("two")
        reporter.end_step(None)

        log.debug(f"Total steps: {len(reporter._report.steps)}")
        assert len(reporter._report.steps) == 2
        assert reporter._report.steps[0].name == "Step 01: one"
        assert reporter._report.steps[1].name == "Step 02: two"

    def test_failed_step(self, reporter):
        log.info("End a step with an exception — verify FAILED status and failure message")
        reporter.begin_step("will fail")
        reporter.end_step(ValueError("bad input"))

        step = reporter._report.steps[0]
        log.debug(f"Step status={step.status}, failureMessage='{step.failureMessage}'")
        assert step.status == "FAILED"
        assert step.failureMessage == "bad input"


class TestPhaseLifecycle:
    def test_empty_passed_setup_removed(self, reporter):
        log.info("Empty PASSED Setup phase should be auto-removed")
        reporter.begin_phase("Setup")
        reporter.end_phase(None)

        log.debug(f"Steps after empty Setup: {len(reporter._report.steps)}")
        assert len(reporter._report.steps) == 0

    def test_empty_passed_teardown_removed(self, reporter):
        log.info("Empty PASSED Teardown phase should be auto-removed")
        reporter.begin_phase("Teardown")
        reporter.end_phase(None)

        log.debug(f"Steps after empty Teardown: {len(reporter._report.steps)}")
        assert len(reporter._report.steps) == 0

    def test_setup_with_events_kept(self, reporter):
        log.info("Setup phase with events should be preserved")
        reporter.begin_phase("Setup")
        ev = ReportEvent(startTime=_now_millis(), level="INFO", event="fixture init")
        reporter.add_event(ev)
        reporter.end_phase(None)

        log.debug(f"Steps: {len(reporter._report.steps)}, name='{reporter._report.steps[0].name}'")
        assert len(reporter._report.steps) == 1
        assert reporter._report.steps[0].name == "Setup"

    def test_failed_setup_kept(self, reporter):
        log.info("FAILED Setup phase should always be preserved")
        reporter.begin_phase("Setup")
        reporter.end_phase(RuntimeError("setup boom"))

        log.debug(f"Step status: {reporter._report.steps[0].status}")
        assert len(reporter._report.steps) == 1
        assert reporter._report.steps[0].status == "FAILED"

    def test_non_lifecycle_phase_always_kept(self, reporter):
        log.info("Non-lifecycle phase (test function name) is always kept even if empty")
        reporter.begin_phase("test_my_func")
        reporter.end_phase(None)

        log.debug(f"Step name: '{reporter._report.steps[0].name}'")
        assert len(reporter._report.steps) == 1
        assert reporter._report.steps[0].name == "test_my_func"


class TestAddEvent:
    def test_event_added_to_current_step(self, reporter, sample_event):
        log.info("Add event to an open step — verify it's captured")
        reporter.begin_step("my step")
        reporter.add_event(sample_event)
        reporter.end_step(None)

        log.debug(f"Events in step: {len(reporter._report.steps[0].events)}")
        assert len(reporter._report.steps[0].events) == 1
        assert reporter._report.steps[0].events[0].event == "Something happened"

    def test_event_without_step_creates_implicit_step(self, reporter, sample_event):
        log.info("Add event without open step — implicit step created with test name")
        reporter.add_event(sample_event)

        log.debug(f"Implicit step name: '{reporter._report.steps[0].name}'")
        assert len(reporter._report.steps) == 1
        assert reporter._report.steps[0].name == "test_example"
        assert len(reporter._report.steps[0].events) == 1

    def test_multiple_events_in_step(self, reporter):
        log.info("Add 5 events to a single step — verify count")
        reporter.begin_step("collect")
        for i in range(5):
            ev = ReportEvent(startTime=_now_millis(), level="DEBUG", event=f"msg-{i}")
            reporter.add_event(ev)
        reporter.end_step(None)

        log.debug(f"Event count: {len(reporter._report.steps[0].events)}")
        assert len(reporter._report.steps[0].events) == 5


class TestFinalize:
    def test_writes_json_file(self, reporter, tmp_path):
        log.info("Finalize reporter — verify JSON file is written to disk")
        reporter.begin_step("s1")
        reporter.end_step(None)
        path = reporter.finalize(status="PASSED")

        json_file = Path(path)
        log.debug(f"JSON path: {json_file}, exists={json_file.exists()}")
        assert path is not None
        assert json_file.exists()
        assert json_file.suffix == ".json"

        data = json.loads(json_file.read_text())
        assert data["testStatus"] == "PASSED"
        assert len(data["steps"]) == 1

    def test_finalize_with_failure(self, reporter, tmp_path):
        log.info("Finalize with FAILED status — verify failure fields in JSON")
        reporter.begin_step("fail")
        reporter.end_step(None)
        path = reporter.finalize(
            status="FAILED",
            failure_message="assertion error",
            stack_trace="Traceback...",
        )

        data = json.loads(Path(path).read_text())
        log.debug(f"Status={data['testStatus']}, failureMessage='{data['failureMessage']}'")
        assert data["testStatus"] == "FAILED"
        assert data["failureMessage"] == "assertion error"
        assert data["stackTrace"] == "Traceback..."

    def test_finalize_closes_dangling_step(self, reporter, tmp_path):
        log.info("Finalize with an open step — verify it's auto-closed")
        reporter.begin_step("open step")
        path = reporter.finalize(status="PASSED")

        data = json.loads(Path(path).read_text())
        log.debug(f"Auto-closed step: '{data['steps'][0]['name']}'")
        assert len(data["steps"]) == 1
        assert data["steps"][0]["name"] == "Step 01: open step"

    def test_json_file_in_json_subdir(self, reporter, tmp_path):
        log.info("Verify JSON file is written inside a 'json' subdirectory")
        path = reporter.finalize(status="PASSED")
        log.debug(f"Path: {path}")
        assert "/json/" in path or "\\json\\" in path

    def test_class_name_in_json(self, reporter, tmp_path):
        log.info("Verify className field is present in finalized JSON")
        path = reporter.finalize(status="PASSED")
        data = json.loads(Path(path).read_text())
        log.debug(f"className: {data['className']}")
        assert data["className"] == "TestSample"

    def test_all_test_methods_in_json(self, reporter, tmp_path):
        log.info("Verify AllTestMethods list is preserved in JSON output")
        path = reporter.finalize(status="PASSED")
        data = json.loads(Path(path).read_text())
        log.debug(f"AllTestMethods: {data['AllTestMethods']}")
        assert data["AllTestMethods"] == ["test_example", "test_other"]


class TestResolveTimestamp:
    def test_uses_env_var_when_set(self):
        log.info("Set REPORT_TIMESTAMP env var — verify reporter uses it")
        with patch.dict("os.environ", {"REPORT_TIMESTAMP": "12345"}):
            r = TestReporter("t", None, [], "/tmp")
            log.debug(f"Resolved timestamp: {r._timestamp}")
            assert r._timestamp == "12345"

    def test_falls_back_to_epoch_millis(self):
        log.info("No REPORT_TIMESTAMP env var — verify fallback to epoch millis")
        with patch.dict("os.environ", {}, clear=True):
            r = TestReporter("t", None, [], "/tmp")
            log.debug(f"Fallback timestamp: {r._timestamp}")
            assert r._timestamp.isdigit()
            assert int(r._timestamp) > 0
