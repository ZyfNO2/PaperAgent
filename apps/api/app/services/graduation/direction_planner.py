"""Session 62 M1: GraduationDirectionPlanner — heuristic direction templates.

ponytail: 不调 LLM; 不造大框架。
- 输入: 原始题目 + 关键词
- 输出: 2-3 个候选毕业方向 (每个含对象/任务/方法/降级路径)
- 模板触发: 题目里命中 _KEYWORD_TEMPLATES 才生成对应方向;
  未命中 → fallback RAW_TOPIC_TEMPLATES (原题缩小 + 公开数据降级)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class GraduationDirection:
    direction_id: str
    title: str
    research_object: str
    task: str
    method_route: str
    why_graduation_friendly: list[str] = field(default_factory=list)
    fallback_route: str = ""


# 关键词 → 方向模板
# ponytail: 单文件单层映射, 不嵌套 strategy
_KEYWORD_TEMPLATES: list[dict] = [
    {
        "match": ["三维", "3d", "3D", "点云", "点云数据"],
        "title": "基于公开点云/三维缺陷数据集的轻量化目标检测",
        "object": "工业部件 / 建筑结构表面缺陷 (裂缝、孔洞、变形)",
        "task": "三维点云缺陷检测 (目标检测或语义分割)",
        "method": "轻量 3D 检测网络 + 经典 2D baseline 兜底",
        "why": [
            "三维公开数据集较少, 但工业检测子类有 CodeMBI、ShapeNet-SRN 等可替代",
            "baseline 成熟 (PointNet++ / VoteNet / 3D-YOLO)",
            "实验成本可控, 单卡 3090 可跑",
        ],
        "fallback": "三维数据不足时, 降级为二维裂缝/缺陷检测 (CFD / crack500 / SDD-Net)",
    },
    {
        "match": ["损伤", "裂缝", "缺陷", "crack", "damage", "defect"],
        "title": "基于公开裂缝/缺陷数据集的轻量化检测",
        "object": "结构表面裂缝 / 工业部件表面缺陷",
        "task": "像素级或目标级裂缝/缺陷检测",
        "method": "YOLOv8n / U-Net 轻量化 baseline + 多尺度增强",
        "why": [
            "公开数据丰富 (CFD / CrackForest / DeepCrack / CODEBRIM)",
            "baseline 极成熟, 复现成本低",
            "可做消融 (注意力 / 损失函数 / 数据增强)",
            "写作友好, 公式与可视化充足",
        ],
        "fallback": "工业场景数据不可得时, 用公开桥梁 / 路面裂缝数据集 (CODEBRIM / Crack500)",
    },
    {
        "match": ["成像", "图像", "影像", "视觉", "image", "imaging", "vision"],
        "title": "基于公开图像/视觉数据集的目标检测与分类",
        "object": "可见光 / 红外 / X-ray 等成像模态下的目标",
        "task": "目标检测 / 图像分类 / 语义分割",
        "method": "经典 CNN baseline (ResNet / YOLO / U-Net) + 轻量化模块",
        "why": [
            "ImageNet / COCO / VisDrone 等公开数据充足",
            "PyTorch 官方 baseline 极稳定",
            "本科级算力即可复现",
        ],
        "fallback": "特定模态数据不可得时, 退到 VisDrone / COCO 通用目标检测",
    },
    {
        "match": ["结构健康", "桥梁", "路面", "建筑", "隧道", "shm"],
        "title": "基于 SHM 公开数据集的结构健康监测",
        "object": "桥梁 / 道路 / 隧道结构损伤演化",
        "task": "时序异常检测 + 损伤分类",
        "method": "1D-CNN / LSTM 时序 baseline + 注意力模块",
        "why": [
            "IASC / SHM 数据集公开可下载",
            "baseline 轻量, 算力门槛低",
            "结果可视化友好, 工程意义明确",
        ],
        "fallback": "时序数据不可得时, 退化为图像裂缝检测 (CODEBRIM)",
    },
    {
        "match": ["超声", "ct", "x-ray", "xray", "射线"],
        "title": "基于 X-ray / 超声影像的无损检测",
        "object": "焊缝 / 铸件内部缺陷",
        "task": "小目标检测 / 语义分割",
        "method": "YOLOv8s + FPN/PANet 多尺度 neck + 数据增强",
        "why": [
            "GDXray / X-ray 焊缝数据集公开",
            "工业应用背景明确, 答辩友好",
            "可加模块空间大 (CBAM / BiFPN / 小目标检测头)",
        ],
        "fallback": "X-ray 数据不足时, 降级为可见光 PCB 缺陷 (DeepPCB)",
    },
]


# 通用兜底 (任何题目至少有一条)
RAW_TOPIC_TEMPLATES: list[dict] = [
    {
        "title": "基于公开数据集的轻量化目标检测",
        "object": "公开数据集中与原题对象最相近的子集",
        "task": "目标检测",
        "method": "YOLOv8n / Faster R-CNN baseline",
        "why": [
            "不依赖自采数据, 复现门槛最低",
            "有成熟 baseline 与公开评测脚本",
        ],
        "fallback": "数据完全缺失时, 改做综述类题目",
    },
    {
        "title": "原题缩小版 (聚焦二维或单模态)",
        "object": "原题对象的二维 / 单模态近似",
        "task": "图像分类 / 检测",
        "method": "经典 CNN baseline",
        "why": [
            "把三维降到二维, 数据与算力门槛都下降一档",
            "写作与答辩解释成本低",
        ],
        "fallback": "二维数据也不足时, 改用最近邻公开子集 (如 crack500 / CFD)",
    },
    {
        "title": "原题数据驱动降级 (用近邻公开数据替代)",
        "object": "原题对象的最相似公开对象",
        "task": "依数据可用性选择 (检测 / 分割 / 分类)",
        "method": "U-Net / ResNet baseline",
        "why": [
            "即使原题数据完全不可得, 仍能基于近邻数据集完成完整流程",
            "答辩时可以解释成'同源迁移'",
        ],
        "fallback": "所有公开数据都不足时, 改为方法综述 + 小规模自采",
    },
]


def _hit(template: dict, topic_lower: str) -> bool:
    for kw in template["match"]:
        if kw.lower() in topic_lower:
            return True
    return False


def _slug(s: str, n: int = 8) -> str:
    s = re.sub(r"[^\w一-龥]+", "", s)
    return f"dir_{n}_{s[:24]}"


def plan_directions(topic: str, keywords: list[str] | None = None, max_directions: int = 3) -> list[GraduationDirection]:
    """根据题目与关键词生成 2-3 个方向.

    优先级:
    1) 命中 _KEYWORD_TEMPLATES 的模板
    2) 不够 → 用 RAW_TOPIC_TEMPLATES 补齐到 max_directions
    """
    topic_lower = (topic or "").strip()
    if not topic_lower:
        return []
    topic_lc = topic_lower.lower()
    seed_pool = list(keywords or [])
    seed_pool.append(topic_lc)
    topic_with_kw = " ".join(seed_pool).lower()

    directions: list[GraduationDirection] = []
    seen_titles: set[str] = set()
    counter = 0

    # 1) 命中模板
    for tpl in _KEYWORD_TEMPLATES:
        if _hit(tpl, topic_lc) or _hit(tpl, topic_with_kw):
            counter += 1
            d = GraduationDirection(
                direction_id=_slug(tpl["title"], counter),
                title=tpl["title"],
                research_object=tpl["object"],
                task=tpl["task"],
                method_route=tpl["method"],
                why_graduation_friendly=list(tpl["why"]),
                fallback_route=tpl["fallback"],
            )
            if d.title not in seen_titles:
                directions.append(d)
                seen_titles.add(d.title)
            if len(directions) >= max_directions:
                break

    # 2) 兜底
    if len(directions) < 2:
        for tpl in RAW_TOPIC_TEMPLATES:
            if len(directions) >= max_directions:
                break
            counter += 1
            d = GraduationDirection(
                direction_id=_slug(tpl["title"], counter),
                title=tpl["title"],
                research_object=tpl["object"],
                task=tpl["task"],
                method_route=tpl["method"],
                why_graduation_friendly=list(tpl["why"]),
                fallback_route=tpl["fallback"],
            )
            if d.title not in seen_titles:
                directions.append(d)
                seen_titles.add(d.title)

    return directions


if __name__ == "__main__":
    # ponytail: self-check
    ds = plan_directions("基于三维成像的损伤智能检测", keywords=["裂缝", "点云"])
    assert 2 <= len(ds) <= 3, len(ds)
    assert all(d.direction_id and d.title and d.method_route for d in ds), ds
    print(f"OK direction_planner self-check passed (count={len(ds)})")