"""OneTopic MVP 业务核心: 拆解 + 检索 + 评级 + 推荐 + 审核.

设计原则:
- LLM 优先 (prefer="llm" or "auto"), 失败 → heuristic
- 启发式必须能跑通验收, 不许让 LLM 挂掉服务
- 内部不建 DB, 全程在内存里, SSE 流式 emit "step" / "result" 事件
"""

from __future__ import annotations

import json
import logging
import uuid
import re
import time
from collections.abc import Callable
from typing import Any

from ..schemas import (
    BaselineHit,
    DatasetHit,
    EvidenceSummary,
    FeasibilitySummary,
    KeywordBreakdown,
    LightReview,
    OneTopicRequest,
    OneTopicResponse,
    PaperHit,
    PivotRoute,
    ProposalRecommendation,
    ReviewCheck,
    SearchPlan,
    TopicUnderstanding,
    WorkPackageSuggestion,
)
from . import arxiv as arxiv_client
from . import evidence as ev_store
from . import llm

logger = logging.getLogger(__name__)


# ---------- 启发式词典 (LLM 失败兜底) ---------- #

_METHOD_HINTS = {
    "yolo": "YOLO", "yolov": "YOLOv8", "transformer": "Transformer",
    "vit": "ViT", "bert": "BERT", "gpt": "GPT", "llm": "LLM",
    "diffusion": "Diffusion", "gan": "GAN", "resnet": "ResNet",
    "cnn": "CNN", "lstm": "LSTM", "gru": "GRU", "mamba": "Mamba",
    "知识图谱": "知识图谱", "图神经网络": "GNN", "gnn": "GNN",
    "强化学习": "强化学习", "注意力": "注意力机制", "attention": "注意力机制",
    "轻量化": "轻量化", "蒸馏": "知识蒸馏", "剪枝": "剪枝",
    "多模态": "多模态", "跨模态": "跨模态",
}
_TASK_HINTS = {
    "检测": "目标检测", "识别": "图像识别", "分类": "图像分类",
    "分割": "语义分割", "预测": "时序预测", "生成": "图像生成",
    "检索": "信息检索", "推荐": "推荐系统", "聚类": "聚类",
    "诊断": "故障诊断", "翻译": "机器翻译", "摘要": "文本摘要",
    "qa": "问答", "问答": "问答", "对话": "对话系统",
    "tracking": "目标跟踪", "跟踪": "目标跟踪",
    "配准": "图像配准", "重建": "三维重建", "去噪": "图像去噪",
}
_OBJECT_HINTS = {
    "钢材": "钢材", "带钢": "带钢", "钢板": "钢板",
    "桥梁": "桥梁", "道路": "道路", "混凝土": "混凝土",
    "叶片": "叶片", "绝缘子": "绝缘子", "输电线路": "输电线路",
    "路面": "路面", "隧道": "隧道", "建筑": "建筑",
    "电路板": "PCB", "pcb": "PCB",
    "焊缝": "焊缝", "螺栓": "螺栓", "管道": "管道",
    "齿轮": "齿轮", "轴承": "轴承", "零件": "机械零件",
    "水果": "水果", "蔬菜": "蔬菜", "作物": "农作物",
    "医学": "医学影像", "ct": "CT 影像", "mri": "MRI 影像",
    "x光": "X 光影像", "皮肤": "皮肤病变", "眼底": "眼底图像",
    "细胞": "细胞图像", "肺结节": "肺结节",
    "行人": "行人", "车辆": "车辆", "交通": "交通场景",
}
_SCENARIO_HINTS = {
    "工业": "工业质检", "质检": "工业质检", "制造": "智能制造",
    "医疗": "医学影像", "农业": "智慧农业", "遥感": "遥感图像",
    "交通": "智能交通", "自动驾驶": "自动驾驶",
    "电力": "电力巡检", "巡检": "智能巡检",
    "安防": "智能安防", "监控": "视频监控",
    "金融": "金融风控", "教育": "智慧教育", "电商": "电商推荐",
}
_METRIC_HINTS = {
    "map": "mAP", "准确率": "Accuracy", "accuracy": "Accuracy",
    "recall": "Recall", "精确率": "Precision", "precision": "Precision",
    "f1": "F1", "fps": "FPS", "参数量": "Params",
    "flops": "FLOPs", "auc": "AUC", "iou": "IoU", "psnr": "PSNR",
    "ssim": "SSIM", "bleu": "BLEU", "rouge": "ROUGE",
}
_RISK_TERMS = {
    "智能", "通用", "全自动", "实时", "高精度", "大模型", "多模态",
    "端到端", "全场景", "通用智能", "自适应", "鲁棒", "可解释",
}


# ---------- 通用 ---------- #


def _safe_chinese(raw: str) -> str:
    """清洗题目: 去前后空白, 把半角标点换全角, 方便中英混合识别."""

    s = (raw or "").strip()
    if not s:
        return s
    s = s.replace("(", "（").replace(")", "）").replace(",", "，")
    s = s.replace(":", "：").replace(";", "；")
    return s


def _normalize_topic(raw: str) -> str:
    """标准化题目: 保留原题, 仅清理空白和半角标点."""

    return _safe_chinese(raw)


def _has_specific_object(object_keywords: list[str], raw: str) -> bool:
    """判断题目里是否给出具体研究对象 (vs. 抽象词)."""

    if object_keywords:
        return True
    # 退化: 题目里有中文实体词 (>= 2 个汉字且非"基于/方法/研究"等虚词)
    abstract = {"基于", "的", "研究", "方法", "算法", "系统", "应用", "实现", "设计", "优化"}
    tokens = re.findall(r"[一-龥A-Za-z]{2,}", raw)
    for t in tokens:
        if t in abstract:
            continue
        # 任何具象词都算有具体对象
        if any(t.lower() in k.lower() or k in t for k in (
            "钢", "桥", "路", "叶", "电", "管", "轮", "轴", "果",
            "菜", "皮", "眼", "细", "行", "车", "PCB", "焊", "螺",
        )):
            return True
    return False


