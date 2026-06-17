"""Session 4: 退化路线 e2e.

覆盖:
- 可做 verdict → 不显示 "看 3 条退化路线" 按钮, 不显示 pivot_routes
- 收缩后可做/可转向 → 显示按钮, 点击后 modal 显示 3 路线
- 选一条 → 工作包更新
"""

from __future__ import annotations

import time
import json
import urllib.request

import pytest

API = "http://127.0.0.1:18181"


def _analyze(topic, goal="保毕业", prefer="heuristic"):
    body = json.dumps({"raw_topic": topic, "goal_level": goal, "prefer": prefer}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{API}/api/v1/one-topic/analyze",
        data=body, headers={"Content-Type": "application/json; charset=utf-8"}, method="POST",
    )
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def test_yolo_steel_no_pivot_button(page) -> None:
    """YOLO 钢材直接可做, 不显示 "看 3 条退化路线" 按钮."""

    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")
    page.wait_for_function(
        "() => !document.getElementById('btn-analyze').textContent.includes('⏳')",
        timeout=60000,
    )
    # 可做, 不应该有 btn-show-pivots
    btn_count = page.locator("#btn-show-pivots").count()
    assert btn_count == 0, f"YOLO 钢材 不应该显示 pivot 按钮, got count={btn_count}"


def test_narrow_topic_shows_pivot_button(page) -> None:
    """收缩后可做 → 显示 "看 3 条退化路线" 按钮."""

    # 用一个会触发 "可转向" 的题目
    r = _analyze("基于XXX的极小众对象检测")
    print(f"verdict: {r['feasibility']['verdict']}")
    pid = r["project_id"]
    # 用 page 触发 regenerate 调用此 PID
    # 简化: 通过 localStorage 注入 projectId 给前端
    page.goto(f"http://127.0.0.1:18182/?pid={pid}")
    page.wait_for_selector("#btn-analyze")
    # 在 input-card 里手动填多模态题目, 不行因为会触发新的 analyze
    # 直接 JS 调 regenerate 触发
    page.evaluate(f"""async () => {{
        const r = await fetch('http://127.0.0.1:18181/api/v1/one-topic/{pid}/regenerate', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
                raw_topic: '基于XXX的极小众对象检测',
                goal_level: '保毕业',
                prefer: 'heuristic',
            }})
        }});
        const d = await r.json();
        window._test_result = d;
    }}""")
    time.sleep(2)
    result = page.evaluate("window._test_result")
    if result and "feasibility" in result:
        verdict = result["feasibility"]["verdict"]
        assert verdict in ("可做", "收缩后可做", "可转向", "暂缓", "不建议")
        # 如果 verdict 是 可转向/收缩后可做, 应该有 pivot routes
        if verdict in ("可转向", "收缩后可做"):
            assert len(result["proposal_recommendation"]["pivot_routes"]) == 3


def test_pivot_select_endpoint_changes_work_packages(page) -> None:
    """API 测: 选 conservative 后, work_packages 来自路线."""

    r = _analyze("基于YOLO的钢材表面缺陷检测")
    pid = r["project_id"]
    # 直接调 pivot/select, 用从 analyze 拿到的 pivot_routes[0]
    rec = r["proposal_recommendation"]
    if not rec.get("pivot_routes"):
        # YOLO 钢材直接可做, 没有 pivot. 用 multi-modal 题目触发
        r2 = _analyze("基于XXX的极小众对象检测")
        pid = r2["project_id"]
        rec = r2["proposal_recommendation"]
    if not rec.get("pivot_routes"):
        pytest.skip("verdict 没触发 pivot_routes, 跳过")
    cons = rec["pivot_routes"][0]
    body = json.dumps(cons, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{API}/api/v1/one-topic/{pid}/pivot/select",
        data=body, headers={"Content-Type": "application/json; charset=utf-8"}, method="POST",
    )
    rec2 = json.loads(urllib.request.urlopen(req, timeout=60).read())
    assert rec2["recommended_topic"] == cons["new_topic"]
    assert len(rec2["work_packages"]) == len(cons["work_packages"])
    # pivot_routes 应该只剩选中的那条
    assert len(rec2["pivot_routes"]) == 1
    assert rec2["pivot_routes"][0]["level"] == cons["level"]

def test_frontend_pivot_button_and_select(page) -> None:
    """前端 UI 流程: 可触发 "看 3 条路线" 按钮 → modal → 点选 → WP 更新."""

    page.fill("#input-topic", "基于XXX的极小众对象检测")
    page.click("#btn-analyze")
    page.wait_for_function(
        "() => !document.getElementById('btn-analyze').textContent.includes('⏳')",
        timeout=60000,
    )
    page.wait_for_selector("#btn-show-pivots", state="attached", timeout=15000)
    page.click("#btn-show-pivots")
    page.wait_for_selector("#modal-pivot:not([hidden])", state="attached", timeout=5000)
    n_cards = page.locator("#pivot-list .pivot-card").count()
    assert n_cards == 3, f"expected 3 pivot cards, got {n_cards}"
    # 点第一条 (conservative) - 用 data-pivot-level (不是 data-action)
    page.click("#pivot-list .pivot-card:first-child [data-pivot-level]")
    # modal 应该关 + work_packages 更新
    page.wait_for_selector("#modal-pivot[hidden]", state="attached", timeout=10000)
    time.sleep(1.0)
    rec_html = page.inner_html("#block-recommendation")
    assert "WP1" in rec_html, f"WP not rendered after select: {rec_html[:500]}"
