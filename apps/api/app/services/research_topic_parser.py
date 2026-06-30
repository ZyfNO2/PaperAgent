"""Domain-aware rule-based topic parser for research planner.

Does NOT call LLM directly. Parses raw Chinese/English thesis topics into
structured TopicParseResult. Validates and repairs LLM topic_understand output.

Ladder rationale (ponytail):
- Stdlib re (regex) for keyword matching, no NLP dep.
- Lazy helpers only as needed; one module, no subpackages.
"""
from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Domain dictionaries (zh + en)
# ---------------------------------------------------------------------------
DOMAIN_DICTS: dict[str, dict[str, list[str]]] = {
    "vision_3d": {
        "keywords": [
            "三维成像", "3D成像", "3D imaging", "三维重建", "3D reconstruction",
            "点云", "point cloud", "RGB-D", "rgbd", "depth", "深度",
            "stereo", "立体", "SLAM", "slam", "SfM", "sfm", "MVS", "mvs",
            "激光雷达", "lidar", "LiDAR",
            "COLMAP", "colmap", "MVSNet", "mvsnet", "PointNet++", "pointnet++",
            "VoteNet", "votenet", "PointRCNN", "pointrcnn", "OpenPCDet", "openpcdet",
            "3DGS", "3dgs", "3D Gaussian Splatting", "DUSt3R", "dust3r",
            "FoundationStereo", "NeRF", "nerf", "GauHuman",
            "三维检测", "3D detection",
        ],
        "methods": [
            "COLMAP", "MVSNet", "PointNet++", "VoteNet", "PointRCNN",
            "OpenPCDet", "3DGS", "DUSt3R", "NeRF", "FoundationStereo",
        ],
    },
    "vision_2d": {
        "keywords": [
            "YOLO", "yolo", "Faster R-CNN", "faster rcnn", "Mask R-CNN", "mask rcnn",
            "ViT", "vit", "Transformer", "transformer",
            "检测", "缺陷", "缺陷检测", "目标检测", "分割", "分类",
            "工业表面", "钢材", "PCB", "pcb",
            "image", "图像", "图片", "视觉",
            "U-Net", "unet", "ResNet", "resnet",
            "分类网络", "检测网络",
        ],
        "methods": [
            "YOLO", "Faster R-CNN", "Mask R-CNN", "ViT", "U-Net", "ResNet",
        ],
    },
    "nlp_llm": {
        "keywords": [
            "大语言模型", "LLM", "llm", "BERT", "bert", "RoBERTa", "roberta",
            "自然语言", "NLP", "nlp", "文本", "text",
            "情感分析", "文本分类", "舆情", "chatgpt", "ChatGPT",
            "GPT", "gpt", "LoRA", "lora", "RAG", "rag",
            "中文", "chinese",
            "命名实体", "NER", "ner", "问答", "QA",
        ],
        "methods": [
            "BERT", "RoBERTa", "LLM", "LoRA", "RAG", "ChatGPT", "GPT",
        ],
    },
    "signal_timeseries": {
        "keywords": [
            "时序", "时间序列", "故障诊断", "预测", "振动", "传感器",
            "signal", "signals",
            "LSTM", "lstm", "GRU", "gru",
            "anomaly detection", "异常检测",
            "FFT", "fft", "频谱",
            "forecasting", "forecast",
        ],
        "methods": ["LSTM", "GRU", "FFT", "Transformer"],
    },
    "robotics_control": {
        "keywords": [
            "机器人", "机械臂", "ROS", "ros", "控制", "无人机",
            "robot", "arm", "drone", "UAV", "uav",
            "manipulator", "manipulation",
            "PID", "pid", "MPC", "mpc",
            "navigation", "路径规划", "path planning",
            "SLAM",
        ],
        "methods": ["ROS", "PID", "MPC"],
    },
    "remote_sensing": {
        "keywords": [
            "遥感", "卫星", "高光谱", "SAR", "sar",
            "remote sensing", "satellite", "hyperspectral",
            "航拍", "aerial",
            "土地利用", "land use",
        ],
        "methods": [],
    },
    "medical_ai": {
        "keywords": [
            "医学影像", "CT", "ct", "MRI", "mri", "X光", "病理",
            "medical", "medical image", "clinical",
            "肿瘤", "tumor", "病灶", "lesion",
            "诊断", "diagnosis",
        ],
        "methods": [],
    },
    "energy_power": {
        "keywords": [
            "电力", "电网", "新能源", "光伏", "风电", "负荷预测",
            "power", "grid", "solar", "wind", "load forecasting",
            "电池", "battery",
        ],
        "methods": [],
    },
    "civil_infra": {
        "keywords": [
            "桥梁", "隧道", "建筑", "混凝土", "结构监测",
            "bridge", "tunnel", "building", "concrete",
            "structural health", "SHM",
        ],
        "methods": [],
    },
}


