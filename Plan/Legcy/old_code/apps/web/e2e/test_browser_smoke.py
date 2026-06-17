"""Playwright 浏览器 e2e: Phase 01-04 happy + blocked 路径。

跑法:
    1. 起 uvicorn:  .venv/Scripts/python.exe -m uvicorn app.main:app \\
                     --app-dir apps/api --port 18181
    2. 跑:          .venv/Scripts/python.exe -m pytest apps/web/e2e/ -v

由于 apps/web 尚未实现, 真实浏览器渲染路径跳过;
但 ``page.request`` 走真 Chromium session 的 HTTP stack, 仍能验证
后端在浏览器上下文下行为正确 (session/cookie/UA 路径)。

设计:
- happy path: A 项目 → 走完 4 Phase, 校验 allow flags + counts
- blocked path: D 占位 → 校验 409/404 阻断链路
- refresh persistence: GET 端点恢复已生成产物
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from apps.web.e2e.conftest import BASE_URL


REPO = Path(__file__).resolve().parents[3]
DEMO_A = REPO / "data" / "demo_cases" / "A_CS_AI_GRAD.json"


def _check(name: str, ok: bool, detail: str = "") -> bool:
    mark = "OK " if ok else "FAIL"
    print(f"  [{mark}] {name}{(' - ' + detail) if detail else ''}")
    return ok


def _a_intake_body() -> dict:
    body = json.loads(DEMO_A.read_text(encoding="utf-8"))
    suffix = str(int(time.time() * 1000))[-6:]
    body["intake"]["case_id"] = f"{body['intake']['case_id']}_{suffix}"
    return body


def _d_intake_body() -> dict:
    return {"intake": {
        "case_id": f"BROWSER_D_{int(time.time()*1000)%10**6}",
        "goal_level": "保毕业",
        "raw_topic": "TBD",
        "intake_rating": "A",
    }}


# ============================================================ happy path


def test_happy_path_phase_01_to_04_in_browser_context(page) -> None:
    """§5.1 happy path: 真 Chromium session 走完 4 Phase。"""

    failures = 0
    print("=== Playwright e2e: happy path ===")

    # Phase 01: 建档
    r = page.request.post(f"{BASE_URL}/api/v1/projects", data=_a_intake_body())
    if not _check("Phase 01 POST /projects", r.status == 201, f"HTTP {r.status}"):
        return
    pid = r.json()["id"]
    case_id = r.json()["case_id"]
    print(f"    project id={pid} case_id={case_id}")

    # Phase 01: validate
    r = page.request.post(f"{BASE_URL}/api/v1/projects/{pid}/intake/validate")
    v = r.json()
    if not _check(
        "Phase 01 validate → outcome=OK",
        r.status == 200 and v["outcome"] == "OK" and v["allow_proceed_to_phase02"] is True,
        f"outcome={v.get('outcome')}",
    ):
        failures += 1

    # Phase 02: decompose
    r = page.request.post(
        f"{BASE_URL}/api/v1/projects/{pid}/topic/decompose",
        data={"prefer": "heuristic"},
    )
    j = r.json()
    if not _check("Phase 02 decompose",
                  r.status == 200 and j["allow_proceed_to_phase03"] is True,
                  f"HTTP {r.status} rating={j.get('decomposition_rating')}"):
        failures += 1

    # Phase 02: GET spec
    r = page.request.get(f"{BASE_URL}/api/v1/projects/{pid}/topic/spec")
    if not _check("Phase 02 GET /topic/spec", r.status == 200, f"HTTP {r.status}"):
        failures += 1

    # Phase 03: search/plan
    r = page.request.post(f"{BASE_URL}/api/v1/projects/{pid}/search/plan")
    j = r.json()
    if not _check("Phase 03 search/plan",
                  r.status == 200 and j["allow_proceed_to_phase04"] is True,
                  f"HTTP {r.status} maturity={j.get('maturity_rating')}"):
        failures += 1

    # Phase 03: GET plan
    r = page.request.get(f"{BASE_URL}/api/v1/projects/{pid}/search/plan")
    if not _check("Phase 03 GET /search/plan", r.status == 200, f"HTTP {r.status}"):
        failures += 1

    # Phase 04: evidence/build
    r = page.request.post(
        f"{BASE_URL}/api/v1/projects/{pid}/evidence/build",
        data={"prefer": "heuristic"},
    )
    j = r.json()
    if not _check(
        "Phase 04 evidence/build",
        r.status == 200 and j["evidence_rating"] in ("A", "B"),
        f"HTTP {r.status} rating={j.get('evidence_rating')}",
    ):
        failures += 1
    else:
        if not _check("  papers ≥ 5", j["paper_count"] >= 5, f"got {j['paper_count']}"):
            failures += 1
        if not _check("  datasets ≥ 2", j["dataset_count"] >= 2):
            failures += 1
        if not _check("  baselines ≥ 2", j["baseline_count"] >= 2):
            failures += 1

    # Phase 04: GET ledger
    r = page.request.get(f"{BASE_URL}/api/v1/projects/{pid}/evidence/ledger")
    if not _check("Phase 04 GET /evidence/ledger", r.status == 200, f"HTTP {r.status}"):
        failures += 1

    assert failures == 0, f"happy path 有 {failures} 失败"


# ============================================================ blocked path


def test_blocked_path_d_rating_in_browser_context(page) -> None:
    """§5.2 blocked path: D 占位项目在浏览器 session 中被各阶段阻断。"""

    failures = 0
    print("\n=== Playwright e2e: blocked path ===")

    r = page.request.post(f"{BASE_URL}/api/v1/projects", data=_d_intake_body())
    if not _check("POST /projects (D)", r.status == 201, f"HTTP {r.status}"):
        return
    pid = r.json()["id"]
    print(f"    project id={pid}")

    r = page.request.post(f"{BASE_URL}/api/v1/projects/{pid}/intake/validate")
    v = r.json()
    if not _check(
        "validate → outcome=BLOCKED",
        r.status == 200 and v["outcome"] == "BLOCKED" and v["allow_proceed_to_phase02"] is False,
    ):
        failures += 1

    r = page.request.post(
        f"{BASE_URL}/api/v1/projects/{pid}/topic/decompose",
        data={"prefer": "heuristic"},
    )
    if not _check("decompose → 409", r.status == 409, f"HTTP {r.status}"):
        failures += 1

    r = page.request.post(f"{BASE_URL}/api/v1/projects/{pid}/search/plan")
    if not _check("search/plan → 404", r.status == 404, f"HTTP {r.status}"):
        failures += 1

    r = page.request.post(
        f"{BASE_URL}/api/v1/projects/{pid}/evidence/build",
        data={"prefer": "heuristic"},
    )
    if not _check("evidence/build → 404", r.status == 404, f"HTTP {r.status}"):
        failures += 1

    assert failures == 0, f"blocked path 有 {failures} 失败"


# ============================================================ refresh persistence


def test_refresh_persistence_get_endpoints(page) -> None:
    """§5.3 刷新后阶段产物仍能通过 GET 恢复 (模拟页面 reload)。"""

    failures = 0
    print("\n=== Playwright e2e: refresh persistence ===")

    body = _a_intake_body()
    r = page.request.post(f"{BASE_URL}/api/v1/projects", data=body)
    pid = r.json()["id"]
    page.request.post(
        f"{BASE_URL}/api/v1/projects/{pid}/topic/decompose",
        data={"prefer": "heuristic"},
    )
    page.request.post(f"{BASE_URL}/api/v1/projects/{pid}/search/plan")
    page.request.post(
        f"{BASE_URL}/api/v1/projects/{pid}/evidence/build",
        data={"prefer": "heuristic"},
    )

    # 模拟"用户关闭浏览器再打开": 创建新 context 重新 GET
    with page.context.browser.new_context() as new_ctx:
        new_page = new_ctx.new_page()
        for path, name in [
            (f"/api/v1/projects/{pid}/topic/spec", "topic/spec"),
            (f"/api/v1/projects/{pid}/search/plan", "search/plan"),
            (f"/api/v1/projects/{pid}/evidence/ledger", "evidence/ledger"),
        ]:
            r = new_page.request.get(f"{BASE_URL}{path}")
            if not _check(
                f"GET /{name} (新 session)",
                r.status == 200 and len(r.body()) > 100,
                f"HTTP {r.status}",
            ):
                failures += 1
        new_page.close()

    assert failures == 0, f"refresh persistence 有 {failures} 失败"
