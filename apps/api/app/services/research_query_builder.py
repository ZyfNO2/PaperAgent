"""Domain-aware multi-source query builder for research planner.

Builds ResearchQueryPack from TopicParseResult. Generates ≥18 queries total
across 6 source categories, with domain-specific vocabulary. LLM-driven
when available, rule-based fallback otherwise.

Ladder rationale (ponytail):
- Reuse research_prompts for LLM schema/prompt text.
- Reuse research_topic_parser DOMAIN_DICTS for domain vocab (lazy import).
- One module, no subpackages; rules table inline (small enough).
"""
from __future__ import annotations

import logging
from typing import Any

from app.services.llm import LLMUnavailable, chat_json
from app.services.research_prompts import SEARCH_STRATEGY_SCHEMA, search_strategy_system, search_strategy_user

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain-specific query templates (enrichment pools)
# ---------------------------------------------------------------------------
# Per-domain vocabulary that MUST appear (positive) or MUST NOT appear (negative).
# Used by rule_fill_query_pack to assemble domain-correct queries.

_DOMAIN_QUERY_POOLS: dict[str, dict[str, list[str]]] = {
    "vision_3d": {
        "positive_methods": [
            "COLMAP", "MVSNet", "OpenPCDet", "PointNet++", "VoteNet",
            "3D Gaussian Splatting", "DUSt3R", "FoundationStereo", "NeRF",
            "PointRCNN",
        ],
        "paper_templates": [
            "{task} point cloud {object}",
            "3D {task} {object}",
            "{task} 3D point cloud",
            "RGB-D {task} {object}",
            "point cloud {task} benchmark",
            "3D reconstruction {object} inspection",
        ],
        "dataset_templates": [
            "MVTec 3D-AD anomaly detection",
            "Real3D-AD point cloud dataset",
            "3D industrial anomaly dataset",
            "point cloud {task} benchmark",
            "ShapeNet 3D model dataset",
            "ScanObjectNN point cloud dataset",
        ],
        "repo_templates": [
            "OpenPCDet 3D object detection",
            "PointNet++ point cloud github",
            "COLMAP 3D reconstruction github",
            "3D Gaussian Splatting github",
            "DUSt3R 3D reconstruction github",
            "FoundationStereo depth estimation",
            "MVSNet multi-view stereo github",
        ],
        "baseline_templates": [
            "COLMAP SfM MVS baseline",
            "PointNet++ point cloud baseline",
            "OpenPCDet PointRCNN baseline",
            "MVTec 3D-AD anomaly detection baseline",
        ],
        "classic_tool_queries": [
            "COLMAP structure from motion",
            "Open3D point cloud library",
            "MeshLab 3D mesh processing",
            "CloudCompare point cloud viewer",
        ],
        "emerging_method_queries": [
            "3D Gaussian Splatting 2024",
            "DUSt3R global 3D reconstruction",
            "FoundationStereo stereo matching",
            "Point Transformer V3",
        ],
    },
    "vision_2d": {
        "positive_methods": [
            "YOLO", "Faster R-CNN", "Mask R-CNN", "ViT", "U-Net", "ResNet",
        ],
        "paper_templates": [
            "{task} {object} deep learning",
            "{task} {object} YOLO",
            "industrial {task} {object}",
            "surface defect {task} CNN",
            "{task} {object} benchmark",
        ],
        "dataset_templates": [
            "NEU-DET steel surface defect",
            "GC10-DET steel defect dataset",
            "MVTec AD anomaly detection",
            "DAGM texture defect dataset",
            "Severstal steel defect kaggle",
        ],
        "repo_templates": [
            "ultralytics yolov8 github",
            "mmdetection object detection",
            "detectron2 facebook research",
            "timm pytorch image models",
            "segmentation models pytorch",
        ],
        "baseline_templates": [
            "YOLOv8 baseline detection",
            "Faster R-CNN baseline defect",
            "ResNet50 image classification baseline",
            "U-Net segmentation baseline",
        ],
        "classic_tool_queries": [
            "OpenCV image processing",
            "albumentations image augmentation",
            "LabelImg annotation tool",
            "Roboflow dataset management",
        ],
        "emerging_method_queries": [
            "RT-DETR real-time detection",
            "DINO object detection 2024",
            "Segment Anything model industrial",
            "Grounding DINO zero-shot detection",
        ],
    },
    "nlp_llm": {
        "positive_methods": [
            "BERT", "RoBERTa", "LLM", "LoRA", "RAG", "ChatGPT",
        ],
        "paper_templates": [
            "{task} {object} BERT",
            "{task} {object} transformer",
            "pretrained language model {task}",
            "Chinese {task} {object}",
            "fine-tuned BERT {task}",
        ],
        "dataset_templates": [
            "ChnSentiCorp Chinese sentiment",
            "weibo sentiment analysis dataset",
            "THUCNews Chinese text classification",
            "NLPCC sentiment analysis benchmark",
            "huggingface datasets sentiment",
        ],
        "repo_templates": [
            "huggingface transformers github",
            "paddlepaddle paddlenlp github",
            "Chinese-BERT pretrained github",
            "LLaMA-Factory fine-tuning github",
            "peft LoRA huggingface github",
        ],
        "baseline_templates": [
            "BERT-base Chinese baseline",
            "RoBERTa-wwm-ext baseline",
            "TextCNN baseline classification",
            "LSTM baseline sentiment",
        ],
        "classic_tool_queries": [
            "jieba Chinese word segmentation",
            "huggingface tokenizers library",
            "paddlepaddle NLP toolkit",
            "snownlp Chinese sentiment",
        ],
        "emerging_method_queries": [
            "ChatGLM3 fine-tuning 2024",
            "Qwen LLM Chinese downstream",
            "LoRA low-rank adaptation NLP",
            "RAG retrieval augmented generation",
        ],
    },
    "signal_timeseries": {
        "positive_methods": ["LSTM", "GRU", "Transformer"],
        "paper_templates": [
            "{task} {object} LSTM",
            "{task} time series deep learning",
            "anomaly detection sensor LSTM",
            "vibration {task} neural network",
        ],
        "dataset_templates": [
            "UCR time series archive",
            "NAB anomaly benchmark",
            "C-MAPSS turbofan engine",
            "bearing fault dataset CWRU",
        ],
        "repo_templates": [
            "tsai time series library",
            "darts time series forecasting",
            "tensorflow time series github",
            "pytorch-forecasting github",
        ],
        "baseline_templates": [
            "LSTM forecasting baseline",
            "ARIMA baseline forecasting",
            "Transformer time series baseline",
        ],
        "classic_tool_queries": [
            "scipy signal processing",
            "numpy FFT analysis",
        ],
        "emerging_method_queries": [
            "Informer time series 2024",
            "PatchTST time series transformer",
            "TimesNet time series 2024",
        ],
    },
    "robotics_control": {
        "positive_methods": ["ROS", "PID", "MPC"],
        "paper_templates": [
            "{task} robot arm control",
            "{task} mobile robot ROS",
            "autonomous navigation {object}",
            "path planning {object}",
        ],
        "dataset_templates": [
            "KITTI autonomous driving",
            "nuScenes autonomous dataset",
            "Gazebo simulation dataset",
        ],
        "repo_templates": [
            "ROS navigation stack github",
            "moveit motion planning github",
            "PX4 autopilot github",
            "gazebo simulation github",
        ],
        "baseline_templates": [
            "PID control baseline",
            "A* path planning baseline",
            "RRT motion planning baseline",
        ],
        "classic_tool_queries": [
            "ROS robot operating system",
            "RViz visualization tool",
            "Gazebo simulator",
        ],
        "emerging_method_queries": [
            "drone autonomous flight 2024",
            "visual SLAM 2024",
            "neural MPC control 2024",
        ],
    },
}

