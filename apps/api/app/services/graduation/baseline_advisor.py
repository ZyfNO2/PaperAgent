"""Session 62 M4: BaselineAdvisor — 推荐 1-3 个 baseline, 按任务路径分组.

ponytail: 不引外部 baseline 库; 用任务路径字典, 每条路径有独立 baseline 列表.

重要: 一个方向有"主任务"+"子任务"概念. 比如"三维成像的损伤检测":
- 主任务 = 三维重建 (输入→三维表示)
- 子任务 = 三维损伤检测 (在三维表示上识别损伤)
两个任务工作量不同, baseline 不同, 必须分开推荐.
"""
from __future__ import annotations

from dataclasses import dataclass

from .direction_planner import GraduationDirection


# 任务路径 → baseline 列表 (按推荐优先级排序)
# ponytail: 每个路径最多 3 个 baseline; 三维损伤检测必须包含 3D 检测器
TASK_PATH_BASELINES: dict[str, list[dict]] = {
    # 3D 损伤检测 (核心任务: 在三维数据上识别缺陷)
    "3d_detection": [
        {
            "name": "PointNet++",
            "rationale": "三维点云检测/分割经典 baseline, 已被百余篇论文验证, 适合作为 3D 缺陷检测起点",
            "required_data": "三维点云标注 (ShapeNet / ModelNet / 自采工业部件点云)",
            "reproducibility": "high",
            "estimated_compute": "单卡 3090 12-24h",
            "risks": ["对密集小目标敏感度不足"],
        },
        {
            "name": "VoteNet",
            "rationale": "基于投票机制的三维目标检测, 在室内三维检测榜单上效果好",
            "required_data": "三维边界框标注 (SUN RGB-D / ScanNet)",
            "reproducibility": "medium",
            "estimated_compute": "单卡 3090 18-30h",
            "risks": ["室外场景泛化弱"],
        },
        {
            "name": "PointRCNN",
            "rationale": "两阶段三维检测器, 自带前景点分割, 适合做 3D 缺陷检测对比",
            "required_data": "三维点云 + 边界框 (KITTI)",
            "reproducibility": "medium",
            "estimated_compute": "单卡 3090 24-36h",
            "risks": ["算力需求高于单阶段方法"],
        },
    ],
    # 3D 重建 (前置任务: 多视图/单视图→三维表示)
    "3d_reconstruction": [
        {
            "name": "MVSNet",
            "rationale": "多视图三维重建经典 baseline, 代码开源成熟",
            "required_data": "多视角图像 + 相机位姿 (DTU / T&T)",
            "reproducibility": "medium",
            "estimated_compute": "单卡 3090 8-16h",
            "risks": ["纹理缺失区域重建差"],
        },
        {
            "name": "NeRF / Instant-NGP",
            "rationale": "神经辐射场三维重建, 论文引用近万, 实现路径明确",
            "required_data": "多视角图像 (LLFF / NeRF Synthetic)",
            "reproducibility": "medium",
            "estimated_compute": "单卡 3090 12-24h",
            "risks": ["训练时间长, 实时性差"],
        },
        {
            "name": "Occupancy Networks",
            "rationale": "基于占据场的三维隐式重建, 适合不规则形状 (裂缝/孔洞) 表达",
            "required_data": "三维形状 (ShapeNet)",
            "reproducibility": "medium",
            "estimated_compute": "单卡 3090 12-24h",
            "risks": ["推理速度慢"],
        },
    ],
    # 2D 检测 (裂缝/缺陷的二维检测/分类)
    "2d_detection": [
        {
            "name": "YOLOv8n",
            "rationale": "Ultralytics 官方维护, 文档完善, 单卡 3090 即可训练",
            "required_data": "公开目标检测数据集 (COCO / VisDrone / 自采缺陷数据集)",
            "reproducibility": "high",
            "estimated_compute": "单卡 3090 12-24h",
            "risks": ["小目标召回偏低"],
        },
        {
            "name": "YOLOv5s",
            "rationale": "PyTorch 官方实现, 社区资源最多",
            "required_data": "公开目标检测数据集",
            "reproducibility": "high",
            "estimated_compute": "单卡 3090 12-24h",
            "risks": ["新版本相对 v8 略落后"],
        },
        {
            "name": "Faster R-CNN",
            "rationale": "torchvision 内置, 适合做两阶段检测对比",
            "required_data": "COCO / 领域内检测数据",
            "reproducibility": "medium",
            "estimated_compute": "单卡 3090 24-36h",
            "risks": ["速度慢"],
        },
    ],
    # 2D 分割
    "2d_segmentation": [
        {
            "name": "U-Net",
            "rationale": "医学影像 / 裂缝分割经典 baseline, 论文引用过万",
            "required_data": "像素级标注的分割数据集 (Crack500 / CFD / Carvana)",
            "reproducibility": "high",
            "estimated_compute": "单卡 3060 8-16h",
            "risks": ["对细小裂缝欠分割, 可加注意力"],
        },
        {
            "name": "DeepLabV3+",
            "rationale": "torchvision 内置, 多尺度空洞卷积, 适合复杂场景分割",
            "required_data": "像素级标注",
            "reproducibility": "high",
            "estimated_compute": "单卡 3090 8-16h",
            "risks": ["小目标边界仍易模糊"],
        },
        {
            "name": "SegFormer",
            "rationale": "Transformer 轻量化分割, 论文近两年新晋 SOTA",
            "required_data": "像素级标注",
            "reproducibility": "medium",
            "estimated_compute": "单卡 3090 12-20h",
            "risks": ["数据少时容易过拟合"],
        },
    ],
    # 2D 分类
    "2d_classification": [
        {
            "name": "ResNet-50",
            "rationale": "torchvision 官方预训练, 适合做分类方向 baseline",
            "required_data": "ImageNet 或领域内分类数据",
            "reproducibility": "high",
            "estimated_compute": "单卡 3090 6-12h",
            "risks": ["对长尾类别效果一般"],
        },
        {
            "name": "ViT-B/16",
            "rationale": "torchvision 内置预训练 ViT, 适合做 Transformer 分类对比",
            "required_data": "ImageNet / 领域数据",
            "reproducibility": "high",
            "estimated_compute": "单卡 3090 12-18h",
            "risks": ["小数据易过拟合"],
        },
        {
            "name": "EfficientNet-B0",
            "rationale": "复合缩放轻量化分类, 适合边缘部署对比",
            "required_data": "ImageNet / 领域数据",
            "reproducibility": "high",
            "estimated_compute": "单卡 3090 6-10h",
            "risks": ["自定义修改空间小"],
        },
    ],
    # 时序 (SHM / 振动信号)
    "timeseries_shm": [
        {
            "name": "1D-CNN",
            "rationale": "结构健康监测时序信号经典 baseline",
            "required_data": "SHM 时序数据集 (IASC / 自采)",
            "reproducibility": "high",
            "estimated_compute": "单卡 3060 4-8h",
            "risks": ["长序列依赖建模不足"],
        },
        {
            "name": "LSTM",
            "rationale": "经典时序模型, 适合做时序损伤演化基线",
            "required_data": "时序信号",
            "reproducibility": "high",
            "estimated_compute": "单卡 3060 4-8h",
            "risks": ["长程依赖训练慢"],
        },
        {
            "name": "Transformer-Encoder",
            "rationale": "近年时序 SOTA, 适合做新方法对比",
            "required_data": "时序信号",
            "reproducibility": "medium",
            "estimated_compute": "单卡 3090 6-12h",
            "risks": ["数据需求大"],
        },
    ],
    # NLP 预训练 (BERT-style)
    "nlp_pretrain": [
        {
            "name": "BERT-base",
            "rationale": "Google 官方预训练, 论文引用过万, 下游微调路径成熟",
            "required_data": "领域语料 (中文 wiki / 领域文本)",
            "reproducibility": "high",
            "estimated_compute": "单卡 A100 3-5 天",
            "risks": ["显存要求高"],
        },
        {
            "name": "RoBERTa",
            "rationale": "BERT 的改进版, 训练更充分, 同规模效果更好",
            "required_data": "领域语料",
            "reproducibility": "high",
            "estimated_compute": "单卡 A100 3-5 天",
            "risks": ["需要大规模数据"],
        },
        {
            "name": "DistilBERT",
            "rationale": "BERT 的蒸馏版, 速度提升 60%, 适合做轻量化对比",
            "required_data": "同 BERT",
            "reproducibility": "high",
            "estimated_compute": "单卡 3090 1-2 天",
            "risks": ["精度略低于 BERT"],
        },
    ],
    # NLP 下游任务 (文本分类/QA)
    "nlp_downstream": [
        {
            "name": "TextCNN",
            "rationale": "文本分类经典 baseline, 实现极简",
            "required_data": "已标注文本",
            "reproducibility": "high",
            "estimated_compute": "单卡 3090 2-4h",
            "risks": ["对长文本建模弱"],
        },
        {
            "name": "BiLSTM + Attention",
            "rationale": "经典 RNN 基线, 适合做注意力对比",
            "required_data": "已标注文本",
            "reproducibility": "high",
            "estimated_compute": "单卡 3090 4-8h",
            "risks": ["并行性差, 训练慢"],
        },
        {
            "name": "BERT-finetune",
            "rationale": "BERT 微调下游任务, 主流做法",
            "required_data": "已标注文本",
            "reproducibility": "high",
            "estimated_compute": "单卡 3090 8-16h",
            "risks": ["依赖预训练权重"],
        },
    ],
}