def _is_niche_topic(raw: str, keywords: KeywordBreakdown) -> bool:
    """判断题目是否极小众 (启发式).

    启发式: 没有任何标准方法词, 也没有任何常见对象/任务词, 且 LLM 没法识别.
    """

    if keywords.method_keywords or keywords.task_keywords:
        return False
    if keywords.object_keywords:
        return False
    # 没有任何可识别词, 视为极小众
    return len(re.findall(r"[一-龥A-Za-z]{2,}", raw)) <= 3


# ---------- 拆解 (LLM + heuristic) ---------- #


def _heuristic_breakdown(raw: str) -> KeywordBreakdown:
    """纯规则: 用词典 + 正则把题目拆成 method/task/object/scenario/metric/risk."""

    text = raw
    method: list[str] = []
    task: list[str] = []
    obj: list[str] = []
    scenario: list[str] = []
    metric: list[str] = []
    risk: list[str] = []

    low = text.lower()
    for hint, label in _METHOD_HINTS.items():
        if hint.lower() in low and label not in method:
            method.append(label)
    for hint, label in _TASK_HINTS.items():
        if hint in text and label not in task:
            task.append(label)
    for hint, label in _OBJECT_HINTS.items():
        if hint in text and label not in obj:
            obj.append(label)
    for hint, label in _SCENARIO_HINTS.items():
        if hint in text and label not in scenario:
            scenario.append(label)
    for hint, label in _METRIC_HINTS.items():
        if hint.lower() in low and label not in metric:
            metric.append(label)
    for t in _RISK_TERMS:
        if t in text and t not in risk:
            risk.append(t)

    # 抽一个核心对象 (启发式: 取"基于 X 的 Y" 里的 Y, 或 "X 表面缺陷" / "X 检测")
    if not obj:
        m = re.search(r"([一-龥A-Za-z]+(?:表面|内部|外观)?(?:缺陷|裂缝|病害|检测|识别|分割|分类|诊断))", text)
        if m:
            obj.append(m.group(1))
    if not obj:
        # 退化: 取整句作为对象
        obj.append(text)

    # 生成中英检索词
    method_zh = " ".join(method) if method else ""
    obj_zh = obj[0] if obj else text
    task_zh = task[0] if task else "检测"
    query_zh = [f"{method_zh} {obj_zh} {task_zh}".strip()]
    query_zh = [q for q in query_zh if q.strip()]

    method_en = method[0].lower() if method else "deep learning"
    obj_en_map = {
        "钢材": "steel surface", "带钢": "steel strip", "钢板": "steel plate",
        "桥梁": "bridge", "道路": "road", "混凝土": "concrete",
        "叶片": "blade", "绝缘子": "insulator", "输电线路": "transmission line",
        "PCB": "PCB", "电路板": "PCB", "焊缝": "weld",
        "行人": "pedestrian", "车辆": "vehicle",
        "皮肤": "skin", "眼底": "fundus", "肺结节": "lung nodule",
        "CT 影像": "CT", "MRI 影像": "MRI", "X 光影像": "X-ray",
    }
    obj_en = next((v for k, v in obj_en_map.items() if k in obj_zh), obj_zh)
    task_en = "defect detection" if "检测" in task_zh or "缺陷" in obj_zh else (
        "classification" if "分类" in task_zh else (
        "segmentation" if "分割" in task_zh else "recognition"))
    query_en = [f"{method_en} {obj_en} {task_en}".strip()]

    return KeywordBreakdown(
        method_keywords=method,
        task_keywords=task,
        object_keywords=obj,
        scenario_keywords=scenario,
        metric_keywords=metric,
        risk_terms=risk,
        query_keywords_zh=query_zh,
        query_keywords_en=query_en,
    )


def _llm_breakdown(raw: str) -> KeywordBreakdown:
    """LLM 路径: 让 M3 直接输出 KeywordBreakdown JSON."""

    prompt = (
        "你是中国研究生开题选题助手。给定一个选题, 输出一份 JSON, 严格按下面 schema, "
        "不要解释、不要 markdown 包裹:\n"
        "{\n"
        '  "method_keywords": ["方法词 (YOLO / Transformer / 注意力机制)"],\n'
        '  "task_keywords": ["任务词 (检测 / 分类 / 分割)"],\n'
        '  "object_keywords": ["研究对象 (钢材表面缺陷 / 桥梁裂缝)"],\n'
        '  "scenario_keywords": ["应用场景 (工业质检 / 智能巡检)"],\n'
        '  "metric_keywords": ["评价指标 (mAP / Recall / FPS)"],\n'
        '  "risk_terms": ["原题里的高风险词 (智能 / 高精度 / 实时)"]\n'
        "}\n"
        f"选题: {raw}"
    )
    data = llm.chat_json(prompt, system="你是开题选题拆解助手, 严格输出 JSON dict", max_tokens=800)
    return KeywordBreakdown(
        method_keywords=list(data.get("method_keywords") or []),
        task_keywords=list(data.get("task_keywords") or []),
        object_keywords=list(data.get("object_keywords") or []),
        scenario_keywords=list(data.get("scenario_keywords") or []),
        metric_keywords=list(data.get("metric_keywords") or []),
        risk_terms=list(data.get("risk_terms") or []),
        query_keywords_zh=[],
        query_keywords_en=[],
    )


def breakdown_keywords(raw: str, prefer: str) -> KeywordBreakdown:
    if prefer == "heuristic":
        return _heuristic_breakdown(raw)
    try:
        bd = _llm_breakdown(raw)
        # 即使 LLM 成功, 兜底用启发式补全中英检索词
        h = _heuristic_breakdown(raw)
        bd.query_keywords_zh = h.query_keywords_zh
        bd.query_keywords_en = h.query_keywords_en
        return bd
    except llm.LLMUnavailable as exc:
        logger.info("LLM 拆解失败, fallback heuristic: %s", exc)
        return _heuristic_breakdown(raw)


# ---------- 题目理解 ---------- #


