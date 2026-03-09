"""
S3 upload utilities for test reports.

Uses the same environment variables as the JUnit and Playwright reporters
so the CI/CD pipeline configuration is identical across languages.

Requires ``boto3`` — install with ``pip install pytest-reporter-html[s3]``.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
import boto3


def upload_json_report(
    class_name: str,
    test_name: str,
    full_class_name: str,
    json_file_path: str,
) -> None:
    """
    Upload a single test's JSON report to S3.

    Key format matches the JUnit reporter::

        {testType}/{cycle}/{runId}/{suiteName}/{fullClassName}#{filename}
    """

    run_id = os.environ.get("REPORT_RUN_ID")
    if not run_id or not run_id.strip():
        return

    bucket = os.environ.get("REPORT_S3_BUCKET", "external-test-results")
    region = os.environ.get("REPORT_S3_REGION", "eu-central-1")

    test_type = os.environ.get("REPORT_TEST_TYPE")
    cycle = os.environ.get("REPORT_CYCLE")
    suite_name = os.environ.get("REPORT_SUITE_NAME")

    if not (test_type and cycle and suite_name):
        print("  S3 upload skipped: testType, cycle, or suiteName not set")
        return

    key_prefix = f"{test_type}/{cycle}/{run_id}/{suite_name}/"

    # Build S3 key matching JUnit convention — filename already has real timestamp
    json_filename = Path(json_file_path).name
    s3_key = f"{key_prefix}{full_class_name}#{json_filename}"

    s3 = boto3.client("s3", region_name=region)
    s3.upload_file(
        Filename=json_file_path,
        Bucket=bucket,
        Key=s3_key,
        ExtraArgs={"ContentType": "application/json"},
    )
    print(f"  Uploaded to s3://{bucket}/{s3_key}")


def upload_directory(
    local_dir: str,
    key_prefix: str,
    bucket: Optional[str] = None,
    region: Optional[str] = None,
) -> int:
    """
    Upload all files in a directory to S3 recursively.
    Returns the number of files uploaded.
    """

    bucket = bucket or os.environ.get("REPORT_S3_BUCKET", "external-test-results")
    region = region or os.environ.get("REPORT_S3_REGION", "eu-central-1")

    local_path = Path(local_dir)
    if not local_path.exists():
        return 0

    s3 = boto3.client("s3", region_name=region)
    count = 0

    for file_path in local_path.rglob("*"):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(local_path)
        s3_key = f"{key_prefix}{relative.as_posix()}"

        content_type = _get_content_type(file_path.suffix)
        s3.upload_file(
            Filename=str(file_path),
            Bucket=bucket,
            Key=s3_key,
            ExtraArgs={"ContentType": content_type},
        )
        count += 1

    return count


def _get_content_type(ext: str) -> str:
    types = {
        ".json": "application/json",
        ".html": "text/html",
        ".xml": "application/xml",
        ".txt": "text/plain",
        ".css": "text/css",
        ".js": "application/javascript",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".svg": "image/svg+xml",
    }
    return types.get(ext.lower(), "application/octet-stream")
