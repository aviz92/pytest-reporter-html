"""Integration tests for pytest_reporter_html.plugin via pytester."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class TestPluginBasicLifecycle:
    def test_passing_test_produces_json(self, pytester):
        log.info("Run a passing test via pytester — verify JSON is generated")
        pytester.makepyfile("""
            def test_hello():
                assert 1 + 1 == 2
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        log.debug(f"JSON files found: {len(json_files)}")
        assert len(json_files) >= 1

        data = json.loads(json_files[0].read_text())
        log.debug(f"Status: {data['testStatus']}, steps: {len(data['steps'])}")
        assert data["testStatus"] == "PASSED"
        assert len(data["steps"]) >= 1

    def test_failing_test_produces_failed_json(self, pytester):
        log.info("Run a failing test — verify FAILED status and failure message in JSON")
        pytester.makepyfile("""
            def test_fail():
                assert False, "deliberate failure"
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(failed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())
        log.debug(f"Status: {data['testStatus']}, failure: '{data.get('failureMessage', '')}'")
        assert data["testStatus"] == "FAILED"
        assert "deliberate failure" in (data.get("failureMessage") or "")

    def test_multiple_tests_produce_multiple_jsons(self, pytester):
        log.info("Run 3 tests — verify each produces its own JSON")
        pytester.makepyfile("""
            def test_a():
                pass
            def test_b():
                pass
            def test_c():
                pass
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=3)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        log.debug(f"JSON files: {len(json_files)}")
        assert len(json_files) == 3


class TestPluginStepCapture:
    def test_explicit_step_appears_in_json(self, pytester):
        log.info("Use step() context manager in test — verify steps appear in JSON")
        pytester.makepyfile("""
            from pytest_reporter_html import step

            def test_with_steps():
                with step("first"):
                    x = 1
                with step("second"):
                    x = 2
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())
        step_names = [s["name"] for s in data["steps"]]
        log.debug(f"Steps: {step_names}")
        assert any("first" in n for n in step_names)
        assert any("second" in n for n in step_names)

    def test_step_decorator_appears_in_json(self, pytester):
        log.info("Use @step() decorator on helper — verify step appears in JSON")
        pytester.makepyfile("""
            from pytest_reporter_html import step

            @step("helper step")
            def do_work():
                return 42

            def test_decorated():
                result = do_work()
                assert result == 42
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())
        step_names = [s["name"] for s in data["steps"]]
        log.debug(f"Steps: {step_names}")
        assert any("helper step" in n for n in step_names)