def understand_topic(req: OneTopicRequest, keywords: KeywordBreakdown) -> TopicUnderstanding:
    raw = req.raw_topic.strip()
    normalized = _normalize_topic(raw)
    is_specific = _has_specific_object(keywords.object_keywords, raw)
    method = keywords.method_keywords[0] if keywords.method_keywords else "深度学习"
    obj = keywords.object_keywords[0] if keywords.object_keywords else raw
    task = keywords.task_keywords[0] if keywords.task_keywords else "目标检测"
    intent = f"该题目希望使用 {method} 方法, 对「{obj}」进行 {task}, 属于{req.goal_level}路线。"
    if not is_specific:
        intent += " 题目里的研究对象偏抽象, 建议在 Phase 02 补问."
    return TopicUnderstanding(
        raw_topic=raw,
        normalized_topic=normalized,
        intent_zh=intent,
        is_specific_object=is_specific,
    )


# ---------- 检索计划 ---------- #


def build_search_plan(keywords: KeywordBreakdown) -> SearchPlan:
    """三线检索词: 论文 / 数据集 / 工程."""

    obj_zh = keywords.object_keywords[0] if keywords.object_keywords else ""
    method_zh = keywords.method_keywords[0] if keywords.method_keywords else ""
    task_zh = keywords.task_keywords[0] if keywords.task_keywords else "检测"
    obj_en = ""
    method_en = (keywords.method_keywords[0] if keywords.method_keywords else "").lower()

    # 中英对象映射 (复用 _heuristic_breakdown 的逻辑)
    en_map = {
        "钢材": "steel surface", "带钢": "steel strip", "钢板": "steel plate",
        "桥梁": "bridge", "道路": "road", "混凝土": "concrete",
        "叶片": "blade", "绝缘子": "insulator",
        "PCB": "PCB", "焊缝": "weld", "行人": "pedestrian",
        "皮肤": "skin", "眼底": "fundus", "肺结节": "lung nodule",
    }
    for k, v in en_map.items():
        if k in obj_zh:
            obj_en = v
            break
    if not obj_en and obj_zh:
        obj_en = obj_zh

    # 论文线 (中英)
    paper_zh = [
        f"{method_zh} {obj_zh} {task_zh}".strip(),
        f"{obj_zh} {task_zh} 综述",
    ]
    paper_en = [
        f"{method_en} {obj_en} {task_zh}".strip(),
        f"{obj_en} {task_zh} survey",
        f"{method_en} {obj_en} benchmark".strip(),
    ]

    # 数据集线
    dataset_zh = [
        f"{obj_zh} 数据集",
        f"{obj_zh} 公开数据集",
    ]
    dataset_en = [
        f"{obj_en} dataset",
        f"{obj_en} benchmark dataset",
    ]
    if "steel" in obj_en or "带钢" in obj_zh or "钢材" in obj_zh:
        dataset_en += ["NEU-DET steel surface defect", "GC10-DET dataset"]
    if "PCB" in obj_en or "电路板" in obj_zh:
        dataset_en += ["PCB defect dataset DeepPCB"]
    if "bridge" in obj_en or "桥梁" in obj_zh:
        dataset_en += ["bridge crack dataset CODEBRIM"]
    if "skin" in obj_en or "皮肤" in obj_zh:
        dataset_en += ["ISIC skin lesion dataset", "HAM10000"]

    # 工程线
    eng_zh = [
        f"{method_zh} {obj_zh} GitHub",
    ]
    eng_en = [
        f"{method_en} {obj_en} github",
        "ultralytics yolov8 defect detection",
    ]

    plan = SearchPlan(
        paper_queries=[q for q in paper_zh + paper_en if q.strip()],
        dataset_queries=[q for q in dataset_zh + dataset_en if q.strip()],
        engineering_queries=[q for q in eng_zh + eng_en if q.strip()],
    )
    plan.query_total = len(plan.paper_queries) + len(plan.dataset_queries) + len(plan.engineering_queries)
    return plan


# ---------- 证据采集 ---------- #


def _heuristic_papers(keywords: KeywordBreakdown) -> list[PaperHit]:
    """无 arXiv 时给 2-3 篇占位论文 (不让服务挂掉)."""

    obj = keywords.object_keywords[0] if keywords.object_keywords else "目标对象"
    method = keywords.method_keywords[0] if keywords.method_keywords else "深度学习"
    return [
        PaperHit(
            paper_id="H001",
            title=f"基于 {method} 的 {obj} 检测综述 (启发式占位)",
            year=2023,
            source="heuristic",
            summary=f"启发式生成的占位论文, 真实 arXiv 检索见真实卡片.",
            summary_zh=f"该文综述了 {method} 在 {obj} 上的方法 (启发式占位).",
        ),
        PaperHit(
            paper_id="H002",
            title=f"A Survey on {obj} Detection (heuristic placeholder)",
            year=2022,
            source="heuristic",
            summary="Heuristic placeholder paper. Real arXiv cards will replace this when network is available.",
            summary_zh=f"启发式占位: {obj} 综述.",
        ),
    ]


def _heuristic_datasets(keywords: KeywordBreakdown) -> list[DatasetHit]:
    obj = keywords.object_keywords[0] if keywords.object_keywords else ""
    datasets: list[DatasetHit] = []
    if any(k in obj for k in ("钢", "带钢", "钢板")):
        datasets += [
            DatasetHit(dataset_id="DS01", name="NEU-DET", scale="1800 张 / 6 类缺陷",
                       license="学术使用", download="http://faculty.neu.edu.cn/songkechen/zh_CN/zdylm/263270/list/index.htm",
                       fit="高", source="public-known"),
            DatasetHit(dataset_id="DS02", name="GC10-DET", scale="3570 张 / 10 类",
                       license="学术使用", download="https://github.com/lvxiaoming2019/GC10-DET",
                       fit="高", source="public-known"),
        ]
    if "PCB" in obj or "电路板" in obj:
        datasets.append(DatasetHit(
            dataset_id="DS01", name="DeepPCB", scale="1500 张 / 6 类",
            license="MIT", download="https://github.com/tangsanli/DeepPCB",
            fit="高", source="public-known",
        ))
    if "桥" in obj or "桥梁" in obj:
        datasets.append(DatasetHit(
            dataset_id="DS01", name="CODEBRIM", scale="7700 张 / 6 类",
            license="学术使用", download="https://github.com/tody411/CODEBRIM",
            fit="高", source="public-known",
        ))
    if "皮肤" in obj:
        datasets += [
            DatasetHit(dataset_id="DS01", name="HAM10000", scale="10015 张 / 7 类",
                       license="CC BY-NC", download="https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/DBW86T",
                       fit="高", source="public-known"),
            DatasetHit(dataset_id="DS02", name="ISIC Archive", scale="70000+ 张",
                       license="CC BY-NC", download="https://www.isic-archive.com",
                       fit="中", source="public-known"),
        ]
    if not datasets:
        # 兜底: 给 1 个占位, 标记低契合
        datasets.append(DatasetHit(
            dataset_id="DS99", name="(未匹配公开数据集)",
            scale="未知", license="未知", download=None,
            fit="低", source="heuristic",
        ))
    return datasets