# 通用兜底 (任何方向至少有 1 个 baseline)
FALLBACK_BASELINES: list[dict] = TASK_PATH_BASELINES["2d_detection"]


@dataclass
class BaselineRecommendation:
    name: str
    rationale: str
    required_data: str
    reproducibility: str  # low / medium / high
    estimated_compute: str
    risks: list[str]


def _detect_task_paths(direction: GraduationDirection) -> list[str]:
    """从方向抽取任务路径. 可能有多个路径 (例如'三维重建 + 三维检测').

    ponytail: 按 keyword 命中按顺序累加, 不重复.
    """
    text = " ".join([
        direction.title or "",
        direction.task or "",
        direction.method_route or "",
        direction.research_object or "",
    ]).lower()

    paths: list[str] = []

    # 3D 主任务判断
    is_3d = any(k in text for k in ["三维", "3d", "点云"])
    is_reconstruction = any(k in text for k in ["重建", "reconstruct", "mvs", "nerf", "occupancy", "三维表示"])
    is_detection = any(k in text for k in ["检测", "detect", "识别", "损伤", "缺陷", "裂缝"])

    if is_3d:
        # 三维成像题: 优先重建 + 检测两个任务, 这是两个独立工作量
        if is_reconstruction:
            paths.append("3d_reconstruction")
        if is_detection:
            paths.append("3d_detection")
        # 如果都不是, 默认给 3d_detection (用户提到损伤检测)
        if not paths:
            paths.append("3d_detection")

    # 2D 任务 (仅当非 NLP 时才走 2D 分类)
    if any(k in text for k in ["分割", "segment"]):
        if "2d_segmentation" not in paths:
            paths.append("2d_segmentation")
    if any(k in text for k in ["检测", "detect"]) and not is_3d:
        if "2d_detection" not in paths:
            paths.append("2d_detection")

    # NLP (优先级高于 2D 分类, 因为 "基于 BERT 的文本分类" 是 NLP 不是 CV)
    is_nlp = any(k in text for k in ["bert", "roberta", "语言模型", "nlp", "文本", "中文", "预训练"])
    if is_nlp:
        if any(k in text for k in ["预训练", "bert", "roberta", "语言模型", "transformer"]):
            if "nlp_pretrain" not in paths:
                paths.append("nlp_pretrain")
        if any(k in text for k in ["文本分类", "qa", "问答", "nli", "情感分析"]):
            if "nlp_downstream" not in paths:
                paths.append("nlp_downstream")
        # NLP 题不混入 2D 分类
    elif any(k in text for k in ["分类"]):
        if "2d_classification" not in paths:
            paths.append("2d_classification")

    # 时序
    if any(k in text for k in ["时序", "shm", "桥梁", "结构健康", "振动"]):
        if "timeseries_shm" not in paths:
            paths.append("timeseries_shm")

    return paths or ["2d_detection"]


