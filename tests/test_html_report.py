"""Tests for pytest_reporter_html.html_report — HTML generation and helpers."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from pytest_reporter_html.html_report import (
    _escape_html,
    _format_class_name,
    _format_test_name,
    _format_try_number,
    _parse_test_result,
    generate_report,
)

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class TestEscapeHtml:
    def test_escapes_ampersand(self):
        log.info("_escape_html: '&' → '&amp;'")
        result = _escape_html("a & b")
        log.debug(f"Result: '{result}'")
        assert result == "a &amp; b"

    def test_escapes_angle_brackets(self):
        log.info("_escape_html: '<div>' → '&lt;div&gt;'")
        result = _escape_html("<div>")
        log.debug(f"Result: '{result}'")
        assert result == "&lt;div&gt;"

    def test_escapes_quotes(self):
        log.info("_escape_html: double and single quotes are escaped")
        r1 = _escape_html('"hello"')
        r2 = _escape_html("it's")
        log.debug(f"Double: '{r1}', Single: '{r2}'")
        assert r1 == "&quot;hello&quot;"
        assert r2 == "it&#39;s"

    def test_none_returns_empty(self):
        log.info("_escape_html(None) returns empty string")
        assert _escape_html(None) == ""

    def test_plain_text_unchanged(self):
        log.info("_escape_html: plain text passes through unchanged")
        assert _escape_html("hello world") == "hello world"


class TestFormatTestName:
    def test_strips_test_prefix(self):
        log.info("_format_test_name: strip 'test_' prefix and capitalize")
        result = _format_test_name("test_login_success")
        log.debug(f"Result: '{result}'")
        assert result == "Login success"

    def test_camel_case_split(self):
        log.info("_format_test_name: split camelCase into words")
        result = _format_test_name("testLoginSuccess")
        log.debug(f"Result: '{result}'")
        assert result == "Test Login Success"

    def test_empty_string(self):
        log.info("_format_test_name: empty string returns empty")
        assert _format_test_name("") == ""

    def test_just_test_prefix(self):
        log.info("_format_test_name: 'test_' alone returns a string")
        result = _format_test_name("test_")
        log.debug(f"Result: '{result}'")
        assert isinstance(result, str)

    def test_underscores_to_spaces(self):
        log.info("_format_test_name: underscores become spaces")
        result = _format_test_name("test_user_can_login")
        log.debug(f"Result: '{result}'")
        assert result == "User can login"


class TestFormatClassName:
    def test_strips_test_prefix_camel(self):
        log.info("_format_class_name: 'TestAdminScheduler' → 'Admin Scheduler'")
        result = _format_class_name("TestAdminScheduler")
        log.debug(f"Result: '{result}'")
        assert result == "Admin Scheduler"

    def test_strips_test_prefix_snake(self):
        log.info("_format_class_name: 'test_api_amv2' → 'Api Amv2'")
        result = _format_class_name("test_api_amv2")
        log.debug(f"Result: '{result}'")
        assert result == "Api Amv2"

    def test_preserves_acronyms(self):
        log.info("_format_class_name: consecutive uppercase (acronyms) preserved")
        result = _format_class_name("TestUIPages")
        log.debug(f"Result: '{result}'")
        assert result == "UI Pages"

    def test_empty_string(self):
        log.info("_format_class_name: empty string returns empty")
        assert _format_class_name("") == ""

    def test_just_test(self):
        log.info("_format_class_name: 'Test' alone returns a string")
        result = _format_class_name("Test")
        log.debug(f"Result: '{result}'")
        assert isinstance(result, str)

    def test_non_test_prefix(self):
        log.info("_format_class_name: class without 'Test' prefix is still split")
        result = _format_class_name("HelperClass")
        log.debug(f"Result: '{result}'")
        assert result == "Helper Class"

    def test_single_word_after_test(self):
        log.info("_format_class_name: 'TestAuth' → 'Auth'")
        result = _format_class_name("TestAuth")
        log.debug(f"Result: '{result}'")
        assert result == "Auth"


class TestFormatTryNumber:
    def test_first(self):
        log.info("_format_try_number(1) → '1st try'")
        assert _format_try_number(1) == "1st try"

    def test_second(self):
        log.info("_format_try_number(2) → '2nd try'")
        assert _format_try_number(2) == "2nd try"

    def test_third(self):
        log.info("_format_try_number(3) → '3rd try'")
        assert _format_try_number(3) == "3rd try"

    def test_fourth(self):
        log.info("_format_try_number(4) → '4th try'")
        assert _format_try_number(4) == "4th try"

    def test_eleventh(self):
        log.info("_format_try_number(11) → '11th try' (special case)")
        assert _format_try_number(11) == "11th try"

    def test_twelfth(self):
        log.info("_format_try_number(12) → '12th try' (special case)")
        assert _format_try_number(12) == "12th try"

    def test_thirteenth(self):
        log.info("_format_try_number(13) → '13th try' (special case)")
        assert _format_try_number(13) == "13th try"

    def test_twenty_first(self):
        log.info("_format_try_number(21) → '21st try'")
        assert _format_try_number(21) == "21st try"

    def test_zero_returns_empty(self):
        log.info("_format_try_number(0) → empty string")
        assert _format_try_number(0) == ""

    def test_negative_returns_empty(self):
        log.info("_format_try_number(-1) → empty string")
        assert _format_try_number(-1) == ""


class TestParseTestResult:
    def test_parses_passed_test(self):
        log.info("Parse a PASSED test JSON — verify all fields extracted")
        data = {
            "testStatus": "PASSED",
            "className": "TestSample",
            "steps": [
                {
                    "name": "Step 01: do thing",
                    "startTime": 1000,
                    "endTime": 1200,
                    "status": "PASSED",
                    "events": [
                        {"level": "INFO", "event": "hello", "startTime": 1050}
                    ],
                }
            ],
        }
        result = _parse_test_result("test_example_12345.json", data)
        log.debug(f"Parsed: status={result.status}, class={result.className}, method={result.methodName}, duration={result.duration}ms, events={result.eventCount}")
        assert result.status == "PASSED"
        assert result.className == "TestSample"
        assert result.methodName == "test_example"
        assert result.duration == 200
        assert result.eventCount == 1
        assert len(result.steps) == 1
        assert result.steps[0].name == "Step 01: do thing"
        assert len(result.steps[0].events) == 1

    def test_parses_failed_test(self):
        log.info("Parse a FAILED test JSON — verify failure message and stack trace")
        data = {
            "testStatus": "FAILED",
            "failureMessage": "assert False",
            "stackTrace": "Traceback...",
            "steps": [
                {
                    "name": "test_broken",
                    "startTime": 1000,
                    "endTime": 1100,
                    "status": "FAILED",
                    "failureMessage": "assert False",
                    "events": [],
                }
            ],
        }
        result = _parse_test_result("test_broken_99.json", data)
        log.debug(f"Failure: message='{result.failureMessage}', trace present={bool(result.stackTrace)}")
        assert result.status == "FAILED"
        assert result.failureMessage == "assert False"
        assert result.stackTrace == "Traceback..."

    def test_method_name_from_filename(self):
        log.info("Extract method name from JSON filename (strip timestamp suffix)")
        result = _parse_test_result(
            "test_my_feature_1709912345000.json",
            {"steps": [{"startTime": 100, "endTime": 200, "events": []}]},
        )
        log.debug(f"Extracted method name: '{result.methodName}'")
        assert result.methodName == "test_my_feature"

    def test_defaults_for_missing_fields(self):
        log.info("Parse JSON with missing optional fields — verify defaults")
        result = _parse_test_result(
            "test_x_1.json",
            {"steps": [{"startTime": 0, "endTime": 0, "events": []}]},
        )
        log.debug(f"Defaults: className='{result.className}', status={result.status}")
        assert result.className == "Tests"
        assert result.status == "PASSED"

    def test_event_count_across_steps(self):
        log.info("Count events across multiple steps")
        data = {
            "steps": [
                {"startTime": 1, "endTime": 2, "events": [
                    {"level": "INFO", "event": "a"},
                    {"level": "INFO", "event": "b"},
                ]},
                {"startTime": 2, "endTime": 3, "events": [
                    {"level": "DEBUG", "event": "c"},
                ]},
            ],
        }
        result = _parse_test_result("test_x_1.json", data)
        log.debug(f"Total events across 2 steps: {result.eventCount}")
        assert result.eventCount == 3


class TestGenerateReport:
    def _write_json(self, json_dir: Path, name: str, data: dict):
        json_dir.mkdir(parents=True, exist_ok=True)
        (json_dir / name).write_text(json.dumps(data))

    def test_generates_html_from_json(self, tmp_path):
        log.info("Generate HTML report from a single JSON file")
        self._write_json(tmp_path / "json", "test_hello_1.json", {
            "testStatus": "PASSED",
            "className": "TestGreeting",
            "steps": [{
                "name": "test_hello",
                "startTime": 1000,
                "endTime": 1200,
                "status": "PASSED",
                "events": [{"level": "INFO", "event": "hi"}],
            }],
        })

        result = generate_report(str(tmp_path))
        log.debug(f"Report path: {result}")
        assert result is not None

        html_file = Path(result)
        assert html_file.exists()
        html = html_file.read_text()
        assert "test_hello" in html.lower() or "Hello" in html
        assert "PASSED" in html or "pass" in html

    def test_returns_none_for_empty_dir(self, tmp_path):
        log.info("generate_report with empty directory → returns None")
        assert generate_report(str(tmp_path)) is None

    def test_returns_none_for_missing_dir(self, tmp_path):
        log.info("generate_report with nonexistent directory → returns None")
        assert generate_report(str(tmp_path / "nonexistent")) is None

    def test_returns_none_for_empty_json_dir(self, tmp_path):
        log.info("generate_report with empty json/ subdir → returns None")
        (tmp_path / "json").mkdir()
        assert generate_report(str(tmp_path)) is None

    def test_multiple_tests_in_report(self, tmp_path):
        log.info("Generate report with 3 tests (2 PASSED, 1 FAILED)")
        for i, status in enumerate(["PASSED", "FAILED", "PASSED"]):
            self._write_json(tmp_path / "json", f"test_{i}_{i}.json", {
                "testStatus": status,
                "steps": [{
                    "name": f"test_{i}",
                    "startTime": 1000 + i,
                    "endTime": 1100 + i,
                    "status": status,
                    "events": [],
                    **({"failureMessage": "boom"} if status == "FAILED" else {}),
                }],
                **({"failureMessage": "boom"} if status == "FAILED" else {}),
            })

        result = generate_report(str(tmp_path))
        log.debug(f"Report generated: {result is not None}")
        assert result is not None
        html = Path(result).read_text()
        assert "2" in html
        assert "1" in html

    def test_custom_title(self, tmp_path):
        log.info("Generate report with custom title 'My Custom Report'")
        self._write_json(tmp_path / "json", "test_a_1.json", {
            "testStatus": "PASSED",
            "steps": [{"startTime": 1, "endTime": 2, "status": "PASSED", "events": []}],
        })

        result = generate_report(str(tmp_path), title="My Custom Report")
        html = Path(result).read_text()
        log.debug(f"Title found in HTML: {'My Custom Report' in html}")
        assert "My Custom Report" in html

    def test_timestamped_report_also_created(self, tmp_path):
        log.info("Verify timestamped report file (TestReport_All_*.html) is also created")
        self._write_json(tmp_path / "json", "test_a_1.json", {
            "testStatus": "PASSED",
            "steps": [{"startTime": 1, "endTime": 2, "status": "PASSED", "events": []}],
        })

        generate_report(str(tmp_path))
        all_htmls = list(tmp_path.glob("TestReport_All_*.html"))
        log.debug(f"Timestamped reports found: {len(all_htmls)}")
        assert len(all_htmls) >= 1

    def test_report_contains_class_groups(self, tmp_path):
        log.info("Report groups tests by className (TestAuth, TestPayment)")
        self._write_json(tmp_path / "json", "test_a_1.json", {
            "testStatus": "PASSED",
            "className": "TestAuth",
            "steps": [{"startTime": 1, "endTime": 2, "status": "PASSED", "events": []}],
        })
        self._write_json(tmp_path / "json", "test_b_2.json", {
            "testStatus": "PASSED",
            "className": "TestPayment",
            "steps": [{"startTime": 1, "endTime": 2, "status": "PASSED", "events": []}],
        })

        result = generate_report(str(tmp_path))
        html = Path(result).read_text()
        log.debug(f"Auth in HTML: {'Auth' in html}, Payment in HTML: {'Payment' in html}")
        assert "Auth" in html
        assert "Payment" in html

    def test_report_contains_events(self, tmp_path):
        log.info("Verify events are rendered in the HTML report")
        self._write_json(tmp_path / "json", "test_a_1.json", {
            "testStatus": "PASSED",
            "steps": [{
                "startTime": 1, "endTime": 2, "status": "PASSED",
                "events": [
                    {"level": "INFO", "event": "User created successfully"},
                    {"level": "ERROR", "event": "Connection timeout"},
                ],
            }],
        })

        result = generate_report(str(tmp_path))
        html = Path(result).read_text()
        log.debug("Checking event text in HTML output")
        assert "User created successfully" in html
        assert "Connection timeout" in html

    def test_report_handles_special_chars_in_events(self, tmp_path):
        log.info("Verify special chars (<, &, quotes) are HTML-escaped in events")
        self._write_json(tmp_path / "json", "test_a_1.json", {
            "testStatus": "PASSED",
            "steps": [{
                "startTime": 1, "endTime": 2, "status": "PASSED",
                "events": [
                    {"level": "INFO", "event": "value <b>bold</b> & 'quoted'"},
                ],
            }],
        })

        result = generate_report(str(tmp_path))
        html = Path(result).read_text()
        log.debug("Checking HTML-escaped entities in output")
        assert "&lt;b&gt;bold&lt;/b&gt;" in html
        assert "&amp;" in html

    def test_report_contains_log_level_filter(self, tmp_path):
        log.info("Verify HTML report includes log level filter control")
        self._write_json(tmp_path / "json", "test_a_1.json", {
            "testStatus": "PASSED",
            "steps": [{"startTime": 1, "endTime": 2, "status": "PASSED", "events": []}],
        })

        result = generate_report(str(tmp_path))
        html = Path(result).read_text()
        assert "logLevelFilter" in html

    def test_report_contains_search(self, tmp_path):
        log.info("Verify HTML report includes search functionality")
        self._write_json(tmp_path / "json", "test_a_1.json", {
            "testStatus": "PASSED",
            "steps": [{"startTime": 1, "endTime": 2, "status": "PASSED", "events": []}],
        })

        result = generate_report(str(tmp_path))
        html = Path(result).read_text()
        assert "searchTests" in html or "search" in html.lower()

    def test_failed_test_has_failure_info(self, tmp_path):
        log.info("Verify FAILED test shows failure message in HTML")
        self._write_json(tmp_path / "json", "test_fail_1.json", {
            "testStatus": "FAILED",
            "failureMessage": "expected True but got False",
            "stackTrace": "File test.py line 10\n  assert True == False\nAssertionError",
            "steps": [{
                "startTime": 1, "endTime": 2,
                "status": "FAILED",
                "failureMessage": "expected True but got False",
                "events": [],
            }],
        })

        result = generate_report(str(tmp_path))
        html = Path(result).read_text()
        log.debug("Checking failure info in HTML")
        assert "expected True but got False" in html

    def test_invalid_json_skipped(self, tmp_path):
        log.info("Invalid JSON files are skipped without crashing report generation")
        json_dir = tmp_path / "json"
        json_dir.mkdir(parents=True)
        (json_dir / "bad_1.json").write_text("not valid json {{{")
        self._write_json(json_dir.parent / "json", "test_good_1.json", {
            "testStatus": "PASSED",
            "steps": [{"startTime": 1, "endTime": 2, "status": "PASSED", "events": []}],
        })

        result = generate_report(str(tmp_path))
        log.debug(f"Report generated despite bad JSON: {result is not None}")
        assert result is not None