# Object extraction patterns: capture object (not the whole sentence)
_OBJECT_NGRAM_RE = re.compile(
    r"(?:[一-鿿]+|[\w]+)"
    r"(?:表面|结构|图像|影像|数据|样本|纹理|缺陷|损伤|裂纹|文本|语料|信号)"
)
_GENERIC_OBJECT_STOPWORDS = {"基于", "的", "方法", "研究", "分析", "实现", "应用"}


def _split_topic(raw_topic: str) -> list[str]:
    """Split topic by '基于...的' / '的' boundaries to get candidate object phrases."""
    # Common pattern: 基于<method>的<object><task>
    text = raw_topic.strip()
    # Strip leading 基于X的
    m = re.match(r"^基于[一-鿿A-Za-z0-9_-]+的", text)
    if m:
        text = text[m.end():]
    return text


def _extract_keywords(raw_topic: str, keywords: list[str]) -> list[str]:
    """Return list of keywords (in original casing) that appear in raw_topic."""
    raw_lower = raw_topic.lower()
    found: list[str] = []
    for kw in keywords:
        if kw.lower() in raw_lower:
            found.append(kw)
    return found


def _detect_domain(raw_topic: str) -> tuple[str, list[str], float]:
    """Score each domain by keyword hits. Return best domain, hits, confidence."""
    raw_lower = raw_topic.lower()
    scores: dict[str, tuple[int, list[str]]] = {}
    for domain, spec in DOMAIN_DICTS.items():
        hits: list[str] = []
        for kw in spec["keywords"]:
            if kw.lower() in raw_lower:
                hits.append(kw)
        if hits:
            scores[domain] = (len(hits), hits)
    if not scores:
        return "unknown", [], 0.0
    best = max(scores.items(), key=lambda kv: kv[1][0])
    domain, (n_hits, hits) = best
    # Confidence: normalize by keyword count; cap at 0.95 if only 1 hit
    conf = min(0.95, 0.4 + 0.15 * n_hits) if n_hits >= 1 else 0.0
    return domain, hits, conf


def _extract_object_terms(raw_topic: str, task_terms: list[str]) -> list[str]:
    """Extract object terms — NOT the whole sentence.

    Strategy:
    1. Strip leading 基于X的 prefix.
    2. Remove task/method terms from remainder.
    3. Split remainder at task boundaries (检测/分析/诊断).
    """
    remainder = _split_topic(raw_topic)
    # Remove task phrases from tail
    for t in task_terms:
        if t and remainder.endswith(t):
            remainder = remainder[: -len(t)].rstrip("的")
    # Split at task verbs to keep only object head
    cut_patterns = ["检测", "分析", "诊断", "识别", "分类", "分割", "预测", "重建"]
    for pat in cut_patterns:
        idx = remainder.find(pat)
        if idx > 0:
            remainder = remainder[:idx]
    remainder = remainder.strip("的")
    if not remainder:
        return []
    # Further strip trailing 的X structure if too long
    # e.g., "钢材表面" -> ok; "中文舆情文本" -> ok
    return [remainder] if remainder not in _GENERIC_OBJECT_STOPWORDS else []


def _build_query_atoms(
    method_terms: list[str],
    task_terms: list[str],
    object_terms: list[str],
    modality_terms: list[str],
    domain: str,
) -> tuple[list[str], list[str]]:
    """Build Chinese + English search atoms from extracted terms."""
    atoms_zh: list[str] = []
    atoms_en: list[str] = []
    # Map Chinese task -> English task
    task_map = {
        "检测": "detection", "目标检测": "object detection",
        "缺陷检测": "defect detection", "分割": "segmentation",
        "分类": "classification", "识别": "recognition",
        "情感分析": "sentiment analysis", "文本分类": "text classification",
        "三维重建": "3D reconstruction", "损伤检测": "damage detection",
        "异常检测": "anomaly detection", "故障诊断": "fault diagnosis",
    }
    for t in task_terms:
        atoms_zh.append(t)
        en = task_map.get(t)
        if en:
            atoms_en.append(en)
    for m in method_terms:
        atoms_en.append(m)  # methods are usually proper nouns
    for o in object_terms:
        atoms_zh.append(o)
    for mod in modality_terms:
        atoms_en.append(mod) if mod.isascii() else atoms_zh.append(mod)
    # Dedupe while preserving order
    seen = set()
    atoms_zh_dedup = []
    for a in atoms_zh:
        if a not in seen:
            seen.add(a)
            atoms_zh_dedup.append(a)
    seen.clear()
    atoms_en_dedup = []
    for a in atoms_en:
        if a not in seen:
            seen.add(a)
            atoms_en_dedup.append(a)
    return atoms_zh_dedup, atoms_en_dedup


