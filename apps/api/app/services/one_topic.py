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
from . import scoring

logger = logging.getLogger(__name__)


# ---------- 启发式词典 (LLM 失败兜底) ---------- #

_METHOD_HINTS = {
    "yolo": "YOLO", "yolov": "YOLOv8", "transformer": "Transformer",
    "vit": "ViT", "bert": "BERT", "gpt": "GPT", "llm": "LLM",
    "diffusion": "Diffusion", "gan": "GAN", "resnet": "ResNet",
    "cnn": "CNN", "lstm": "LSTM", "gru": "GRU", "mamba": "Mamba",
    "知识图谱": "知识图谱", "图神经网络": "GNN", "gnn": "GNN", "gcn": "GNN", "gat": "GNN", "graph": "GNN",
    "强化学习": "强化学习", "rl": "强化学习", "注意力": "注意力机制", "attention": "注意力机制",
    "轻量化": "轻量化", "蒸馏": "知识蒸馏", "剪枝": "剪枝",
    "多模态": "多模态", "跨模态": "跨模态",
    # Session 5: 数字孪生 / 物理信息 / 扩散 / Mamba / DETR / LoRA / 医学影像
    "pinn": "PINN", "物理信息": "PINN", "物理神经网络": "PINN", "物理感知": "PINN",
    "数字孪生": "数字孪生", "digital twin": "数字孪生", "孪生": "数字孪生",
    "有限元": "有限元", "fem": "有限元", "fea": "有限元", "仿真": "有限元",
    "detr": "DETR", "deit": "DeiT", "dino": "DINO",
    "lora": "LoRA", "peft": "PEFT", "rag": "RAG", "agent": "Agent",
    "扩散模型": "Diffusion", "stable diffusion": "Diffusion", "ddpm": "Diffusion",
    "wgan": "GAN", "cyclegan": "GAN", "stylegan": "GAN",
    "snn": "脉冲神经网络", "脉冲": "脉冲神经网络", "spiking": "脉冲神经网络",
    "neural ode": "Neural ODE", "ode": "Neural ODE", "pde": "PDE",
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
_OBJECT_HINTS_EXT = {  # Session 5: PINN / 数字孪生 / 推荐 / 时序 通用对象
    "机构": "机构", "机械系统": "机械系统", "传动链": "传动链", "传动": "传动",
    "装备": "工业装备", "工业装备": "工业装备", "机械": "机械", "机电": "机电",
    "传感器": "传感器", "振动": "振动信号", "时序": "时序信号", "时间序列": "时序信号",
    "推荐": "推荐系统", "排序": "推荐系统", "item": "推荐系统",
    "医学": "医学影像", "病理": "医学影像", "影像": "医学影像", "ct": "CT 影像", "mri": "MRI 影像",
}
_PUBLIC_DATASET_OBJECTS = {  # Session 5: 路线 nearest-neighbor 用
    "钢材": "NEU-DET", "带钢": "NEU-DET", "钢板": "NEU-DET",
    "电路板": "DeepPCB", "pcb": "DeepPCB", "焊缝": "DeepPCB",
    "桥梁": "CODEBRIM", "裂缝": "CODEBRIM", "道路": "CODEBRIM",
    "皮肤": "HAM10000", "皮肤病": "HAM10000", "病变": "HAM10000",
    "肺结节": "LUNA16", "肺": "LUNA16",
    "车辆": "KITTI", "行人": "CityPersons",
    "细胞": "CellNuclei", "血细胞": "CellNuclei",
    "叶": "PlantDoc", "作物": "PlantDoc", "植物": "PlantDoc", "水果": "FruitVeg",
}
_OBJECT_HINTS = {
    # Session 5 通用对象 (PINN / 数字孪生 / 推荐 / 时序)
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
    # Session 5 PINN 数字孪生 推荐 时序
    "机构": "机械机构", "机械系统": "机械系统", "机械": "机械",
    "传动链": "传动链", "传动": "传动系统", "装备": "工业装备", "工业装备": "工业装备",
    "机电": "机电系统",
    "传感器": "传感器信号", "振动": "振动信号", "时序": "时序信号", "时间序列": "时序信号",
    "推荐": "推荐系统", "排序": "推荐系统", "知识图谱": "知识图谱",
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
            # Session 5: 抽象对象词也算具体 (机构/机械系统/...)
            "机构", "机械", "传动", "装备", "机电", "传感器", "振动", "时序",
            "时间", "推荐", "排序", "知识图谱",
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
    """LLM 路径: 优先用搜索助手 (arXiv 同领域参考) → LLM 拆题.

    Session 6 §13.1: 先调 keyword_search_assistant 拿同领域 3-5 篇高引,
    LLM 参考这些论文写关键词, 不是凭空写. 失败 → 旧 LLM 路径 → 启发式.
    """

    from . import keyword_search_assistant as ks

    # 1) 搜索助手: arXiv 搜同领域 + LLM 参考
    assistant_kw = ks.search_assistant(raw, prefer="auto")

    # 2) 启发式 (兜底, 任何时候都跑, 用来补 query_keywords_zh/en)
    h = _heuristic_breakdown(raw)

    if assistant_kw is not None:
        # 3) 合并 LLM 搜索助手 + 启发式
        merged = ks.merge_with_heuristic(assistant_kw, {
            "method_keywords": h.method_keywords,
            "task_keywords": h.task_keywords,
            "object_keywords": h.object_keywords,
            "scenario_keywords": h.scenario_keywords,
            "metric_keywords": h.metric_keywords,
            "risk_terms": h.risk_terms,
        })
        bd = KeywordBreakdown(
            method_keywords=merged["method_keywords"],
            task_keywords=merged["task_keywords"],
            object_keywords=merged["object_keywords"],
            scenario_keywords=merged["scenario_keywords"],
            metric_keywords=merged["metric_keywords"],
            risk_terms=merged["risk_terms"],
            query_keywords_zh=h.query_keywords_zh,
            query_keywords_en=h.query_keywords_en,
        )
        return bd

    # 4) 旧路径: 直接调 LLM
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
    bd = KeywordBreakdown(
        method_keywords=list(data.get("method_keywords") or []),
        task_keywords=list(data.get("task_keywords") or []),
        object_keywords=list(data.get("object_keywords") or []),
        scenario_keywords=list(data.get("scenario_keywords") or []),
        metric_keywords=list(data.get("metric_keywords") or []),
        risk_terms=list(data.get("risk_terms") or []),
        query_keywords_zh=h.query_keywords_zh,
        query_keywords_en=h.query_keywords_en,
    )
    return bd


def breakdown_keywords(raw: str, prefer: str) -> KeywordBreakdown:
    if prefer == "heuristic":
        return _heuristic_breakdown(raw)
    try:
        return _llm_breakdown(raw)
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
                         license="AGPL-3.0",
                         reproduce_difficulty="低", source="github"),
            BaselineHit(baseline_id="BL02", name="YOLOv5 (Ultralytics 官方)",
                         paper_title="YOLOv5 by Ultralytics",
                         repository_url="https://github.com/ultralytics/yolov5",
                         license="GPL-3.0",
                         reproduce_difficulty="低", source="github"),
        ]
    if "transformer" in method or "vit" in method:
        return [
            BaselineHit(baseline_id="BL01", name="Swin Transformer",
                         paper_title="Swin Transformer: Hierarchical Vision Transformer using Shifted Windows",
                         repository_url="https://github.com/microsoft/Swin-Transformer",
                         reproduce_difficulty="中", source="github"),
        ]
    if "bert" in method or "llm" in method or "gpt" in method or "rag" in method or "agent" in method:
        return [
            BaselineHit(baseline_id="BL01", name="BERT (HuggingFace)",
                         paper_title="BERT: Pre-training of Deep Bidirectional Transformers",
                         repository_url="https://github.com/google-research/bert",
                         reproduce_difficulty="中", source="github"),
            BaselineHit(baseline_id="BL02", name="HuggingFace Transformers",
                         paper_title="State-of-the-art Natural Language Processing",
                         repository_url="https://github.com/huggingface/transformers",
                         reproduce_difficulty="中", source="github"),
        ]
    # Session 5: PINN / 数字孪生 / 物理
    if "pinn" in method or "物理信息" in method or "物理神经网络" in method or "数字孪生" in method or "digital twin" in method:
        return [
            BaselineHit(baseline_id="BL01", name="DeepXDE (PINN 求解器)",
                         paper_title="DeepXDE: A Deep Learning Library for Solving Differential Equations",
                         repository_url="https://github.com/lululxvi/deepxde",
                         reproduce_difficulty="中", source="github"),
            BaselineHit(baseline_id="BL02", name="NVIDIA Modulus (Physics-ML)",
                         paper_title="NVIDIA Modulus: A Framework for Physics-ML",
                         repository_url="https://github.com/NVIDIA/modulus",
                         reproduce_difficulty="高", source="github"),
        ]
    # Session 5: 扩散模型
    if "diffusion" in method or "扩散" in method:
        return [
            BaselineHit(baseline_id="BL01", name="Stable Diffusion (diffusers)",
                         paper_title="High-Resolution Image Synthesis with Latent Diffusion Models",
                         repository_url="https://github.com/huggingface/diffusers",
                         reproduce_difficulty="中", source="github"),
            BaselineHit(baseline_id="BL02", name="DDPM (lucidrains)",
                         paper_title="Denoising Diffusion Probabilistic Models",
                         repository_url="https://github.com/lucidrains/denoising-diffusion-pytorch",
                         reproduce_difficulty="中", source="github"),
        ]
    # Session 5: GNN / GCN / GAT
    if "gnn" in method or "gcn" in method or "gat" in method or "图神经" in method or "知识图谱" in method:
        return [
            BaselineHit(baseline_id="BL01", name="PyTorch Geometric (PyG)",
                         paper_title="Fast Graph Representation Learning with PyTorch Geometric",
                         repository_url="https://github.com/pyg-team/pytorch_geometric",
                         reproduce_difficulty="中", source="github"),
            BaselineHit(baseline_id="BL02", name="DGL (Deep Graph Library)",
                         paper_title="Deep Graph Library",
                         repository_url="https://github.com/dmlc/dgl",
                         reproduce_difficulty="中", source="github"),
        ]
    # Session 5: GAN
    if "gan" in method:
        return [
            BaselineHit(baseline_id="BL01", name="PyTorch GAN Zoo",
                         paper_title="A PyTorch GAN Zoo",
                         repository_url="https://github.com/facebookresearch/pytorch_GAN_zoo",
                         reproduce_difficulty="中", source="github"),
        ]
    # Session 5: Mamba (状态空间模型)
    if "mamba" in method:
        return [
            BaselineHit(baseline_id="BL01", name="Mamba (state-spaces)",
                         paper_title="Mamba: Linear-Time Sequence Modeling with Selective State Spaces",
                         repository_url="https://github.com/state-spaces/mamba",
                         reproduce_difficulty="高", source="github"),
        ]
    # Session 5: 强化学习 / RL
    if "强化学习" in method or "rl" in method:
        return [
            BaselineHit(baseline_id="BL01", name="Stable-Baselines3",
                         paper_title="Stable-Baselines3: Reliable Reinforcement Learning Implementations",
                         repository_url="https://github.com/DLR-RM/stable-baselines3",
                         reproduce_difficulty="中", source="github"),
        ]
    # 兜底: 不再硬编码 ResNet, 给个通用"请补充"占位 (并把 reproduce_difficulty 标 未知)
    return [
        BaselineHit(baseline_id="BL99", name="(未匹配通用 baseline, 请手动补)",
                     paper_title=None,
                     repository_url=None,
                     reproduce_difficulty="未知", source="heuristic"),
    ]