_DEFAULT_POOL = _DOMAIN_QUERY_POOLS["vision_2d"]  # fallback for unknown domains


# ---------------------------------------------------------------------------
# Negative-domain keyword filter (intersect with topic_parse.negative_domains)
# ---------------------------------------------------------------------------
def _build_negative_filters(topic_parse: dict) -> list[str]:
    """Build negative filter list from topic_parse.negative_domains.

    Maps domain names to representative method/tool names to exclude.
    """
    negatives = topic_parse.get("negative_domains", []) or []
    # negative_domains may contain both domain names ("YOLO") and method names
    # Convert domain-style entries to representative methods
    DOMAIN_TO_METHODS = {
        "vision_3d": ["3DGS", "DUSt3R", "COLMAP", "NeRF"],
        "vision_2d": ["YOLO", "U-Net", "Faster R-CNN"],
        "nlp_llm": ["BERT", "RoBERTa", "LLM"],
        "signal_timeseries": ["LSTM", "GRU"],
        "robotics_control": ["ROS", "PID"],
    }
    filters: list[str] = []
    for neg in negatives:
        if neg in DOMAIN_TO_METHODS:
            filters.extend(DOMAIN_TO_METHODS[neg])
        else:
            filters.append(neg)
    return list(dict.fromkeys(filters))  # dedupe preserving order


