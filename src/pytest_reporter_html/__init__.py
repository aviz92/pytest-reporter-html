"""
pytest-reporter-html — Pytest reporter for HTML test reports.

Public API::

    from pytest_reporter_html import step

    @step("Create user")
    async def create_user(client):
        ...

    def test_example(report_log, report_step):
        with report_step("Verify"):
            report_log.info("checking result")
            ...
"""
from .step import step
from .logger import ReportLogger
from .types import JsonReport, ReportStep, ReportEvent

__all__ = [
    "step",
    "ReportLogger",
    "JsonReport",
    "ReportStep",
    "ReportEvent",
]