# ---------- LLM rerank arxiv (Session 6 §2 症状 3 根治) ---------- #


_RERANK_PROMPT = """你是科研选题相关性评估助手. 给定一个**用户开题题目**和 N 篇 arXiv 命中论文, 对每篇打 0-1 的相关性分数.

**用户题目**: {raw_topic}
**题目关键词**: {keywords_block}

**arXiv 命中 (按原顺序编号, 1-based)**:
{papers_block}

**严格输出 JSON 数组** (无 markdown fence, 无解释), 长度等于 arXiv 命中数, 每项是 0-1 浮点 (≥ 0.8 强相关, 0.5-0.8 一般, 0.3-0.5 弱, < 0.3 无关):
[score1, score2, ...]
"""


def _llm_rerank_papers(
    papers: list[PaperHit],
    keywords: KeywordBreakdown,
) -> list[PaperHit]:
    """让 LLM 给每篇 arXiv 论文打 0-1 相关性, 过滤 < 0.3 的明显无关论文.

    Fallback: LLM 失败 → 返回原列表 (heuristic 评分仍生效).
    """

    if len(papers) <= 1:
        return papers

    keywords_block = ", ".join(
        (keywords.method_keywords or []) + (keywords.task_keywords or []) + (keywords.object_keywords or [])
    )
    papers_block = "\n".join(
        f"  [{i+1}] {p.title}\n      摘要: {(p.summary or '')[:200]}"
        for i, p in enumerate(papers)
    )
    raw_topic = keywords.query_keywords_zh[0] if keywords.query_keywords_zh else (
        " ".join((keywords.method_keywords or []) + (keywords.task_keywords or []) + (keywords.object_keywords or []))
    )
    prompt = _RERANK_PROMPT.format(
        raw_topic=raw_topic,
        keywords_block=keywords_block,
        papers_block=papers_block,
    )

    try:
        result = llm.chat_json_array(prompt, temperature=0.1, max_tokens=400, timeout=20.0)
    except llm.LLMUnavailable as exc:
        logger.info("LLM rerank 失败, fallback 不过滤: %s", exc)
        return papers

    if len(result) != len(papers):
        # 长度对不上, 视为失败
        return papers

    # 把 LLM 分数写进 relevance_score 字段, 过滤 < 0.3
    kept: list[PaperHit] = []
    for p, s in zip(papers, result):
        try:
            score = float(s)
        except (TypeError, ValueError):
            score = 0.5
        score = max(0.0, min(1.0, score))
        # 用 LLM 分数覆盖 heuristic 分数
        new_p = p.model_copy(update={"relevance_score": round(score, 3)})
        if score >= 0.3:
            kept.append(new_p)
        else:
            logger.info("LLM rerank 过滤掉无关论文: %s (score=%.2f): %s", p.paper_id, score, p.title[:80])
    return kept if kept else papers  # 极端情况: 全过滤掉 → 保留原列表 (heuristic 兜底)


