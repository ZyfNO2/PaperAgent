"""Re1.1 Loop 4 — cross-domain 5 case runner (runs in-process, no subprocess).

Uses live StepFun (FAST_JSON_PRIMARY=stepfun) for all LLM calls.
retrieve_node may fall through to placeholder seed if legacy adapter fails;
this is an upstream bug (missing build_axis_bound_queries export) — see
Plan/PaperAgent_Re11_PITFALLS.md #9.

Outputs:
- Plan/PaperAgent_Re11_Loop4_跨领域小样例5.md
- tmp_re11_eval/loop4/<case_id>.json * 5
- tmp_re11_eval/loop4/summary.json
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path

# Windows console UTF-8 safety (PITFALLS.md #8)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent.parent  # apps/api/scripts -> repo root
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "tmp_re11_eval" / "loop4"
OUT_DIR.mkdir(parents=True, exist_ok=True)

os.environ["FAST_JSON_PRIMARY"] = "stepfun"
os.environ["HUMAN_GATE_ENABLED"] = "false"
os.environ["LANGGRAPH_CHECKPOINTER"] = "memory"
os.environ["LLM_PROVIDER"] = "stepfun"
os.environ["MINIMAX_DISABLED"] = "true"

import dotenv
dotenv.load_dotenv(str(ROOT / ".env"))

import apps.api.app.services.agents.graph.research_graph as rg  # noqa: E402

CASES = [
    {
        "case_id": "re11-l4-road-crack",
        "title": "基于深度学习的道路裂缝检测与分类研究",
        "topic": "Deep learning-based road crack detection and classification",
        "topic_atoms": {
            "method": ["deep learning", "CNN", "U-Net", "object detection"],
            "object": ["asphalt road crack", "concrete pavement", "road surface"],
            "task": ["crack detection", "crack classification", "image segmentation"],
            "domain": ["transportation engineering", "computer vision"],
            "dataset_terms": ["Crack500", "CrackTree200", "CEDD"],
            "baseline_terms": ["U-Net", "ResNet", "YOLO"],
            "avoid_terms": ["medical image", "steel-only", "indoor floor"],
        },
    },
    {
        "case_id": "re11-l4-mono-recon",
        "title": "基于单目视觉的室内场景三维重建关键技术研究",
        "topic": "Monocular visual indoor 3D scene reconstruction",
        "topic_atoms": {
            "method": ["monocular depth", "NeRF", "3D Gaussian Splatting", "SfM"],
            "object": ["indoor scene", "room", "corridor"],
            "task": ["3D reconstruction", "depth estimation", "novel view synthesis"],
            "domain": ["computer graphics", "robotics"],
            "dataset_terms": ["ScanNet", "NYU Depth V2", "Tanks and Temples"],
            "baseline_terms": ["NeRF", "MiDaS", "COLMAP"],
            "avoid_terms": ["multi-view stereo", "LiDAR-only"],
        },
    },
    {
        "case_id": "re11-l4-rag-qa",
        "title": "基于检索增强生成的企业知识库问答系统研究",
        "topic": "Retrieval-augmented generation for enterprise knowledge base QA",
        "topic_atoms": {
            "method": ["retrieval-augmented generation", "RAG", "vector search", "fine-tuning"],
            "object": ["enterprise documents", "knowledge base", "FAQ"],
            "task": ["open-domain QA", "retrieval", "grounded generation"],
            "domain": ["NLP", "information retrieval"],
            "dataset_terms": ["MS MARCO", "Natural Questions", "TriviaQA"],
            "baseline_terms": ["BM25", "DPR", "GPT-3.5"],
            "avoid_terms": ["medical QA", "code-only"],
        },
    },
    {
        "case_id": "re11-l4-steel-monitor",
        "title": "基于压电传感器的钢结构健康监测与损伤识别研究",
        "topic": "Piezoelectric sensor-based steel structure structural health monitoring and damage identification",
        "topic_atoms": {
            "method": ["piezoelectric", "guided wave", "vibration analysis", "deep learning"],
            "object": ["steel beam", "steel bridge", "weld joint"],
            "task": ["damage identification", "structural health monitoring", "anomaly detection"],
            "domain": ["structural engineering", "non-destructive evaluation"],
            "dataset_terms": ["Z24 Bridge", "I-40 Bridge", "Steel bridge SHM benchmark"],
            "baseline_terms": ["wavelet transform", "autoencoder", "random forest"],
            "avoid_terms": ["concrete-only", "wind-turbine-only"],
        },
    },
    {
        "case_id": "re11-l4-uav-crop",
        "title": "基于无人机遥感的农作物病虫害智能监测研究",
        "topic": "UAV remote sensing-based crop pest and disease monitoring",
        "topic_atoms": {
            "method": ["UAV", "remote sensing", "object detection", "CNN"],
            "object": ["crop leaf", "paddy field", "maize", "wheat"],
            "task": ["pest detection", "disease segmentation", "precision agriculture"],
            "domain": ["agricultural engineering", "remote sensing"],
            "dataset_terms": ["PlantVillage", "IP102", "Global Wheat Head Detection"],
            "baseline_terms": ["Faster R-CNN", "ResNet-50", "SVM"],
            "avoid_terms": ["satellite-only", "weed-only", "medical leaf"],
        },
    },
]


def run_one(case: dict) -> dict:
    t0 = time.time()
    state = {
        "case_id": case["case_id"],
        "topic": case["topic"],
        "user_constraints": {},
        "topic_atoms": case["topic_atoms"],
        "trace_events": [],
        "errors": [],
    }
    g = rg.build_graph()
    try:
        out = g.invoke(state, config={"configurable": {"thread_id": case["case_id"]}})
    except Exception as exc:
        return {
            "case_id": case["case_id"], "title": case["title"],
            "status": f"graph_error:{type(exc).__name__}",
            "elapsed_s": round(time.time() - t0, 2),
            "error": str(exc)[:1500],
        }

    rec = out.get("final_recommendation") or {}
    events = out.get("trace_events") or []
    errors = out.get("errors") or []

    # Pull verified papers' 5-top titles + keyword breakdown
    papers_top = []
    for p in (out.get("verified_papers") or [])[:5]:
        papers_top.append({
            "title": p.get("title"),
            "verdict": p.get("verdict"),
            "hit_keywords": p.get("hit_keywords"),
            "unrelated_keywords": p.get("unrelated_keywords"),
            "relation_to_topic": p.get("relation_to_topic"),
            "url_missing": p.get("url_missing"),
        })

    result = {
        "case_id": case["case_id"],
        "title": case["title"],
        "status": "pass" if rec.get("low_bar_status") == "pass" else "weak",
        "n_papers_total": len(out.get("paper_candidates") or []),
        "n_verified": len(out.get("verified_papers") or []),
        "n_baseline": len(out.get("baseline_candidates") or []),
        "n_parallel": len(out.get("parallel_candidates") or []),
        "n_dataset": len(out.get("dataset_candidates") or []),
        "n_repo": len(out.get("repo_candidates") or []),
        "n_work_packages": len(out.get("work_packages") or []),
        "n_trace_events": len(events),
        "n_errors": len(errors),
        "elapsed_s": round(time.time() - t0, 2),
        "low_bar_status": rec.get("low_bar_status"),
        "human_gate_status": rec.get("human_gate_status") if isinstance(rec.get("human_gate_status"), str) else (rec.get("human_gate_status") or {}).get("status"),
        "notes": rec.get("notes"),
        "errors": errors,
        "papers_top5": papers_top,
        "final_recommendation": rec,
        "events_summary": [
            {"node": e.get("node"), "elapsed": e.get("elapsed_s"),
             "errors_n": len(e.get("errors") or [])} for e in events
        ],
    }

    (OUT_DIR / f'{case["case_id"]}.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return result


def main() -> int:
    results = []
    flags = []
    start = time.time()
    for case in CASES:
        print(f"\n=== Running {case['case_id']}: {case['title']}")
        ret = run_one(case)
        verdict = "OK" if ret["status"] in ("pass", "weak") else "FAIL"
        flags.append(ret["status"] == "pass")
        print(f"  {verdict} {case['case_id']}: paper={ret.get('n_verified')}, "
              f"ds={ret.get('n_dataset')}, repo={ret.get('n_repo')}, "
              f"wp={ret.get('n_work_packages')}, t={ret.get('elapsed_s')}s"
              f"{', errors=' + str(ret.get('n_errors')) if ret.get('n_errors') else ''}")
        results.append(ret)

    accepted = sum(1 for f in flags if f)
    summary = {
        "n": len(results),
        "accept": flags,
        "accepted_n": accepted,
        "pass_ratio": accepted / len(results) if results else 0,
        "total_elapsed_s": round(time.time() - start, 2),
        "per_case": [
            {
                "case_id": r["case_id"], "title": r["title"],
                "status": r["status"],
                "n_verified": r.get("n_verified", 0),
                "n_dataset": r.get("n_dataset", 0),
                "n_repo": r.get("n_repo", 0),
                "n_work_packages": r.get("n_work_packages", 0),
                "elapsed_s": r.get("elapsed_s", 0),
                "n_errors": r.get("n_errors", 0),
            } for r in results
        ],
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\n===== Loop 4 summary: {accepted}/{len(results)} pass, total {round(time.time()-start,2)}s =====")
    print(f"Wrote {OUT_DIR}/summary.json + {len(results)} case traces")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
