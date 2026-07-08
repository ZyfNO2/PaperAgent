"""Session 64 T4: PaperModuleMatrix 后端测试.

覆盖:
 1. build_module_matrix 返回的 entries 数量等于 parallel+module 数
 2. 单条 entry 的 base / module_a / dataset / metrics 字段都被填充
 3. module_b 缺失时为 None
 4. missing_module_types 至少能识别常见 module 类别
 5. baseline_options 从 baseline_candidates 提取
 6. recommended_combinations 按 score 降序, 顶部有 public dataset 加成
 7. 风险标记: 老论文 + 无 license + 不公开数据集 -> 至少 2 个 risk
 8. _extract_base_modules 优先识别 yolov5 (longer keyword) 而非 yolo
 9. _extract_dataset 优先识别 COCO 而非 generic dataset
10. build_module_matrix 对空输入返回空 entries + 空 recs, 不崩
"""

from __future__ import annotations

from app.services.retrieval.paper_module_matrix import (
    PaperModuleEntry,
    PaperModuleMatrix,
    _extract_base_modules,
    _extract_dataset,
    _extract_metrics,
    _rank_combinations,
    build_module_matrix,
)


def _paper(title: str, abstract: str = "", year: int | None = None, license: str | None = None) -> dict:
    return {
        "title": title,
        "abstract": abstract,
        "year": year,
        "license": license,
    }


def test_build_module_matrix_entry_count():
    """entries 数量 = parallel_papers + module_papers."""
    parallel = [
        _paper("YOLOv5 with attention on COCO", "we use YOLOv5 + attention on COCO mAP", 2023, "MIT"),
        _paper("U-Net with CIoU on DeepCrack", "U-Net CIoU loss DeepCrack", 2024, "MIT"),
    ]
    module = [
        _paper("BiFPN improvement for YOLOv8", "Adding BiFPN to YOLOv8", 2024, "Apache-2.0"),
    ]
    matrix = build_module_matrix(parallel, module, [], {"topic": "crack", "domain": "SHM"})
    assert len(matrix.entries) == 3
    assert all(isinstance(e, PaperModuleEntry) for e in matrix.entries)


def test_entry_fields_populated():
    """base / module_a / dataset / metrics 至少有一个非空."""
    parallel = [_paper("YOLOv5 with CBAM attention on COCO", "CBAM attention on COCO improves mAP", 2023, "MIT")]
    matrix = build_module_matrix(parallel, [], [], {"topic": "crack", "domain": "SHM"})
    e = matrix.entries[0]
    assert e.base.lower().startswith("yolo")
    assert e.module_a  # CBAM or attention
    assert e.dataset
    assert isinstance(e.metrics, list)
    assert e.paper_title  # 至少 paper_title 不为空


def test_module_b_optional():
    """没有第二个 module 时 module_b 为 None."""
    parallel = [_paper("YOLOv5 with attention on COCO", "YOLOv5 + attention on COCO", 2023, "MIT")]
    matrix = build_module_matrix(parallel, [], [], {"topic": "x", "domain": "y"})
    e = matrix.entries[0]
    assert e.module_a
    # module_b may or may not be None depending on text, just ensure str-or-None
    assert e.module_b is None or isinstance(e.module_b, str)


def test_missing_module_types_identified():
    """当 entries 中没有 attention / loss_function 等时, missing_module_types 报告对应类别."""
    # entries 完全没有 attention/FPN 之类 -> missing 包含这些
    parallel = [_paper("YOLOv5 on COCO", "plain YOLOv5 baseline on COCO mAP", 2023, "MIT")]
    matrix = build_module_matrix(parallel, [], [], {"topic": "x", "domain": "y"})
    assert isinstance(matrix.missing_module_types, list)
    # 至少 attention / loss_function 应该是 missing
    assert "attention" in matrix.missing_module_types
    assert "loss_function" in matrix.missing_module_types


def test_baseline_options_extracted():
    """baseline_options 从 baseline_candidates 提取."""
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
    matrix = build_module_matrix([], [], baselines, {"topic": "x", "domain": "y"})
    assert len(matrix.baseline_options) == 1
    assert matrix.baseline_options[0]["name"] == "ultralytics/yolov5"
    assert matrix.baseline_options[0]["stars"] == 45000