def _needs_clarification(domain: str, object_terms: list[str]) -> list[str]:
    """Return clarification questions when domain or object is ambiguous."""
    q: list[str] = []
    if not object_terms or all(o in {"数据", "样本", "图像", "影像"} for o in object_terms):
        q.append("研究对象不够具体：能否明确具体的应用场景(如桥梁/工业零件/混凝土/钢材/医疗影像等)?")
    return q


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def parse_topic_rule_based(raw_topic: str) -> dict:
    """Rule-based topic parsing, no LLM needed.

    Returns a dict matching the topic_understand schema (subset relevant to
    deterministic parsing). Caller (research_planner_agent) merges this with
    LLM output and runs validate_and_repair_llm_output.
    """
    raw = raw_topic.strip()

    # 1. Domain detection
    domain, domain_hits, conf = _detect_domain(raw)

    # 2. Method terms
    method_terms: list[str] = []
    if domain in DOMAIN_DICTS:
        for m in DOMAIN_DICTS[domain]["methods"]:
            if m.lower() in raw.lower():
                method_terms.append(m)
    # Also catch explicitly mentioned methods regardless of domain
    for d, spec in DOMAIN_DICTS.items():
        for m in spec["methods"]:
            if m.lower() in raw.lower() and m not in method_terms:
                method_terms.append(m)

    # 3. Task terms
    task_zh = [
        "检测", "目标检测", "缺陷检测", "分割", "分类", "识别",
        "情感分析", "文本分类", "三维重建", "损伤检测",
        "异常检测", "故障诊断", "预测",
    ]
    task_terms = [t for t in task_zh if t in raw]

    # 4. Object terms (NOT the whole sentence)
    object_terms = _extract_object_terms(raw, task_terms)

    # 5. Modality terms
    modality_map = {
        "三维成像": "3D imaging", "3D成像": "3D imaging",
        "三维重建": "3D reconstruction", "点云": "point cloud",
        "RGB-D": "RGB-D", "激光雷达": "lidar",
        "文本": "text", "图像": "image", "影像": "image",
        "高光谱": "hyperspectral", "卫星": "satellite",
    }
    modality_terms: list[str] = []
    for zh, en in modality_map.items():
        if zh in raw:
            modality_terms.append(zh)
            if en not in modality_terms:
                modality_terms.append(en)

    # 6. Risk terms (hedges like 智能/自动/鲁棒)
    risk_pattern = re.compile(r"(智能|自动|鲁棒|泛化|高效|实时)")
    risk_terms = risk_pattern.findall(raw)

    # 7. Query atoms
    atoms_zh, atoms_en = _build_query_atoms(
        method_terms, task_terms, object_terms, modality_terms, domain
    )

    # 8. Negative domains (other domains' methods that should NOT be used)
    negative_domains: list[str] = []
    if domain == "vision_3d":
        negative_domains = ["YOLO", "U-Net", "BERT"]
    elif domain == "vision_2d":
        negative_domains = ["3DGS", "DUSt3R", "COLMAP", "NeRF"]
    elif domain == "nlp_llm":
        negative_domains = ["YOLO", "U-Net", "PointNet", "COLMAP", "ResNet"]

    # 9. Clarification
    clarification = _needs_clarification(domain, object_terms)

    return {
        "raw_topic": raw,
        "normalized_topic": raw,
        "domain_route": domain,
        "domain_confidence": round(conf, 2),
        "method_terms": method_terms,
        "task_terms": task_terms,
        "object_terms": object_terms,
        "modality_terms": modality_terms,
        "data_terms": [],
        "metric_terms": [],
        "risk_terms": risk_terms,
        "query_atoms_zh": atoms_zh,
        "query_atoms_en": atoms_en,
        "negative_domains": negative_domains,
        "needs_clarification": clarification,
        "why_this_route": f"基于关键词命中 ({len(domain_hits)} 项) 选择 {domain}; 命中: {', '.join(domain_hits[:5])}",
    }