def recommend_baselines(
    direction: GraduationDirection,
    *,
    has_dataset: bool,
    max_n: int = 3,
) -> list[BaselineRecommendation]:
    """为单个方向推荐 1-3 个 baseline.

    ponytail: 多任务路径时, 每个路径最多 1-2 个 baseline, 总数 ≤ max_n.
    """

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

    paths = _detect_task_paths(direction)
    out: list[BaselineRecommendation] = []

    # 多路径: 每个路径分配 1 个, 单路径: 给最多 max_n 个
    per_path = max(1, max_n // len(paths))
    for path in paths:
        tpls = TASK_PATH_BASELINES.get(path, FALLBACK_BASELINES)
        for tpl in tpls[:per_path]:
            out.append(BaselineRecommendation(
                name=tpl["name"],
                rationale=tpl["rationale"],
                required_data=tpl["required_data"],
                reproducibility=tpl["reproducibility"],
                estimated_compute=tpl["estimated_compute"],
                risks=list(tpl["risks"]),
            ))
        if len(out) >= max_n:
            break

    # 不够则补兜底
    while len(out) < 1:
        tpl = FALLBACK_BASELINES[len(out) % len(FALLBACK_BASELINES)]
        out.append(BaselineRecommendation(
            name=tpl["name"],
            rationale=tpl["rationale"],
            required_data=tpl["required_data"],
            reproducibility=tpl["reproducibility"],
            estimated_compute=tpl["estimated_compute"],
            risks=list(tpl["risks"]),
        ))

    return out[:max_n]


if __name__ == "__main__":
    # ponytail: self-check — 验证 3D 题拆成 重建+检测 两条路径
    d_3d = GraduationDirection(
        direction_id="d3d",
        title="基于公开点云/三维缺陷数据集的轻量化目标检测",
        research_object="工业部件表面缺陷",
        task="三维点云缺陷检测",
        method_route="轻量 3D 检测网络",
        why_graduation_friendly=[],
        fallback_route="降级二维",
    )
    bs = recommend_baselines(d_3d, has_dataset=True, max_n=3)
    print(f"3D 方向 baseline 数: {len(bs)}")
    for b in bs:
        print(f"  - {b.name}")

    # 验证 NLP 题
    d_nlp = GraduationDirection(
        direction_id="dnlp",
        title="基于 BERT 的中文文本分类预训练",
        research_object="中文领域文本",
        task="文本分类",
        method_route="BERT 微调",
        why_graduation_friendly=[],
        fallback_route="",
    )
    bs_nlp = recommend_baselines(d_nlp, has_dataset=True, max_n=3)
    print(f"NLP 方向 baseline 数: {len(bs_nlp)}")
    for b in bs_nlp:
        print(f"  - {b.name}")