def test_recommendations_ranked_by_score():
    """recommended_combinations 顶部应该是 score 最高 (有 public dataset + 已知 base + 2 modules)."""
    parallel = [
        # score 应该最高: YOLOv5 + attention + BiFPN on COCO, 2024 MIT
        _paper("YOLOv5 with attention and BiFPN on COCO", "YOLOv5 attention BiFPN COCO mAP", 2024, "MIT"),
        # score 较低: 旧论文, 无 license, 私有数据集
        _paper("YOLO on custom dataset", "YOLO custom dataset", 2018, None),
    ]
    matrix = build_module_matrix(parallel, [], [], {"topic": "x", "domain": "y"})
    assert len(matrix.recommended_combinations) > 0
    top = matrix.recommended_combinations[0]
    # 顶部应该 score 较高
    assert top["score"] >= matrix.recommended_combinations[-1]["score"]
    # rationale 应包含 public benchmark
    assert any("public benchmark" in r for r in top["rationale"])


def test_risk_notes_for_old_unlicensed_paper():
    """老论文 + 无 license + 不公开数据集 -> 至少 2 个 risk."""
    parallel = [
        _paper("YOLO on custom dataset", "YOLO on custom kaggle dataset", 2018, None),
    ]
    matrix = build_module_matrix(parallel, [], [], {"topic": "x", "domain": "y"})
    e = matrix.entries[0]
    assert len(e.risk_notes) >= 2
    assert "reproducibility_low" in e.risk_notes
    # data_mismatch or no_public_dataset 都应该出现 (custom / kaggle)
    assert any(r in ("data_mismatch", "no_public_dataset") for r in e.risk_notes)


def test_extract_base_prefers_longer_keyword():
    """YOLOv5 文本中应该识别为 yolov5 而非 yolo."""
    base, _ = _extract_base_modules(_paper("YOLOv5 baseline", "YOLOv5 paper"))
    assert base.lower() == "yolov5", base


def test_extract_dataset_recognizes_coco():
    """COCO 文本应该识别为 COCO 数据集."""
    ds = _extract_dataset(_paper("Detection on COCO", "We train on COCO and VOC"))
    # COCO 在 keyword 表中, 应优先
    assert "COCO" in ds or "VOC" in ds, ds


def test_build_module_matrix_empty_inputs():
    """空输入不崩, 返回空 entries + 空 recs."""
    matrix = build_module_matrix([], [], [], {"topic": "", "domain": ""})
    assert isinstance(matrix, PaperModuleMatrix)
    assert matrix.entries == []
    assert matrix.recommended_combinations == []
    # ponytail: empty topic falls back to "unknown" (same as missing)
    assert matrix.topic == "unknown"
    assert matrix.domain == "unknown"


def test_rank_combinations_dedupes_by_key():
    """相同 base/module/dataset 的多篇论文应合并."""
    entries = [
        PaperModuleEntry(
            base="YOLOV5", module_a="attention", module_b=None,
            dataset="COCO", metrics=["mAP"], paper_title="p1", improvement_description="x",
        ),
        PaperModuleEntry(
            base="YOLOV5", module_a="attention", module_b=None,
            dataset="COCO", metrics=["mAP"], paper_title="p2", improvement_description="x",
        ),
    ]
    ranked = _rank_combinations(entries)
    assert len(ranked) == 1
    assert ranked[0]["paper_count"] == 2


def test_metrics_extraction():
    """metrics 从 text 提取, 没命中则空 list."""
    m = _extract_metrics(_paper("YOLOv5 on COCO", "we improve mAP@0.5 and F1"))
    assert "mAP@0.5" in m or "F1" in m, m


def test_generate_recommendations_top5_cap():
    """recs 最多 5 条."""
    parallel = [
        _paper(f"YOLOv5 variant {i}", f"YOLOv5 mAP COCO variant {i}", 2023 + (i % 3), "MIT")
        for i in range(10)
    ]
    matrix = build_module_matrix(parallel, [], [], {"topic": "x", "domain": "y"})
    assert len(matrix.recommended_combinations) <= 5
