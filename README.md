# pytest-reporter-html

[![PyPI version](https://img.shields.io/pypi/v/pytest-reporter-html)](https://pypi.org/project/pytest-reporter-html/)
[![PyPI downloads](https://img.shields.io/pypi/dm/pytest-reporter-html)](https://pypistats.org/packages/pytest-reporter-html)
[![Python versions](https://img.shields.io/pypi/pyversions/pytest-reporter-html)](https://pypi.org/project/pytest-reporter-html/)
[![License](https://img.shields.io/pypi/l/pytest-reporter-html)](https://github.com/YevgenyFarber/pytest-reporter-html/blob/main/LICENSE)

A pytest plugin that automatically generates rich, interactive HTML test reports with **log capture**, **step tracking**, **exception rendering**, and **real-time filtering**.

Install it, configure a capture mode, run `pytest`, get a report.

---

## Installation

```bash
pip install pytest-reporter-html
```

For S3 upload support (CI environments):

```bash
pip install pytest-reporter-html[s3]
```

## Quick Start

Enable a capture mode in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
report_mode = "all"     # auto + step + manual (see Capture Modes below)
```

Run pytest:

```bash
pytest
```

After the run:

```
================================================================================
  All Tests Completed - Aggregated Report:
   /absolute/path/to/build/test-reports/TestReport_Latest.html
   Open in browser: file:///absolute/path/to/build/test-reports/TestReport_Latest.html
================================================================================
```

Open the HTML file in any browser.

---

## How It Works

The plugin hooks into pytest's test lifecycle and builds a structured report for every test, organized as:

```
Session
 └── Test Class / Module (collapsible group)
      └── Test Function (collapsible)
           └── Step (auto-created per test phase)
                └── Event (captured log line)
```

### Zero-Config Log Capture

The plugin attaches a handler to Python's **root logger** at test start and removes it at teardown. Any code that uses standard `logging` — your application, third-party libraries, anything — has its output captured as **events** in the report. No imports, no fixtures, no code changes.

```python
# your application code (not test code)
import logging
logger = logging.getLogger(__name__)

def create_order(items):
    logger.info(f"Creating order with {len(items)} items")
    order = db.insert(items)
    logger.info(f"Order created: {order.id}")
    return order

def validate_payment(order_id, method):
    logger.debug(f"Validating payment for order {order_id}")
    if method not in SUPPORTED_METHODS:
        logger.error(f"Unsupported payment method: {method}")
        raise ValueError(f"Unsupported: {method}")
    logger.info("Payment validated")
```

```python
# your test — no plugin imports needed
def test_place_order():
    order = create_order([{"sku": "A1", "qty": 2}])
    validate_payment(order.id, "card")
    assert order.status == "confirmed"
```

The report captures every `logger.*()` call from `create_order` and `validate_payment` as events, even though the test itself has no logging code:

```
Test: test_place_order                                               PASSED
 └── test_place_order                                       PASSED    85ms
      ├── INFO  Creating order with 1 items         orders.py:5
      ├── INFO  Order created: ord-123              orders.py:7
      ├── DEBUG Validating payment for order ord-123 payments.py:3
      └── INFO  Payment validated                   payments.py:7
```

Each captured event records:
- **Level** — `TRACE`, `DEBUG`, `INFO`, `WARN`, `ERROR`
- **Message** — the formatted log message
- **Source file** and **line number** — from the actual call site
- **Timestamp** — millisecond precision

### Exception Capture

Exceptions logged via `logger.exception()` or `logger.error(..., exc_info=True)` are captured with their **full formatted traceback**, rendered as a collapsible block in the HTML report — exactly as they would appear at runtime.

### Automatic Phase Steps

For each test, the plugin automatically creates steps for the pytest lifecycle phases:

- **Setup** — fixture setup (hidden if empty and passed)
- **\<test function name\>** — the test body itself
- **Teardown** — fixture teardown (hidden if empty and passed)

This means every test has at least one step (its own name) where all captured events are grouped — without any code on your part.

### Adding Descriptive Logs to Tests

While the plugin captures application-level logging automatically, you can add descriptive logs directly in your tests to make the report more readable:

```python
import logging

logger = logging.getLogger(__name__)

class TestCheckout:
    def test_empty_cart_rejected(self):
        logger.info("Attempting checkout with empty cart")
        response = client.post("/checkout", json={"items": []})

        logger.info(f"Response status: {response.status_code}")
        assert response.status_code == 400

        logger.info("Empty cart correctly rejected")

    def test_successful_purchase(self):
        logger.info("Adding item to cart and checking out")
        cart = Cart()
        cart.add("SKU-42", qty=2)
        response = client.post("/checkout", json=cart.to_dict())

        logger.info(f"Order ID: {response.json()['order_id']}")
        assert response.status_code == 201
```

These `logger.info()` calls appear as events in the report, making it clear what each test does when you read the HTML output.

---

## Explicit Steps (Optional)

For tests with multiple logical phases, you can optionally use the `step` context manager to group events into **named steps**. This is entirely optional — most tests work fine with just logging.

### `step` as Context Manager

```python
from pytest_reporter_html import step

def test_user_lifecycle():
    with step("Create user"):
        response = client.post("/users", json={"name": "Alice"})
        assert response.status_code == 201
        user_id = response.json()["id"]

    with step("Update profile"):
        client.patch(f"/users/{user_id}", json={"role": "admin"})

    with step("Verify changes"):
        user = client.get(f"/users/{user_id}").json()
        assert user["role"] == "admin"
```

Report output:

```
Test: test_user_lifecycle                                            PASSED
 ├── Step 01: Create user                               PASSED    120ms
 ├── Step 02: Update profile                            PASSED     45ms
 └── Step 03: Verify changes                            PASSED     30ms
```

If a step raises, it is marked **FAILED** with the exception message and stack trace.

### `step` as Decorator

```python
from pytest_reporter_html import step

@step("Create admin user")
def create_admin(client, name):
    return client.post("/admin", json={"name": name}).json()

def test_admin_flow():
    admin = create_admin(client, "Bob")     # → Step 01: Create admin user
    assert admin["role"] == "admin"
```

Async functions are supported:

```python
@step("Fetch data")
async def fetch_data(session):
    async with session.get("/data") as resp:
        return await resp.json()
```

### `report_step` Fixture

If you prefer not to import `step` directly:

```python
def test_example(report_step):
    with report_step("Prepare"):
        data = load_fixtures()
    with report_step("Execute"):
        result = process(data)
```

---

## Fixtures Reference

All fixtures are available automatically — no imports or configuration needed.

### `report_log`

A logger that writes events directly to the report (bypasses Python's logging system):

```python
def test_example(report_log):
    report_log.info("Starting test")
    report_log.debug("Debug detail")
    report_log.warn("Something unexpected")
    report_log.error("Something failed")
```

> Most projects don't need this — standard `logging` is captured automatically.

### `report_step`

The `step` context manager, available as a fixture:

```python
def test_example(report_step):
    with report_step("Do something"):
        ...
```

### `report_test_name`

Override the test name in the report (useful for parameterized tests):

```python
def test_firewall_rule(rule, report_test_name):
    report_test_name(rule.name)  # "Allow-HTTP-Inbound" instead of "test_firewall_rule[rule0]"
```

---

## Output Structure

```
build/test-reports/
├── json/
│   ├── test_login_1709912345000.json
│   ├── test_checkout_1709912345100.json
│   └── ...
├── TestReport_Latest.html            ← open this
└── TestReport_All_1709912345000.html ← timestamped copy
```

- **JSON files** — one per test, containing steps, events, status, timing, and metadata
- **HTML report** — aggregated single-page dashboard

### JSON Structure

```json
{
  "testStatus": "PASSED",
  "className": "TestCheckout",
  "steps": [
    {
      "name": "test_empty_cart_rejected",
      "status": "PASSED",
      "startTime": 1709912345000,
      "endTime": 1709912345120,
      "events": [
        {
          "level": "INFO",
          "event": "Attempting checkout with empty cart",
          "startTime": 1709912345010,
          "sourceFileName": "test_checkout.py",
          "sourceLineNumber": 8
        },
        {
          "level": "INFO",
          "event": "Response status: 400",
          "startTime": 1709912345080,
          "sourceFileName": "test_checkout.py",
          "sourceLineNumber": 11
        }
      ]
    }
  ],
  "AllTestMethods": ["test_empty_cart_rejected", "test_successful_purchase"]
}
```

---

## HTML Report Features

- **Progress bar** — visual pass/fail ratio at the top
- **Search** — filter tests by name in real time
- **Status filter** — show All / Passed / Failed
- **Log level filter** — show events at TRACE / DEBUG / INFO / WARN / ERROR and above
- **Collapsible class groups** — tests grouped by class or module, with pass/fail badges
- **Collapsible tests** — click to expand and see steps and events
- **Collapsible steps** — each step shows its events, duration, and status
- **Auto-expand failures** — failed tests and steps open by default
- **Exception rendering** — full tracebacks in collapsible `<pre>` blocks
- **Expand All / Collapse All** — toolbar buttons
- **Copy report URL** — one-click copy

---

## Configuration

All options go in `pyproject.toml` under `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
report_mode = "all"
report_dir = "build/test-reports"
report_title = "My Project"
report_log_level = "INFO"
report_html = true
report_exclude_loggers = "urllib3,botocore,httpcore"
```

### Options Reference

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `report_enabled` | `bool` | `true` | Master switch — set to `false` to completely disable the reporter |
| `report_mode` | `string` | *(empty — disabled)* | Capture mode (see [Capture Modes](#capture-modes)). **Must be set to enable reporting.** |
| `report_dir` | `string` | `build/test-reports` | Output directory for JSON and HTML reports |
| `report_title` | `string` | `Test Report` | Title shown in the HTML report header |
| `report_log_level` | `string` | `DEBUG` | Minimum log level to capture: `TRACE`, `DEBUG`, `INFO`, `WARN`, `ERROR` |
| `report_auto_log` | `bool` | `true` | Legacy toggle for auto log capture (prefer `report_mode`) |
| `report_html` | `bool` | `true` | Generate the aggregated HTML report at session end |
| `report_exclude_loggers` | `string` | *(empty)* | Comma-separated logger name prefixes to exclude from capture |

### CLI Options

| Flag | Description |
|------|-------------|
| `--disable-reporter` | Completely disable the reporter (no JSON, no HTML) |
| `--no-report-html` | Disable HTML report generation (JSON still produced) |

### Capture Modes

The plugin supports three capture modes that can be used individually or combined:

| Mode | What it captures |
|------|-----------------|
| `auto` | Python's standard `logging` output — zero-config, captures application and test logs |
| `step` | Explicit `step()` context manager and decorator calls |
| `manual` | The `report_log` fixture (`report_log.info(...)`, etc.) |

By default no mode is active — **you must set `report_mode` to enable reporting**. Set it in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
# Enable all modes
report_mode = "all"

# Only auto-capture Python logging (step() and report_log become no-ops)
report_mode = "auto"

# Only explicit steps (no auto-log, report_log becomes no-op)
report_mode = "step"

# Only report_log fixture (no auto-log, step() becomes no-op)
report_mode = "manual"

# Combine modes with comma-separated values
report_mode = "auto,step"
report_mode = "step,manual"
```

When a mode is not selected, its API becomes a **silent no-op** — test code using `step()` or `report_log` will still run without errors, but events won't appear in the report.

### Disabling the Reporter

To completely disable all reporting (no JSON, no HTML, no overhead):

```bash
# Via CLI flag
pytest --disable-reporter

# Via ini option
# pyproject.toml
[tool.pytest.ini_options]
report_enabled = false
```

When disabled, all hooks are skipped, `step()` is a no-op, and `report_log` is a no-op.

### Excluding Noisy Loggers

```toml
[tool.pytest.ini_options]
report_exclude_loggers = "urllib3,botocore,httpcore,asyncio"
```

---

## S3 Upload (CI)

Set environment variables to upload reports to S3 automatically:

| Variable | Required | Description |
|----------|----------|-------------|
| `REPORT_CI_RUN` | Yes | Set to `true` to enable S3 upload |
| `REPORT_RUN_ID` | Yes | Unique run identifier |
| `REPORT_TIMESTAMP` | No | Run timestamp (defaults to current time) |
| `REPORT_S3_BUCKET` | No | S3 bucket (default: `external-test-results`) |
| `REPORT_S3_REGION` | No | S3 region (default: `eu-central-1`) |
| `REPORT_TEST_TYPE` | No | Test type for S3 key prefix |
| `REPORT_CYCLE` | No | Test cycle for S3 key prefix |
| `REPORT_SUITE_NAME` | No | Suite name for S3 key prefix |

Requires: `pip install pytest-reporter-html[s3]`

## Compatibility

- Python 3.10+
- pytest 7.0+
- Works with `pytest-asyncio`, `pytest-xdist`, and standard pytest plugins
- Sync and async tests fully supported

## License

MIT
