"""Smoke test for the 12-case demo fixtures.

Reads every JSON in ``data/demo_cases/``, POSTs it to a live uvicorn,
POSTs ``/intake/validate``, and asserts that the returned ``intake_rating``
matches the rating encoded in the filename prefix (``A_``, ``B_``, ``C_``,
``D_``).

Exits non-zero on any failure.

Usage:
    python scripts/demo_smoke.py [BASE_URL]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


REPO = Path(__file__).resolve().parents[1]
DEMO_DIR = REPO / "data" / "demo_cases"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18181"

EXPECTED_OUTCOME = {
    "A": "OK",
    "B": "OK",
    "C": "NEED_CLARIFICATION",
    "D": "BLOCKED",
}


def _check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "OK " if ok else "FAIL"
    print(f"  [{mark}] {label}{(' - ' + detail) if detail else ''}")
    return ok


def _scrub(c: httpx.Client) -> None:
    """Best-effort cleanup of leftover demo projects (case_id-based)."""

    for jf in DEMO_DIR.glob("*.json"):
        case_id = json.loads(jf.read_text(encoding="utf-8"))["intake"]["case_id"]
        try:
            c.delete(f"/api/v1/projects/by-case/{case_id}")
        except Exception:
            pass


def main() -> int:
    files = sorted(DEMO_DIR.glob("*.json"))
    if not files:
        print(f"no fixtures found in {DEMO_DIR}")
        return 1
    print(f"=== demo smoke @ {BASE} ({len(files)} cases) ===")

    failures = 0
    with httpx.Client(base_url=BASE, timeout=15.0) as c:
        _scrub(c)

        for jf in files:
            m = re.match(r"^([ABCD])_", jf.name)
            if not m:
                print(f"  [SKIP] {jf.name} (filename must start with A_/B_/C_/D_)")
                continue
            expected_rating = m.group(1)
            expected_outcome = EXPECTED_OUTCOME[expected_rating]

            body = json.loads(jf.read_text(encoding="utf-8"))
            case_id = body["intake"]["case_id"]
            label = f"{expected_rating}_{jf.stem[2:]}"

            # 1) POST 建档
            r = c.post("/api/v1/projects", json=body)
            if not _check(
                f"POST {label}",
                r.status_code == 201,
                f"HTTP {r.status_code} {r.text[:100]}",
            ):
                failures += 1
                continue
            pid = r.json()["id"]

            # 2) 服务端返回的 intake_rating 应当与文件名一致
            persisted_rating = r.json()["payload"]["intake_rating"]
            if not _check(
                f"  rating persisted = {expected_rating}",
                persisted_rating == expected_rating,
                f"got {persisted_rating}",
            ):
                failures += 1

            # 3) POST validate
            r = c.post(f"/api/v1/projects/{pid}/intake/validate")
            if r.status_code != 200:
                _check(f"  validate {label}", False, f"HTTP {r.status_code}")
                failures += 1
                continue
            v = r.json()
            if not _check(
                f"  validate outcome = {expected_outcome}",
                v["outcome"] == expected_outcome and v["intake_rating"] == expected_rating,
                f"got outcome={v['outcome']} rating={v['intake_rating']}",
            ):
                failures += 1

            # 4) allow_proceed_to_phase02 标志应当严格符合
            expected_allow = expected_outcome == "OK"
            if not _check(
                f"  allow_proceed_to_phase02 = {expected_allow}",
                v["allow_proceed_to_phase02"] is expected_allow,
                f"got {v['allow_proceed_to_phase02']}",
            ):
                failures += 1

    print()
    if failures:
        print(f"=== DEMO SMOKE FAILED ({failures} failures) ===")
        return 1
    print("=== DEMO SMOKE OK ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
