"""
Pytest plugin for HTML test reporting.

Registered automatically via the ``pytest11`` entry-point when the
package is installed.  No configuration required — just ``pip install``.

Provides:
- ``report_log`` fixture — a :class:`ReportLogger` bound to the test
- ``report_step`` fixture — the :class:`step` context manager / decorator
- Automatic JSON report generation per test
- S3 upload in CI mode
"""
from __future__ import annotations

import os
import traceback

import pytest

from .logger import ReportLogger, _NoOpReportLogger
from .logging_bridge import ReportLoggingHandler, attach_logging_bridge, detach_logging_bridge
from .reporter import TestReporter
from .step import _active_reporter, _set_steps_enabled, step


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register CLI options for the HTML reporter."""
    group = parser.getgroup("reporter-html", "HTML Test Reporter")
    group.addoption(
        "--no-report-html",
        action="store_true",
        default=False,
        help="Disable HTML report generation",
    )
    group.addoption(
        "--disable-reporter",
        action="store_true",
        default=False,
        help="Completely disable the reporter (no JSON/HTML output)",
    )

    parser.addini("report_enabled", default=True, type="bool",
                  help="Master switch to enable/disable the reporter")
    parser.addini("report_mode", default="",
                  help="Capture mode: auto, step, manual, all (comma-separated for combos; empty = disabled)")
    parser.addini("report_dir", default="build/test-reports",
                  help="Output directory for JSON and HTML reports")
    parser.addini("report_title", default="Test Report",
                  help="Title shown in the HTML report header")
    parser.addini("report_log_level", default="DEBUG",
                  help="Minimum log level to capture (TRACE/DEBUG/INFO/WARN/ERROR)")
    parser.addini("report_auto_log", default=True, type="bool",
                  help="Auto-capture Python logging into report events (legacy; prefer report_mode)")
    parser.addini("report_html", default=True, type="bool",
                  help="Generate aggregated HTML report")
    parser.addini("report_exclude_loggers", default="",
                  help="Comma-separated logger prefixes to exclude from capture")


class _ReportConfig:
    """Resolved configuration values, set once in pytest_configure."""
    enabled: bool = True
    mode_auto: bool = False
    mode_step: bool = False
    mode_manual: bool = False
    output_dir: str = "build/test-reports"
    title: str = "Test Report"
    log_level: str = "DEBUG"
    auto_log: bool = True
    generate_html: bool = True
    exclude_loggers: list[str] = []
    no_html_cli: bool = False


_cfg = _ReportConfig()


def _parse_modes(mode_str: str) -> tuple[bool, bool, bool]:
    """Return (auto, step, manual) flags from a mode string."""
    modes = {m.strip().lower() for m in mode_str.split(",") if m.strip()}
    if not modes:
        return False, False, False
    if "all" in modes:
        return True, True, True
    return "auto" in modes, "step" in modes, "manual" in modes


def pytest_configure(config: pytest.Config) -> None:
    """Register marker and resolve configuration."""
    config.addinivalue_line(
        "markers", "report: mark test for HTML reporting"
    )

    _cfg.enabled = config.getini("report_enabled")
    if config.getoption("--disable-reporter", default=False):
        _cfg.enabled = False

    mode_str = config.getini("report_mode") or ""
    _cfg.mode_auto, _cfg.mode_step, _cfg.mode_manual = _parse_modes(mode_str)

    _cfg.output_dir = config.getini("report_dir") or "build/test-reports"
    _cfg.title = config.getini("report_title") or "Test Report"
    _cfg.log_level = (config.getini("report_log_level") or "DEBUG").upper()
    _cfg.auto_log = _cfg.mode_auto and config.getini("report_auto_log")
    _cfg.generate_html = config.getini("report_html")
    _cfg.exclude_loggers = [
        s.strip()
        for s in (config.getini("report_exclude_loggers") or "").split(",")
        if s.strip()
    ]
    _cfg.no_html_cli = config.getoption("--no-report-html", default=False)

    _set_steps_enabled(_cfg.enabled and _cfg.mode_step)


# ---------------------------------------------------------------------------
# Session-level: collect all test method names
# ---------------------------------------------------------------------------

_all_test_methods: list[str] = []


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Collect all test function names for the ``AllTestMethods`` field."""
    if not _cfg.enabled:
        return
    global _all_test_methods
    _all_test_methods = [item.name for item in items]


# ---------------------------------------------------------------------------
# Per-test lifecycle
# ---------------------------------------------------------------------------

# Store reporter and logging handler per-node so teardown can access them.
_reporters: dict[str, TestReporter] = {}
_logging_handlers: dict[str, ReportLoggingHandler] = {}