# ---------------------------------------------------------------------------
# Rule-based query pack builder (fallback path)
# ---------------------------------------------------------------------------
def _safe_get(pool: dict[str, list[str]], key: str, default: list[str]) -> list[str]:
    return pool.get(key, default) if pool else default


def rule_fill_query_pack(topic_parse: dict) -> dict:
    """Fallback rule-based query pack builder. No LLM needed.

    Assembles queries from domain-specific pools using topic_parse atoms.
    """
    domain = topic_parse.get("domain_route", "unknown") or "unknown"
    pool = _DOMAIN_QUERY_POOLS.get(domain, _DEFAULT_POOL)

    atoms_en = topic_parse.get("query_atoms_en") or []
    atoms_zh = topic_parse.get("query_atoms_zh") or []
    task_terms = topic_parse.get("task_terms") or []
    object_terms = topic_parse.get("object_terms") or []
    method_terms = topic_parse.get("method_terms") or []

    # Pick first reasonable English task/object token for template filling
    en_task = next((a for a in atoms_en if any(k in a.lower() for k in ["detection", "segmentation", "classification", "reconstruction", "analysis", "diagnosis"])), "detection")
    en_obj = next((a for a in atoms_en if a.lower() not in {"detection", "segmentation", "classification", "reconstruction", "analysis"}), "")
    zh_obj = object_terms[0] if object_terms else ""

    # --- paper_queries: 6-10 ---
    paper: list[str] = []
    for tmpl in _safe_get(pool, "paper_templates", []):
        q = tmpl.format(task=en_task, object=en_obj or zh_obj).strip()
        q = " ".join(q.split())  # collapse whitespace
        if 3 <= len(q.split()) <= 10 and q not in paper:
            paper.append(q)
    # Add method-specific queries
    for m in method_terms[:3]:
        q = f"{m} {en_task}".strip()
        if 3 <= len(q.split()) <= 8 and q not in paper:
            paper.append(q)
    # Pad from positive_methods if short
    for m in pool.get("positive_methods", [])[:4]:
        q = f"{m} {en_obj}".strip()
        if 3 <= len(q.split()) <= 8 and q not in paper and len(paper) < 8:
            paper.append(q)

    # --- dataset_queries: 3-6 ---
    dataset: list[str] = []
    for tmpl in _safe_get(pool, "dataset_templates", []):
        q = tmpl.format(task=en_task, object=en_obj or zh_obj).strip()
        q = " ".join(q.split())
        if 3 <= len(q.split()) <= 10 and q not in dataset:
            dataset.append(q)

    # --- repo_queries: 3-6 ---
    repo: list[str] = []
    for tmpl in _safe_get(pool, "repo_templates", []):
        q = tmpl.format(task=en_task, object=en_obj or zh_obj).strip()
        q = " ".join(q.split())
        if 3 <= len(q.split()) <= 10 and q not in repo:
            repo.append(q)

    # --- baseline_queries: 2-4 ---
    baseline: list[str] = []
    for tmpl in _safe_get(pool, "baseline_templates", []):
        q = tmpl.format(task=en_task, object=en_obj or zh_obj).strip()
        q = " ".join(q.split())
        if 3 <= len(q.split()) <= 10 and q not in baseline:
            baseline.append(q)

    # --- classic_tool_queries: 2-4 ---
    classic = list(pool.get("classic_tool_queries", []))

    # --- emerging_method_queries: 2-4 ---
    emerging = list(pool.get("emerging_method_queries", []))

    # --- negative_queries ---
    negative = _build_negative_filters(topic_parse)

    return {
        "paper_queries": paper[:10],
        "dataset_queries": dataset[:6],
        "repo_queries": repo[:6],
        "baseline_queries": baseline[:4],
        "classic_tool_queries": classic[:4],
        "emerging_method_queries": emerging[:4],
        "negative_queries": negative,
        "domain_route": domain,
    }


