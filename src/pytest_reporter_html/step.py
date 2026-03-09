"""
Step tracking for test reports.

Provides two APIs:

1. **Context manager** — for inline steps within a test::

       with step("Create user"):
           log.info("Creating user")
           ...

2. **Decorator** — for helper functions that are always a step::

       @step("Create user via API")
       def create_user(session, name):
           ...

Both sync and async functions/blocks are supported.
"""
from __future__ import annotations

import functools
import inspect
from contextvars import ContextVar
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .reporter import TestReporter

# ---- context-var holding the active reporter for the current test ----
# Set by the plugin before each test, cleared after.
_active_reporter: ContextVar[Optional[TestReporter]] = ContextVar(
    "_active_reporter", default=None
)


def _get_reporter() -> Optional[TestReporter]:
    """Return the active TestReporter, or None."""
    return _active_reporter.get()


class step:
    """
    Context manager **and** decorator for creating a named step.

    As context manager::

        with step("Verify result"):
            assert resp.status_code == 200

    As decorator (sync or async):

        @step("Create user")
        async def create_user(client):
            ...

    If the block/function raises, the step is marked FAILED with the
    exception message and traceback.
    """

    def __init__(self, name: str):
        self.name = name

    # ---- context manager (sync) ----

    def __enter__(self):
        reporter = _get_reporter()
        if reporter is not None:
            reporter.begin_step(self.name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        reporter = _get_reporter()
        if reporter is not None:
            reporter.end_step(exc_val)
        return False  # don't suppress

    # ---- context manager (async) ----

    async def __aenter__(self):
        reporter = _get_reporter()
        if reporter is not None:
            reporter.begin_step(self.name)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        reporter = _get_reporter()
        if reporter is not None:
            reporter.end_step(exc_val)
        return False

    # ---- decorator ----

    def __call__(self, func):
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                async with self:
                    result = await func(*args, **kwargs)
                return result

            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                with self:
                    result = func(*args, **kwargs)
                return result

            return sync_wrapper
