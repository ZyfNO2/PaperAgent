"""Comprehensive dataset catalog for research projects.

Provides structured access to benchmark datasets across multiple domains
including 3D vision, 2D vision, and NLP tasks. Used for paper recommendation
and baseline reproduction guidance.
"""

from typing import Optional


DATASET_CATALOG: dict[str, dict] = {
    # 3D / Point Cloud Anomaly Detection
    "MVTec 3D-AD": {
        "domain": "vision_3d",
        "task": "anomaly_detection",
        "url": "https://www.mvtec.com/research-teaching/datasets/mvtec-3d-ad",
        "license": "MVTec TOS",
        "scale": "RGB+3D point cloud, multiple industrial objects",
        "reproduce_difficulty": "低",
    },
    "Real3D-AD": {
        "domain": "vision_3d",
        "task": "point_cloud_anomaly_detection",
        "url": "https://github.com/M-3LAB/Real3D-AD",
        "license": "MIT",
        "reproduce_difficulty": "中",
    },
    "ModelNet40": {
        "domain": "vision_3d",
        "task": "3d_classification",
        "url": "https://modelnet.princeton.edu/",
        "reproduce_difficulty": "低",
    },
    "ScanNet": {
        "domain": "vision_3d",
        "task": "3d_reconstruction",
        "url": "http://www.scan-net.org/",
        "reproduce_difficulty": "中",
    },
    "SUN RGB-D": {
        "domain": "vision_3d",
        "task": "rgbd_scene",
        "url": "https://rgbd.cs.princeton.edu/",
        "reproduce_difficulty": "低",
    },
    # 2D Industrial Defect Detection
    "NEU-DET": {
        "domain": "vision_2d",
        "task": "defect_detection",
        "url": "http://faculty.neu.edu.cn/songkechen/",
        "license": "Academic",
        "scale": "1800 images, 6 defect classes",
        "reproduce_difficulty": "低",
    },
    "GC10-DET": {
        "domain": "vision_2d",
        "task": "defect_detection",
        "url": "https://github.com/lvxiaoming2019/GC10-DET",
        "license": "Academic",
        "scale": "3570 images, 10 classes",
        "reproduce_difficulty": "低",
    },
    # NLP / Text
    "ChnSentiCorp": {
        "domain": "nlp_llm",
        "task": "sentiment_analysis",
        "url": "https://huggingface.co/datasets/ChnSentiCorp",
        "license": "Open",
        "reproduce_difficulty": "低",
    },
    "CLUE/TNEWS": {
        "domain": "nlp_llm",
        "task": "text_classification",
        "url": "https://www.cluebenchmarks.com/",
        "license": "Academic",
        "reproduce_difficulty": "低",
    },
    # Signal / acoustic classification
    "ShipsEar": {
        "domain": "signal_timeseries",
        "task": "underwater_acoustic_classification",
        "url": "https://github.com/LCAV/pyroomacoustics-data",
        "license": "Academic",
        "reproduce_difficulty": "medium",
    },
    "DeepShip": {
        "domain": "signal_timeseries",
        "task": "underwater_acoustic_classification",
        "url": "https://github.com/yvanscher/DeepShip",
        "license": "Research",
        "reproduce_difficulty": "medium",
    },
    "DCASE 2018 Task 1": {
        "domain": "signal_timeseries",
        "task": "acoustic_classification",
        "url": "https://dcase.community/challenge2018/task-acoustic-scene-classification",
        "license": "Academic",
        "reproduce_difficulty": "low",
    },
}


def search_datasets(domain: str, task: Optional[str] = None) -> list[dict]:
    """Search dataset catalog by domain and optional task.

    Args:
        domain: The research domain (e.g., "vision_3d", "vision_2d", "nlp_llm").
        task: Optional task filter (e.g., "anomaly_detection", "classification").

    Returns:
        List of dataset entries matching the criteria. Each entry includes
        all catalog metadata (url, license, scale, reproduce_difficulty, etc.).
    """
    results = []
    for name, meta in DATASET_CATALOG.items():
        if meta.get("domain") != domain:
            continue
        if task is not None and meta.get("task") != task:
            continue
        results.append({"name": name, **meta})
    return results
