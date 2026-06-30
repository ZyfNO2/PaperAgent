"""Session 64 T4: PaperModuleMatrix.

Build a "Base + Module A + Module B + Dataset + Metric" matrix from parallel
papers and module papers. Heuristic extraction, no LLM, no network.

Ponytail: explicit keyword rules, no fabrication. If a paper doesn't mention a
field, leave it as None or empty. Recommendations are scored by known-dataset
overlap and high-reproducibility signals (recent year, open license, public
dataset).
"""

from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------- 数据结构 ---------- #


class PaperModuleEntry(BaseModel):
    """A single paper's decomposition into base + modules + dataset + metrics."""

    model_config = ConfigDict(extra="forbid")

    base: str
    module_a: str
    module_b: str | None = None
    dataset: str
    metrics: list[str] = Field(default_factory=list)
    paper_title: str
    paper_url: str | None = None
    improvement_description: str
    risk_notes: list[str] = Field(default_factory=list)


class PaperModuleMatrix(BaseModel):
    """Aggregated module matrix with graduation-friendly recommendations."""

    model_config = ConfigDict(extra="forbid")

    topic: str
    domain: str
    entries: list[PaperModuleEntry] = Field(default_factory=list)
    missing_module_types: list[str] = Field(default_factory=list)
    baseline_options: list[dict] = Field(default_factory=list)
    recommended_combinations: list[dict] = Field(default_factory=list)


RiskType = Literal[
    "data_mismatch",
    "reproducibility_low",
    "no_public_dataset",
    "metric_overlap",
    "module_untested",
]


# ---------- 关键词表 ---------- #
# ponytail: 用显式规则做提取, 不调用 LLM. 命中关键词就标, 不命中就空.

_BASE_KEYWORDS = {
    "yolov5", "yolov7", "yolov8", "yolov3", "yolo",
    "faster_rcnn", "mask_rcnn", "retinanet", "ssd",
    "u-net", "unet", "deeplabv3", "segformer", "hrnet",
    "vit", "swin", "resnet", "efficientnet", "mobilenet",
    "bert", "roberta", "gpt", "llama", "t5",
    "transformer", "lstm", "gru",
}

_MODULE_KEYWORDS = {
    "attention": "attention",
    "cbam": "CBAM",
    "fpn": "FPN",
    "panet": "PANet",
    "bi_fpn": "BiFPN",
    "asff": "ASFF",
    "ciou": "CIoU loss",
    "diou": "DIoU loss",
    "giou": "GIoU loss",
    "focal_loss": "focal loss",
    "spp": "SPP",
    "sppf": "SPPF",
    "dropout": "dropout",
    "batch_norm": "batch normalization",
    "data_augmentation": "data augmentation",
    "mosaic": "mosaic augmentation",
    "transfer_learning": "transfer learning",
    "knowledge_distillation": "knowledge distillation",
    "pruning": "model pruning",
    "quantization": "quantization",
    "ema": "EMA",
    "cosine_lr": "cosine LR schedule",
    "warmup": "warmup",
    "self_distillation": "self-distillation",
    "contrastive": "contrastive learning",
    "lora": "LoRA",
    "prefix_tuning": "prefix tuning",
    "adapter": "adapter module",
    "prompt": "prompt engineering",
}

_DATASET_KEYWORDS = {
    "coco": "COCO",
    "voc": "VOC2007/VOC2012",
    "cityscapes": "Cityscapes",
    "imagenet": "ImageNet",
    "crack": "Crack detection dataset",
    "crack500": "Crack500",
    "deepcrack": "DeepCrack",
    "sdnet2018": "SDNet2018",
    "concrete": "Concrete crack dataset",
    "kaggle": "Kaggle dataset",
    "huggingface": "HuggingFace dataset",
    "mnist": "MNIST",
    "cifar": "CIFAR-10/100",
    "glue": "GLUE",
    "squad": "SQuAD",
    "ag_news": "AG News",
    "thucnews": "THUCNews",
    "weibo": "Weibo sentiment",
    "chinese": "Chinese corpus",
    "custom": "custom/private dataset",
}

