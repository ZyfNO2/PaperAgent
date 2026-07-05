"""Verify-prompt strictness test: manually-curated candidates × steel-YOLOv5 topic.

We use hand-picked papers with KNOWN ground-truth verdicts to measure whether
the current verifier prompt produces the right spread. 8 candidates span
 accept / weak_reject / reject territory.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "api"))

os.environ.setdefault("FAST_JSON_PRIMARY", "stepfun")
os.environ.setdefault("STEPFUN_MODEL", "step-3.7-flash")
os.environ.setdefault("LLM_PROVIDER", "stepfun")
os.environ.setdefault("LLM_THINKING_BUDGET", "6000")
os.environ.setdefault("MINIMAX_DISABLED", "true")

import dotenv
dotenv.load_dotenv(str(ROOT / ".env"))

# Topic atoms (as produced by topic_parser)
ATOMS = {
    "method": ["YOLOv5"],
    "object": ["steel"],
    "task": ["defect detection"],
    "scenario": ["hot-rolled strip"],
    "domain": "vision_2d",
    "dataset_terms": ["NEU-DET"],
    "baseline_terms": ["steel surface"],
    "avoid_terms": [],
}

TOPIC = "YOLOv5-based steel surface defect detection on hot-rolled strip using NEU-DET dataset"

CANDIDATES: list[tuple[dict, str, str]] = [
    # --- SHOULD BE ACCEPT (baseline or parallel + hit_keyword) ---
    (
        {
            "title": "NEU-DET: A Benchmark Dataset for Steel Surface Defect Detection",
            "abstract": "We present NEU-DET, a public benchmark with 1800 images of "
                "6 steel surface defect types: rolled-in scale, patches, crazing, "
                "pitted surface, inclusion, scratches. We evaluate Faster R-CNN, "
                "YOLOv3, and YOLOv5 as baseline detectors.",
            "source": "openalex",
        },
        "accept",
        "dataset paper with YOLOv5 baseline + NEU-DET → baseline source",
    ),
    (
        {
            "title": "Steel Surface Defect Detection Using Improved YOLOv5 with "
                "CBAM Attention Module",
            "abstract": "We propose a modified YOLOv5 architecture adding CBAM "
                "attention to detect surface defects on hot-rolled steel strip. "
                "Evaluated on NEU-DET achieving 94.3% mAP.",
            "source": "openalex",
        },
        "accept",
        "YOLOv5 + NEU-DET + steel defect → independent method = parallel",
    ),
    (
        {
            "title": "A Comparative Study of YOLOv5 and YOLOv8 for Steel "
                "Surface Defect Classification on NEU-DET",
            "abstract": "This paper compares YOLOv5s and YOLOx for 6-class "
                "steel surface defect classification.  NEU-DET dataset, "
                "ablation on augmentation strategies.",
            "source": "openalex",
        },
        "accept",
        "YOLOv5 vs YOLOv8 on same dataset/method → comparative baseline",
    ),

    # --- SHOULD BE WEAK_REJECT (generic relevance only) ---
    (
        {
            "title": "YOLOv5-Based Real-Time Object Detection for Autonomous Driving",
            "abstract": "We deploy YOLOv5 on edge devices for pedestrian and vehicle "
                "detection in urban driving scenes. Evaluated on KITTI and BDD100K.",
            "source": "openalex",
        },
        "weak_reject",
        "YOLOv5 same method but different domain (driving not steel)",
    ),
    (
        {
            "title": "A Survey of Deep Learning for Surface Defect Detection",
            "abstract": "We review 120 papers on surface defect detection covering "
                "steel, fabric, semiconductor, and solar cell inspection. "
                "Compare CNN, Transformer, and unsupervised approaches.",
            "source": "openalex",
        },
        "weak_reject",
        "Survey only mentions steel/defect detection briefly → too generic",
    ),
    (
        {
            "title": "YOLOv5 for Medical Image Segmentation: A Feasibility Study",
            "abstract": "YOLOv5 is adapted for X-ray image segmentation in "
                "chest radiology. Evaluated on NIH ChestX-ray14 dataset.",
            "source": "openalex",
        },
        "weak_reject",
        "YOLOv5 same method but domain = medical, no steel/defect",
    ),

    # --- SHOULD BE REJECT (no relevance) ---
    (
        {
            "title": "Transformer-Based Language Model for Legal Document Summarization",
            "abstract": "We fine-tune BERT for summarizing Chinese court judgments. "
                "2000 documents from Beijing courts.",
            "source": "openalex",
        },
        "reject",
        "different domain (legal NLP), no relevance",
    ),
    (
        {
            "title": "A Reinforcement Learning Approach to Portfolio Optimization",
            "abstract": "Deep Q-Network for stock portfolio selection. "
                "Backtested on S&P 500 2015-2023.",
            "source": "openalex",
        },
        "reject",
        "different domain (finance RL), no relevance",
    ),
]


def main() -> None:
    from apps.api.app.services.agents.prompts import re11_paper_verifier as P
    from apps.api.app.services.llm_router import call_json

    results: list[dict] = []
    accept_count = 0
    weak_reject_count = 0
    reject_count = 0

    for i, (cand, *rest) in enumerate(CANDIDATES):
        expected = rest[0]
        rationale = rest[1] if len(rest) > 1 else ""
        t0 = time.time()
        try:
            built = P.build_one(TOPIC, ATOMS, cand)
            out = call_json(built["user"], system=built["system"],
                            profile="fast_json", max_tokens=1200, timeout=120)
            elapsed = round(time.time() - t0, 1)

            verdict = (out.get("verdict") or "").lower().strip()
            hit_kw = out.get("hit_keywords") or []
            rel = out.get("relation_to_topic") or ""

            if verdict == "accept":
                accept_count += 1
            elif verdict == "weak_reject":
                weak_reject_count += 1
            else:
                reject_count += 1

            correct = (
                (expected == "accept" and verdict == "accept")
                or (expected == "weak_reject" and verdict in ("weak_reject", "accept"))
                or (expected == "reject" and verdict in ("reject", "weak_reject"))
            )
            mark = "✅" if correct else "❌"

            results.append({
                "i": i,
                "title": cand["title"][:60],
                "expected": expected,
                "actual": verdict,
                "relation": rel,
                "hit_kw": hit_kw,
                "correct": mark,
                "rationale": rationale,
                "time_s": elapsed,
            })
            print(f"  {mark} [{expected} → {verdict}] {cand['title'][:55]}")
            print(f"      rel={rel}  hit_kw={hit_kw}  ({elapsed}s)")
        except Exception as exc:
            elapsed = round(time.time() - t0, 1)
            print(f"  ⚠️  [ERROR] {cand['title'][:55]}: {type(exc).__name__} ({elapsed}s)")
            results.append({
                "i": i, "title": cand["title"][:60],
                "expected": expected, "actual": "ERROR",
                "error": type(exc).__name__, "time_s": elapsed,
            })

    # Summary verdict mapping
    print("\n" + "=" * 60)
    print("SUMMARY")
    print(f"  accept={accept_count}  weak_reject={weak_reject_count}  "
          f"reject={reject_count}")
    n_correct = sum(1 for r in results if r.get("correct") == "✅")
    n_total = len([r for r in results if "error" not in r])
    print(f"  correct: {n_correct}/{n_total}")

    print("\nExpected vs Actual table:")
    print(f"  {'#':>3} {'Expected':<12} {'Actual':<12} {'OK':<4} Title")
    for r in results:
        mark = r.get("correct", "⚠️")
        print(f"  {r['i']:>3} {r.get('expected','?'):<12} {r.get('actual','?'):<12} "
              f"{mark:<4} {r['title'][:55]}")

    # Persist
    out_path = ROOT / "tmp_re12_eval" / "verify_strictness_test.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "topic": TOPIC,
            "atoms": ATOMS,
            "results": results,
            "summary": {
                "accept": accept_count,
                "weak_reject": weak_reject_count,
                "reject": reject_count,
            },
        }, ensure_ascii=False) + "\n")
    print(f"\nResults appended to {out_path}")


if __name__ == "__main__":
    main()
