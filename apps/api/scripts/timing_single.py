"""Quick single-topic timing validation for Re1.2 optimization."""
import io
import os
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "api"))

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
os.environ.setdefault("TOPIC_PARSER_TIMEOUT_S", "20")
os.environ.setdefault("VERIFIER_TIMEOUT_S", "25")
os.environ.setdefault("WORK_PACKAGE_TIMEOUT_S", "20")
os.environ.setdefault("DATASET_REPO_TIMEOUT_S", "20")
os.environ.setdefault("TARGETED_REPAIR_TIMEOUT_S", "20")
os.environ.setdefault("PAPERAGENT_HTTP_TIMEOUT_S", "6")
os.environ.setdefault("VERIFIER_MAX_WORKERS", "2")
os.environ.setdefault("VERIFIER_MAX_ATTEMPTS", "1")
os.environ.setdefault("DATASET_REPO_MAX_WORKERS", "2")
os.environ.setdefault("MINIMAX_DISABLED", "true")

import dotenv

dotenv.load_dotenv(str(ROOT / ".env"))

import apps.api.app.services.agents.graph.research_graph as rg
from apps.api.app.services.agents.graph.state import ResearchState

g = rg.build_graph()
t0 = time.time()
state_in: ResearchState = {
    "case_id": "timing-test",
    "topic": "YOLOv5-based steel surface defect detection on hot-rolled strip using NEU-DET dataset",
    "user_constraints": {
        "topic_zh": "基于YOLOv5的钢铁表面缺陷检测研究",
        "max_verify_candidates": 2,
        "max_dataset_paper_lookups": 1,
    },
    "trace_events": [],
    "provider_profile": "fast_json",
    "errors": [],
}
out = g.invoke(state_in, config={"configurable": {"thread_id": "timing-test"}})
elapsed = round(time.time() - t0, 1)

node_timings: dict[str, float] = {}
for ev in out.get("trace_events") or []:
    nd = ev.get("node", "?")
    el = float(ev.get("elapsed_s") or 0)
    node_timings[nd] = node_timings.get(nd, 0) + el

print(f"\nTOTAL: {elapsed}s")
print(
    f"verified={len(out.get('verified_papers') or [])} "
    f"baseline={len(out.get('baseline_candidates') or [])} "
    f"dataset={len(out.get('dataset_candidates') or [])} "
    f"repo={len(out.get('repo_candidates') or [])} "
    f"wp={len(out.get('work_packages') or [])}"
)
print("Per-node timing (sorted):")
for nd, t in sorted(node_timings.items(), key=lambda kv: kv[1], reverse=True):
    print(f"  {nd:30s} {t:8.1f}s")