def validate_and_repair_llm_output(llm_output: dict, raw_topic: str) -> dict:
    """Validate LLM output against schema, repair common issues.

    Repairs applied (in order):
    1. Missing fields: fill with rule-based parse defaults.
    2. object_terms == raw_topic: re-extract from rule-based parser.
    3. domain_route conflicts with method keyword hints: override.
    4. Mark llm_output_repaired=True and domain_route_conflict=True if repairs applied.

    Returns a new dict; does not mutate input.
    """
    if not isinstance(llm_output, dict):
        llm_output = {}

    rule_based = parse_topic_rule_based(raw_topic)

    repaired = dict(llm_output)  # shallow copy
    repairs_applied = False
    domain_conflict = False

    # 1. Ensure required fields exist
    for field in [
        "raw_topic", "normalized_topic", "domain_route", "domain_confidence",
        "method_terms", "task_terms", "object_terms", "modality_terms",
        "data_terms", "metric_terms", "risk_terms",
        "query_atoms_zh", "query_atoms_en", "negative_domains",
        "needs_clarification", "why_this_route",
    ]:
        if field not in repaired or repaired[field] is None:
            repaired[field] = rule_based.get(field, [] if field.endswith("_terms") or field.endswith("_atoms_zh") or field.endswith("_atoms_en") or field.endswith("_domains") or field.endswith("_clarification") else "" if field != "domain_confidence" else 0.0)
            repairs_applied = True

    # 2. Fix object_terms if it's the whole sentence
    obj = repaired.get("object_terms", [])
    if isinstance(obj, list) and obj and any(o == raw_topic or o == raw_topic.strip() for o in obj):
        repaired["object_terms"] = rule_based["object_terms"]
        repairs_applied = True

    # 3. domain_route conflict: if LLM route has methods that belong to a different domain
    llm_domain = repaired.get("domain_route", "unknown")
    llm_methods = repaired.get("method_terms", [])
    # Find ground-truth domain by methods
    detected_by_method: str | None = None
    for d, spec in DOMAIN_DICTS.items():
        for m in spec["methods"]:
            if any(m.lower() == lm.lower() for lm in llm_methods):
                detected_by_method = d
                break
        if detected_by_method:
            break
    if detected_by_method and detected_by_method != llm_domain:
        repaired["domain_route"] = detected_by_method
        domain_conflict = True
        repairs_applied = True
        # Re-add negative_domains
        repaired["negative_domains"] = rule_based["negative_domains"]

    # 4. If object_terms is empty, borrow from rule-based
    if not repaired.get("object_terms"):
        repaired["object_terms"] = rule_based["object_terms"]
        if rule_based["object_terms"]:
            repairs_applied = True

    # 5. If domain_route is unknown but rule-based has confidence, use rule-based
    if repaired.get("domain_route") == "unknown" and rule_based["domain_route"] != "unknown":
        if rule_based["domain_confidence"] >= 0.5:
            repaired["domain_route"] = rule_based["domain_route"]
            repairs_applied = True

    # Mark repair metadata
    repaired["llm_output_repaired"] = repairs_applied
    repaired["domain_route_conflict"] = domain_conflict

    return repaired


# ---------------------------------------------------------------------------
# Self-check (lazy: one assert-based __main__ demo, no test framework)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Test case 1
    r1 = parse_topic_rule_based("基于三维成像的损伤智能检测")
    assert r1["domain_route"] == "vision_3d", f"T1 fail: {r1['domain_route']}"
    assert "3DGS" not in r1["negative_domains"] or r1["domain_route"] != "vision_3d", "T1 should not warn against 3DGS for vision_3d"
    assert r1["object_terms"] != ["基于三维成像的损伤智能检测"], f"T1 object wrong: {r1['object_terms']}"

    # Test case 2
    r2 = parse_topic_rule_based("基于YOLO的钢材表面缺陷检测")
    assert r2["domain_route"] == "vision_2d", f"T2 fail: {r2['domain_route']}"
    for neg in ["3DGS", "DUSt3R", "COLMAP"]:
        assert neg in r2["negative_domains"], f"T2 must include {neg} in negative_domains"
    assert "YOLO" in r2["method_terms"], f"T2 must extract YOLO: {r2['method_terms']}"

    # Test case 3
    r3 = parse_topic_rule_based("基于大语言模型的中文舆情情感分析")
    assert r3["domain_route"] == "nlp_llm", f"T3 fail: {r3['domain_route']}"
    for neg in ["YOLO", "U-Net", "PointNet", "COLMAP"]:
        assert neg in r3["negative_domains"], f"T3 must include {neg} in negative_domains"

    # Repair check: object_terms == raw_topic
    bad = {"raw_topic": "x", "domain_route": "vision_2d", "method_terms": [],
           "task_terms": [], "object_terms": ["基于YOLO的钢材表面缺陷检测"]}
    repaired = validate_and_repair_llm_output(bad, "基于YOLO的钢材表面缺陷检测")
    assert repaired["object_terms"] != ["基于YOLO的钢材表面缺陷检测"], "repair must split object_terms"

    print("All 4 self-checks passed.")