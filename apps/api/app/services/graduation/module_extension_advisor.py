"""Session 62 M5: ModuleExtensionAdvisor — recommend 2-4 ablation-ready modules.

ponytail: 不引第三方 ablation 框架; 模块库固定 8 个, 按任务类型筛。
"""
from __future__ import annotations

from dataclasses import dataclass

from .direction_planner import GraduationDirection
from .baseline_advisor import BaselineRecommendation


_MODULE_LIBRARY: list[dict] = [
    {
        "name": "CBAM 注意力模块",
        "attach_to": "backbone 末端 + neck 输出",
        "problem_solved": "通道/空间注意力, 提升小目标/裂缝召回",
        "ablation_plan": "对比 baseline vs +CBAM, 报告 mAP / Recall 提升",
        "task_match": ["detect", "segmentation"],
        "effort": "S",
        "risks": ["参数量略增, 需重测 FPS"],
    },
    {
        "name": "多尺度特征融合 (BiFPN / FPN+PAN)",
        "attach_to": "neck 替换为 BiFPN",
        "problem_solved": "多尺度小目标/大目标同时提升",
        "ablation_plan": "对比 baseline-FPN vs +BiFPN, 报告各尺度 mAP",
        "task_match": ["detect"],
        "effort": "M",
        "risks": ["显存占用上升"],
    },
    {
        "name": "轻量化 neck (GhostConv / ShuffleNet 块)",
        "attach_to": "neck 替换为 Ghost 模块",
        "problem_solved": "参数与 FLOPs 显著下降, 适合边缘部署",
        "ablation_plan": "对比 baseline FLOPs/Params vs +Ghost neck",
        "task_match": ["detect", "segmentation"],
        "effort": "M",
        "risks": ["精度可能轻微下降, 需报告 trade-off"],
    },
    {
        "name": "Mosaic+MixUp 数据增强",
        "attach_to": "数据加载层",
        "problem_solved": "提升样本多样性, 缓解过拟合",
        "ablation_plan": "对比基线 vs +Mosaic/MixUp, 报告 mAP 与 loss 曲线",
        "task_match": ["detect", "classification"],
        "effort": "S",
        "risks": ["需重新调学习率"],
    },
    {
        "name": "Focal Loss / Dice Loss 替换",
        "attach_to": "loss 头",
        "problem_solved": "正负样本不均衡 / 小目标欠拟合",
        "ablation_plan": "对比 CE vs Focal/Dice, 报告 PR 曲线",
        "task_match": ["detect", "segmentation"],
        "effort": "S",
        "risks": ["超参 gamma/alpha 需调"],
    },
    {
        "name": "小目标检测头 (P2 / 4-scale head)",
        "attach_to": "head 增加 P2 层",
        "problem_solved": "微小缺陷召回率提升",
        "ablation_plan": "对比 baseline 3-scale vs +P2, 报告小目标 AP",
        "task_match": ["detect"],
        "effort": "M",
        "risks": ["显存上升, 需降 batch"],
    },
    {
        "name": "边缘/纹理增强预处理 (Sobel / Laplacian)",
        "attach_to": "数据预处理层",
        "problem_solved": "突出边缘纹理, 减少光照干扰",
        "ablation_plan": "对比原图 vs 边缘增强, 报告 mAP 与可视化",
        "task_match": ["detect", "segmentation"],
        "effort": "S",
        "risks": ["对某些场景反而引入噪声"],
    },
    {
        "name": "模型蒸馏 (Teacher-Student)",
        "attach_to": "训练 pipeline",
        "problem_solved": "在保持精度的同时压缩模型, 适合部署",
        "ablation_plan": "对比 student-only vs +teacher KD, 报告 mAP / Params",
        "task_match": ["detect", "classification"],
        "effort": "L",
        "risks": ["训练时长翻倍, 需 teacher 预训练"],
    },
]


@dataclass
class ExtensionModule:
    name: str
    attach_to: str
    problem_solved: str
    ablation_plan: str
    effort: str  # S/M/L
    risks: list[str]


def _baseline_tags(baselines: list[BaselineRecommendation]) -> set[str]:
    tags: set[str] = set()
    for b in baselines:
        n = (b.name or "").lower()
        if "yolo" in n or "faster" in n:
            tags.add("detect")
        if "unet" in n or "u-net" in n:
            tags.add("segmentation")
        if "resnet" in n:
            tags.add("classification")
        if "pointnet" in n:
            tags.add("3d")
        if "1d-cnn" in n:
            tags.add("timeseries")
    return tags


def recommend_modules(
    direction: GraduationDirection,
    baselines: list[BaselineRecommendation],
    *,
    max_n: int = 4,
) -> list[ExtensionModule]:
    """按方向任务 + baseline 类型筛 2-4 个模块."""

    text = " ".join([
        direction.title or "",
        direction.task or "",
        direction.method_route or "",
        direction.research_object or "",
    ]).lower()
    tags: set[str] = set()
    if any(k in text for k in ["分割", "segment"]):
        tags.add("segmentation")
    if any(k in text for k in ["分类"]):
        tags.add("classification")
    if any(k in text for k in ["检测", "detect"]):
        tags.add("detect")
    if any(k in text for k in ["三维", "3d", "点云"]):
        tags.add("3d")
    if any(k in text for k in ["时序", "shm", "桥梁", "结构健康"]):
        tags.add("timeseries")

    # 用 baseline tag 补齐
    tags.update(_baseline_tags(baselines))
    if not tags:
        tags = {"detect"}

    picked: list[ExtensionModule] = []
    for m in _MODULE_LIBRARY:
        match = m["task_match"]
        if any(t in tags for t in match):
            picked.append(ExtensionModule(
                name=m["name"],
                attach_to=m["attach_to"],
                problem_solved=m["problem_solved"],
                ablation_plan=m["ablation_plan"],
                effort=m["effort"],
                risks=list(m["risks"]),
            ))
        if len(picked) >= max_n:
            break

    # 如果一个都没匹配到, 给保底
    if not picked:
        picked = [ExtensionModule(
            name=m["name"],
            attach_to=m["attach_to"],
            problem_solved=m["problem_solved"],
            ablation_plan=m["ablation_plan"],
            effort=m["effort"],
            risks=list(m["risks"]),
        ) for m in _MODULE_LIBRARY[:max_n]]

    return picked


if __name__ == "__main__":
    # ponytail: self-check
    d = GraduationDirection(
        direction_id="d1",
        title="基于公开裂缝数据集的轻量化检测",
        research_object="裂缝",
        task="目标检测",
        method_route="YOLOv8n",
        why_graduation_friendly=[],
        fallback_route="",
    )
    bs = [BaselineRecommendation(name="YOLOv8n", rationale="", required_data="", reproducibility="high", estimated_compute="", risks=[])]
    mods = recommend_modules(d, bs, max_n=4)
    assert 2 <= len(mods) <= 4, len(mods)
    assert all(m.name and m.attach_to and m.ablation_plan for m in mods), mods
    print(f"OK module_extension_advisor self-check (modules={len(mods)})")