def collect_evidence(
    keywords: KeywordBreakdown,
    plan: SearchPlan,
    prefer: str,
    arxiv_hits: list[arxiv_client.ArxivPaper] | None = None,
) -> EvidenceSummary:
    """调 arXiv 真检索 (失败 → 启发式占位).

    arxiv_hits: 可选. SSE 流式路径先搜一次 arxiv 用来 emit 步骤, 这里复用避免重复.
    Session 6: LLM rerank 过滤无关论文.
    """

    # 1) 论文: arXiv 真检索 (如已传 arxiv_hits 则复用)
    papers: list[PaperHit] = []
    if arxiv_hits is None:
        arxiv_hits = []
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

    # Session 6: LLM rerank arxiv 命中 (症状 3 根治)
    # 让 LLM 给每篇打 relevance_score, 过滤 < 0.3 的明显无关论文
    if papers and prefer != "heuristic":
        papers = _llm_rerank_papers(papers, keywords)

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

    # Session 5: 给 paper/dataset/repo 加 score + paper_type (SOP §7.3-7.5)
    kw_for_score = {
        "method_keywords": keywords.method_keywords,
        "task_keywords": keywords.task_keywords,
        "object_keywords": keywords.object_keywords,
        "scenario_keywords": keywords.scenario_keywords,
        "metric_keywords": keywords.metric_keywords,
    }
    papers_dict = [p.model_dump() for p in papers]
    datasets_dict = [d.model_dump() for d in datasets]
    baselines_dict = [b.model_dump() for b in baselines]
    scoring.attach_scores_to_evidence(papers_dict, datasets_dict, baselines_dict, kw_for_score)
    # 用 model_validate 重建 (Pydantic v2 model_copy 静默丢字段)
    from ..schemas import PaperHit as _PH, DatasetHit as _DH, BaselineHit as _BH
    papers = [_PH.model_validate(d) for d in papers_dict]
    datasets = [_DH.model_validate(d) for d in datasets_dict]
    baselines = [_BH.model_validate(d) for d in baselines_dict]

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

    # Session 5: 评分喂给 5 档 (SOP §4.5). 算"可入池"集合
    usable_papers = [p for p in ev.papers
                     if (p.relevance_score or 0) >= 0.3
                     and p.paper_type not in ("irrelevant", None)]
    avg_paper_score = (
        sum(p.relevance_score for p in usable_papers) / len(usable_papers)
        if usable_papers else 0.0
    )
    usable_datasets = [d for d in ev.datasets
                       if (d.quality_score or 0) >= 0.4
                       and d.dataset_status in ("ready", "needs_preprocess")]
    usable_repos = [b for b in ev.baselines
                    if (b.quality_score or 0) >= 0.4
                    and b.repo_type in ("official", "reproduction", "baseline_framework")]

    paper_status = ("✓ 有 arXiv 真实论文 (平均分 %.2f)" % avg_paper_score) if ev.arxiv_paper_count >= 3 else (
        "⚠ 论文偏少 (< 3 篇)" if ev.arxiv_paper_count > 0 else "✗ 无 arXiv 真实论文 (启发式占位)")
    dataset_status = ("✓ 有公开数据集 (%d 个 ready)" % len(usable_datasets)) if ev.has_public_dataset else "✗ 未匹配到公开数据集"
    baseline_status = ("✓ 有可复现 baseline (%d 个)" % len(usable_repos)) if ev.has_repro_baseline else "⚠ baseline 复现难度未知"
    engineering_status = ("✓ 有 GitHub 工程" if any(b.repository_url for b in ev.baselines)
                          else "⚠ 未确认 GitHub 工程")

    if not ev.has_public_dataset:
        missing.append("缺少明确公开数据集 (需补问)")
    if not ev.has_repro_baseline:
        missing.append("缺少可复现 baseline (复现成本未知)")
    if paper_count < 3:
        missing.append("论文偏少 (方向成熟度未确认)")
    if avg_paper_score and avg_paper_score < 0.4:
        missing.append(f"arXiv 论文相关性偏低 (平均分 {avg_paper_score:.2f}), 方向需要补检索词")
    if niche:
        missing.append("题目研究对象极小众, 公开数据几乎不存在")

    # 决策 (SOP §4.5 + §9.4 5 档: GO/NARROW/PIVOT/PARK/STOP)
    # Session 5 升级: 不只看数量, 还要看评分质量
    if niche and not ev.has_public_dataset:
        verdict: Literal["可做", "收缩后可做", "可转向", "暂缓", "不建议"] = "暂缓"
        reason = "题目对象极小众, 公开数据集几乎不存在, 建议收缩到成熟对象 (钢材/PCB/桥梁等) 或加自采数据."
    elif not usable_datasets and not usable_repos:
        # 无可用数据集 + 无可复现 repo
        if not ev.has_public_dataset and not ev.has_repro_baseline:
            verdict = "不建议"
            reason = "缺少 ready 状态数据集 + 可复现 baseline, 当前阶段不建议开题."
        else:
            verdict = "可转向"
            reason = "原题方向可行, 但数据集/Repo 评分均偏低, 建议转向相邻成熟方向."
    elif (len(usable_papers) >= 3 and avg_paper_score >= 0.5
          and len(usable_datasets) >= 1 and len(usable_repos) >= 1
          and ev.has_metrics):
        verdict = "可做"
        reason = (f"论文 {len(usable_papers)} 篇 (平均分 {avg_paper_score:.2f}) + "
                  f"数据集 {len(usable_datasets)} 个 + repo {len(usable_repos)} 个 + 指标齐备, 可进入开题报告推荐.")
    elif not ev.has_public_dataset or not ev.has_repro_baseline:
        verdict = "可转向"
        reason = "原题方向可行, 但当前路线证据不足, 建议转向相邻成熟方向 (如钢材→带钢/PCB 等已稳定开源数据集场景)."
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


