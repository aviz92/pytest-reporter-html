"""Tests for pytest_reporter_html.const."""

from __future__ import annotations

import pytest

from pytest_reporter_html.const import PluginConfig, TestStatus


class TestTestStatus:
    def test_values_are_ordered_by_severity(self) -> None:
        assert (
            TestStatus.PASSED < TestStatus.SKIPPED < TestStatus.FAILED < TestStatus.ERROR
        ), "Statuses must be ordered PASSED < SKIPPED < FAILED < ERROR"

    def test_comparison_passed_vs_failed(self) -> None:
        assert TestStatus["FAILED"] > TestStatus["PASSED"], "FAILED must be more severe than PASSED"

    def test_comparison_error_vs_failed(self) -> None:
        assert TestStatus["ERROR"] > TestStatus["FAILED"], "ERROR must be more severe than FAILED"

    def test_lookup_by_name(self) -> None:
        assert TestStatus["PASSED"] == TestStatus.PASSED, "Lookup by name must return correct member"

    @pytest.mark.parametrize(
        "name,expected_value",
        [
            ("PASSED", 0),
            ("SKIPPED", 1),
            ("FAILED", 2),
            ("ERROR", 3),
        ],
    )
    def test_int_values(self, name: str, expected_value: int) -> None:
        assert (
            TestStatus[name] == expected_value
        ), f"TestStatus[{name!r}] should be {expected_value}, got {TestStatus[name]}"

    def test_is_int_enum(self) -> None:
        assert isinstance(TestStatus.PASSED, int), "TestStatus members must be integers"


class TestPluginConfig:
    def test_default_output_dir(self) -> None:
        cfg = PluginConfig()
        assert (
            cfg.output_dir == "build/test-reports"
        ), f"Default output_dir should be 'build/test-reports', got {cfg.output_dir!r}"

    def test_default_title(self) -> None:
        cfg = PluginConfig()
        assert cfg.title == "Test Report", f"Default title should be 'Test Report', got {cfg.title!r}"

    def test_default_generate_html_is_false(self) -> None:
        cfg = PluginConfig()
        assert cfg.generate_html is False, f"Default generate_html should be False, got {cfg.generate_html!r}"

    def test_custom_values(self) -> None:
        cfg = PluginConfig(output_dir="/tmp/reports", title="My Report", generate_html=True)
        assert cfg.output_dir == "/tmp/reports", "output_dir not set correctly"
        assert cfg.title == "My Report", "title not set correctly"
        assert cfg.generate_html is True, "generate_html not set correctly"
