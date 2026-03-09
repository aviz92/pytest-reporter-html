"""Tests for pytest_reporter_html.types — dataclass serialization."""
from __future__ import annotations

import logging

from pytest_reporter_html.types import JsonReport, ReportEvent, ReportStep, _now_millis

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class TestReportEvent:
    def test_to_dict_required_fields(self):
        log.info("Create ReportEvent with required fields only (startTime, level, event)")
        ev = ReportEvent(startTime=1000, level="INFO", event="hello")
        d = ev.to_dict()
        log.debug(f"Serialized dict: {d}")
        assert d == {"startTime": 1000, "level": "INFO", "event": "hello"}

    def test_to_dict_with_optional_fields(self):
        log.info("Create ReportEvent with all optional fields (type, sourceFileName, sourceLineNumber)")
        ev = ReportEvent(
            startTime=1000,
            level="ERROR",
            event="fail",
            type="json",
            sourceFileName="app.py",
            sourceLineNumber=99,
        )
        d = ev.to_dict()
        log.debug(f"Optional fields present: type={d['type']}, file={d['sourceFileName']}, line={d['sourceLineNumber']}")
        assert d["type"] == "json"
        assert d["sourceFileName"] == "app.py"
        assert d["sourceLineNumber"] == 99

    def test_to_dict_omits_none_optionals(self):
        log.info("Verify None optional fields are omitted from serialized dict")
        ev = ReportEvent(startTime=1000, level="DEBUG", event="x")
        d = ev.to_dict()
        log.debug(f"Keys in dict: {list(d.keys())}")
        assert "type" not in d
        assert "sourceFileName" not in d
        assert "sourceLineNumber" not in d


class TestReportStep:
    def test_defaults(self):
        log.info("Create ReportStep with only startTime — verify all defaults")
        step = ReportStep(startTime=5000)
        log.debug(f"endTime={step.endTime}, name='{step.name}', status={step.status}, events={step.events}")
        assert step.endTime == 0
        assert step.name == ""
        assert step.status == "PASSED"
        assert step.events == []
        assert step.failureMessage is None
        assert step.stackTrace is None

    def test_to_dict_minimal(self):
        log.info("Serialize a minimal PASSED step to dict")
        step = ReportStep(startTime=5000, endTime=5100, name="s1", status="PASSED")
        d = step.to_dict()
        log.debug(f"Serialized keys: {list(d.keys())}")
        assert d["startTime"] == 5000
        assert d["endTime"] == 5100
        assert d["name"] == "s1"
        assert d["status"] == "PASSED"
        assert d["events"] == []
        assert "failureMessage" not in d
        assert "stackTrace" not in d

    def test_to_dict_with_failure(self):
        log.info("Serialize a FAILED step with failure message and stack trace")
        step = ReportStep(
            startTime=5000,
            endTime=5200,
            name="broken",
            status="FAILED",
            failureMessage="assertion failed",
            stackTrace="Traceback ...",
        )
        d = step.to_dict()
        log.debug(f"Failure info: message='{d['failureMessage']}', trace present={bool(d.get('stackTrace'))}")
        assert d["status"] == "FAILED"
        assert d["failureMessage"] == "assertion failed"
        assert d["stackTrace"] == "Traceback ..."

    def test_to_dict_serializes_events(self):
        log.info("Verify events inside a step are serialized in to_dict()")
        ev = ReportEvent(startTime=5010, level="INFO", event="hi")
        step = ReportStep(startTime=5000, events=[ev])
        d = step.to_dict()
        log.debug(f"Event count: {len(d['events'])}, first event: {d['events'][0]['event']}")
        assert len(d["events"]) == 1
        assert d["events"][0]["event"] == "hi"


class TestJsonReport:
    def test_defaults(self):
        log.info("Create JsonReport with defaults — check initial state")
        report = JsonReport()
        log.debug(f"status={report.testStatus}, steps={len(report.steps)}, methods={report.AllTestMethods}")
        assert report.testStatus == "PASSED"
        assert report.steps == []
        assert report.AllTestMethods == []
        assert report.className is None

    def test_to_dict_minimal(self):
        log.info("Serialize minimal JsonReport — verify optional fields are omitted")
        report = JsonReport(AllTestMethods=["test_a"])
        d = report.to_dict()
        log.debug(f"Dict keys: {list(d.keys())}")
        assert d["testStatus"] == "PASSED"
        assert d["AllTestMethods"] == ["test_a"]
        assert d["steps"] == []
        assert "className" not in d
        assert "failureMessage" not in d
        assert "stackTrace" not in d
        assert "externalTestReportLink" not in d

    def test_to_dict_with_all_fields(self):
        log.info("Serialize JsonReport with all fields populated")
        step = ReportStep(startTime=1000, endTime=1100, name="s")
        report = JsonReport(
            steps=[step],
            AllTestMethods=["test_a", "test_b"],
            testStatus="FAILED",
            className="TestFoo",
            failureMessage="boom",
            stackTrace="line 1\nline 2",
            externalTestReportLink="https://example.com/report",
        )
        d = report.to_dict()
        log.debug(f"Status={d['testStatus']}, className={d['className']}, steps={len(d['steps'])}")
        assert d["testStatus"] == "FAILED"
        assert d["className"] == "TestFoo"
        assert d["failureMessage"] == "boom"
        assert d["stackTrace"] == "line 1\nline 2"
        assert d["externalTestReportLink"] == "https://example.com/report"
        assert len(d["steps"]) == 1

    def test_to_dict_steps_are_serialized(self):
        log.info("Verify nested step events are serialized through JsonReport.to_dict()")
        ev = ReportEvent(startTime=100, level="WARN", event="careful")
        step = ReportStep(startTime=100, endTime=200, name="s", events=[ev])
        report = JsonReport(steps=[step])
        d = report.to_dict()
        log.debug(f"Nested event level: {d['steps'][0]['events'][0]['level']}")
        assert d["steps"][0]["events"][0]["level"] == "WARN"


class TestNowMillis:
    def test_returns_positive_int(self):
        log.info("Verify _now_millis returns a positive integer")
        ts = _now_millis()
        log.debug(f"Timestamp: {ts}")
        assert isinstance(ts, int)
        assert ts > 0

    def test_monotonic(self):
        log.info("Verify two consecutive _now_millis calls are monotonically ordered")
        t1 = _now_millis()
        t2 = _now_millis()
        log.debug(f"t1={t1}, t2={t2}, diff={t2 - t1}")
        assert t2 >= t1
