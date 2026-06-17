"""端到端 SSE 冒烟: 走完 8 phase 流式, 解析每条 trace 事件, 最后下载 Markdown.

不带 playwright, 不带 LLM 全部走 heuristic (避免 5 分钟级阻塞).
用法: PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/e2e_stream_smoke.py
"""
from __future__ import annotations

import json
import sys
import time
from typing import Any

import httpx

API = "http://127.0.0.1:18181"


def parse_sse(text: str) -> list[dict[str, Any]]:
    """把 SSE 文本切成事件列表. 每条事件以 \\n\\n 分隔, data: {...} 形式."""
    events: list[dict[str, Any]] = []
    for chunk in text.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        for line in chunk.splitlines():
            if line.startswith("data: "):
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass
    return events


def stream_post(path: str, body: dict | None = None) -> tuple[list[dict], float]:
    """POST + 接收 SSE, 返回 (events, elapsed_seconds)."""
    t0 = time.time()
    with httpx.stream("POST", API + path, json=body or {}, timeout=180) as r:
        r.raise_for_status()
        text = r.read().decode("utf-8")
    return parse_sse(text), time.time() - t0


def step(name: str, ev: dict) -> None:
    t = ev.get("type", "?")
    icon = {"start": "🚀", "step": "  ·", "llm": "  🤖", "result": "  ✅",
            "error": "  ❌", "warn": "  ⚠", "end": "🏁"}.get(t, "  ?")
    detail = ev.get("detail", ev.get("name", ""))
    meta = ev.get("meta") or {}
    meta_str = (" " + " ".join(f"{k}={v}" for k, v in list(meta.items())[:3])) if meta else ""
    print(f"  {icon} {detail}{meta_str}")


def main() -> int:
    print("=" * 70)
    print("E2E Stream Smoke: YOLOv8 带钢表面缺陷检测  (heuristic 全程)")
    print("=" * 70)

    # ----- Phase 01: create project (非流式) -----
    print("\n[Phase 01] create project")
    intake = {
        "case_id": f"E2E_STREAM_{int(time.time()) % 100000}",
        "major": "计算机科学与技术", "degree_type": "硕士", "goal_level": "保毕业",
        "proposal_deadline": "2026-10-15", "thesis_deadline": "2027-06-01",
        "first_result_deadline": "2026-12-31", "advisor_direction": "工业质检",
        "school_requirements": [], "inherited_resources": [],
        "student_resources": {
            "programming_level": "熟练", "dl_or_algorithm_foundation": "中",
            "paper_reading_ability": "中", "english_reading_ability": "中",
            "compute_resource": "笔记本 3060", "weekly_hours": 25,
            "data_collection_ability": "中", "data_annotation_ability": "中",
            "code_reproduction_ability": "中", "system_dev_ability": "中",
        },
        "raw_topic": "基于轻量化注意力机制的YOLOv8带钢表面缺陷检测算法研究",
        "must_keep": ["YOLOv8", "带钢表面缺陷", "轻量化", "注意力机制"],
        "can_drop": [], "missing_fields": [], "intake_rating": "A",
    }
    r = httpx.post(f"{API}/api/v1/projects", json={"intake": intake}, timeout=30)
    r.raise_for_status()
    pid = r.json()["id"]
    print(f"  pid={pid}")

    r = httpx.post(f"{API}/api/v1/projects/{pid}/intake/validate", timeout=15)
    r.raise_for_status()
    vj = r.json()
    print(f"  outcome={vj.get('outcome')} rating={vj.get('intake_rating')}")
    if vj.get("outcome") != "OK":
        print("  ❌ Phase 01 阻断, 终止")
        return 1

    # ----- Phase 02-08: stream -----
    stream_calls = [
        (2, f"/api/v1/projects/{pid}/topic/decompose/stream", {"prefer": "heuristic"}),
        (3, f"/api/v1/projects/{pid}/search/plan/stream", None),
        (4, f"/api/v1/projects/{pid}/evidence/build/stream", {"prefer": "heuristic"}),
        (5, f"/api/v1/projects/{pid}/risk/evaluate/stream", {"prefer": "heuristic"}),
        (6, f"/api/v1/projects/{pid}/work_package/plan/stream", None),
        (7, f"/api/v1/projects/{pid}/proposal/draft/stream", None),
        (7, f"/api/v1/projects/{pid}/committee/review/stream", None),
        (8, f"/api/v1/projects/{pid}/final_package/build/stream", None),
    ]
    for n, path, body in stream_calls:
        print(f"\n[Phase 0{n} stream] {path}")
        try:
            evs, secs = stream_post(path, body)
        except Exception as e:
            print(f"  ❌ 请求失败: {e}")
            return 1
        print(f"  ⏱ {secs:.1f}s | 事件数 {len(evs)}")
        ok = False
        for ev in evs:
            step(f"p{n}", ev)
            if ev.get("type") == "error":
                print(f"  ❌ 流式返回 error 事件")
                return 1
            if ev.get("type") == "result":
                ok = True
        if not ok:
            print(f"  ❌ 流式未收到 result 事件")
            return 1

    # ----- Phase 08 markdown -----
    print(f"\n[Phase 08 markdown]")
    r = httpx.get(f"{API}/api/v1/projects/{pid}/final_package/markdown", timeout=15)
    if r.status_code == 200:
        path = f"tmp/proposal_{pid}.md"
        with open(path, "wb") as f:
            f.write(r.content)
        print(f"  ✓ 已保存: {path} ({len(r.content)} chars)")
    else:
        print(f"  ❌ HTTP {r.status_code}: {r.text[:200]}")
        return 1

    print("\n" + "=" * 70)
    print(f"✅ 8 phase 流式端到端 PASS (pid={pid})")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
