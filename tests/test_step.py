"""Tests for pytest_reporter_html.step — step context manager and decorator."""
from __future__ import annotations

import asyncio
import logging

import pytest

from pytest_reporter_html.step import _active_reporter, step

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class TestStepContextManager:
    def test_creates_step_on_enter_exit(self, reporter):
        log.info("Use step() as context manager — verify step is created and PASSED")
        _active_reporter.set(reporter)
        try:
            with step("my step"):
                pass

            s = reporter._report.steps[0]
            log.debug(f"Step name='{s.name}', status={s.status}")
            assert len(reporter._report.steps) == 1
            assert s.name == "Step 01: my step"
            assert s.status == "PASSED"
        finally:
            _active_reporter.set(None)

    def test_step_failed_on_exception(self, reporter):
        log.info("Raise exception inside step — verify FAILED status and failure message")
        _active_reporter.set(reporter)
        try:
            with pytest.raises(ValueError, match="bad"):
                with step("failing"):
                    raise ValueError("bad")

            s = reporter._report.steps[0]
            log.debug(f"Step status={s.status}, failureMessage='{s.failureMessage}'")
            assert s.status == "FAILED"
            assert s.failureMessage == "bad"
        finally:
            _active_reporter.set(None)

    def test_exception_propagates(self, reporter):
        log.info("Verify exception propagates out of step context manager")
        _active_reporter.set(reporter)
        try:
            with pytest.raises(RuntimeError):
                with step("boom"):
                    raise RuntimeError("crash")
            log.debug("RuntimeError was re-raised as expected")
        finally:
            _active_reporter.set(None)

    def test_nested_steps(self, reporter):
        log.info("Create two sequential steps — verify both are recorded in order")
        _active_reporter.set(reporter)
        try:
            with step("outer"):
                pass
            with step("inner"):
                pass

            names = [s.name for s in reporter._report.steps]
            log.debug(f"Step names: {names}")
            assert len(reporter._report.steps) == 2
            assert names[0] == "Step 01: outer"
            assert names[1] == "Step 02: inner"
        finally:
            _active_reporter.set(None)

    def test_noop_without_reporter(self):
        log.info("Use step() with no active reporter — should be a no-op")
        _active_reporter.set(None)
        with step("ignored"):
            pass
        log.debug("No error raised — step was silently ignored")

    def test_noop_when_steps_disabled(self, reporter):
        log.info("Set _steps_enabled=False — step() becomes no-op even with active reporter")
        from pytest_reporter_html.step import _set_steps_enabled
        _active_reporter.set(reporter)
        try:
            _set_steps_enabled(False)
            with step("should not appear"):
                pass
            log.debug(f"Steps recorded: {len(reporter._report.steps)}")
            assert len(reporter._report.steps) == 0
        finally:
            _set_steps_enabled(True)
            _active_reporter.set(None)


class TestStepAsyncContextManager:
    async def test_async_step(self, reporter):
        log.info("Use step() as async context manager — verify PASSED step")
        _active_reporter.set(reporter)
        try:
            async with step("async work"):
                await asyncio.sleep(0)

            s = reporter._report.steps[0]
            log.debug(f"Async step name='{s.name}', status={s.status}")
            assert len(reporter._report.steps) == 1
            assert s.name == "Step 01: async work"
            assert s.status == "PASSED"
        finally:
            _active_reporter.set(None)

    async def test_async_step_failed(self, reporter):
        log.info("Raise exception in async step — verify FAILED status")
        _active_reporter.set(reporter)
        try:
            with pytest.raises(ValueError):
                async with step("fail"):
                    raise ValueError("async fail")

            log.debug(f"Async step status: {reporter._report.steps[0].status}")
            assert reporter._report.steps[0].status == "FAILED"
        finally:
            _active_reporter.set(None)


class TestStepDecorator:
    def test_sync_decorator(self, reporter):
        log.info("Use step() as sync decorator — verify step created and return value preserved")
        _active_reporter.set(reporter)
        try:
            @step("decorated")
            def helper():
                return 42

            result = helper()
            log.debug(f"Return value: {result}, step name='{reporter._report.steps[0].name}'")
            assert result == 42
            assert len(reporter._report.steps) == 1
            assert reporter._report.steps[0].name == "Step 01: decorated"
            assert reporter._report.steps[0].status == "PASSED"
        finally:
            _active_reporter.set(None)

    def test_sync_decorator_with_args(self, reporter):
        log.info("Decorated function with arguments — verify args are passed through")
        _active_reporter.set(reporter)
        try:
            @step("add")
            def add(a, b):
                return a + b

            result = add(3, 4)
            log.debug(f"add(3, 4) = {result}")
            assert result == 7
        finally:
            _active_reporter.set(None)

    def test_sync_decorator_failure(self, reporter):
        log.info("Decorated function raises — verify step is FAILED and exception propagates")
        _active_reporter.set(reporter)
        try:
            @step("will fail")
            def fail():
                raise TypeError("wrong type")

            with pytest.raises(TypeError):
                fail()

            log.debug(f"Step status: {reporter._report.steps[0].status}")
            assert reporter._report.steps[0].status == "FAILED"
        finally:
            _active_reporter.set(None)

    async def test_async_decorator(self, reporter):
        log.info("Use step() as async decorator — verify step and return value")
        _active_reporter.set(reporter)
        try:
            @step("async decorated")
            async def async_helper():
                await asyncio.sleep(0)
                return "done"

            result = await async_helper()
            log.debug(f"Async return: '{result}', step='{reporter._report.steps[0].name}'")
            assert result == "done"
            assert len(reporter._report.steps) == 1
            assert reporter._report.steps[0].name == "Step 01: async decorated"
        finally:
            _active_reporter.set(None)

    async def test_async_decorator_failure(self, reporter):
        log.info("Async decorated function raises — verify FAILED step")
        _active_reporter.set(reporter)
        try:
            @step("async fail")
            async def boom():
                raise IOError("disk full")

            with pytest.raises(IOError):
                await boom()

            log.debug(f"Step status: {reporter._report.steps[0].status}")
            assert reporter._report.steps[0].status == "FAILED"
        finally:
            _active_reporter.set(None)

    def test_decorator_preserves_function_name(self, reporter):
        log.info("Verify @step decorator preserves the original function's __name__")
        _active_reporter.set(reporter)
        try:
            @step("named")
            def my_function():
                pass

            log.debug(f"Function name: {my_function.__name__}")
            assert my_function.__name__ == "my_function"
        finally:
            _active_reporter.set(None)