def _heuristic_baselines(keywords: KeywordBreakdown) -> list[BaselineHit]:
    method = (keywords.method_keywords[0] or "").lower() if keywords.method_keywords else ""
    if "yolo" in method:
        return [
            BaselineHit(baseline_id="BL01", name="YOLOv8 (Ultralytics 官方)",
                         paper_title="Ultralytics YOLOv8",
                         repository_url="https://github.com/ultralytics/ultralytics",
                         reproduce_difficulty="低", source="github"),
            BaselineHit(baseline_id="BL02", name="YOLOv5 (Ultralytics 官方)",
                         paper_title="YOLOv5 by Ultralytics",
                         repository_url="https://github.com/ultralytics/yolov5",
                         reproduce_difficulty="低", source="github"),
        ]
    if "transformer" in method or "vit" in method:
        return [
            BaselineHit(baseline_id="BL01", name="Swin Transformer",
                         paper_title="Swin Transformer: Hierarchical Vision Transformer using Shifted Windows",
                         repository_url="https://github.com/microsoft/Swin-Transformer",
                         reproduce_difficulty="中", source="github"),
        ]
    if "bert" in method or "llm" in method or "gpt" in method:
        return [
            BaselineHit(baseline_id="BL01", name="BERT (HuggingFace)",
                         paper_title="BERT: Pre-training of Deep Bidirectional Transformers",
                         repository_url="https://github.com/google-research/bert",
                         reproduce_difficulty="中", source="github"),
        ]
    # 兜底
    return [
        BaselineHit(baseline_id="BL99", name="ResNet-50 (torchvision)",
                     paper_title="Deep Residual Learning for Image Recognition",
                     repository_url="https://github.com/pytorch/vision",
                     reproduce_difficulty="低", source="github"),
    ]


def collect_evidence(
    keywords: KeywordBreakdown,
    plan: SearchPlan,
    prefer: str,
) -> EvidenceSummary:
    """调 arXiv 真检索 (失败 → 启发式占位)."""

    # 1) 论文: arXiv 真检索
    papers: list[PaperHit] = []
    arxiv_hits: list[arxiv_client.ArxivPaper] = []
    try:
        arxiv_hits = arxiv_client.search_arxiv(plan.paper_queries, max_per_query=2, max_total=6)
    except Exception as exc:  # noqa: BLE001
        logger.warning("arxiv 检索异常: %s", exc)

    if arxiv_hits:
        for p in arxiv_hits:
            papers.append(PaperHit(
                paper_id=p.arxiv_id,
                title=p.title,
                authors=p.authors,
                year=p.year or None,
                url=p.abs_url,
                summary=p.summary,
                summary_zh=arxiv_client.summarize_paper_zh(p.title, p.summary),
                source="arXiv",
            ))
    else:
        papers = _heuristic_papers(keywords)

    # 2) 数据集: 启发式词典 (不调 LLM, 稳定)
    datasets = _heuristic_datasets(keywords)

    # 3) Baseline: 启发式
    baselines = _heuristic_baselines(keywords)

    # 4) 指标: 从 keywords 取 + 兜底
    metrics = list(keywords.metric_keywords) or ["mAP", "Recall", "Precision"]

    arxiv_paper_count = sum(1 for p in papers if p.source == "arXiv")
    has_public_dataset = any(d.fit in ("高", "中") and d.dataset_id != "DS99" for d in datasets)
    has_repro = any(b.reproduce_difficulty in ("低", "中") and b.repository_url for b in baselines)
    has_metrics = len(metrics) > 0

    return EvidenceSummary(
        papers=papers,
        datasets=datasets,
        baselines=baselines,
        metrics=metrics,
        paper_count=len(papers),
        arxiv_paper_count=arxiv_paper_count,
        dataset_count=len(datasets),
        baseline_count=len(baselines),
        has_public_dataset=has_public_dataset,
        has_repro_baseline=has_repro,
        has_metrics=has_metrics,
    )


# ---------- 可行性判断 (§7.3) ---------- #


