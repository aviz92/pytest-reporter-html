#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

rm -rf build/test-reports/json/*.json build/test-reports/*.html

echo "Running pytest-reporter-html tests..."
uv run pytest tests/ -v --tb=short "$@"