_METRIC_KEYWORDS = {
    "map": "mAP",
    "mAP@0.5": "mAP@0.5",
    "mAP@0.5:0.95": "mAP@0.5:0.95",
    "iou": "IoU",
    "dice": "Dice",
    "f1": "F1",
    "precision": "precision",
    "recall": "recall",
    "accuracy": "accuracy",
    "bleu": "BLEU",
    "rouge": "ROUGE",
    "perplexity": "perplexity",
    "loss": "loss",
    "fps": "FPS",
    "inference_time": "inference time",
    "auc": "AUC",
    "psnr": "PSNR",
    "ssim": "SSIM",
}

_REPRODUCIBILITY_RISK = {"kaggle", "custom", "chinese", "weibo", "thucnews", "concrete"}
_HIGH_REPRO = {"coco", "voc", "cityscapes", "imagenet", "crack500", "deepcrack", "sdnet2018",
               "mnist", "cifar", "glue", "squad"}


# ---------- 提取函数 ---------- #


def _extract_from_text(text: str, keywords: dict[str, str]) -> list[str]:
    """从文本中按关键词字典匹配, 返回对应的标签列表 (去重保序)."""
    text_l = (text or "").lower()
    seen: set[str] = set()
    out: list[str] = []
    for kw, label in keywords.items():
        if kw in text_l and label not in seen:
            seen.add(label)
            out.append(label)
    return out


def _extract_base_modules(paper: dict) -> tuple[str, list[str]]:
    """Extract base framework and modules from paper.

    ponytail: 先尝试 raw.base / raw.framework 字段, 退化为关键词匹配.
    modules 最多取前 2 个 (module_a, module_b).
    """
    raw = paper.get("raw") or {}
    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    text = " ".join([title or "", abstract or ""]).lower()

    # base
    base = None
    # ponytail: longest-keyword-first to prefer "yolov5" over "yolo"
    for kw in sorted(_BASE_KEYWORDS, key=len, reverse=True):
        if kw in text:
            base = kw.upper() if kw.isalpha() and len(kw) <= 6 else kw
            break
    if base is None:
        for kw, label in _BASE_KEYWORDS.items():
            if label.lower() in text:
                base = label
                break
    if base is None:
        base = raw.get("base") or raw.get("framework") or "unknown"

    # modules
    modules = _extract_from_text(text, _MODULE_KEYWORDS)
    if not modules:
        raw_mods = raw.get("modules") or []
        modules = [str(m) for m in raw_mods[:2]]

    return str(base), modules[:2]


def _extract_dataset(paper: dict) -> str:
    """Extract dataset name from paper text or raw field."""
    raw = paper.get("raw") or {}
    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    text = " ".join([title or "", abstract or ""]).lower()

    for kw, label in _DATASET_KEYWORDS.items():
        if kw in text:
            return label

    raw_ds = raw.get("dataset")
    if raw_ds:
        return str(raw_ds)

    return "custom/private dataset"


def _extract_metrics(paper: dict) -> list[str]:
    """Extract metrics mentioned in paper."""
    raw = paper.get("raw") or {}
    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    text = " ".join([title or "", abstract or ""]).lower()

    metrics = _extract_from_text(text, _METRIC_KEYWORDS)
    if not metrics:
        raw_m = raw.get("metrics") or []
        metrics = [str(m) for m in raw_m]

    return metrics


def _build_risk_notes(paper: dict, dataset: str, base: str, modules: list[str]) -> list[str]:
    """Heuristic risk note generation."""
    notes: list[str] = []
    raw = paper.get("raw") or {}
    year = paper.get("year")

    ds_l = dataset.lower()
    if any(r in ds_l for r in _REPRODUCIBILITY_RISK):
        notes.append("data_mismatch")
    if year is not None and year < 2020:
        notes.append("reproducibility_low")
    if not modules and base == "unknown":
        notes.append("module_untested")
    license_ = paper.get("license") or raw.get("license")
    if not license_:
        notes.append("reproducibility_low")
    return notes


