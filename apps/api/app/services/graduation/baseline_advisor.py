"""Session 62 M4: BaselineAdvisor — recommend 1-3 baselines per direction.

ponytail: 不引外部 baseline 库; 用 5 类经典模型 + 模板按方向特征匹配。
- 优先级: 轻量成熟 > 常用公开实现 > 论文官方代码 > 重模型 > 纯理论
- 不推荐没有数据集支撑的 baseline (在 risk_scorer 已扣分, 这里再次确认)
"""
from __future__ import annotations

from dataclasses import dataclass

from .direction_planner import GraduationDirection


# 经典 baseline 模板
_BASELINE_TEMPLATES: list[dict] = [
    {
        "name": "YOLOv8n",
        "tags": ["detect", "lightweight", "pytorch"],
        "rationale": "Ultralytics 官方维护, 文档完善, 单卡 3090 即可训练, 适合目标检测类方向",
        "required_data": "公开目标检测数据集 (COCO / VisDrone / 自采缺陷数据集)",
        "reproducibility": "high",
        "estimated_compute": "单卡 3090 12-24h",
        "risks": ["小目标召回偏低", "需调 anchor-free 头"],
    },
    {
        "name": "YOLOv5s",
        "tags": ["detect", "lightweight", "pytorch"],
        "rationale": "PyTorch 官方实现, 社区资源最多, 适合工程复现与改进",
        "required_data": "公开目标检测数据集",
        "reproducibility": "high",
        "estimated_compute": "单卡 3090 12-24h",
        "risks": ["新版本相对 v8 略落后"],
    },
    {
        "name": "U-Net",
        "tags": ["segmentation", "lightweight"],
        "rationale": "医学影像 / 裂缝分割经典 baseline, 论文引用过万, 实现极简",
        "required_data": "像素级标注的分割数据集 (Crack500 / CFD / Carvana)",
        "reproducibility": "high",
        "estimated_compute": "单卡 3060 8-16h",
        "risks": ["对细小裂缝欠分割, 可加注意力"],
    },
    {
        "name": "ResNet-50",
        "tags": ["classification", "lightweight"],
        "rationale": "torchvision 官方预训练, 适合做分类方向 baseline",
        "required_data": "ImageNet 或领域内分类数据",
        "reproducibility": "high",
        "estimated_compute": "单卡 3090 6-12h",
        "risks": ["对长尾类别效果一般"],
    },
    {
        "name": "Faster R-CNN",
        "tags": ["detect", "pytorch"],
        "rationale": "torchvision 内置, 适合做两阶段检测对比",
        "required_data": "COCO / 领域内检测数据",
        "reproducibility": "medium",
        "estimated_compute": "单卡 3090 24-36h",
        "risks": ["速度慢, 实时性要求高的场景不适用"],
    },
    {
        "name": "PointNet++",
        "tags": ["3d", "pointcloud"],
        "rationale": "三维点云经典 baseline, 适合三维缺陷检测",
        "required_data": "三维点云标注数据 (ShapeNet / 自采)",
        "reproducibility": "medium",
        "estimated_compute": "单卡 3090 12-24h",
        "risks": ["对密集小目标敏感度不足"],
    },
    {
        "name": "1D-CNN",
        "tags": ["timeseries", "shm"],
        "rationale": "结构健康监测时序信号经典 baseline",
        "required_data": "SHM 时序数据集 (IASC / 自采)",
        "reproducibility": "high",
        "estimated_compute": "单卡 3060 4-8h",
        "risks": ["长序列依赖建模不足"],
    },
]


@dataclass
class BaselineRecommendation:
    name: str
    rationale: str
    required_data: str
    reproducibility: str  # low / medium / high
    estimated_compute: str
    risks: list[str]


def _match_tags(direction: GraduationDirection) -> set[str]:
    """从方向中抽取关键 tag."""
    text = " ".join([
        direction.title or "",
        direction.task or "",
        direction.method_route or "",
        direction.research_object or "",
    ]).lower()
    tags: set[str] = set()
    if any(k in text for k in ["三维", "3d", "点云"]):
        tags.add("3d")
    if any(k in text for k in ["时序", "shm", "桥梁", "结构健康"]):
        tags.add("shm")
        tags.add("timeseries")
    if any(k in text for k in ["分割", "segment"]):
        tags.add("segmentation")
    if any(k in text for k in ["分类"]):
        tags.add("classification")
    if any(k in text for k in ["检测", "detect"]):
        tags.add("detect")
    return tags


def recommend_baselines(
    direction: GraduationDirection,
    *,
    has_dataset: bool,
    max_n: int = 3,
) -> list[BaselineRecommendation]:
    """为单个方向推荐 1-3 个 baseline."""

    if not has_dataset:
        # 没数据集时, 只给一个'先用公开数据集预热'的提示型 baseline
        return [BaselineRecommendation(
            name="YOLOv8n (需先准备公开数据集)",
            rationale="题目方向需要先锁定公开数据集再选 baseline; 该 baseline 数据需求最普适",
            required_data="任何可下载的目标检测数据集 (COCO / VisDrone)",
            reproducibility="high",
            estimated_compute="单卡 3090 12-24h",
            risks=["数据未锁定前不要开始训练"],
        )]

    tags = _match_tags(direction)
    candidates: list[BaselineRecommendation] = []
    for tpl in _BASELINE_TEMPLATES:
        tpl_tags = set(tpl["tags"])
        if tags and not (tpl_tags & tags):
            continue
        candidates.append(BaselineRecommendation(
            name=tpl["name"],
            rationale=tpl["rationale"],
            required_data=tpl["required_data"],
            reproducibility=tpl["reproducibility"],
            estimated_compute=tpl["estimated_compute"],
            risks=list(tpl["risks"]),
        ))
        if len(candidates) >= max_n:
            break

    # 如果 tags 没匹配到任何 baseline, 给一个保底
    if not candidates:
        candidates = [BaselineRecommendation(
            name=tpl["name"],
            rationale=tpl["rationale"],
            required_data=tpl["required_data"],
            reproducibility=tpl["reproducibility"],
            estimated_compute=tpl["estimated_compute"],
            risks=list(tpl["risks"]),
        ) for tpl in _BASELINE_TEMPLATES[:max_n]
        ]

    return candidates


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
    bs = recommend_baselines(d, has_dataset=True, max_n=3)
    assert 1 <= len(bs) <= 3, len(bs)
    assert all(b.name and b.rationale for b in bs), bs

    bs2 = recommend_baselines(d, has_dataset=False, max_n=3)
    assert len(bs2) == 1, len(bs2)
    assert "需先准备公开数据集" in bs2[0].name
    print(f"OK baseline_advisor self-check (with={len(bs)}, without={len(bs2)})")