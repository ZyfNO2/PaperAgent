"""Re1.2 LIVE run script.

Runs 3 real topics (steel / slam / medical) with the new 14-node pipeline
and conditional repair loops. Writing per-case:

- tmp_re12_eval/<case_id>/state.json        final ResearchState
- tmp_re12_eval/<case_id>/trace.json         node_events list
- tmp_re12_eval/<case_id>/evidence_graph.json

Env knobs:
  FAST_JSON_PRIMARY=stepfun
  STEPFUN_MODEL=step-3.7-flash
  LLM_PROVIDER=stepfun
  LLM_THINKING_BUDGET=6000
  PAPERAGENT_MAX_REPAIR_ROUNDS=2
  PAPERAGENT_SKIP_SEARCH_PLANNER=true
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path

# Windows console UTF-8 (PITFALLS.md entry #8)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "api"))

OUT_DIR = ROOT / "tmp_re12_eval"

os.environ.setdefault("FAST_JSON_PRIMARY", "stepfun")
os.environ.setdefault("STEPFUN_BASE_URL", "https://api.stepfun.com/step_plan/v1")
os.environ.setdefault("STEPFUN_MODEL", "step-3.7-flash")
os.environ.setdefault("LLM_PROVIDER", "stepfun")
os.environ.setdefault("LLM_THINKING_BUDGET", "6000")
os.environ.setdefault("HUMAN_GATE_ENABLED", "false")
os.environ.setdefault("LANGGRAPH_CHECKPOINTER", "memory")
os.environ.setdefault("PAPERAGENT_MAX_REPAIR_ROUNDS", "2")
os.environ.setdefault("PAPERAGENT_SKIP_SEARCH_PLANNER", "true")
os.environ.setdefault("LLM_RPM_LIMIT", "0")
os.environ.setdefault("STEPFUN_RPM_LIMIT", "10")
os.environ.setdefault("VERIFIER_MAX_WORKERS", "1")
os.environ.setdefault("TOPIC_PARSER_TIMEOUT_S", "20")
os.environ.setdefault("VERIFIER_TIMEOUT_S", "25")
os.environ.setdefault("WORK_PACKAGE_TIMEOUT_S", "20")
os.environ.setdefault("DATASET_REPO_TIMEOUT_S", "20")
os.environ.setdefault("TARGETED_REPAIR_TIMEOUT_S", "20")
os.environ.setdefault("PAPERAGENT_HTTP_TIMEOUT_S", "6")
os.environ.setdefault("DATASET_REPO_MAX_WORKERS", "2")
os.environ.setdefault("VOAPI_USAGE_POLICY", "premium_review_only")
os.environ.setdefault("MINIMAX_DISABLED", "true")

import dotenv  # noqa: E402
dotenv.load_dotenv(str(ROOT / ".env"))

import apps.api.app.services.agents.graph.nodes as _nodes_mod  # noqa: F401,E402
import apps.api.app.services.agents.graph.research_graph as rg  # noqa: E402
from apps.api.app.services.agents.graph.state import ResearchState  # noqa: E402

CASES = [
    {
        "case_id": "re12-l5-road-crack",
        "title": "基于深度学习的道路裂缝检测与分类研究",
        "topic": "Deep learning-based road crack detection and classification using CNN",
        "topic_atoms": None,
    },
    {
        "case_id": "re12-l5-mono-recon",
        "title": "基于单目视觉的室内场景三维重建关键技术研究",
        "topic": "Monocular camera-based indoor 3D scene reconstruction with deep learning",
        "topic_atoms": None,
    },
    {
        "case_id": "re12-l5-rag-qa",
        "title": "基于检索增强生成的企业知识库问答系统研究",
        "topic": "Retrieval-augmented generation for enterprise knowledge base question answering",
        "topic_atoms": None,
    },
    {
        "case_id": "re12-l5-steel-monitor",
        "title": "基于压电传感器的钢结构健康监测与损伤识别研究",
        "topic": "Piezoelectric sensor-based steel structural health monitoring and damage identification",
        "topic_atoms": None,
    },
    {
        "case_id": "re12-l5-uav-crop",
        "title": "基于无人机遥感的农作物病虫害智能监测研究",
        "topic": "UAV remote sensing for crop pest and disease detection using deep learning",
        "topic_atoms": None,
    },
]


def run_one(case: dict) -> dict:
    case_id = case["case_id"]
    t0 = time.time()
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    state_in: ResearchState = {
        "case_id": case_id,
        "topic": case["topic"],
        "user_constraints": {"topic_zh": case["title"]},
        "trace_events": [],
        "provider_profile": "fast_json",
        "errors": [],
    }
    g = rg.build_graph()
    out = g.invoke(state_in, config={"configurable": {"thread_id": case_id}})

    elapsed = round(time.time() - t0, 2)
    out["elapsed_s"] = elapsed

    (case_dir / "state.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    (case_dir / "trace.json").write_text(
        json.dumps(out.get("trace_events") or [], ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    (case_dir / "evidence_graph.json").write_text(
        json.dumps(out.get("evidence_graph") or {}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    # Per-node timing breakdown
    node_timings: dict[str, float] = {}
    for ev in out.get("trace_events") or []:
        nd = ev.get("node", "?")
        el = float(ev.get("elapsed_s") or 0)
        node_timings[nd] = node_timings.get(nd, 0) + el
    top5 = sorted(node_timings.items(), key=lambda kv: kv[1], reverse=True)[:8]
    timing_str = " | ".join(f"{n}:{t:.1f}s" for n, t in top5)

    print(f"[{case_id}] t={elapsed}s | "
          f"papers={len(out.get('verified_papers') or [])} | "
          f"baseline={len(out.get('baseline_candidates') or [])} | "
          f"parallel={len(out.get('parallel_candidates') or [])} | "
          f"dataset={len(out.get('dataset_candidates') or [])} | "
          f"repo={len(out.get('repo_candidates') or [])} | "
          f"wp={len(out.get('work_packages') or [])} | "
          f"nodes_fired={len(out.get('trace_events') or [])}")
    print(f"  timing: {timing_str}")
    return out


def main() -> int:
    start = time.time()
    results = []
    for c in CASES:
        print(f"\n=== Running {c['case_id']}: {c['title']} ===")
        try:
            results.append(run_one(c))
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED: {exc}")
            results.append({"case_id": c["case_id"], "error": str(exc)})
    print(f"\n=== TOTAL elapsed: {round(time.time()-start,2)}s ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