def _module_label(item: pytest.Item) -> str:
    """Derive a readable class/module label from a pytest item."""
    if item.cls:
        return item.cls.__name__
    module = getattr(item, "module", None)
    if module:
        name = getattr(module, "__name__", "")
        parts = name.rsplit(".", 1)
        return parts[-1] if parts else name
    return None


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """Create a TestReporter before each test and open a Setup step."""
    if not _cfg.enabled:
        return

    test_name = item.name
    class_name = _module_label(item)

    reporter = TestReporter(
        test_name=test_name,
        class_name=class_name,
        all_test_methods=list(_all_test_methods),
        output_dir=_cfg.output_dir,
    )

    _reporters[item.nodeid] = reporter
    _active_reporter.set(reporter)

    if _cfg.auto_log:
        handler = attach_logging_bridge(
            reporter,
            log_level=_cfg.log_level,
            exclude_loggers=_cfg.exclude_loggers,
        )
        _logging_handlers[item.nodeid] = handler

    reporter.begin_phase("Setup")


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """Capture test outcome per phase and manage phase steps."""
    if not _cfg.enabled:
        return
    reporter = _reporters.get(item.nodeid)
    if reporter is None:
        return

    if call.when == "setup":
        reporter.end_phase(call.excinfo)
        if call.excinfo is None:
            reporter.begin_phase(item.name)
        return

    if call.when == "call":
        error = call.excinfo.value if call.excinfo else None
        reporter.end_phase(error)
        if call.excinfo is not None:
            _phase_failures[item.nodeid] = (
                str(call.excinfo.value),
                "".join(traceback.format_exception(
                    call.excinfo.type, call.excinfo.value, call.excinfo.tb
                )),
            )
        return

    if call.when == "teardown":
        reporter.end_phase(call.excinfo)

        failure = _phase_failures.pop(item.nodeid, None)
        if failure:
            final_status = "FAILED"
            failure_message, stack_trace = failure
        else:
            final_status = "PASSED"
            failure_message = None
            stack_trace = None

        json_path = reporter.finalize(
            status=final_status,
            failure_message=failure_message,
            stack_trace=stack_trace,
        )

        if json_path and _should_upload_to_s3():
            _upload_json_to_s3(item, json_path)

        handler = _logging_handlers.pop(item.nodeid, None)
        if handler:
            detach_logging_bridge(handler)
        _active_reporter.set(None)
        _reporters.pop(item.nodeid, None)


_phase_failures: dict[str, tuple[str, str]] = {}


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_teardown(item: pytest.Item) -> None:
    """Open a Teardown phase step."""
    if not _cfg.enabled:
        return
    reporter = _reporters.get(item.nodeid)
    if reporter is None:
        return
    reporter.begin_phase("Teardown")




# ---------------------------------------------------------------------------
# Session end
# ---------------------------------------------------------------------------

def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if not _cfg.enabled:
        return

    output_dir = session.config.getini("report_dir") or _cfg.output_dir
    title = session.config.getini("report_title") or _cfg.title
    generate_html = session.config.getini("report_html")
    no_html_cli = session.config.getoption("--no-report-html", default=False)

    if generate_html and not no_html_cli:
        from .html_report import generate_report

        report_path = generate_report(output_dir, title=title)
        if report_path:
            abs_path = os.path.abspath(report_path)
            print(f"\n{'=' * 80}")
            print("  All Tests Completed - Aggregated Report:")
            print(f"   {abs_path}")
            print(f"   Open in browser: file://{abs_path}")
            print(f"{'=' * 80}\n")

            if _should_upload_to_s3():
                _upload_html_report_to_s3(output_dir)
        else:
            print(f"\nReports saved to: {output_dir}/json/")
    else:
        print(f"\nReports saved to: {output_dir}/json/")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def report_log(request: pytest.FixtureRequest) -> ReportLogger:
    """
    A report logger bound to the current test.

    Usage::

        def test_example(report_log):
            report_log.info("hello")
    """
    if not _cfg.enabled or not _cfg.mode_manual:
        return _NoOpReportLogger()

    reporter = _reporters.get(request.node.nodeid)
    if reporter is None:
        reporter = TestReporter(
            test_name=request.node.name,
            class_name=request.node.cls.__name__ if request.node.cls else None,
            all_test_methods=[],
            output_dir=_cfg.output_dir,
        )
        _reporters[request.node.nodeid] = reporter
        _active_reporter.set(reporter)

    return ReportLogger(reporter)


@pytest.fixture
def report_test_name(request: pytest.FixtureRequest):
    """
    Override the test name used in the JSON report filename and metadata.

    Usage::

        def test_firewall_rule(test_case, report_test_name):
            report_test_name(test_case.name)
    """
    def _set(name: str) -> None:
        if not _cfg.enabled:
            return
        reporter = _reporters.get(request.node.nodeid)
        if reporter is not None:
            reporter.test_name = name

    return _set


@pytest.fixture
def report_step() -> type[step]:
    """
    The ``step`` context manager / decorator.

    Usage::

        def test_example(report_step):
            with report_step("Create user"):
                ...
    """
    return step


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------

def _should_upload_to_s3() -> bool:
    ci = os.environ.get("REPORT_CI_RUN")
    run_id = os.environ.get("REPORT_RUN_ID")
    return ci == "true" and bool(run_id)


def _upload_json_to_s3(item: pytest.Item, json_path: str) -> None:
    try:
        from .s3_utils import upload_json_report

        test_name = item.name
        class_name = item.cls.__name__ if item.cls else item.module.__name__
        full_class_name = (
            f"{item.module.__name__}.{item.cls.__name__}"
            if item.cls
            else item.module.__name__
        )

        upload_json_report(
            class_name=class_name,
            test_name=test_name,
            full_class_name=full_class_name,
            json_file_path=json_path,
        )
    except ImportError:
        # boto3 not installed — skip silently
        pass
    except Exception as exc:
        print(f"  Failed to upload to S3: {exc}")


def _upload_html_report_to_s3(output_dir: str) -> None:
    """Upload the aggregated HTML report directory to S3."""
    try:
        from .s3_utils import upload_directory

        run_id = os.environ.get("REPORT_RUN_ID")
        if not run_id:
            return

        test_type = os.environ.get("REPORT_TEST_TYPE")
        cycle = os.environ.get("REPORT_CYCLE")
        suite_name = os.environ.get("REPORT_SUITE_NAME")

        if test_type and cycle and suite_name:
            key_prefix = f"{test_type}/{cycle}/{run_id}/{suite_name}/html-report/"
        else:
            key_prefix = f"{run_id}/html-report/"

        count = upload_directory(output_dir, key_prefix)
        if count > 0:
            print(f"  Uploaded {count} report files to S3")
    except ImportError:
        pass
    except Exception as exc:
        print(f"  Failed to upload HTML report to S3: {exc}")
