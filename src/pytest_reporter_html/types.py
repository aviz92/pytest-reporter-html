"""
Dataclasses for the pytest-reporter-html JSON report format.

These match the exact schema produced by the JUnit and Playwright reporters
so pytest results can be consumed identically.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ReportEvent:
    """A single log event within a step."""
    startTime: int
    level: str
    event: str
    type: Optional[str] = None
    sourceFileName: Optional[str] = None
    sourceLineNumber: Optional[int] = None

    def to_dict(self) -> dict:
        d: dict = {
            "startTime": self.startTime,
            "level": self.level,
            "event": self.event,
        }
        if self.type is not None:
            d["type"] = self.type
        if self.sourceFileName is not None:
            d["sourceFileName"] = self.sourceFileName
        if self.sourceLineNumber is not None:
            d["sourceLineNumber"] = self.sourceLineNumber
        return d


@dataclass
class ReportStep:
    """A logical step in a test (e.g. 'Create user', 'Verify result')."""
    startTime: int
    endTime: int = 0
    name: str = ""
    status: str = "PASSED"
    events: list[ReportEvent] = field(default_factory=list)
    failureMessage: Optional[str] = None
    stackTrace: Optional[str] = None

    def to_dict(self) -> dict:
        d: dict = {
            "startTime": self.startTime,
            "endTime": self.endTime,
            "name": self.name,
            "status": self.status,
            "events": [e.to_dict() for e in self.events],
        }
        if self.failureMessage is not None:
            d["failureMessage"] = self.failureMessage
        if self.stackTrace is not None:
            d["stackTrace"] = self.stackTrace
        return d


@dataclass
class JsonReport:
    """
    Top-level JSON report structure.

    Field names match the JUnit/Playwright reporters exactly:
    - ``AllTestMethods`` is PascalCase to match the existing schema.
    """
    steps: list[ReportStep] = field(default_factory=list)
    AllTestMethods: list[str] = field(default_factory=list)
    testStatus: str = "PASSED"
    className: Optional[str] = None
    failureMessage: Optional[str] = None
    stackTrace: Optional[str] = None
    externalTestReportLink: Optional[str] = None

    def to_dict(self) -> dict:
        d: dict = {
            "steps": [s.to_dict() for s in self.steps],
            "AllTestMethods": self.AllTestMethods,
            "testStatus": self.testStatus,
        }
        if self.className:
            d["className"] = self.className
        if self.failureMessage is not None:
            d["failureMessage"] = self.failureMessage
        if self.stackTrace is not None:
            d["stackTrace"] = self.stackTrace
        if self.externalTestReportLink is not None:
            d["externalTestReportLink"] = self.externalTestReportLink
        return d


def _now_millis() -> int:
    """Current time as epoch milliseconds."""
    return int(time.time() * 1000)
