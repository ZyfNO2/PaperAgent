"""Comprehensive baseline catalog for research projects.

Provides structured access to baseline implementations across multiple domains
including 3D reconstruction, point cloud detection, 2D detection, and NLP.
Used for paper recommendation, reproduction guidance, and graduation-fit assessment.
"""

from typing import Optional


BASELINE_CATALOG: dict[str, dict] = {
    # 3D Reconstruction
    "COLMAP": {
        "domain": "vision_3d",
        "category": "classic_reconstruction",
        "url": "https://github.com/colmap/colmap",
        "license": "BSD",
        "reproduce_difficulty": "低",
        "graduation_fit": "high",
        "description": "Classic SfM/MVS pipeline",
    },
    "MVSNet": {
        "domain": "vision_3d",
        "category": "classic_reconstruction",
        "reproduce_difficulty": "中",
        "graduation_fit": "high",
    },
    "3DGS": {
        "domain": "vision_3d",
        "category": "emerging",
        "url": "https://github.com/graphdeco-inria/gaussian-splatting",
        "license": "CC BY-NC-SA",
        "reproduce_difficulty": "高",
        "graduation_fit": "medium",
        "description": "Novel view synthesis, high GPU memory",
    },
    "DUSt3R": {
        "domain": "vision_3d",
        "category": "emerging",
        "url": "https://github.com/naver/dust3r",
        "license": "Apache 2.0",
        "reproduce_difficulty": "高",
        "graduation_fit": "medium",
    },
    "FoundationStereo": {
        "domain": "vision_3d",
        "category": "emerging",
        "url": "https://github.com/NVlabs/FoundationStereo",
        "license": "NVIDIA",
        "reproduce_difficulty": "高",
        "graduation_fit": "low",
    },
    # Point Cloud Detection
    "PointNet++": {
        "domain": "vision_3d",
        "category": "point_cloud_detection",
        "url": "https://github.com/erikwijmans/Pointnet2_PyTorch",
        "license": "MIT",
        "reproduce_difficulty": "低",
        "graduation_fit": "high",
    },
    "OpenPCDet": {
        "domain": "vision_3d",
        "category": "point_cloud_detection",
        "url": "https://github.com/open-mmlab/OpenPCDet",
        "license": "Apache 2.0",
        "reproduce_difficulty": "低",
        "graduation_fit": "high",
    },
    # 2D Detection
    "YOLOv8": {
        "domain": "vision_2d",
        "category": "object_detection",
        "url": "https://github.com/ultralytics/ultralytics",
        "license": "AGPL-3.0",
        "reproduce_difficulty": "低",
        "graduation_fit": "high",
    },
    # NLP
    "BERT": {
        "domain": "nlp_llm",
        "category": "language_model",
        "url": "https://github.com/google-research/bert",
        "license": "Apache 2.0",
        "reproduce_difficulty": "中",
        "graduation_fit": "high",
    },
    "RoBERTa": {
        "domain": "nlp_llm",
        "category": "language_model",
        "reproduce_difficulty": "中",
        "graduation_fit": "high",
    },
    "LoRA": {
        "domain": "nlp_llm",
        "category": "fine_tuning",
        "url": "https://github.com/microsoft/LoRA",
        "license": "MIT",
        "reproduce_difficulty": "低",
        "graduation_fit": "high",
    },
}


def search_baselines(domain: str, category: Optional[str] = None) -> list[dict]:
    """Search baseline catalog by domain and optional category.

    Args:
        domain: The research domain (e.g., "vision_3d", "vision_2d", "nlp_llm").
        category: Optional category filter (e.g., "classic_reconstruction",
                  "emerging", "object_detection", "language_model").

    Returns:
        List of baseline entries matching the criteria. Each entry includes
        all catalog metadata (url, license, reproduce_difficulty,
        graduation_fit, description, etc.).
    """
    results = []
    for name, meta in BASELINE_CATALOG.items():
        if meta.get("domain") != domain:
            continue
        if category is not None and meta.get("category") != category:
            continue
        results.append({"name": name, **meta})
    return results
