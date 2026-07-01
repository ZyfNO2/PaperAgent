"""Session 51: 实验需求多标签抽取 (题名+摘要 → 9 标签).

9 标签 (SOP §4.1 / 测试集文档 §6.2):
    single_gpu_ok                YOLO/U-Net/Faster R-CNN/Mask R-CNN/GAN + 无硬件词
    cpu_or_light_gpu_ok          SCADA/可靠性/传统算法/无深度学习词
    large_gpu_optional           点云补全/多模态融合/大规模3D
    h100_level_not_recommended   系统判必须 H100 → 标「不适合毕业复现」
    self_collected_dataset       无公开数据匹配 + 自采/现场/企业数据
    public_dataset_available     命中公开数据集名 (NEU-DET/KITTI 等)
    hardware_platform_required   机械臂/机器人/相机/Jetson/结构光/LiDAR/ZED/ROS
    annotation_heavy             缺陷/小目标/多类别 + 无公开数据
    domain_data_permission_risk  医学/人体/电力巡检/SCADA/企业生产

双路径 (SOP §8.2):
    LLM 抽多标签 → 失败 → heuristic 规则兜底. assessment_mode 标 llm/heuristic.

核心约束:
- 不许让 LLM 挂掉服务 (LLM 不可用必须 fallback 到 heuristic).
- H100 不是默认需求; 普通 YOLO/U-Net 不许误判为 h100 级.
"""

from __future__ import annotations

import logging
from typing import Any

from ...schemas_thesis_eval import ExperimentNeedTag

logger = logging.getLogger(__name__)

# ---------- heuristic 规则 (对齐 SOP §8.1) ---------- #

# 单卡可跑的方法词
_SINGLE_GPU_METHODS = {
    "yolo", "yolov", "u-net", "unet", "faster r-cnn", "faster rcnn",
    "mask r-cnn", "mask rcnn", "gan", "retinanet", "ssd", "cnn", "resnet",
    "深度学习", "卷积",
}
# 大显存可选 (非必要) 的方法词
_LARGE_GPU_METHODS = {
    "点云补全", "多模态融合", "大规模3d", "三维重建", "三维点云",
    "slam", "点云", "rgb-d", "双目", "lidar",
}
# 传统/轻算力词
_CPU_LIGHT_METHODS = {
    "scada", "可靠性", "故障诊断", "传统算法", "支持向量机", "svm",
    "随机森林", "小波", "贝叶斯", "机理模型",
}
# 硬件平台词 (主风险)
_HARDWARE_WORDS = {
    "机械臂", "机器人", "相机", "jetson", "结构光", "lidar", "zed",
    "ros", "云台", "无人机", "巡检车", "实验台", "转台", "光学系统",
    "抓取", "机械手", "运动控制", "伺服",
}
# 公开数据集名 (命中即 public_dataset_available)
_PUBLIC_DATASETS = {
    "neu-det", "kitti", "nuscenes", "coco", "voc", "imagenet",
    "cityscapes", "dota", "xview", "visdrone", "uavdt", "steel",
    "公开数据集", "公开遥感", "公开点云", "公开交通",
}
# 自采数据词
_SELF_COLLECT_WORDS = {
    "自采", "自建", "现场", "企业数据", "实测", "采集", "实验室数据",
    "生产现场", "巡检图像",
}
# 合规/权限风险词
_PERMISSION_WORDS = {
    "医学", "医疗", "人体", "患者", "ct", "mri", "超声",
    "电力巡检", "巡检", "scada", "企业生产", "工业现场", "生产数据",
    "合规", "权限", "隐私",
}
# 标注重词
_ANNOTATION_WORDS = {
    "缺陷", "小目标", "多类别", "类别不均衡", "标注", "细粒度",
}

# 所有 9 个合法标签 (h100 默认不标, 除非系统判定必须)
_ALL_TAGS: tuple[ExperimentNeedTag, ...] = (
    "single_gpu_ok",
    "cpu_or_light_gpu_ok",
    "large_gpu_optional",
    "h100_level_not_recommended",
    "self_collected_dataset",
    "public_dataset_available",
    "hardware_platform_required",
    "annotation_heavy",
    "domain_data_permission_risk",
)


def _text_lower(text: str) -> str:
    return (text or "").lower()


def _has_any(text_lower: str, words: set[str]) -> bool:
    return any(w in text_lower for w in words)


