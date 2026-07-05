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
os.environ.setdefault("STEPFUN_MODEL", "step-3.7-flash")
os.environ.setdefault("LLM_PROVIDER", "stepfun")
os.environ.setdefault("LLM_THINKING_BUDGET", "6000")
os.environ.setdefault("HUMAN_GATE_ENABLED", "false")
os.environ.setdefault("LANGGRAPH_CHECKPOINTER", "memory")
os.environ.setdefault("PAPERAGENT_MAX_REPAIR_ROUNDS", "2")
os.environ.setdefault("VOAPI_USAGE_POLICY", "premium_review_only")
os.environ.setdefault("MINIMAX_DISABLED", "true")

import dotenv  # noqa: E402
dotenv.load_dotenv(str(ROOT / ".env"))

import apps.api.app.services.agents.graph.nodes as _nodes_mod  # noqa: F401,E402
import apps.api.app.services.agents.graph.research_graph as rg  # noqa: E402
from apps.api.app.services.agents.graph.state import ResearchState  # noqa: E402

CASES = [
    {
        "case_id": "re12-l3-steel-yolov5",
        "title": "基于YOLOv5的钢铁表面缺陷检测研究",
        "topic": "YOLOv5-based steel surface defect detection on hot-rolled strip using NEU-DET dataset",
        "topic_atoms": None,
    },
    {
        "case_id": "re12-l3-semantic-slam",
        "title": "基于深度学习的视觉SLAM语义地图的研究",
        "topic": "Deep learning-based visual SLAM semantic mapping for indoor environments",
        "topic_atoms": None,
    },
    {
        "case_id": "re12-l3-medical-llm",
        "title": "基于大语言模型的医学问答可信度评估方法研究",
        "topic": "LLM-based medical question-answer credibility and factuality estimation",
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
    print(f"[{case_id}] t={elapsed}s | "
          f"papers={len(out.get('verified_papers') or [])} | "
          f"baseline={len(out.get('baseline_candidates') or [])} | "
          f"parallel={len(out.get('parallel_candidates') or [])} | "
          f"dataset={len(out.get('dataset_candidates') or [])} | "
          f"repo={len(out.get('repo_candidates') or [])} | "
          f"wp={len(out.get('work_packages') or [])} | "
          f"nodes_fired={len(out.get('trace_events') or [])}")
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
