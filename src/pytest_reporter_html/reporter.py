"""
JSON report builder for a single test.

One ``TestReporter`` instance is created per test by the plugin.
It accumulates steps and events, then writes the final JSON file.
"""
from __future__ import annotations

import json
import os
import traceback
from pathlib import Path
from typing import Optional

from .types import JsonReport, ReportStep, ReportEvent, _now_millis


class TestReporter:
    """
    Builds a ``JsonReport`` for a single test function.

    Lifecycle (managed by the plugin):
        1. ``__init__`` — at test setup
        2. ``_begin_step`` / ``_end_step`` — via ``step()`` context manager
        3. ``_add_event`` — via ``ReportLogger``
        4. ``finalize`` — at test teardown, writes JSON
    """

    def __init__(
        self,
        test_name: str,
        class_name: Optional[str],
        all_test_methods: list[str],
        output_dir: str,
    ):
        self.test_name = test_name
        self.class_name = class_name
        self.output_dir = output_dir
        self._timestamp = self._resolve_timestamp()

        self._report = JsonReport(AllTestMethods=all_test_methods, className=class_name)
        self._current_step: Optional[ReportStep] = None
        self._step_counter = 0
        self._is_phase_step = False

    @staticmethod
    def _resolve_timestamp() -> str:
        """
        Use ``REPORT_TIMESTAMP`` env var if set (CI mode),
        otherwise fall back to current epoch millis.
        """
        ts = os.environ.get("REPORT_TIMESTAMP")
        if ts and ts.strip():
            return ts.strip()
        return str(_now_millis())

    # ---- step management (called by step context manager) ----

    def begin_step(self, name: str) -> None:
        if self._current_step is not None:
            self._close_current_step(None)

        self._step_counter += 1
        label = f"Step {self._step_counter:02d}: {name}"
        self._current_step = ReportStep(
            startTime=_now_millis(),
            name=label,
        )
        self._is_phase_step = False

    def end_step(self, error: Optional[BaseException]) -> None:
        self._close_current_step(error)

    # ---- phase steps (auto-created by plugin for setup/call/teardown) ----

    def begin_phase(self, name: str) -> None:
        if self._current_step is not None:
            self._close_current_step(None)

        self._current_step = ReportStep(
            startTime=_now_millis(),
            name=name,
        )
        self._is_phase_step = True

    def end_phase(self, error: Optional[BaseException] = None) -> None:
        if self._current_step is None:
            return

        is_phase = self._is_phase_step
        self._close_current_step(error)

        if is_phase:
            last = self._report.steps[-1]
            is_lifecycle = last.name in ("Setup", "Teardown")
            if is_lifecycle and not last.events and last.status == "PASSED":
                self._report.steps.pop()

    def _close_current_step(self, error: Optional[BaseException]) -> None:
        if self._current_step is None:
            return

        self._current_step.endTime = _now_millis()

        if error is not None:
            self._current_step.status = "FAILED"
            err = error.value if hasattr(error, "value") else error
            self._current_step.failureMessage = str(err)
            tb = getattr(error, "tb", None) or getattr(err, "__traceback__", None)
            if tb:
                self._current_step.stackTrace = "".join(
                    traceback.format_exception(type(err), err, tb)
                )
        else:
            self._current_step.status = "PASSED"

        self._report.steps.append(self._current_step)
        self._current_step = None
        self._is_phase_step = False

    # ---- event management (called by logger) ----

    def add_event(self, event: ReportEvent) -> None:
        if self._current_step is not None:
            self._current_step.events.append(event)
        else:
            implicit = ReportStep(
                startTime=event.startTime,
                endTime=event.startTime,
                name=self.test_name,
                status="PASSED",
                events=[event],
            )
            self._report.steps.append(implicit)

    # ---- finalization ----

    def finalize(
        self,
        status: str,
        failure_message: Optional[str] = None,
        stack_trace: Optional[str] = None,
    ) -> Optional[str]:
        """
        Close any open step, set final status, write JSON file.
        Returns the file path written, or ``None`` on error.
        """
        # Close any dangling step
        if self._current_step is not None:
            self._close_current_step(None)

        self._report.testStatus = status
        self._report.failureMessage = failure_message
        self._report.stackTrace = stack_trace

        # Build external report link if S3 is configured
        link = self._build_external_link()
        if link:
            self._report.externalTestReportLink = link

        return self._write_json()

    def _write_json(self) -> Optional[str]:
        """Write the report to disk and return the file path."""
        try:
            out = Path(self.output_dir) / "json"
            out.mkdir(parents=True, exist_ok=True)

            filename = f"{self.test_name}_{self._timestamp}.json"
            filepath = out / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self._report.to_dict(), f, indent=2, ensure_ascii=False)

            print(f"  JSON report saved: {filepath}")
            return str(filepath)
        except Exception as exc:
            print(f"  Failed to write JSON report: {exc}")
            return None

    @staticmethod
    def _build_external_link() -> Optional[str]:
        """Build the S3 URL for the external report (same env vars as JUnit)."""
        run_id = os.environ.get("REPORT_RUN_ID")
        if not run_id or not run_id.strip():
            return None

        bucket = os.environ.get("REPORT_S3_BUCKET", "external-test-results")
        region = os.environ.get("REPORT_S3_REGION", "eu-central-1")

        test_type = os.environ.get("REPORT_TEST_TYPE")
        cycle = os.environ.get("REPORT_CYCLE")
        suite_name = os.environ.get("REPORT_SUITE_NAME")

        if test_type and cycle and suite_name:
            prefix = f"{test_type}/{cycle}/{run_id}/{suite_name}/html-report/"
        else:
            prefix = f"{run_id}/html-report/"

        return f"https://{bucket}.s3.{region}.amazonaws.com/{prefix}TestReport_Latest.html"
