"""完整 Phase 01-04 端到端 smoke (happy + blocked)。

按 Plan/reports/Phase_02-04_后续测试与验收需求.md §4 编写。
需 uvicorn 已启动：

    .venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --port 18181

用法：
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/full_smoke.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


REPO = Path(__file__).resolve().parents[1]
DEMO_DIR = REPO / "data" / "demo_cases"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18181"


def _check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "OK " if ok else "FAIL"
    print(f"  [{mark}] {label}{(' - ' + detail) if detail else ''}")
    return ok


def _load(case_id: str) -> dict:
    """按 case_id 找 demo JSON。"""

    candidates = [
        DEMO_DIR / f"A_{case_id}.json",
        DEMO_DIR / f"B_{case_id}.json",
        DEMO_DIR / f"C_{case_id}.json",
        DEMO_DIR / f"D_{case_id}.json",
    ]
    for c in candidates:
        if c.exists():
            body = json.loads(c.read_text(encoding="utf-8"))
            # 加唯一后缀防止 409
            suffix = str(int(time.time() * 1000))[-6:]
            body["intake"]["case_id"] = f"{body['intake']['case_id']}_{suffix}"
            return body
    raise FileNotFoundError(f"no demo case for {case_id}")


def happy_path(c: httpx.Client) -> int:
    print(f"\n=== happy path: A_CS_AI_GRAD @ {BASE} ===")
    failures = 0

    # 1) 建档 A
    body = _load("CS_AI_GRAD")
    r = c.post("/api/v1/projects", json=body)
    if not _check("POST /projects (A)", r.status_code == 201, f"HTTP {r.status_code}"):
        return failures + 1
    pid = r.json()["id"]
    case_id = r.json()["case_id"]
    print(f"    project id={pid} case_id={case_id}")

    # 2) Phase 01 validate
    r = c.post(f"/api/v1/projects/{pid}/intake/validate")
    v = r.json()
    if not _check(
        "POST /intake/validate → outcome=OK",
        r.status_code == 200 and v["outcome"] == "OK" and v["allow_proceed_to_phase02"] is True,
        f"outcome={v.get('outcome')} rating={v.get('intake_rating')}",
    ):
        failures += 1

    # 3) Phase 02 decompose (heuristic 不消耗 LLM 配额)
    r = c.post(f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"})
    j = r.json()
    if not _check(
        "POST /topic/decompose",
        r.status_code == 200 and j["allow_proceed_to_phase03"] is True,
        f"HTTP {r.status_code} rating={j.get('decomposition_rating')}",
    ):
        failures += 1
    else:
        spec = j["payload"]
        if not _check(
            "  TopicSpec 必填字段齐全",
            all(spec.get(k) is not None for k in ("normalized_topic", "task_type",
                                                    "evaluation_metrics", "risk_terms",
                                                    "thesis_mapping", "work_package_drafts")),
        ):
            failures += 1
        if not _check("  work_package_drafts ≥ 2", len(spec["work_package_drafts"]) >= 2):
            failures += 1

    # 4) Phase 02 GET 恢复
    r = c.get(f"/api/v1/projects/{pid}/topic/spec")
    if not _check("GET /topic/spec (200 + normalized_topic 非空)",
                  r.status_code == 200 and r.json()["payload"]["normalized_topic"].strip() != "",
                  f"HTTP {r.status_code}"):
        failures += 1

    # 5) Phase 03 search/plan
    r = c.post(f"/api/v1/projects/{pid}/search/plan")
    j = r.json()
    if not _check(
        "POST /search/plan",
        r.status_code == 200 and j["allow_proceed_to_phase04"] is True,
        f"HTTP {r.status_code} maturity={j.get('maturity_rating')}",
    ):
        failures += 1
    else:
        plan = j["payload"]
        layers = [l["layer"] for l in plan["query_layers"]]
        if not _check("  L0-L6 七层齐全", layers == ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]):
            failures += 1
        total_queries = sum(len(l["queries"]) for l in plan["query_layers"])
        if not _check(f"  总检索词 ≥ 10 (当前 {total_queries})", total_queries >= 10):
            failures += 1
        l6 = next((l for l in plan["query_layers"] if l["layer"] == "L6"), None)
        if not _check("  L6 Pivot ≥ 1 词", l6 is not None and len(l6["queries"]) >= 1):
            failures += 1

    # 6) Phase 03 GET
    r = c.get(f"/api/v1/projects/{pid}/search/plan")
    if not _check("GET /search/plan (200, 7 层)",
                  r.status_code == 200 and len(r.json()["payload"]["query_layers"]) == 7,
                  f"HTTP {r.status_code}"):
        failures += 1

    # 7) Phase 04 evidence/build
    r = c.post(f"/api/v1/projects/{pid}/evidence/build", json={"prefer": "heuristic"})
    j = r.json()
    if not _check(
        "POST /evidence/build",
        r.status_code == 200 and j["evidence_rating"] in ("A", "B"),
        f"HTTP {r.status_code} rating={j.get('evidence_rating')}",
    ):
        failures += 1
    else:
        if not _check("  papers ≥ 5", j["paper_count"] >= 5,
                      f"got {j['paper_count']}"):
            failures += 1
        if not _check("  datasets ≥ 2", j["dataset_count"] >= 2,
                      f"got {j['dataset_count']}"):
            failures += 1
        if not _check("  baselines ≥ 2", j["baseline_count"] >= 2,
                      f"got {j['baseline_count']}"):
            failures += 1
        if not _check("  metrics ≥ 1", j["metric_count"] >= 1,
                      f"got {j['metric_count']}"):
            failures += 1

    # 8) Phase 04 GET
    r = c.get(f"/api/v1/projects/{pid}/evidence/ledger")
    if not _check("GET /evidence/ledger (200, papers ≥ 5)",
                  r.status_code == 200 and r.json()["paper_count"] >= 5,
                  f"HTTP {r.status_code}"):
        failures += 1

    return failures


def _load_d_payload() -> dict:
    """构造一个 D 占位 payload（无需 demo 文件）。"""

    return {"intake": {
        "case_id": f"SMOKE_BLOCKED_{int(time.time()*1000)%10**6}",
        "goal_level": "保毕业",
        "raw_topic": "TBD",
        "intake_rating": "A",
    }}


def blocked_path(c: httpx.Client) -> int:
    print(f"\n=== blocked path: D 占位 @ {BASE} ===")
    failures = 0

    # 1) 建档 D
    body = _load_d_payload()
    r = c.post("/api/v1/projects", json=body)
    if not _check("POST /projects (D 占位)", r.status_code == 201, f"HTTP {r.status_code}"):
        return failures + 1
    pid = r.json()["id"]
    print(f"    project id={pid}")

    # 2) Phase 01 validate → BLOCKED
    r = c.post(f"/api/v1/projects/{pid}/intake/validate")
    v = r.json()
    if not _check(
        "POST /intake/validate → outcome=BLOCKED",
        r.status_code == 200 and v["outcome"] == "BLOCKED" and v["allow_proceed_to_phase02"] is False,
        f"outcome={v.get('outcome')}",
    ):
        failures += 1

    # 3) Phase 02 → 409
    r = c.post(f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"})
    if not _check(
        "POST /topic/decompose → 409",
        r.status_code == 409 and "Phase 01 状态" in r.json()["detail"],
        f"HTTP {r.status_code}",
    ):
        failures += 1

    # 4) Phase 03 → 404 (无 TopicSpec)
    r = c.post(f"/api/v1/projects/{pid}/search/plan")
    if not _check("POST /search/plan → 404 (无 TopicSpec)",
                  r.status_code == 404, f"HTTP {r.status_code}"):
        failures += 1

    # 5) Phase 04 → 404 (无 TopicSpec)
    r = c.post(f"/api/v1/projects/{pid}/evidence/build", json={"prefer": "heuristic"})
    if not _check("POST /evidence/build → 404 (无 TopicSpec)",
                  r.status_code == 404, f"HTTP {r.status_code}"):
        failures += 1

    return failures


def main() -> int:
    print(f"=== full smoke @ {BASE} ===")
    failures = 0
    with httpx.Client(base_url=BASE, timeout=60.0) as c:
        try:
            c.get("/health")
        except Exception as exc:
            print(f"  [FAIL] uvicorn 不可达: {exc}")
            print(f"  提示: .venv/Scripts/python.exe -m uvicorn app.main:app "
                  f"--app-dir apps/api --port 18181")
            return 1

        failures += happy_path(c)
        failures += blocked_path(c)

    print()
    if failures:
        print(f"=== FULL SMOKE FAILED ({failures} failures) ===")
        return 1
    print("=== FULL SMOKE OK (happy + blocked 全部通过) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