def judge_feasibility(req: OneTopicRequest, keywords: KeywordBreakdown, ev: EvidenceSummary) -> FeasibilitySummary:
    paper_count = ev.arxiv_paper_count or ev.paper_count
    niche = _is_niche_topic(req.raw_topic, keywords)
    missing: list[str] = []

    paper_status = "✓ 有 arXiv 真实论文" if ev.arxiv_paper_count >= 3 else (
        "⚠ 论文偏少 (< 3 篇)" if ev.arxiv_paper_count > 0 else "✗ 无 arXiv 真实论文 (启发式占位)")
    dataset_status = "✓ 有公开数据集" if ev.has_public_dataset else "✗ 未匹配到公开数据集"
    baseline_status = "✓ 有可复现 baseline" if ev.has_repro_baseline else "⚠ baseline 复现难度未知"
    engineering_status = ("✓ 有 GitHub 工程" if any(b.repository_url for b in ev.baselines)
                          else "⚠ 未确认 GitHub 工程")

    if not ev.has_public_dataset:
        missing.append("缺少明确公开数据集 (需补问)")
    if not ev.has_repro_baseline:
        missing.append("缺少可复现 baseline (复现成本未知)")
    if paper_count < 3:
        missing.append("论文偏少 (方向成熟度未确认)")
    if niche:
        missing.append("题目研究对象极小众, 公开数据几乎不存在")

    # 决策 (SOP §9.4 5 档: GO/NARROW/PIVOT/PARK/STOP)
    if niche and not ev.has_public_dataset:
        verdict: Literal["可做", "收缩后可做", "可转向", "暂缓", "不建议"] = "暂缓"
        reason = "题目对象极小众, 公开数据集几乎不存在, 建议收缩到成熟对象 (钢材/PCB/桥梁等) 或加自采数据."
    elif not ev.has_public_dataset and not ev.has_repro_baseline:
        verdict = "不建议"
        reason = "缺少公开数据集和可复现 baseline, 当前阶段不建议开题."
    elif not ev.has_public_dataset or not ev.has_repro_baseline:
        verdict = "可转向"
        reason = "原题方向可行, 但当前路线证据不足, 建议转向相邻成熟方向 (如钢材→带钢/PCB 等已稳定开源数据集场景)."
    elif paper_count >= 3 and ev.has_metrics:
        verdict = "可做"
        reason = "论文 + 数据集 + baseline + 指标都齐备, 可进入开题报告推荐."
    else:
        verdict = "收缩后可做"
        reason = "基础齐备, 建议收缩题目边界以降低风险."

    if verdict == "可做":
        next_action = "进入开题报告骨架 + 工作包推荐."
    elif verdict == "收缩后可做":
        next_action = "优先确认数据集与 baseline 名称, 再收缩题目边界."
    elif verdict == "可转向":
        next_action = "看 3 条退化路线 (保守/平衡/激进), 用户选一条后生成对应工作包."
    elif verdict == "暂缓":
        next_action = "改换研究对象到成熟方向, 或启动自采数据计划."
    else:
        next_action = "重新选择方向, 当前题目不建议开题."

    return FeasibilitySummary(
        verdict=verdict,
        reason=reason,
        paper_status=paper_status,
        dataset_status=dataset_status,
        baseline_status=baseline_status,
        engineering_status=engineering_status,
        missing_evidence=missing,
        recommended_next_action=next_action,
    )


# ---------- 退化路线 (§10) ---------- #


def generate_pivot_routes(
    req: OneTopicRequest, keywords: KeywordBreakdown, ev: EvidenceSummary, feas: FeasibilitySummary,
) -> list[PivotRoute]:
    """SOP §10.3 三条路线 (保守/平衡/激进).

    只在 verdict=可转向 / 收缩后可做 时有意义 (其他 verdict 给 0/1 条).
    路线 = 不同 aggressiveness 的题目收缩 + 工作包调整.
    """

    method = keywords.method_keywords[0] if keywords.method_keywords else "深度学习方法"
    obj = keywords.object_keywords[0] if keywords.object_keywords else "目标对象"
    task = keywords.task_keywords[0] if keywords.task_keywords else "目标检测"

    if feas.verdict not in ("可转向", "收缩后可做"):
        return []

    removed = list(keywords.risk_terms or [])
    preserved = [k for k in (keywords.method_keywords + keywords.task_keywords) if k]

    # 保守: 用最稳的成熟对象 (YOLO + 钢材), 公开数据集, 创新轻
    cons = PivotRoute(
        level="conservative",
        new_topic=f"基于 {method} 的钢材表面缺陷检测方法研究",
        preserved_keywords=preserved + ["钢材表面缺陷"],
        removed_keywords=removed + ["多模态", "高精度", "实时"],
        tradeoff="去掉多模态 / 实时, 限定到钢材+检测. 创新空间小但风险最低, 容易出第一张结果表.",
        work_packages=[
            WorkPackageSuggestion(
                wp_id="WP1",
                title=f"基于公开数据集复现 {method} baseline",
                research_question=f"{method} 在钢材表面缺陷数据上的 baseline 性能如何?",
                method_approach=f"采用 {method} 官方实现, 在 NEU-DET/GC10-DET 上训练.",
                data_source="NEU-DET / GC10-DET",
                experiment_plan="按标准 split 训练, 报告 mAP / Recall / FPS.",
                chapter="第三章",
            ),
            WorkPackageSuggestion(
                wp_id="WP2",
                title="轻量模块改进 + 消融实验",
                research_question="轻量 backbone / 注意力模块能否在 baseline 之上提升精度?",
                method_approach="在主干插入轻量化模块, 其他超参保持一致.",
                data_source="同 WP1",
                experiment_plan="消融实验: baseline vs baseline+模块; 多组指标对比.",
                chapter="第四章",
            ),
        ],
    )

    # 平衡: 用原始对象, 公开数据集 + 少量自采, 轻量模块
    bal = PivotRoute(
        level="balanced",
        new_topic=feas.reason and (keywords.object_keywords[0] if keywords.object_keywords else obj) + f" {task} 方法研究",
        preserved_keywords=preserved + (keywords.object_keywords[:1] if keywords.object_keywords else [obj]),
        removed_keywords=[r for r in removed if r not in ["高精度", "实时"]],
        tradeoff="保留原始对象, 用公开数据集 + 自采小规模验证. 创新适中, 风险适中.",
        work_packages=[
            WorkPackageSuggestion(
                wp_id="WP1",
                title=f"公开数据集上复现 {method} baseline + 自采小规模验证",
                research_question="原始对象上的 baseline 表现 + 自采数据上的迁移能力?",
                method_approach=f"{method} 标准实现 + 自采 100-200 张作 domain adaptation.",
                data_source="公开数据集 + 自采小批量",
                experiment_plan="baseline 在公开集 + 自采集分别报告, 给出迁移 gap.",
                chapter="第三章",
            ),
            WorkPackageSuggestion(
                wp_id="WP2",
                title="针对原始对象的轻量改进 + 跨域消融",
                research_question="模块改进在原始对象上的增量是多少?",
                method_approach="针对原始对象特性 (光照/尺度/类别分布) 设计模块.",
                data_source="同 WP1",
                experiment_plan="消融 + 跨域对比.",
                chapter="第四章",
            ),
        ],
    )

    # 激进: 保留原对象 + 多模态/3D, 加自采大数据, 创新强
    agg = PivotRoute(
        level="aggressive",
        new_topic=f"基于 {method} + 多模态的 {obj} {task} 新方法",
        preserved_keywords=preserved + (keywords.object_keywords[:1] if keywords.object_keywords else [obj]) + ["多模态"],
        removed_keywords=[],
        tradeoff="保留所有原题要素 + 多模态, 必须自采大规模数据. 创新强, 风险高, 时间成本大.",
        work_packages=[
            WorkPackageSuggestion(
                wp_id="WP1",
                title="自采多模态数据采集与标注",
                research_question="如何构建 {obj} 的多模态数据集?",
                method_approach="RGB-D / 红外-可见光双模态自采 + 标注流程设计.",
                data_source="自采 1000+ 张多模态数据",
                experiment_plan="数据采集方案 + 标注一致性 + 数据集统计.",
                chapter="第三章",
            ),
            WorkPackageSuggestion(
                wp_id="WP2",
                title="多模态融合方法设计 + 跨模态消融",
                research_question="多模态融合在 {obj} 上的增益?",
                method_approach="跨模态特征对齐 + 决策融合.",
                data_source="自采多模态数据",
                experiment_plan="单模态 vs 融合 消融; 不同融合策略对比.",
                chapter="第四章",
            ),
        ],
    )

    return [cons, bal, agg]