class TestPluginLogCapture:
    def test_logging_captured_as_events(self, pytester):
        log.info("Emit logging messages in test — verify captured as events in JSON")
        pytester.makepyfile("""
            import logging
            logger = logging.getLogger("test_app_capture")
            logger.setLevel(logging.DEBUG)

            def test_with_logging():
                logger.info("action performed")
                logger.debug("detail info")
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        all_events = []
        for s in data["steps"]:
            all_events.extend(s.get("events", []))

        messages = [e["event"] for e in all_events]
        log.debug(f"Captured messages: {messages}")
        assert "action performed" in messages

    def test_logging_disabled_when_auto_log_false(self, pytester):
        log.info("Set report_auto_log=false — verify logging is NOT captured")
        pytester.makepyfile("""
            import logging
            logger = logging.getLogger("test_app_disabled")

            def test_no_capture():
                logger.info("should not appear")
        """)
        pytester.makeini("""
            [pytest]
            report_mode = all
            report_auto_log = false
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        all_events = []
        for s in data["steps"]:
            all_events.extend(s.get("events", []))

        messages = [e["event"] for e in all_events]
        log.debug(f"Events (should be empty): {messages}")
        assert "should not appear" not in messages


class TestPluginPhaseSteps:
    def test_empty_setup_teardown_removed(self, pytester):
        log.info("Simple test — verify empty Setup and Teardown phases are removed")
        pytester.makepyfile("""
            def test_simple():
                assert True
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        step_names = [s["name"] for s in data["steps"]]
        log.debug(f"Steps (no Setup/Teardown): {step_names}")
        assert "Setup" not in step_names
        assert "Teardown" not in step_names

    def test_test_body_step_present(self, pytester):
        log.info("Verify test function body creates a step named after the test")
        pytester.makepyfile("""
            def test_body():
                x = 1 + 1
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        step_names = [s["name"] for s in data["steps"]]
        log.debug(f"Steps: {step_names}")
        assert "test_body" in step_names


class TestPluginConfig:
    def test_custom_output_dir(self, pytester):
        log.info("Set report_dir=custom_output — verify JSON written there")
        pytester.makepyfile("""
            def test_pass():
                pass
        """)
        pytester.makeini("""
            [pytest]
            report_mode = all
            report_dir = custom_output
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        custom_dir = pytester.path / "custom_output" / "json"
        json_files = list(custom_dir.glob("*.json"))
        log.debug(f"Files in custom dir: {len(json_files)}")
        assert len(json_files) == 1

    def test_no_report_html_flag(self, pytester):
        log.info("Use --no-report-html flag — verify no HTML is generated")
        pytester.makepyfile("""
            def test_pass():
                pass
        """)
        result = pytester.runpytest("-q", "--no-report-html")
        result.assert_outcomes(passed=1)

        html_files = list(pytester.path.rglob("*.html"))
        log.debug(f"HTML files: {len(html_files)}")
        assert len(html_files) == 0

    def test_custom_title_in_html(self, pytester):
        log.info("Set report_title='My Custom Title' — verify it appears in HTML")
        pytester.makepyfile("""
            def test_pass():
                pass
        """)
        pytester.makeini("""
            [pytest]
            report_mode = all
            report_title = My Custom Title
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        html_files = list(pytester.path.rglob("TestReport_Latest.html"))
        if html_files:
            html = html_files[0].read_text()
            log.debug(f"Title in HTML: {'My Custom Title' in html}")
            assert "My Custom Title" in html


class TestPluginClassName:
    def test_class_name_in_json(self, pytester):
        log.info("Test in a class — verify className field in JSON")
        pytester.makepyfile("""
            class TestMyFeature:
                def test_something(self):
                    assert True
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())
        log.debug(f"className: {data.get('className')}")
        assert data.get("className") == "TestMyFeature"

    def test_module_name_for_functions(self, pytester):
        log.info("Standalone test function — verify className falls back to module name")
        pytester.makepyfile("""
            def test_standalone():
                assert True
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())
        log.debug(f"className (module fallback): {data.get('className')}")
        assert data.get("className") is not None


class TestPluginFixtures:
    def test_report_log_fixture(self, pytester):
        log.info("Use report_log fixture — verify message captured in JSON")
        pytester.makepyfile("""
            def test_with_log(report_log):
                report_log.info("logged via fixture")
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        all_events = []
        for s in data["steps"]:
            all_events.extend(s.get("events", []))

        messages = [e["event"] for e in all_events]
        log.debug(f"Messages: {messages}")
        assert "logged via fixture" in messages

    def test_report_step_fixture(self, pytester):
        log.info("Use report_step fixture — verify step name in JSON")
        pytester.makepyfile("""
            def test_with_step(report_step):
                with report_step("fixture step"):
                    pass
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())
        step_names = [s["name"] for s in data["steps"]]
        log.debug(f"Steps: {step_names}")
        assert any("fixture step" in n for n in step_names)

    def test_report_test_name_fixture(self, pytester):
        log.info("Use report_test_name fixture — verify custom name in JSON filename")
        pytester.makepyfile("""
            def test_rename(report_test_name):
                report_test_name("custom_name")
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        filenames = [f.name for f in json_files]
        log.debug(f"Filenames: {filenames}")
        assert any("custom_name" in n for n in filenames)


class TestDescriptiveLogsInTests:
    """Use case: Adding descriptive logs to tests via standard logging."""

    def test_multiple_log_levels_captured(self, pytester):
        log.info("Verify INFO, DEBUG, WARN, ERROR log levels are all captured as events")
        pytester.makepyfile("""
            import logging
            logger = logging.getLogger("myapp.orders")
            logger.setLevel(logging.DEBUG)

            def test_checkout():
                logger.info("Adding item to cart")
                logger.debug("Cart contents: {'sku': 'A1', 'qty': 2}")
                logger.warning("Inventory low for SKU A1")
                logger.error("Payment gateway timeout")
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        all_events = []
        for s in data["steps"]:
            all_events.extend(s.get("events", []))

        assert len(all_events) == 4
        levels = [e["level"] for e in all_events]
        assert levels == ["INFO", "DEBUG", "WARN", "ERROR"]
        assert all_events[0]["event"] == "Adding item to cart"
        assert all_events[3]["event"] == "Payment gateway timeout"

    def test_application_code_logs_captured(self, pytester):
        log.info("Verify logs from application code (not test code) are also captured")
        pytester.makepyfile(app_module="""
            import logging
            logger = logging.getLogger("myapp.service")
            logger.setLevel(logging.DEBUG)

            def create_user(name):
                logger.info(f"Creating user: {name}")
                logger.debug(f"Validating name length: {len(name)}")
                return {"id": 1, "name": name}
        """)
        pytester.makepyfile("""
            from app_module import create_user

            def test_user_creation():
                user = create_user("Alice")
                assert user["name"] == "Alice"
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        all_events = []
        for s in data["steps"]:
            all_events.extend(s.get("events", []))

        messages = [e["event"] for e in all_events]
        assert "Creating user: Alice" in messages
        assert "Validating name length: 5" in messages

    def test_source_file_and_line_captured(self, pytester):
        log.info("Verify sourceFileName and sourceLineNumber are captured for log events")
        pytester.makepyfile("""
            import logging
            logger = logging.getLogger("srctest")
            logger.setLevel(logging.DEBUG)

            def test_source_info():
                logger.info("track me")
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        all_events = []
        for s in data["steps"]:
            all_events.extend(s.get("events", []))

        ev = next(e for e in all_events if e["event"] == "track me")
        assert ev.get("sourceFileName") is not None
        assert ev.get("sourceLineNumber") is not None
        assert ev["sourceLineNumber"] > 0

    def test_exception_traceback_captured(self, pytester):
        log.info("Verify logger.exception() captures full traceback in event text")
        pytester.makepyfile("""
            import logging
            logger = logging.getLogger("exc_test")
            logger.setLevel(logging.DEBUG)

            def test_exception_logging():
                try:
                    raise ValueError("bad input")
                except ValueError:
                    logger.exception("Operation failed")
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        all_events = []
        for s in data["steps"]:
            all_events.extend(s.get("events", []))

        ev = next(e for e in all_events if "Operation failed" in e["event"])
        assert "Traceback (most recent call last):" in ev["event"]
        assert "ValueError: bad input" in ev["event"]
        assert ev["level"] == "ERROR"

    def test_json_message_detected(self, pytester):
        log.info("Verify JSON string in log message is detected with type='json'")
        pytester.makepyfile("""
            import logging
            logger = logging.getLogger("json_detect")
            logger.setLevel(logging.DEBUG)

            def test_json_log():
                logger.info('{"user": "Alice", "action": "login"}')
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        all_events = []
        for s in data["steps"]:
            all_events.extend(s.get("events", []))

        ev = next(e for e in all_events if "Alice" in e["event"])
        assert ev.get("type") == "json"


class TestExplicitSteps:
    """Use case: Explicit steps via step() context manager."""

    def test_events_grouped_inside_correct_step(self, pytester):
        log.info("Verify log events are grouped inside their respective step context")
        pytester.makepyfile("""
            import logging
            from pytest_reporter_html import step

            logger = logging.getLogger("step_group")
            logger.setLevel(logging.DEBUG)

            def test_grouped():
                with step("Create user"):
                    logger.info("Sending POST /users")
                    logger.info("User created: id=42")

                with step("Verify user"):
                    logger.info("Fetching GET /users/42")
                    logger.info("User verified")
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        create_step = next(s for s in data["steps"] if "Create user" in s["name"])
        verify_step = next(s for s in data["steps"] if "Verify user" in s["name"])

        create_msgs = [e["event"] for e in create_step["events"]]
        verify_msgs = [e["event"] for e in verify_step["events"]]

        assert "Sending POST /users" in create_msgs
        assert "User created: id=42" in create_msgs
        assert "Fetching GET /users/42" in verify_msgs
        assert "User verified" in verify_msgs

        assert "Fetching GET /users/42" not in create_msgs
        assert "Sending POST /users" not in verify_msgs

    def test_failed_step_records_failure(self, pytester):
        log.info("Verify a step that raises records FAILED status with failure message")
        pytester.makepyfile("""
            from pytest_reporter_html import step

            def test_step_fail():
                with step("Will succeed"):
                    x = 1

                with step("Will fail"):
                    raise ValueError("bad value")
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(failed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        success_step = next(s for s in data["steps"] if "Will succeed" in s["name"])
        fail_step = next(s for s in data["steps"] if "Will fail" in s["name"])

        assert success_step["status"] == "PASSED"
        assert fail_step["status"] == "FAILED"
        assert "bad value" in (fail_step.get("failureMessage") or "")

    def test_step_duration_recorded(self, pytester):
        log.info("Verify step duration (endTime - startTime) is recorded correctly")
        pytester.makepyfile("""
            import time
            from pytest_reporter_html import step

            def test_timed():
                with step("quick step"):
                    time.sleep(0.05)
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        timed_step = next(s for s in data["steps"] if "quick step" in s["name"])
        duration = timed_step["endTime"] - timed_step["startTime"]
        assert duration >= 40

    def test_three_sequential_steps(self, pytester):
        log.info("Verify 3 sequential steps are recorded in order A < B < C")
        pytester.makepyfile("""
            from pytest_reporter_html import step

            def test_multi():
                with step("Step A"):
                    pass
                with step("Step B"):
                    pass
                with step("Step C"):
                    pass
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        step_names = [s["name"] for s in data["steps"]]
        assert any("Step A" in n for n in step_names)
        assert any("Step B" in n for n in step_names)
        assert any("Step C" in n for n in step_names)

        a_idx = next(i for i, n in enumerate(step_names) if "Step A" in n)
        b_idx = next(i for i, n in enumerate(step_names) if "Step B" in n)
        c_idx = next(i for i, n in enumerate(step_names) if "Step C" in n)
        assert a_idx < b_idx < c_idx


class TestStepDecorator:
    """Use case: step as decorator on helper functions."""

    def test_decorated_function_creates_step(self, pytester):
        log.info("@step decorator on function — verify step created in JSON")
        pytester.makepyfile("""
            from pytest_reporter_html import step

            @step("Create order")
            def create_order(items):
                return {"id": "ord-1", "items": items}

            def test_order():
                order = create_order(["SKU-1", "SKU-2"])
                assert order["id"] == "ord-1"
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        step_names = [s["name"] for s in data["steps"]]
        assert any("Create order" in n for n in step_names)

    def test_multiple_decorated_helpers_in_sequence(self, pytester):
        log.info("Multiple @step decorated helpers — verify each creates its own step with events")
        pytester.makepyfile("""
            import logging
            from pytest_reporter_html import step

            logger = logging.getLogger("helpers")
            logger.setLevel(logging.DEBUG)

            @step("Create user")
            def create_user(name):
                logger.info(f"Creating {name}")
                return {"name": name}

            @step("Delete user")
            def delete_user(name):
                logger.info(f"Deleting {name}")

            @step("Verify cleanup")
            def verify_cleanup():
                logger.info("Verified: no users remain")

            def test_lifecycle():
                user = create_user("Bob")
                assert user["name"] == "Bob"
                delete_user("Bob")
                verify_cleanup()
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        step_names = [s["name"] for s in data["steps"]]
        assert any("Create user" in n for n in step_names)
        assert any("Delete user" in n for n in step_names)
        assert any("Verify cleanup" in n for n in step_names)

        create_step = next(s for s in data["steps"] if "Create user" in s["name"])
        delete_step = next(s for s in data["steps"] if "Delete user" in s["name"])
        verify_step = next(s for s in data["steps"] if "Verify cleanup" in s["name"])

        assert any("Creating Bob" in e["event"] for e in create_step["events"])
        assert any("Deleting Bob" in e["event"] for e in delete_step["events"])
        assert any("no users remain" in e["event"] for e in verify_step["events"])

    def test_decorated_function_failure(self, pytester):
        log.info("@step decorated function that raises — verify FAILED step in JSON")
        pytester.makepyfile("""
            from pytest_reporter_html import step

            @step("Validate input")
            def validate(value):
                if value < 0:
                    raise ValueError("Negative not allowed")

            def test_validation_fail():
                validate(-1)
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(failed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        fail_step = next(s for s in data["steps"] if "Validate input" in s["name"])
        assert fail_step["status"] == "FAILED"
        assert "Negative not allowed" in (fail_step.get("failureMessage") or "")

    def test_decorated_function_return_value_preserved(self, pytester):
        log.info("@step decorator preserves the wrapped function's return value")
        pytester.makepyfile("""
            from pytest_reporter_html import step

            @step("Compute result")
            def compute(x, y):
                return x * y + 10

            def test_return_value():
                result = compute(3, 4)
                assert result == 22
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

    def test_async_decorated_function(self, pytester):
        log.info("@step decorator on async function — verify step in JSON")
        pytester.makepyfile("""
            import asyncio
            from pytest_reporter_html import step

            @step("Fetch data")
            async def fetch():
                await asyncio.sleep(0.01)
                return [1, 2, 3]

            async def test_async_fetch():
                data = await fetch()
                assert data == [1, 2, 3]
        """)
        pytester.makeini("""
            [pytest]
            report_mode = all
            asyncio_mode = auto
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        step_names = [s["name"] for s in data["steps"]]
        assert any("Fetch data" in n for n in step_names)

    def test_mixed_steps_and_decorator(self, pytester):
        log.info("Mix @step decorator with step() context manager — all steps recorded")
        pytester.makepyfile("""
            import logging
            from pytest_reporter_html import step

            logger = logging.getLogger("mixed")
            logger.setLevel(logging.DEBUG)

            @step("Helper A")
            def helper_a():
                logger.info("Inside helper A")
                return "a"

            def test_mixed():
                result = helper_a()
                assert result == "a"

                with step("Inline step B"):
                    logger.info("Inside inline step B")

                with step("Inline step C"):
                    logger.info("Inside inline step C")
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(Path(str(pytester.path)).rglob("*.json"))
        data = json.loads(json_files[0].read_text())

        step_names = [s["name"] for s in data["steps"]]
        assert any("Helper A" in n for n in step_names)
        assert any("Inline step B" in n for n in step_names)
        assert any("Inline step C" in n for n in step_names)

        a_step = next(s for s in data["steps"] if "Helper A" in s["name"])
        b_step = next(s for s in data["steps"] if "Inline step B" in s["name"])
        c_step = next(s for s in data["steps"] if "Inline step C" in s["name"])

        assert any("Inside helper A" in e["event"] for e in a_step["events"])
        assert any("Inside inline step B" in e["event"] for e in b_step["events"])
        assert any("Inside inline step C" in e["event"] for e in c_step["events"])


class TestPluginHtmlGeneration:
    def test_html_report_generated(self, pytester):
        log.info("Verify HTML report is generated with test names")
        pytester.makepyfile("""
            def test_one():
                pass
            def test_two():
                pass
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=2)

        html_files = list(pytester.path.rglob("TestReport_Latest.html"))
        assert len(html_files) == 1
        html = html_files[0].read_text()
        assert "<html" in html
        assert "test_one" in html.lower() or "One" in html
        assert "test_two" in html.lower() or "Two" in html

    def test_html_disabled_via_ini(self, pytester):
        log.info("Set report_html=false in ini — verify no HTML generated")
        pytester.makepyfile("""
            def test_pass():
                pass
        """)
        pytester.makeini("""
            [pytest]
            report_mode = all
            report_html = false
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        html_files = list(pytester.path.rglob("*.html"))
        assert len(html_files) == 0


# ---------------------------------------------------------------------------
# Disable reporter
# ---------------------------------------------------------------------------


class TestDisableReporter:
    """Verify --disable-reporter and report_enabled=false turn off everything."""

    def test_disable_via_cli_flag(self, pytester):
        log.info("--disable-reporter flag — no JSON and no HTML produced")
        pytester.makepyfile("""
            import logging
            logger = logging.getLogger("app")
            logger.setLevel(logging.DEBUG)

            def test_hello():
                logger.info("should not be captured")
                assert True
        """)
        result = pytester.runpytest("-q", "--disable-reporter")
        result.assert_outcomes(passed=1)

        json_files = list(pytester.path.rglob("*.json"))
        html_files = list(pytester.path.rglob("*.html"))
        log.debug(f"JSON files: {len(json_files)}, HTML files: {len(html_files)}")
        assert len(json_files) == 0
        assert len(html_files) == 0

    def test_disable_via_ini(self, pytester):
        log.info("report_enabled=false in ini — no JSON and no HTML produced")
        pytester.makepyfile("""
            def test_hello():
                assert True
        """)
        pytester.makeini("""
            [pytest]
            report_mode = all
            report_enabled = false
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(pytester.path.rglob("*.json"))
        html_files = list(pytester.path.rglob("*.html"))
        log.debug(f"JSON files: {len(json_files)}, HTML files: {len(html_files)}")
        assert len(json_files) == 0
        assert len(html_files) == 0

    def test_disable_does_not_break_tests(self, pytester):
        log.info("Disabled reporter — step() and report_log still work as no-ops")
        pytester.makepyfile("""
            from pytest_reporter_html import step

            @step("helper")
            def do_work():
                return 42

            def test_with_step_and_log(report_log):
                report_log.info("no-op")
                with step("inline"):
                    result = do_work()
                assert result == 42
        """)
        result = pytester.runpytest("-q", "--disable-reporter")
        result.assert_outcomes(passed=1)


# ---------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------


class TestReportModeAuto:
    """report_mode = auto — only Python logging capture, step/manual disabled."""

    def test_auto_mode_captures_logging(self, pytester):
        log.info("mode=auto — standard logging is captured")
        pytester.makepyfile("""
            import logging
            logger = logging.getLogger("myapp")
            logger.setLevel(logging.DEBUG)

            def test_auto():
                logger.info("auto captured")
        """)
        pytester.makeini("""
            [pytest]
            report_mode = auto
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(pytester.path.rglob("*.json"))
        data = json.loads(json_files[0].read_text())
        all_events = [e for s in data["steps"] for e in s.get("events", [])]
        messages = [e["event"] for e in all_events]
        log.debug(f"Events: {messages}")
        assert "auto captured" in messages

    def test_auto_mode_step_is_noop(self, pytester):
        log.info("mode=auto — step() is a no-op, no step in JSON")
        pytester.makepyfile("""
            from pytest_reporter_html import step

            def test_step_noop():
                with step("should not appear"):
                    x = 1
                assert x == 1
        """)
        pytester.makeini("""
            [pytest]
            report_mode = auto
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(pytester.path.rglob("*.json"))
        data = json.loads(json_files[0].read_text())
        step_names = [s["name"] for s in data["steps"]]
        log.debug(f"Steps: {step_names}")
        assert not any("should not appear" in n for n in step_names)

    def test_auto_mode_report_log_is_noop(self, pytester):
        log.info("mode=auto — report_log fixture is a no-op")
        pytester.makepyfile("""
            def test_manual_noop(report_log):
                report_log.info("should not appear")
        """)
        pytester.makeini("""
            [pytest]
            report_mode = auto
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(pytester.path.rglob("*.json"))
        data = json.loads(json_files[0].read_text())
        all_events = [e for s in data["steps"] for e in s.get("events", [])]
        messages = [e["event"] for e in all_events]
        log.debug(f"Events: {messages}")
        assert "should not appear" not in messages


class TestReportModeStep:
    """report_mode = step — only step() capture, auto-log/manual disabled."""

    def test_step_mode_captures_steps(self, pytester):
        log.info("mode=step — step() context manager creates steps")
        pytester.makepyfile("""
            from pytest_reporter_html import step

            def test_explicit():
                with step("my step"):
                    x = 1
                assert x == 1
        """)
        pytester.makeini("""
            [pytest]
            report_mode = step
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(pytester.path.rglob("*.json"))
        data = json.loads(json_files[0].read_text())
        step_names = [s["name"] for s in data["steps"]]
        log.debug(f"Steps: {step_names}")
        assert any("my step" in n for n in step_names)

    def test_step_mode_no_auto_logging(self, pytester):
        log.info("mode=step — standard logging is NOT captured")
        pytester.makepyfile("""
            import logging
            logger = logging.getLogger("noisy")
            logger.setLevel(logging.DEBUG)

            def test_no_auto():
                logger.info("should not be captured")
        """)
        pytester.makeini("""
            [pytest]
            report_mode = step
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(pytester.path.rglob("*.json"))
        data = json.loads(json_files[0].read_text())
        all_events = [e for s in data["steps"] for e in s.get("events", [])]
        messages = [e["event"] for e in all_events]
        log.debug(f"Events: {messages}")
        assert "should not be captured" not in messages


class TestReportModeManual:
    """report_mode = manual — only report_log fixture, auto-log/step disabled."""

    def test_manual_mode_captures_report_log(self, pytester):
        log.info("mode=manual — report_log fixture captures events")
        pytester.makepyfile("""
            def test_manual(report_log):
                report_log.info("manual event")
        """)
        pytester.makeini("""
            [pytest]
            report_mode = manual
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(pytester.path.rglob("*.json"))
        data = json.loads(json_files[0].read_text())
        all_events = [e for s in data["steps"] for e in s.get("events", [])]
        messages = [e["event"] for e in all_events]
        log.debug(f"Events: {messages}")
        assert "manual event" in messages

    def test_manual_mode_step_is_noop(self, pytester):
        log.info("mode=manual — step() is a no-op")
        pytester.makepyfile("""
            from pytest_reporter_html import step

            def test_no_step():
                with step("should not appear"):
                    pass
        """)
        pytester.makeini("""
            [pytest]
            report_mode = manual
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(pytester.path.rglob("*.json"))
        data = json.loads(json_files[0].read_text())
        step_names = [s["name"] for s in data["steps"]]
        log.debug(f"Steps: {step_names}")
        assert not any("should not appear" in n for n in step_names)

    def test_manual_mode_no_auto_logging(self, pytester):
        log.info("mode=manual — standard logging is NOT captured")
        pytester.makepyfile("""
            import logging
            logger = logging.getLogger("noisy")
            logger.setLevel(logging.DEBUG)

            def test_no_auto():
                logger.info("should not be captured")
        """)
        pytester.makeini("""
            [pytest]
            report_mode = manual
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(pytester.path.rglob("*.json"))
        data = json.loads(json_files[0].read_text())
        all_events = [e for s in data["steps"] for e in s.get("events", [])]
        messages = [e["event"] for e in all_events]
        log.debug(f"Events: {messages}")
        assert "should not be captured" not in messages


class TestReportModeCombo:
    """report_mode with comma-separated values."""

    def test_auto_step_combo(self, pytester):
        log.info("mode=auto,step — both auto logging and step() active")
        pytester.makepyfile("""
            import logging
            from pytest_reporter_html import step

            logger = logging.getLogger("combo")
            logger.setLevel(logging.DEBUG)

            def test_combo():
                with step("my step"):
                    logger.info("inside step")
                logger.info("outside step")
        """)
        pytester.makeini("""
            [pytest]
            report_mode = auto,step
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(pytester.path.rglob("*.json"))
        data = json.loads(json_files[0].read_text())
        step_names = [s["name"] for s in data["steps"]]
        all_events = [e for s in data["steps"] for e in s.get("events", [])]
        messages = [e["event"] for e in all_events]
        log.debug(f"Steps: {step_names}, Events: {messages}")
        assert any("my step" in n for n in step_names)
        assert "inside step" in messages

    def test_step_manual_combo(self, pytester):
        log.info("mode=step,manual — step() and report_log active, no auto-log")
        pytester.makepyfile("""
            import logging
            from pytest_reporter_html import step

            logger = logging.getLogger("noisy")
            logger.setLevel(logging.DEBUG)

            def test_combo(report_log):
                with step("explicit"):
                    report_log.info("manual inside step")
                logger.info("auto should not appear")
        """)
        pytester.makeini("""
            [pytest]
            report_mode = step,manual
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(pytester.path.rglob("*.json"))
        data = json.loads(json_files[0].read_text())
        step_names = [s["name"] for s in data["steps"]]
        all_events = [e for s in data["steps"] for e in s.get("events", [])]
        messages = [e["event"] for e in all_events]
        log.debug(f"Steps: {step_names}, Events: {messages}")
        assert any("explicit" in n for n in step_names)
        assert "manual inside step" in messages
        assert "auto should not appear" not in messages

    def test_all_mode_explicit(self, pytester):
        log.info("mode=all — everything enabled (default)")
        pytester.makepyfile("""
            import logging
            from pytest_reporter_html import step

            logger = logging.getLogger("allmode")
            logger.setLevel(logging.DEBUG)

            def test_everything(report_log):
                logger.info("auto event")
                with step("explicit step"):
                    pass
                report_log.info("manual event")
        """)
        pytester.makeini("""
            [pytest]
            report_mode = all
        """)
        result = pytester.runpytest("-q")
        result.assert_outcomes(passed=1)

        json_files = list(pytester.path.rglob("*.json"))
        data = json.loads(json_files[0].read_text())
        step_names = [s["name"] for s in data["steps"]]
        all_events = [e for s in data["steps"] for e in s.get("events", [])]
        messages = [e["event"] for e in all_events]
        log.debug(f"Steps: {step_names}, Events: {messages}")
        assert any("explicit step" in n for n in step_names)
        assert "auto event" in messages
        assert "manual event" in messages
