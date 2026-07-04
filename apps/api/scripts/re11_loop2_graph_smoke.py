"""Re1.1 Loop 2 — Graph Smoke with REAL StepFun LLM (no mocks).

SOP §14 Loop 2:
  - All main nodes enter LangGraph.
  - Every node writes trace.
  - case_id becomes thread_id.
  - human_gate_node passes through when disabled.
  - Final state has paper/dataset/repo/work_package fields.

We use StepFun as fast_json provider via FAST_JSON_PRIMARY=stepfun.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "tmp_re11_eval" / "loop2"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    t0 = time.time()
    os.environ.setdefault("FAST_JSON_PRIMARY", "stepfun")
    os.environ.setdefault("HUMAN_GATE_ENABLED", "false")
    os.environ.setdefault("LANGGRAPH_CHECKPOINTER", "memory")

    import apps.api.app.services.agents.graph.research_graph as rg
    from apps.api.app.services.agents.graph.state import ResearchState

    # Use a tiny abstract topic so legacy adapter search has a chance.
    topic = "Deep learning for crack detection on concrete surfaces"
    atoms = {
        "method": ["deep learning", "U-Net"],
        "object": ["concrete crack"],
        "task": ["image segmentation", "damage detection"],
        "domain": ["structural engineering", "computer vision"],
        "dataset_terms": ["SDNET2018", "Crack500"],
        "baseline_terms": ["U-Net", "ResNet-50"],
        "avoid_terms": ["asphalt-only", "medical"],
    }
    case_id = "re11-loop2-smoke-001"
    state: ResearchState = {"case_id": case_id, "topic": topic,
                            "user_constraints": {}, "topic_atoms": atoms,
                            "trace_events": [], "errors": []}

    # Keep only 1 LLM round (work-package stage triggers a call); cap dataset_repo.
    g = rg.build_graph()
    out = g.invoke(state, config={"configurable": {"thread_id": case_id}})

    events = out.get("trace_events") or []
    names = [e.get("node") for e in events]
    errors = out.get("errors") or []

    trace_path = OUT_DIR / f"{case_id}.json"
    trace_path.write_text(json.dumps({
        "case_id": case_id,
        "topic": topic,
        "elapsed": round(time.time() - t0, 2),
        "nodes_fired": names,
        "n_events": len(events),
        "errors": errors,
        "errors_n": len(errors),
        "provider_profile": out.get("provider_profile"),
        "final_recommendation": out.get("final_recommendation"),
        "human_gate": out.get("human_gate"),
        "has_paper_candidates": bool(out.get("paper_candidates")),
        "has_verified_papers": bool(out.get("verified_papers")),
        "has_dataset_candidates": bool(out.get("dataset_candidates")),
        "has_repo_candidates": bool(out.get("repo_candidates")),
        "has_work_packages": bool(out.get("work_packages")),
        "events": events,
    }, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print(f"Wrote {trace_path}")
    print(f"Elapsed: {round(time.time() - t0, 2)}s")
    print(f"Nodes fired: {names}")
    print(f"Errors: {errors or '(none)'}")
    print(f"Final: {out.get('final_recommendation')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