# ---------------------------------------------------------------------------
# LLM-driven query pack builder (primary path)
# ---------------------------------------------------------------------------
def _flatten_llm_strategies(llm_result: dict) -> dict:
    """Convert LLM search_strategies output to flat ResearchQueryPack dict."""
    strategies = llm_result.get("search_strategies", []) or []

    paper: list[str] = []
    dataset: list[str] = []
    repo: list[str] = []
    baseline: list[str] = []
    classic: list[str] = []
    emerging: list[str] = []

    for strat in strategies:
        target = strat.get("target_type", "")
        queries = strat.get("queries", []) or []
        name = strat.get("name", "")
        # Bucket by both target_type and name for robustness
        if target == "paper" or name == "core_papers":
            paper.extend(queries)
        elif target == "dataset" or name == "datasets":
            dataset.extend(queries)
        elif target == "repo" or name == "github_repos":
            repo.extend(queries)
        elif target == "baseline" or name == "classic_baselines":
            baseline.extend(queries)
        elif target == "tool" or name in {"classic_tools", "emerging_methods"}:
            if name == "emerging_methods":
                emerging.extend(queries)
            else:
                classic.extend(queries)

    negative = llm_result.get("negative_filters", []) or []

    return {
        "paper_queries": paper,
        "dataset_queries": dataset,
        "repo_queries": repo,
        "baseline_queries": baseline,
        "classic_tool_queries": classic,
        "emerging_method_queries": emerging,
        "negative_queries": negative,
        "domain_route": llm_result.get("domain_route", "unknown"),
    }


