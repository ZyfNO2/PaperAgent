#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH="config/provider-router-balanced.example.json"
REQUESTS=24
CONCURRENCY=8
REQUIRE_SUCCESSFUL_ENDPOINTS=2
OUTPUT_PATH="artifacts/provider-router-load-report.json"
SKIP_INSTALL=0
SKIP_SEMANTIC=0
SKIP_LIVE=0

usage() {
  cat <<'EOF'
Usage: scripts/run_local_semantic_and_router_test.sh [options]

Options:
  --config PATH                    Router JSON configuration.
  --requests N                     Total live probe requests (default: 24).
  --concurrency N                  Concurrent probes (default: 8).
  --require-successful-endpoints N Minimum endpoints with at least one success (default: 2).
  --output PATH                    JSON report path.
  --skip-install                   Do not install development dependencies.
  --skip-semantic                  Skip offline semantic regression tests.
  --skip-live                      Skip real provider router probes.
  -h, --help                       Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) CONFIG_PATH="$2"; shift 2 ;;
    --requests) REQUESTS="$2"; shift 2 ;;
    --concurrency) CONCURRENCY="$2"; shift 2 ;;
    --require-successful-endpoints) REQUIRE_SUCCESSFUL_ENDPOINTS="$2"; shift 2 ;;
    --output) OUTPUT_PATH="$2"; shift 2 ;;
    --skip-install) SKIP_INSTALL=1; shift ;;
    --skip-semantic) SKIP_SEMANTIC=1; shift ;;
    --skip-live) SKIP_LIVE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ "$SKIP_INSTALL" -eq 0 ]]; then
  echo "[1/3] Installing PaperAgent development dependencies..."
  python -m pip install -e '.[dev]'
fi

if [[ "$SKIP_SEMANTIC" -eq 0 ]]; then
  echo "[2/3] Running role-bound semantic and router regression tests..."
  python -m pytest -q \
    tests/methodology/test_strict_method_design.py \
    tests/methodology/test_method_design_draft.py \
    tests/evals/test_academic_tailoring_retrieval_v1_scorer.py \
    tests/evals/test_academic_tailoring_retrieval_v2_scorer.py \
    tests/providers/test_routing_llm_provider.py \
    tests/scripts/test_provider_router_load.py
fi

if [[ "$SKIP_LIVE" -eq 0 ]]; then
  echo "[3/3] Running live concurrent router probes..."
  python scripts/test_provider_router_load.py \
    --config "$CONFIG_PATH" \
    --requests "$REQUESTS" \
    --concurrency "$CONCURRENCY" \
    --output "$OUTPUT_PATH"

  python - "$OUTPUT_PATH" "$REQUIRE_SUCCESSFUL_ENDPOINTS" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
required = int(sys.argv[2])
report = json.loads(report_path.read_text(encoding="utf-8"))
endpoints = report.get("endpoints", {})
successful = {
    endpoint_id: payload
    for endpoint_id, payload in endpoints.items()
    if int(payload.get("successes", 0)) > 0
}
if report.get("status") != "passed":
    raise SystemExit(
        f"router load report status is {report.get('status')!r}, expected 'passed'"
    )
if len(successful) < required:
    distribution = ", ".join(
        f"{endpoint_id}={payload.get('successes', 0)}"
        for endpoint_id, payload in endpoints.items()
    )
    raise SystemExit(
        f"only {len(successful)} endpoints completed requests; required {required}. "
        f"Distribution: {distribution}"
    )

print("Router validation passed.")
print(f"  Throughput: {report.get('throughput_requests_per_second')} requests/s")
print(f"  Request p95: {report.get('request_latency_ms', {}).get('p95')} ms")
print(f"  Successful endpoints: {len(successful)}")
for endpoint_id, payload in endpoints.items():
    latency = payload.get("latency_ms", {})
    print(
        f"  - {endpoint_id}: calls={payload.get('calls')}, "
        f"successes={payload.get('successes')}, failures={payload.get('failures')}, "
        f"p95={latency.get('p95')} ms"
    )
print(f"  Report: {report_path.resolve()}")
PY
fi