def _nearest_public_dataset(object_keywords):
    """根据原题对象词, 选 _PUBLIC_DATASET_OBJECTS 里的 nearest public dataset.

    用于 conservative 路线: 若原题无公开数据集, 推荐相邻最稳对象.
    """

    for obj in object_keywords:
        for key, dataset in _PUBLIC_DATASET_OBJECTS.items():
            if key in obj or obj in key:
                return f"{key} ({dataset})"
    return "目标对象 (NEU-DET)"  # 兜底


def generate_pivot_routes(
    req, keywords, ev, feas,
):
    """SOP 10.3 三条路线 (保守/平衡/激进).

    Session 5 改造: 不再硬编码 - 保守路线按原题语义生成:
    - 原题有公开数据集 -> 保守保留原题, 收缩 risk_terms
    - 原题无公开数据集 -> 保守推荐相邻最稳对象 (nearest public dataset)
    """

    method = keywords.method_keywords[0] if keywords.method_keywords else "深度学习方法"
    obj = keywords.object_keywords[0] if keywords.object_keywords else "目标对象"
    task = keywords.task_keywords[0] if keywords.task_keywords else "目标检测"
    obj_list = keywords.object_keywords or [obj]

    if feas.verdict not in ("可转向", "收缩后可做"):
        return []

    removed = list(keywords.risk_terms or [])
    preserved = [k for k in (keywords.method_keywords + keywords.task_keywords) if k]

    has_public = any(d.fit in ("高", "中") and d.dataset_id != "DS99" for d in ev.datasets)
    nearest_ds = _nearest_public_dataset(obj_list)

    if has_public:
        cons_obj = obj_list[0] if obj_list else "目标对象"
        cons_dataset = ev.datasets[0].name if ev.datasets else "公开数据集"
        cons_topic = f"基于 {method} 的 {cons_obj} {task} 方法研究"
        cons_data_source = cons_dataset
        cons_research_q = f"{method} 在 {cons_obj} 上的 baseline 表现如何?"
        cons_dataset_name = cons_dataset
    else:
        parts = (nearest_ds.split(" (") + [""])[:2]
        cons_obj = parts[0]
        cons_dataset_name = parts[1].rstrip(")")
        cons_topic = f"基于 {method} 的 {cons_obj} {task} 方法研究"
        cons_data_source = f"{cons_dataset_name} (相邻最稳公开数据集)"
        cons_research_q = f"{method} 在 {cons_obj} 上的 baseline 表现如何?"

    cons = PivotRoute(
        level="conservative",
        new_topic=cons_topic,
        preserved_keywords=preserved + obj_list,
        removed_keywords=removed,
        tradeoff=f"去掉 risk_terms, 限定到 1 个公开数据集 ({cons_data_source}). 创新空间小但风险最低, 容易出第一张结果表.",
        work_packages=[
            WorkPackageSuggestion(
                wp_id="WP1",
                title=f"基于 {cons_dataset_name or cons_data_source} 复现 {method} baseline",
                research_question=cons_research_q,
                method_approach=f"采用 {method} 官方实现, 在 {cons_data_source} 上训练.",
                data_source=cons_data_source,
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

    bal_obj = obj_list[0] if obj_list else "目标对象"
    bal = PivotRoute(
        level="balanced",
        new_topic=f"基于 {method} 的 {bal_obj} {task} 方法研究",
        preserved_keywords=preserved + obj_list,
        removed_keywords=[r for r in removed if r not in ["高精度", "实时"]],
        tradeoff="保留原始对象, 用公开数据集 + 自采小规模验证. 创新适中, 风险适中.",
        work_packages=[
            WorkPackageSuggestion(
                wp_id="WP1",
                title=f"公开数据集上复现 {method} baseline + 自采小批量验证",
                research_question=f"原始对象 {bal_obj} 上的 baseline 表现 + 自采数据的迁移能力?",
                method_approach=f"{method} 标准实现 + 自采 100-200 张作 domain adaptation.",
                data_source="公开数据集 + 自采小批量",
                experiment_plan="baseline 在公开集 + 自采集分别报告, 给出迁移 gap.",
                chapter="第三章",
            ),
            WorkPackageSuggestion(
                wp_id="WP2",
                title="针对原始对象的轻量改进 + 跨域消融",
                research_question="模块改进在原始对象上的增量是多少?",
                method_approach=f"针对 {bal_obj} 特性设计模块.",
                data_source="同 WP1",
                experiment_plan="消融 + 跨域对比.",
                chapter="第四章",
            ),
        ],
    )

    agg_obj = obj_list[0] if obj_list else "目标对象"
    agg = PivotRoute(
        level="aggressive",
        new_topic=f"基于 {method} + 多模态的 {agg_obj} {task} 新方法",
        preserved_keywords=preserved + obj_list + ["多模态"],
        removed_keywords=[],
        tradeoff="保留所有原题要素 + 多模态, 必须自采大规模数据. 创新强, 风险高, 时间成本大.",
        work_packages=[
            WorkPackageSuggestion(
                wp_id="WP1",
                title=f"自采多模态数据采集与标注 ({agg_obj})",
                research_question=f"如何构建 {agg_obj} 的多模态数据集?",
                method_approach="RGB-D / 红外-可见光双模态自采 + 标注流程设计.",
                data_source=f"自采 1000+ 张 {agg_obj} 多模态数据",
                experiment_plan="数据采集方案 + 标注一致性 + 数据集统计.",
                chapter="第三章",
            ),
            WorkPackageSuggestion(
                wp_id="WP2",
                title="多模态融合方法设计 + 跨模态消融",
                research_question=f"多模态融合在 {agg_obj} 上的增益?",
                method_approach="跨模态特征对齐 + 决策融合.",
                data_source=f"自采 {agg_obj} 多模态数据",
                experiment_plan="单模态 vs 融合 消融; 不同融合策略对比.",
                chapter="第四章",
            ),
        ],
    )

    return [cons, bal, agg]
def recommend_proposal(
    req: OneTopicRequest, keywords: KeywordBreakdown, ev: EvidenceSummary, feas: FeasibilitySummary,
) -> ProposalRecommendation:
    """Session 6 §3: 优先 LLM 写推荐 + 工作包, 失败 fallback 启发式模板."""

    # 启发式 fallback 模板 (保留作为兜底)
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

    # Session 6: LLM 路径覆盖启发式
    if req.prefer != "heuristic":
        from . import llm_content
        llm_result = llm_content.recommend_proposal_llm(
            raw_topic=req.raw_topic,
            goal_level=req.goal_level,
            keywords={
                "method_keywords": keywords.method_keywords,
                "task_keywords": keywords.task_keywords,
                "object_keywords": keywords.object_keywords,
                "scenario_keywords": keywords.scenario_keywords,
                "metric_keywords": keywords.metric_keywords,
                "risk_terms": keywords.risk_terms,
            },
            arxiv_count=ev.arxiv_paper_count,
            paper_count=ev.paper_count,
            dataset_names=[d.name for d in ev.datasets],
            has_dataset=ev.has_public_dataset,
            baseline_names=[b.name for b in ev.baselines],
            has_baseline=ev.has_repro_baseline,
            metrics=ev.metrics,
            verdict=feas.verdict,
            feas_reason=feas.reason,
        )
        if llm_result:
            # 解析 WP
            llm_wps = []
            for wp_dict in llm_result.get("work_packages") or []:
                if not isinstance(wp_dict, dict):
                    continue
                try:
                    llm_wps.append(WorkPackageSuggestion(
                        wp_id=str(wp_dict.get("wp_id") or f"WP{len(llm_wps)+1}"),
                        title=str(wp_dict.get("title") or "工作包"),
                        research_question=str(wp_dict.get("research_question") or ""),
                        method_approach=str(wp_dict.get("method_approach") or ""),
                        data_source=str(wp_dict.get("data_source") or ""),
                        experiment_plan=str(wp_dict.get("experiment_plan") or ""),
                        chapter=str(wp_dict.get("chapter") or "第三章"),
                    ))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("LLM WP 解析失败: %s", exc)
                    continue
            if llm_wps:
                return ProposalRecommendation(
                    recommended_topic=str(llm_result.get("recommended_topic") or recommended),
                    recommendation_reason=list(llm_result.get("recommendation_reasons") or reasons),
                    work_packages=llm_wps,
                    proposal_outline=outline,
                    pivot_routes=pivot_routes,
                )

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
    """Session 6 §4: 优先 LLM 写 5 维审核, 失败 fallback 启发式."""

    # 启发式 fallback (保留作为模板)
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

    # Session 6: LLM 路径覆盖启发式
    if req.prefer != "heuristic":
        from . import llm_content
        llm_result = llm_content.light_review_llm(
            raw_topic=req.raw_topic,
            goal_level=req.goal_level,
            arxiv_count=ev.arxiv_paper_count,
            paper_count=ev.paper_count,
            dataset_names=[d.name for d in ev.datasets],
            has_dataset=ev.has_public_dataset,
            baseline_names=[b.name for b in ev.baselines],
            has_baseline=ev.has_repro_baseline,
            metrics=ev.metrics,
            verdict=feas.verdict,
            feas_reason=feas.reason,
        )
        if llm_result:
            llm_checks: list[ReviewCheck] = []
            for c_dict in llm_result.get("checks") or []:
                if not isinstance(c_dict, dict):
                    continue
                try:
                    llm_checks.append(ReviewCheck(
                        dimension=str(c_dict.get("dimension") or "未命名"),
                        result=str(c_dict.get("result") or "需补充"),
                        comment=str(c_dict.get("comment") or ""),
                    ))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("LLM check 解析失败: %s", exc)
                    continue
            if llm_checks:
                return LightReview(
                    verdict=str(llm_result.get("verdict") or verdict),
                    summary=str(llm_result.get("summary") or summary),
                    checks=llm_checks,
                    revision_checklist=list(llm_result.get("revision_checklist") or revisions),
                )

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

    # 装配 evidence (走 collect_evidence 走评分 + 去重; 复用 arxiv_papers 避免重复检索)
    emit("step", "⚙️ 正在合成证据 + 评分 + 分类", {"phase": "evidence_scoring"})
    ev = collect_evidence(keywords, plan, req.prefer, arxiv_hits=arxiv_papers)
    arxiv_paper_count = ev.arxiv_paper_count
    metrics = ev.metrics

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