# ---------------------------------------------------------------------------
# Minimum-query enforcement
# ---------------------------------------------------------------------------
def ensure_minimum_queries(query_pack: dict, min_total: int = 18) -> dict:
    """Ensure total query count meets minimum by padding short buckets.

    Strategy: if total < min_total, borrow from paper_queries (synthesize
    from method/object terms) and dataset_queries. Never pad negative_queries.
    """
    pack = {k: list(v) if isinstance(v, list) else v for k, v in query_pack.items()}
    paper = pack.get("paper_queries", [])
    dataset = pack.get("dataset_queries", [])
    repo = pack.get("repo_queries", [])
    baseline = pack.get("baseline_queries", [])
    classic = pack.get("classic_tool_queries", [])
    emerging = pack.get("emerging_method_queries", [])

    total = len(paper) + len(dataset) + len(repo) + len(baseline) + len(classic) + len(emerging)
    if total >= min_total:
        return pack

    # Padding strategies per bucket — never invent domains, only reuse methods
    domain = pack.get("domain_route", "unknown")
    pool = _DOMAIN_QUERY_POOLS.get(domain, _DEFAULT_POOL)
    positive = pool.get("positive_methods", [])

    deficit = min_total - total

    # Pad paper first (most flexible)
    for m in positive:
        if deficit <= 0:
            break
        q = f"{m} benchmark evaluation"
        if q not in paper:
            paper.append(q)
            deficit -= 1

    # Pad dataset if still short
    for tmpl in pool.get("dataset_templates", []):
        if deficit <= 0:
            break
        q = tmpl.replace("{task}", "evaluation").replace("{object}", "benchmark").strip()
        if q not in dataset:
            dataset.append(q)
            deficit -= 1

    # Pad repo if still short
    for tmpl in pool.get("repo_templates", []):
        if deficit <= 0:
            break
        q = tmpl.replace("{task}", "toolkit").replace("{object}", "library").strip()
        if q not in repo:
            repo.append(q)
            deficit -= 1

    pack["paper_queries"] = paper
    pack["dataset_queries"] = dataset
    pack["repo_queries"] = repo
    return pack


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def build_query_pack(topic_parse: dict, max_queries: int = 40) -> dict:
    """Build multi-source query pack from TopicParseResult.

    Tries LLM first; on failure falls back to rule_fill_query_pack.
    Always runs ensure_minimum_queries to guarantee ≥18 queries.
    Truncates to max_queries (default 40) if LLM overshoots.
    """
    domain = topic_parse.get("domain_route", "unknown") or "unknown"
    pack: dict | None = None

    # 1. Try LLM path
    try:
        topic_parse_json = _topic_parse_for_llm(topic_parse)
        # Need a problem_decompose placeholder if missing — use empty skeleton
        problem_decompose_json = '{"sub_questions": [], "graduation_safe_path": "", "high_risk_path": ""}'
        system = search_strategy_system()
        user = search_strategy_user(topic_parse_json, problem_decompose_json)
        llm_result = chat_json(user, system=system, max_tokens=2000, timeout=30.0)
        pack = _flatten_llm_strategies(llm_result)
        logger.info("LLM query pack built for domain=%s", domain)
    except LLMUnavailable as exc:
        logger.warning("LLM unavailable (%s); using rule_fill_query_pack", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM query build failed (%s); using rule_fill_query_pack", exc)

    # 2. Fallback if LLM failed or returned nothing useful
    if pack is None or sum(
        len(pack.get(k, []))
        for k in ("paper_queries", "dataset_queries", "repo_queries",
                  "baseline_queries", "classic_tool_queries", "emerging_method_queries")
    ) < 6:
        pack = rule_fill_query_pack(topic_parse)
        logger.info("Rule-based query pack built for domain=%s", domain)

    # 3. Inject negative_filters from topic_parse if LLM didn't add them
    if not pack.get("negative_queries"):
        pack["negative_queries"] = _build_negative_filters(topic_parse)

    # 4. Set domain_route
    pack["domain_route"] = domain

    # 5. Ensure domain-required positive methods appear (defense-in-depth)
    pack = _ensure_domain_coverage(pack, topic_parse)

    # 6. Ensure minimum queries (≥18 by default)
    pack = ensure_minimum_queries(pack, min_total=18)

    # 7. Truncate to max_queries budget (proportional cut)
    total = sum(
        len(pack.get(k, []))
        for k in ("paper_queries", "dataset_queries", "repo_queries",
                  "baseline_queries", "classic_tool_queries", "emerging_method_queries")
    )
    if total > max_queries:
        pack = _truncate_pack(pack, max_queries)

    return pack


def _ensure_domain_coverage(pack: dict, topic_parse: dict) -> dict:
    """Inject domain-required positive terms if LLM/rule pack missed them.

    Defense-in-depth: even when LLM succeeds, ensure domain-critical methods
    (3DGS/DUSt3R for vision_3d, BERT/RoBERTa for nlp_llm, etc.) appear in the
    pack so retrieval will surface the right evidence.
    """
    domain = pack.get("domain_route", "unknown") or topic_parse.get("domain_route", "unknown")
    pool = _DOMAIN_QUERY_POOLS.get(domain, _DEFAULT_POOL)
    required_positive = pool.get("positive_methods", [])

    all_q = " ".join(q for k in _BUCKET_KEYS for q in pack.get(k, []))
    all_q_lower = all_q.lower()

    # Check both full name AND canonical short forms (3DGS for "3D Gaussian Splatting")
    _ALIASES = {
        "3D Gaussian Splatting": ["3d gaussian splatting", "3dgs", "gaussian splatting"],
        "FoundationStereo": ["foundationstereo", "foundation stereo"],
    }

    def _has_method(text_lower: str, method: str) -> bool:
        forms = _ALIASES.get(method, [method.lower()])
        return any(f in text_lower for f in forms)

    missing = [m for m in required_positive if not _has_method(all_q_lower, m)]
    if not missing:
        return pack

    # Splice missing methods into repo_queries (most natural home for repos)
    repo = list(pack.get("repo_queries", []))
    for m in missing[:3]:  # cap to avoid bloat
        q = f"{m} github implementation"
        if q not in repo:
            repo.append(q)
    pack["repo_queries"] = repo[:6]
    return pack


_BUCKET_KEYS = (
    "paper_queries", "dataset_queries", "repo_queries",
    "baseline_queries", "classic_tool_queries", "emerging_method_queries",
)


def _truncate_pack(pack: dict, max_total: int) -> dict:
    """Truncate query pack to max_total, keeping all categories represented."""
    buckets = [
        ("paper_queries", 8),
        ("dataset_queries", 5),
        ("repo_queries", 5),
        ("baseline_queries", 3),
        ("classic_tool_queries", 3),
        ("emerging_method_queries", 3),
    ]
    # First pass: cap each bucket at its proportional budget
    total = 0
    out = {}
    for key, cap in buckets:
        items = pack.get(key, [])[:cap]
        out[key] = items
        total += len(items)
    # Second pass: if still over, drop from paper_queries first
    if total > max_total:
        overflow = total - max_total
        out["paper_queries"] = out["paper_queries"][:-overflow] if overflow < len(out["paper_queries"]) else []
    out["negative_queries"] = pack.get("negative_queries", [])
    out["domain_route"] = pack.get("domain_route", "unknown")
    return out


def _topic_parse_for_llm(topic_parse: dict) -> str:
    """Serialize topic_parse for LLM prompt (strip non-serializable junk)."""
    import json
    safe = {
        "raw_topic": topic_parse.get("raw_topic", ""),
        "domain_route": topic_parse.get("domain_route", "unknown"),
        "method_terms": topic_parse.get("method_terms", []),
        "task_terms": topic_parse.get("task_terms", []),
        "object_terms": topic_parse.get("object_terms", []),
        "modality_terms": topic_parse.get("modality_terms", []),
        "query_atoms_zh": topic_parse.get("query_atoms_zh", []),
        "query_atoms_en": topic_parse.get("query_atoms_en", []),
        "negative_domains": topic_parse.get("negative_domains", []),
    }
    return json.dumps(safe, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Self-check (ponytail: one __main__ assert demo, no pytest framework here)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from app.services.research_topic_parser import parse_topic_rule_based

    _all_query_keys = ("paper_queries", "dataset_queries", "repo_queries",
                       "baseline_queries", "classic_tool_queries", "emerging_method_queries")

    def _all_queries(pack: dict) -> str:
        return " ".join(q for k in _all_query_keys for q in pack.get(k, []))

    def _total(pack: dict) -> int:
        return sum(len(pack.get(k, [])) for k in _all_query_keys)

    def _has(text: str, *needles: str) -> bool:
        return any(n.lower() in text.lower() for n in needles)

    # Golden case 1: 3D topic
    r1 = parse_topic_rule_based("基于三维成像的损伤智能检测")
    pack1 = build_query_pack(r1)
    total1 = _total(pack1)
    assert total1 >= 18, f"3D pack total {total1} < 18"
    all_q1 = _all_queries(pack1)
    assert _has(all_q1, "3D Gaussian Splatting", "3DGS"), f"3D pack must include 3DGS: {pack1}"
    assert _has(all_q1, "DUSt3R"), f"3D pack must include DUSt3R: {pack1}"
    assert "YOLO" not in all_q1, f"3D pack must NOT include YOLO: {pack1}"

    # Golden case 2: YOLO steel
    r2 = parse_topic_rule_based("基于YOLO的钢材表面缺陷检测")
    pack2 = build_query_pack(r2)
    all_q2 = _all_queries(pack2)
    assert "3DGS" not in all_q2 and "3D Gaussian Splatting" not in all_q2.lower(), f"YOLO pack must NOT include 3DGS: {pack2}"
    assert "DUSt3R" not in all_q2, f"YOLO pack must NOT include DUSt3R: {pack2}"
    assert "COLMAP" not in all_q2, f"YOLO pack must NOT include COLMAP: {pack2}"

    # Golden case 3: NLP sentiment
    r3 = parse_topic_rule_based("基于大语言模型的中文舆情情感分析")
    pack3 = build_query_pack(r3)
    all_q3 = _all_queries(pack3)
    assert "BERT" in all_q3, f"NLP pack must include BERT: {pack3}"
    assert "RoBERTa" in all_q3, f"NLP pack must include RoBERTa: {pack3}"
    assert "YOLO" not in all_q3, f"NLP pack must NOT include YOLO: {pack3}"
    assert "PointNet" not in all_q3, f"NLP pack must NOT include PointNet: {pack3}"

    print("T3 self-check passed: 3D={}, YOLO={}, NLP={}".format(
        total1, _total(pack2), _total(pack3),
    ))