# ---------- 开题建议 (§8) ---------- #


def recommend_proposal(
    req: OneTopicRequest, keywords: KeywordBreakdown, ev: EvidenceSummary, feas: FeasibilitySummary,
) -> ProposalRecommendation:
    method = keywords.method_keywords[0] if keywords.method_keywords else "深度学习方法"
    obj = keywords.object_keywords[0] if keywords.object_keywords else "目标对象"
    task = keywords.task_keywords[0] if keywords.task_keywords else "目标检测"
    metric = ev.metrics[0] if ev.metrics else "mAP"

    recommended = f"基于 {method} 的 {obj} {task} 方法研究"

    reasons = []
    if ev.arxiv_paper_count >= 3:
        reasons.append(f"arXiv 真实论文 {ev.arxiv_paper_count} 篇, 方向成熟度有保障.")
    if ev.has_public_dataset:
        reasons.append("有公开数据集可用, 复现成本低.")
    if ev.has_repro_baseline:
        reasons.append("有可复现 baseline (GitHub 工程), 起步快.")
    if ev.has_metrics:
        reasons.append(f"评价指标 ({', '.join(ev.metrics[:3])}) 可量化, 容易出第一张结果表.")
    if not reasons:
        reasons.append("已根据启发式给出基本建议, 仍需补充证据.")

    # 工作包
    wp1 = WorkPackageSuggestion(
        wp_id="WP1",
        title=f"基于公开数据集复现 {method} baseline",
        research_question=f"{method} 在 {obj} 上的标准 baseline 表现如何?",
        method_approach=f"采用 {method} 标准实现, 在公开数据集上训练/验证.",
        data_source=(ev.datasets[0].name if ev.datasets and ev.datasets[0].dataset_id != "DS99" else "待确认公开数据集"),
        experiment_plan=f"按标准 split 训练, 报告 {', '.join(ev.metrics[:3])} 等指标.",
        chapter="第三章",
    )
    wp2_method = "轻量化模块" if "yolo" in method.lower() else "注意力机制"
    wp2 = WorkPackageSuggestion(
        wp_id="WP2",
        title=f"引入 {wp2_method} 并进行消融实验",
        research_question=f"在 baseline 基础上加入 {wp2_method} 是否能进一步提升 {metric}?",
        method_approach=f"在 {method} 主干中插入 {wp2_method} 模块, 保持其他超参一致.",
        data_source="同 WP1 公开数据集",
        experiment_plan=f"消融实验: 关闭 vs 开启 {wp2_method}; 多组 {metric} 对比.",
        chapter="第四章",
    )

    outline = [
        "1. 研究背景与意义",
        "2. 国内外研究现状 (基于检索到的 arXiv 论文综述)",
        "3. 研究内容与目标 (WP1 + WP2)",
        "4. 技术路线 (baseline → 改进 → 消融)",
        "5. 实验方案 (数据集 / 评价指标 / baseline 对比)",
        "6. 预期创新点",
        "7. 进度计划",
        "8. 风险预案",
    ]

    pivot_routes = generate_pivot_routes(req, keywords, ev, feas)

    return ProposalRecommendation(
        recommended_topic=recommended,
        recommendation_reason=reasons,
        work_packages=[wp1, wp2],
        proposal_outline=outline,
        pivot_routes=pivot_routes,
    )


# ---------- 选 pivot (§10.4) ---------- #


def apply_pivot_route(route: PivotRoute, keywords: KeywordBreakdown, ev: EvidenceSummary) -> ProposalRecommendation:
    """用户选了 1 条路线后, 用该路线生成对应工作包 + 建议."""

    method = keywords.method_keywords[0] if keywords.method_keywords else "深度学习方法"
    obj = keywords.object_keywords[0] if keywords.object_keywords else "目标对象"
    task = keywords.task_keywords[0] if keywords.task_keywords else "目标检测"
    metric = ev.metrics[0] if ev.metrics else "mAP"

    reasons = [
        f"按 {route.level} 路线收缩题目.",
        f"保留关键词: {', '.join(route.preserved_keywords) or '(无)'}",
        f"去掉关键词: {', '.join(route.removed_keywords) or '(无)'}",
        route.tradeoff,
    ]

    outline = [
        "1. 研究背景与意义",
        f"2. 国内外研究现状 ({len(ev.papers)} 篇论文, {len(evidence_status(ev))} 个数据集)",
        f"3. 研究内容与目标 ({len(route.work_packages)} 个工作包)",
        "4. 技术路线",
        "5. 实验方案 (数据集 / 评价指标 / baseline 对比)",
        "6. 预期创新点",
        "7. 进度计划",
        "8. 风险预案",
    ]

    return ProposalRecommendation(
        recommended_topic=route.new_topic,
        recommendation_reason=reasons,
        work_packages=route.work_packages,
        proposal_outline=outline,
        pivot_routes=[route],
    )


