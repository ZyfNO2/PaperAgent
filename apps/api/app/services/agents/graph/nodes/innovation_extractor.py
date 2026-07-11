"""innovation_extractor — Re1.4 MVP node."""
import re
import time
import logging
from typing import Any
from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)

from ._util import emit_trace as _emit

# Re3.9: Cross-node dataset scan list — same as dataset_repo_extractor fallback list.
# Imported lazily to avoid circular import at module load.
_DS_FALLBACK_NAMES = [
    "NEU-DET", "GC10-DET", "MVTec AD",
    "KITTI", "TUM RGB-D", "EuRoC", "Bonn", "ScanNet", "Middlebury",
    "DTU", "ETH3D", "Tanks and Temples", "BlendedMVS",
    "COCO", "Pascal VOC", "ImageNet", "CIFAR", "MNIST",
    "Cityscapes", "nuScenes", "DOTA", "VisDrone", "UAVDT", "Waymo",
    "DIOR", "AID", "NWPU-RESISC45", "xView",
    "LIDC-IDRI", "MIMIC-CXR", "ChestX-ray14", "NIH ChestX-ray",
    "BRATS", "ISIC", "TCIA", "PACS", "CheXpert", "LUNA16",
    "YCB", "GraspNet", "DexNet", "EGAD",
    "SURREAL", "Human3.6M", "AMASS", "SMPL",
    "Make3D", "NYU Depth V2", "NYUv2", "DIODE",
    "DeepCrack", "CrackTree", "GAPs384", "CRACK500", "SDNET2018",
    "ShapeNet", "ModelNet", "PlantVillage",
    "ADE20K", "VOC2012", "Synthia", "FlyingChairs", "Sintel",
    "TartanAir", "Matterport3D", "Stanford2D3D", "BDD100K",
]


def _cross_node_dataset_scan(
    innovation_points: list[dict[str, Any]],
    stitching_plan: dict[str, Any],
    existing_ds: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Scan innovation_points + stitching_plan text for dataset names missed by dataset_repo_extractor."""
    existing_names = {str(d.get("name", "")).lower() for d in existing_ds}

    scan_parts = []
    for ip in innovation_points:
        scan_parts.append(str(ip.get("description", "")))
        scan_parts.append(str(ip.get("stitching_plan", "")))
    scan_parts.append(str(stitching_plan.get("baseline_model", "")))
    scan_parts.append(str(stitching_plan.get("module_b", "")))
    scan_parts.append(str(stitching_plan.get("module_c", "")))
    scan_parts.extend(str(s) for s in stitching_plan.get("stitching_steps", []))
    scan_text = " ".join(scan_parts).lower()

    new_ds: list[dict[str, Any]] = []
    for ds_name in _DS_FALLBACK_NAMES:
        if ds_name.lower() in scan_text and ds_name.lower() not in existing_names:
            new_ds.append({
                "from_paper": "innovation_extractor_cross_scan",
                "linked_paper_id": re.sub(r"[^a-z0-9]+", "-", ds_name.lower()).strip("-") or "unknown",
                "kind": "dataset",
                "name": ds_name,
                "url": None,
                "source": "cross_node:innovation_extractor",
                "availability": "named",
                "status": "found",
                "reproducibility_hint": "",
                "risk": "",
            })
            existing_names.add(ds_name.lower())
    return new_ds


def _heuristic(state):
    baselines = state.get("baseline_candidates") or []
    parallels = state.get("parallel_candidates") or []
    b_title = (baselines[0].get("title", "") if baselines else "未知baseline")
    b_id = (baselines[0].get("paper_id") or baselines[0].get("doi") or b_title) if baselines else ""
    p_title = (parallels[0].get("title", "") if parallels else "未知parallel")
    return {
        "innovation_points": [{"description": f"在{b_title}基础上借鉴{p_title}的模块",
                                "baseline_used": b_title, "stitched_modules": [p_title],
                                "stitching_plan": "待LLM生成", "estimated_difficulty": "中",
                                "evidence_ref": b_title,
                                "candidate_ids": [b_id] if b_id else [],
                                "evidence_snippets": [],
                                "novelty_score": 5.0,
                                "feasibility_score": 5.0,
                                "evidence_score": 5.0 if b_id else 0.0,
                                "status": "pending" if b_id else "needs_evidence"}],
        "stitching_plan": {"baseline_model": b_title, "module_b": p_title, "module_c": "",
                           "stitching_steps": ["1. 复现baseline", "2. 提取parallel模块", "3. 拼接测试"],
                           "risk_notes": ["heuristic fallback，需人工确认"]}
    }

def innovation_extractor_node(state: ResearchState) -> dict[str, Any]:
    t0 = time.time()
    topic = state.get("topic") or ""
    baselines = state.get("baseline_candidates") or []
    parallels = state.get("parallel_candidates") or []

    try:
        from apps.api.app.services.agents.graph.validators.llm_output_validator import (
            call_json_with_validation,
        )
        from apps.api.app.services.agents.prompts import innovation_extractor as P
        built = P.build(topic, baselines, parallels)
        out = call_json_with_validation(
            built["user"],
            system=built["system"],
            node_name="innovation_extractor",
            profile="fast_json",
            max_tokens=2000,
            timeout=30,
            fallback=_heuristic(state),
        )
        if isinstance(out, dict) and ("innovation_points" in out or "stitching_plan" in out):
            result_inn = out.get("innovation_points", [])
            result_plan = out.get("stitching_plan", {})
        else:
            h = _heuristic(state)
            result_inn, result_plan = h["innovation_points"], h["stitching_plan"]
        prov = "fast_json"
    except Exception as exc:
        logger.warning("innovation_extractor LLM failed: %s — heuristic fallback", exc)
        h = _heuristic(state)
        result_inn, result_plan = h["innovation_points"], h["stitching_plan"]
        prov = "heuristic"

    # Re3.9: Cross-node dataset补全
    existing_ds = list(state.get("dataset_candidates") or [])
    new_ds = _cross_node_dataset_scan(result_inn, result_plan, existing_ds)
    merged_ds = existing_ds + new_ds

    # Re4.3: Binding validator — mark needs_evidence for innovations without evidence
    try:
        from apps.api.app.services.agents.graph.validators.binding_validator import (
            _build_evidence_index,
            validate_innovations,
        )
        evidence_index = _build_evidence_index(state)
        validated_inns, _inn_issues = validate_innovations(result_inn, evidence_index)
        result_inn = [ip.model_dump() for ip in validated_inns]
    except Exception as exc:
        logger.debug("innovation_extractor binding validator skipped: %s", exc)

    trace = _emit("innovation_extractor", t0,
                  {"n_baseline": len(baselines), "n_parallel": len(parallels)},
                  {"n_innovation": len(result_inn), "n_datasets_found": len(new_ds)},
                  [{"tool": "innovation_extractor.llm" if prov != "heuristic" else "heuristic"}],
                  prov, [],
                  state_keys=["innovation_points", "stitching_plan",
                              "dataset_candidates", "trace_events"])
    return {"innovation_points": result_inn, "stitching_plan": result_plan,
            "dataset_candidates": merged_ds,
            "trace_events": [trace]}