def extract_experiment_needs_heuristic(title: str, abstract: str | None) -> list[ExperimentNeedTag]:
    """启发式规则抽 9 标签 (SOP §8.1).

    H100 默认不标: 普通检测/分割类即使方法重也不会判为 h100 级.
    """
    text = _text_lower(title) + " " + _text_lower(abstract or "")
    tags: list[ExperimentNeedTag] = []
    has_hardware = _has_any(text, _HARDWARE_WORDS)

    # --- compute_need (互斥优先级: cpu_light > large_gpu > single_gpu; h100 默认不标) ---
    is_cpu_light = _has_any(text, _CPU_LIGHT_METHODS)
    is_large_gpu = _has_any(text, _LARGE_GPU_METHODS)
    is_single_method = _has_any(text, _SINGLE_GPU_METHODS)

    if is_cpu_light and not is_single_method:
        tags.append("cpu_or_light_gpu_ok")
    elif is_large_gpu:
        tags.append("large_gpu_optional")
    elif is_single_method:
        tags.append("single_gpu_ok")
    else:
        # 无明显方法词: 默认轻算力 (传统/工程类论文)
        tags.append("cpu_or_light_gpu_ok")

    # --- data_need (可多标) ---
    has_public = _has_any(text, _PUBLIC_DATASETS)
    has_self = _has_any(text, _SELF_COLLECT_WORDS)
    has_permission = _has_any(text, _PERMISSION_WORDS)
    has_annotation = _has_any(text, _ANNOTATION_WORDS)

    if has_public:
        tags.append("public_dataset_available")
    if has_self or (has_annotation and not has_public):
        # 有标注重 + 无公开数据 → 自采
        tags.append("self_collected_dataset")
    if has_permission:
        tags.append("domain_data_permission_risk")
    if has_annotation:
        tags.append("annotation_heavy")

    # --- hardware_need ---
    if has_hardware:
        tags.append("hardware_platform_required")

    # --- h100: 默认不标. 仅当同时命中 large_gpu + 多模态 + 硬件 + 合规 (极端情况) 才标 ---
    if (
        is_large_gpu
        and _has_any(text, {"多模态攻防", "大模型", "diffusion"})
        and has_hardware
    ):
        tags.append("h100_level_not_recommended")

    # 去重保序
    seen: set[str] = set()
    deduped: list[ExperimentNeedTag] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped


# ---------- LLM 路径 (失败 → heuristic 兜底) ---------- #

_LLM_SYSTEM = """你是工科论文实验需求标注助手。根据题名和摘要片段, 从以下 9 个标签里选多标签:
single_gpu_ok, cpu_or_light_gpu_ok, large_gpu_optional, h100_level_not_recommended,
self_collected_dataset, public_dataset_available, hardware_platform_required,
annotation_heavy, domain_data_permission_risk。
规则: H100 默认不标 (除非必须); 普通 YOLO/U-Net 标 single_gpu_ok; SCADA/传统算法标 cpu_or_light_gpu_ok。
只返回 JSON: {"tags": ["..."]}。"""


def _call_llm_tags(title: str, abstract: str | None) -> list[ExperimentNeedTag]:
    """调 LLM 抽标签. 失败 raise, 让上层 fallback."""
    from ..llm import LLMUnavailable, chat_json

    prompt = f"题名: {title}\n摘要片段: {abstract or '(无)'}"
    resp = chat_json(prompt, system=_LLM_SYSTEM, temperature=0.1, max_tokens=300, timeout=20.0)
    raw_tags = resp.get("tags", []) if isinstance(resp, dict) else []
    out: list[ExperimentNeedTag] = []
    for t in raw_tags:
        if isinstance(t, str) and t in _ALL_TAGS:
            out.append(t)  # type: ignore[arg-type]
    if not out:
        raise LLMUnavailable("LLM 返回标签为空或全部非法, fallback 到 heuristic")
    # 去重保序
    seen: set[str] = set()
    deduped: list[ExperimentNeedTag] = []
    for t in out:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped


def extract_experiment_needs(
    title: str,
    abstract: str | None,
    *,
    use_llm: bool = False,
) -> tuple[list[ExperimentNeedTag], str]:
    """抽 9 标签多标签.

    Args:
        title: 题名
        abstract: 摘要片段 (可 None)
        use_llm: 是否尝试 LLM 路径 (默认 False; True 时 LLM 失败自动 fallback heuristic)

    Returns:
        (tags, assessment_mode): assessment_mode 为 "llm" 或 "heuristic".
    """
    if use_llm:
        try:
            tags = _call_llm_tags(title, abstract)
            return tags, "llm"
        except Exception as exc:  # noqa: BLE001 — LLM 不可用必须降级, 不许挂服务
            logger.info("LLM need extraction failed, fallback to heuristic: %s", exc)
    tags = extract_experiment_needs_heuristic(title, abstract)
    return tags, "heuristic"
