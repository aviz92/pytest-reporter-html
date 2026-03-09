# pytest-reporter-html

Pytest plugin that generates rich, interactive HTML test reports with step tracking, log capture, and filtering.

## Installation

```bash
pip install pytest-reporter-html
```

For S3 upload support:

```bash
pip install pytest-reporter-html[s3]
```

## Quick Start

Just install and run pytest — the plugin activates automatically:

```bash
pytest
```

Reports are written to `build/test-reports/` by default.

## Configuration

All options go in `pyproject.toml` under `[tool.pytest.ini_options]`:

| Option | Default | Description |
|--------|---------|-------------|
| `report_dir` | `build/test-reports` | Output directory for JSON and HTML reports |
| `report_title` | `Test Report` | Title shown in the HTML report header |
| `report_log_level` | `DEBUG` | Minimum log level to capture (`TRACE`/`DEBUG`/`INFO`/`WARN`/`ERROR`) |
| `report_auto_log` | `true` | Auto-capture Python logging into report events |
| `report_html` | `true` | Generate aggregated HTML report at session end |
| `report_exclude_loggers` | *(empty)* | Comma-separated logger prefixes to exclude from capture |

Example:

```toml
[tool.pytest.ini_options]
report_dir = "output/reports"
report_title = "My Project Tests"
report_log_level = "INFO"
report_exclude_loggers = "urllib3,botocore"
```

### CLI Options

| Flag | Description |
|------|-------------|
| `--no-report-html` | Disable HTML report generation (JSON still produced) |

## Fixtures

### `report_log`

A logger bound to the current test. Events appear in the HTML report.

```python
def test_login(report_log):
    report_log.info("Attempting login")
    result = login("user", "pass")
    report_log.info(f"Login result: {result}")
```

### `report_step`

The `step` context manager / decorator for grouping events into named steps.

```python
def test_checkout(report_step):
    with report_step("Add item to cart"):
        cart.add(item)

    with report_step("Complete payment"):
        cart.checkout()
```

`step` can also be used as a decorator:

```python
from pytest_reporter_html import step

@step("Validate response")
def validate(response):
    assert response.status_code == 200
```

### `report_test_name`

Override the test name in the report (useful for parameterized tests).

```python
def test_rule(test_case, report_test_name):
    report_test_name(test_case.name)
```

## S3 Upload (CI)

Set these environment variables to enable automatic S3 upload:

| Variable | Description |
|----------|-------------|
| `REPORT_CI_RUN` | Set to `true` to enable CI mode |
| `REPORT_RUN_ID` | Unique run identifier |
| `REPORT_TIMESTAMP` | Run timestamp |
| `REPORT_S3_BUCKET` | S3 bucket name (default: `external-test-results`) |
| `REPORT_S3_REGION` | S3 region (default: `eu-central-1`) |
| `REPORT_TEST_TYPE` | Test type identifier for S3 key prefix |
| `REPORT_CYCLE` | Test cycle for S3 key prefix |
| `REPORT_SUITE_NAME` | Suite name for S3 key prefix |

## License

MIT