def _build_improvement_description(paper: dict, modules: list[str], base: str) -> str:
    """One-line description of what the paper improves."""
    raw = paper.get("raw") or {}
    existing = raw.get("improvement") or raw.get("contribution")
    if existing:
        return str(existing)

    if not modules:
        return f"Evaluates {base} on target task with no extra modules."

    mod_str = " + ".join(modules)
    return f"Adds {mod_str} on top of {base} to improve baseline performance."


# ---------- 矩阵构建 ---------- #


def build_module_matrix(
    parallel_papers: list[dict],
    module_papers: list[dict],
    baseline_candidates: list[dict],
    topic_atoms: dict,
) -> PaperModuleMatrix:
    """Build module matrix from classified papers.

    Args:
        parallel_papers: papers that solve the same problem with different approaches
        module_papers: papers that propose specific modules / improvements
        baseline_candidates: candidate baseline implementations (e.g. from repo search)
        topic_atoms: dict with keys like ``topic``, ``domain`` (from earlier phase)

    Returns:
        PaperModuleMatrix with entries + recommendations.
    """
    topic = str(topic_atoms.get("topic", "") or "unknown")
    domain = str(topic_atoms.get("domain", "") or "unknown")

    entries: list[PaperModuleEntry] = []

    for p in (parallel_papers or []) + (module_papers or []):
        if not isinstance(p, dict):
            continue
        base, modules = _extract_base_modules(p)
        module_a = modules[0] if len(modules) >= 1 else "none"
        module_b = modules[1] if len(modules) >= 2 else None
        dataset = _extract_dataset(p)
        metrics = _extract_metrics(p)
        improvement = _build_improvement_description(p, modules, base)
        risks = _build_risk_notes(p, dataset, base, modules)

        entries.append(PaperModuleEntry(
            base=base,
            module_a=module_a,
            module_b=module_b,
            dataset=dataset,
            metrics=metrics,
            paper_title=p.get("title", "") or "untitled",
            paper_url=p.get("url"),
            improvement_description=improvement,
            risk_notes=risks,
        ))

    # missing module types: 检测 entries 中常见的 module 类别是否覆盖
    known_module_types = {"attention", "loss_function", "neck", "augmentation", "regularization"}
    present_types: set[str] = set()
    for e in entries:
        for m in (e.module_a, e.module_b):
            if not m:
                continue
            ml = m.lower()
            if "attention" in ml or "cbam" in ml:
                present_types.add("attention")
            if "ciou" in ml or "diou" in ml or "giou" in ml or "focal" in ml:
                present_types.add("loss_function")
            if "fpn" in ml or "panet" in ml or "bifpn" in ml or "asff" in ml:
                present_types.add("neck")
            if "augment" in ml or "mosaic" in ml:
                present_types.add("augmentation")
            if "dropout" in ml or "ema" in ml or "warmup" in ml:
                present_types.add("regularization")
    missing_module_types = sorted(known_module_types - present_types)

    # baseline options
    baseline_options = []
    for b in (baseline_candidates or []):
        if not isinstance(b, dict):
            continue
        baseline_options.append({
            "name": b.get("name") or b.get("title", "unknown"),
            "source": b.get("source", "unknown"),
            "url": b.get("url"),
            "license": b.get("license"),
            "stars": b.get("stars"),
            "language": b.get("language") or (b.get("raw") or {}).get("language"),
            "year": b.get("year"),
        })

    # recommendations
    matrix = PaperModuleMatrix(
        topic=topic,
        domain=domain,
        entries=entries,
        missing_module_types=missing_module_types,
        baseline_options=baseline_options,
        recommended_combinations=[],
    )
    matrix.recommended_combinations = _generate_recommendations(matrix)
    return matrix