def evidence_status(ev: EvidenceSummary) -> list[str]:
    """helper for apply_pivot_route outline."""

    return [d.name or d.dataset_id for d in ev.datasets]


# ---------- 低门槛审核 (§9) ---------- #


def light_review(
    req: OneTopicRequest, keywords: KeywordBreakdown, ev: EvidenceSummary, feas: FeasibilitySummary,
) -> LightReview:
    checks: list[ReviewCheck] = []

    # 1. 题目边界
    boundary_ok = bool(keywords.object_keywords) and bool(keywords.task_keywords)
    checks.append(ReviewCheck(
        dimension="题目边界",
        result="通过" if boundary_ok else "需补充",
        comment=("研究对象与任务明确." if boundary_ok else
                 "题目里研究对象或任务不够具体, 建议在 Phase 02 补问."),
    ))

    # 2. 数据集
    checks.append(ReviewCheck(
        dimension="数据集",
        result="通过" if ev.has_public_dataset else "需补充",
        comment=("已匹配到公开数据集." if ev.has_public_dataset else
                 "需要明确使用哪个公开数据集 (NEU-DET / DeepPCB / ...)."),
    ))

    # 3. Baseline
    checks.append(ReviewCheck(
        dimension="Baseline",
        result="通过" if ev.has_repro_baseline else "需补充",
        comment=("YOLO/主流 baseline 工程成熟." if ev.has_repro_baseline else
                 "需要确认 baseline 复现路径和成本."),
    ))

    # 4. 工作量 (用 method 数量 + risk 词数量 启发式)
    risk_count = len(keywords.risk_terms)
    workload_ok = risk_count <= 2
    checks.append(ReviewCheck(
        dimension="工作量",
        result="通过" if workload_ok else "需补充",
        comment=(f"可拆成 2 个工作包, 风险词 {risk_count} 个 ({'在' if workload_ok else '超出'}安全范围)."),
    ))

    # 5. 开题表达
    expr_ok = bool(keywords.method_keywords) and bool(keywords.metric_keywords)
    checks.append(ReviewCheck(
        dimension="开题表达",
        result="通过" if expr_ok else "需补充",
        comment=("方法词 + 评价指标可量化, 容易讲清楚." if expr_ok else
                 "需补充方法词 (用什么) 与评价指标 (怎么评价)."),
    ))

    # 总体结论
    if feas.verdict == "可做":
        verdict: Literal["通过", "有条件通过", "需修改", "不建议"] = "通过"
        summary = "题目方向可行, 证据齐备, 可进入开题报告."
    elif feas.verdict == "收缩后可做":
        verdict = "有条件通过"
        summary = "题目方向可行, 但需要先确认数据集 / baseline 名称, 然后收缩边界."
    elif feas.verdict == "暂缓":
        verdict = "需修改"
        summary = "题目方向暂缓, 建议改换研究对象或先补充自采数据计划."
    else:
        verdict = "不建议"
        summary = "当前题目不建议开题, 建议重新选择方向."

    # 修改清单
    revisions: list[str] = []
    for c in checks:
        if c.result in ("需补充", "有条件通过", "不通过"):
            revisions.append(f"[{c.dimension}] {c.comment}")
    if not revisions:
        revisions.append("无明显修改项, 可进入开题报告生成阶段.")

    return LightReview(
        verdict=verdict,
        summary=summary,
        checks=checks,
        revision_checklist=revisions,
    )


# ---------- 编排主入口 ---------- #


def _coerce_keywords(d: dict | None) -> KeywordBreakdown | None:
    """用户编辑过的 keywords 转为 KeywordBreakdown (Session 3 Gate 1)."""

    if not d:
        return None
    try:
        return KeywordBreakdown.model_validate(d)
    except Exception:
        return None


def _coerce_search_plan(d: dict | None) -> SearchPlan | None:
    """用户编辑过的 search_plan 转为 SearchPlan (Session 3 Gate 2)."""

    if not d:
        return None
    try:
        return SearchPlan.model_validate(d)
    except Exception:
        return None


def run_one_topic(req: OneTopicRequest) -> OneTopicResponse:
    t0 = time.time()
    keywords = _coerce_keywords(req.confirmed_keywords) or breakdown_keywords(req.raw_topic, req.prefer)
    topic = understand_topic(req, keywords)
    plan = _coerce_search_plan(req.confirmed_search_plan) or build_search_plan(keywords)
    ev = collect_evidence(keywords, plan, req.prefer)
    feas = judge_feasibility(req, keywords, ev)
    rec = recommend_proposal(req, keywords, ev, feas)
    rev = light_review(req, keywords, ev, feas)
    elapsed_ms = int((time.time() - t0) * 1000)
    project_id = req.project_id_override or ("ot_" + uuid.uuid4().hex[:12])
    # Auto-ingest into the per-project ledger (SOP 5 + 13.1).
    try:
        ev_store.ingest_auto_evidence(project_id, ev)
    except Exception:  # noqa: BLE001
        pass

    return OneTopicResponse(
        project_id=project_id,
        request=req,
        topic_understanding=topic,
        keyword_breakdown=keywords,
        search_plan=plan,
        evidence_summary=ev,
        feasibility=feas,
        proposal_recommendation=rec,
        light_review=rev,
        elapsed_ms=elapsed_ms,
    )


# ---------- 流式 (SSE) ---------- #


def run_one_topic_stream(
    req: OneTopicRequest,
    emit: Callable[[str, str, dict[str, Any] | None], None],
) -> None:
    """SSE emit 包装. emit(name, detail, meta). 走完业务后 emit('result', ...) 上传数据."""

    emit("start", "OneTopic MVP 启动", {"raw_topic": req.raw_topic})

    # Session 3 Gate 1+2: 如果用户已经确认过 keywords/plan, 直接用, 跳过自动拆解
    confirmed_kw = _coerce_keywords(req.confirmed_keywords)
    confirmed_plan = _coerce_search_plan(req.confirmed_search_plan)
    if confirmed_kw and confirmed_plan:
        emit("step", "✅ 使用用户确认的关键词 + 检索词 (Gate 1+2 跳过)", {
            "method_keywords": confirmed_kw.method_keywords,
            "plan_total": len(confirmed_plan.paper_queries) + len(confirmed_plan.dataset_queries),
        })
        keywords = confirmed_kw
        plan = confirmed_plan
    else:
        # Step 1: 关键词拆解
        emit("step", "🔍 正在拆出方法词、任务词、对象词", {"phase": "keyword_decompose"})
        keywords = breakdown_keywords(req.raw_topic, req.prefer)
    emit("step", f"✓ 拆出方法词 {len(keywords.method_keywords)} / 任务词 {len(keywords.task_keywords)} / 对象词 {len(keywords.object_keywords)}", {
        "method_keywords": keywords.method_keywords,
        "task_keywords": keywords.task_keywords,
        "object_keywords": keywords.object_keywords,
    })

    # Step 2: 题目理解
    emit("step", "🧠 正在理解题目意图", {"phase": "topic_understanding"})
    topic = understand_topic(req, keywords)
    emit("step", f"✓ 标准化题目 + 中文意图生成", {"normalized_topic": topic.normalized_topic})

    # Step 3: 三线检索计划
    emit("step", "🗺️ 正在生成论文 / 数据集 / 工程三线检索词", {"phase": "search_plan"})
    plan = build_search_plan(keywords)
    emit("step", f"✓ 检索词 {plan.query_total} 条 (论文 {len(plan.paper_queries)} / 数据集 {len(plan.dataset_queries)} / 工程 {len(plan.engineering_queries)})", {
        "query_total": plan.query_total,
    })

    # Step 4: 论文线检索 (arXiv)
    emit("step", "📚 正在搜索相关论文 (arXiv 真实检索)", {"phase": "paper_search"})
    arxiv_papers: list[arxiv_client.ArxivPaper] = []
    try:
        arxiv_papers = arxiv_client.search_arxiv(plan.paper_queries, max_per_query=2, max_total=6)
    except Exception as exc:  # noqa: BLE001
        emit("warn", f"arXiv 检索失败, 用启发式兜底: {exc}", None)
    emit("step", f"✓ 论文命中 {len(arxiv_papers)} 篇 (arXiv 真实)", {"arxiv_count": len(arxiv_papers)})

    # Step 5: 数据集线
    emit("step", "💾 正在搜索公开数据集", {"phase": "dataset_search"})
    datasets = _heuristic_datasets(keywords)
    emit("step", f"✓ 数据集命中 {len(datasets)} 个 (公开词典匹配)", {"dataset_count": len(datasets)})

    # Step 6: 工程线
    emit("step", "🔗 正在检查是否有 GitHub 工程", {"phase": "engineering_search"})
    baselines = _heuristic_baselines(keywords)
    emit("step", f"✓ Baseline 候选 {len(baselines)} 个", {"baseline_count": len(baselines)})

    # 装配 evidence
    papers: list[PaperHit] = []
    for p in arxiv_papers:
        papers.append(PaperHit(
            paper_id=p.arxiv_id, title=p.title, authors=p.authors,
            year=p.year or None, url=p.abs_url, summary=p.summary,
            summary_zh=arxiv_client.summarize_paper_zh(p.title, p.summary),
            source="arXiv",
        ))
    if not papers:
        papers = _heuristic_papers(keywords)
    arxiv_paper_count = sum(1 for p in papers if p.source == "arXiv")
    metrics = list(keywords.metric_keywords) or ["mAP", "Recall", "Precision"]
    ev = EvidenceSummary(
        papers=papers, datasets=datasets, baselines=baselines,
        metrics=metrics, paper_count=len(papers),
        arxiv_paper_count=arxiv_paper_count,
        dataset_count=len(datasets), baseline_count=len(baselines),
        has_public_dataset=any(d.fit in ("高", "中") and d.dataset_id != "DS99" for d in datasets),
        has_repro_baseline=any(b.repository_url for b in baselines),
        has_metrics=bool(metrics),
    )

    # Step 7: 可行性判断
    emit("step", "⚖️ 正在生成可行性判断", {"phase": "feasibility"})
    feas = judge_feasibility(req, keywords, ev)
    emit("step", f"✓ 可行性: {feas.verdict} — {feas.reason[:50]}...", {
        "verdict": feas.verdict,
        "missing_evidence": feas.missing_evidence,
    })

    # Step 8: 开题建议
    emit("step", "📦 正在生成开题建议 + 工作包", {"phase": "proposal_recommendation"})
    rec = recommend_proposal(req, keywords, ev, feas)
    emit("step", f"✓ 推荐题目: {rec.recommended_topic}", {
        "work_package_count": len(rec.work_packages),
    })

    # Step 9: 低门槛审核
    emit("step", "🛡️ 正在跑低门槛模拟审核 (5 维)", {"phase": "light_review"})
    rev = light_review(req, keywords, ev, feas)
    emit("step", f"✓ 审核结论: {rev.verdict}", {
        "verdict": rev.verdict,
        "check_count": len(rev.checks),
    })

    # Final result
    emit("step", "🎁 全部完成, 打包返回", {"phase": "result"})

    project_id = req.project_id_override or ("ot_" + uuid.uuid4().hex[:12])
    try:
        ev_store.ingest_auto_evidence(project_id, ev)
    except Exception:  # noqa: BLE001
        pass
    response = OneTopicResponse(
        project_id=project_id,
        request=req,
        topic_understanding=topic,
        keyword_breakdown=keywords,
        search_plan=plan,
        evidence_summary=ev,
        feasibility=feas,
        proposal_recommendation=rec,
        light_review=rev,
    )
    emit("result", "OneTopic MVP 完成", response.model_dump(mode="json"))