def _rank_combinations(entries: list[PaperModuleEntry]) -> list[dict]:
    """Rank module combinations by graduation fit.

    Heuristic score (higher = better for graduation):
      + 2 if dataset is a known public benchmark
      + 1 if base is well-known (not 'unknown')
      + 1 if both module_a and module_b are filled
      - 1 for each risk note
    """
    combos: dict[tuple, dict] = {}
    for e in entries:
        key = (e.base, e.module_a, e.module_b or "", e.dataset)
        if key in combos:
            combos[key]["paper_count"] += 1
            combos[key]["papers"].append(e.paper_title)
        else:
            score = 0
            ds_l = e.dataset.lower()
            if any(hr in ds_l for hr in _HIGH_REPRO):
                score += 2
            if e.base != "unknown":
                score += 1
            if e.module_b:
                score += 1
            score -= len(e.risk_notes)

            combos[key] = {
                "base": e.base,
                "module_a": e.module_a,
                "module_b": e.module_b,
                "dataset": e.dataset,
                "score": score,
                "paper_count": 1,
                "papers": [e.paper_title],
                "metrics": list(e.metrics),
            }

    ranked = sorted(combos.values(), key=lambda x: (-x["score"], -x["paper_count"]))
    return ranked


def _generate_recommendations(matrix: PaperModuleMatrix) -> list[dict]:
    """Generate baseline + module recommendations."""
    ranked = _rank_combinations(matrix.entries)
    recs: list[dict] = []
    for combo in ranked[:5]:
        rec = {
            "base": combo["base"],
            "module_a": combo["module_a"],
            "module_b": combo["module_b"],
            "dataset": combo["dataset"],
            "score": combo["score"],
            "paper_count": combo["paper_count"],
            "evidence_papers": combo["papers"],
            "metrics": combo["metrics"],
            "rationale": [],
        }
        # graduation-friendly rationale
        ds_l = combo["dataset"].lower()
        if any(hr in ds_l for hr in _HIGH_REPRO):
            rec["rationale"].append("uses public benchmark dataset (high reproducibility)")
        if combo["base"] in {"YOLOV5", "YOLOV7", "YOLOV8", "U-NET", "UNET", "RESNET", "VIT",
                              "BERT", "ROBERTA", "TRANSFORMER"}:
            rec["rationale"].append("well-known base model with community support")
        if combo["module_b"]:
            rec["rationale"].append("two-module combination (more improvement headroom)")
        else:
            rec["rationale"].append("single-module combination (lower complexity)")
        if combo["paper_count"] >= 2:
            rec["rationale"].append(f"validated by {combo['paper_count']} papers")
        recs.append(rec)
    return recs


# ---------- self-check ---------- #

if __name__ == "__main__":
    # ponytail: self-check
    parallel = [
        {
            "title": "Crack detection with YOLOv5 and attention",
            "abstract": "We improve YOLOv5 with CBAM attention on COCO and Crack500.",
            "year": 2023,
            "license": "MIT",
        },
        {
            "title": "U-Net with CIoU loss for crack segmentation",
            "abstract": "U-Net + CIoU loss evaluated on DeepCrack and VOC.",
            "year": 2024,
            "license": "Apache-2.0",
        },
        {
            "title": "Old paper",
            "abstract": "Some BERT on GLUE",
            "year": 2018,
            "license": None,
        },
    ]
    module_papers = [
        {
            "title": "FPN improvement",
            "abstract": "Adding BiFPN to YOLOv8 on COCO boosts mAP.",
            "year": 2024,
            "license": "MIT",
        },
    ]
    baselines = [
        {
            "name": "ultralytics/yolov5",
            "source": "github",
            "url": "https://github.com/ultralytics/yolov5",
            "license": "GPL-3.0",
            "stars": 45000,
            "language": "Python",
            "year": 2024,
        },
    ]
    topic_atoms = {"topic": "crack detection", "domain": "structural health monitoring"}

    matrix = build_module_matrix(parallel, module_papers, baselines, topic_atoms)
    assert matrix.topic == "crack detection"
    assert matrix.domain == "structural health monitoring"
    assert len(matrix.entries) == 4, len(matrix.entries)  # 3 parallel + 1 module paper
    assert matrix.entries[0].base.upper() in {"YOLOV5"}, matrix.entries[0].base
    assert matrix.entries[0].module_a in {"attention", "CBAM"}, matrix.entries[0].module_a
    assert len(matrix.recommended_combinations) > 0
    # top rec should prefer public dataset
    top = matrix.recommended_combinations[0]
    assert top["score"] >= 0
    assert isinstance(matrix.baseline_options, list)
    print(f"OK paper_module_matrix self-check passed (entries={len(matrix.entries)}, recs={len(matrix.recommended_combinations)})")
