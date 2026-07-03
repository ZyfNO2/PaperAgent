"""Re06 — Evidence role classification (topic / proxy / pretrain / generic).

Returns a structured role tag + human-readable reason for every
dataset / baseline / parallel candidate, based purely on metadata
(title, abstract, url, doi, source_type) — NO network call, NO LLM,
NO substring-on-local-blacklist judgement.

This is the role axis half of Re06's evidence consistency audit.
The other half is ``evidence_consistency.py`` (axis coverage +
consistency_status). Both are wired into ``compute_resource_status``
to replace the old ``STRONG_NOISE_TOKENS`` keyword gate.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


# Canonical pretrain / generic benchmark families. Kept short on
# purpose: the role is "this dataset is generic by reputation", not
# "this dataset exists at all".  If the rule-of-thumb category is not
# here, the candidate falls back to proxy/topic based on axis match.
# Note: KITTI / KITTI-360 are deliberately NOT here — for a
# point-cloud-completion topic they are proxy (autonomous-driving
# benchmark), not pretrain.  Same for ScanNet/Matterport3D/ModelNet:
# they live here because they're canonical, but the topic-axis
# branch can still promote them to topic_dataset.
_GENERIC_PRETRAIN_FAMILIES: tuple[str, ...] = (
    "COCO", "ImageNet", "Pascal VOC", "PASCAL VOC", "Cityscapes",
    "DOTA", "DOTA-v1.5", "DOTA-v2", "DIOR", "LEVIR-CD", "NWPU-RESISC45",
    "AID",
    "ShapeNet", "ShapeNetCore", "ModelNet10", "ModelNet40",
    "PCN", "Completion3D", "MVPG", "DTU", "ETH3D", "Tanks and Temples",
    "BlendedMVS", "TUM RGBD", "NeRF", "LLFF", "ApolloScape", "Waymo",
    "MVTec AD", "VisA", "NEU-DET", "Severstal", "GC10-DET",
    "PCB-defect", "STI",
)


@dataclass
class DatasetRole:
    role: str           # topic | proxy | pretrain | generic | rejected
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "reason": self.reason}


def classify_dataset_role(
    candidate: dict[str, Any],
    *,
    topic_atoms: dict[str, list[str]] | None = None,
) -> DatasetRole:
    """Classify a dataset candidate's role against the topic atoms.

    Parameters
    ----------
    candidate
        Must contain at least ``title``; optional ``name``, ``abstract``,
        ``url``, ``source_type``.
    topic_atoms
        Dict shaped ``{"task": [...], "object": [...], "scenario": [...]}``
        — used for axis matching when present.
    """
    name = (candidate.get("name") or candidate.get("title") or "").strip()
    abstract = (candidate.get("abstract") or candidate.get("snippet") or "").strip()
    haystack = " ".join([name, abstract]).strip()
    name_lc = name.lower()

    if not haystack:
        return DatasetRole(
            role="rejected",
            reason="insufficient_metadata: dataset candidate lacks title and abstract",
        )

    # 1. Topic axis match (HIGHER priority than pretrain list) — if
    #    the candidate name shares tokens with topic atoms, it is a
    #    topic_dataset regardless of whether it is on the canonical
    #    pretrain roster.
    if topic_atoms:
        all_atoms: list[str] = []
        for k in ("task", "object", "method", "scenario"):
            for a in (topic_atoms.get(k) or []):
                if a:
                    all_atoms.append(a.lower())
        if all_atoms and any(a in name_lc for a in all_atoms):
            return DatasetRole(
                role="topic",
                reason="name shares tokens with topic atoms",
            )

    # 2. Pretrain / generic family match — name token appears verbatim
    #    in the canonical pretrain list.  This is a name match, not a
    #    substring-on-blacklist: we look up the candidate's *name*
    #    (case-sensitive token) in a fixed roster of well-known
    #    benchmark families.  NOT a domain blocklist.
    for fam in _GENERIC_PRETRAIN_FAMILIES:
        if fam.lower() == name_lc or re.search(
            r"(^|[\s/_\-])" + re.escape(fam) + r"($|[\s/_\-])",
            haystack, flags=re.IGNORECASE,
        ):
            return DatasetRole(
                role="pretrain",
                reason=f"canonical pretrain/benchmark family: {fam}",
            )

    # 3. Source type / URL hints
    src = (candidate.get("source_type") or candidate.get("source") or "").lower()
    url = (candidate.get("url") or "").lower()
    if "huggingface" in src or "huggingface.co" in url:
        # HuggingFace datasets are often domain-specific benchmarks —
        # treat as proxy unless topic-axis match already promoted it.
        return DatasetRole(
            role="proxy",
            reason="huggingface source — domain benchmark, axis not directly aligned",
        )

    # 4. Generic vision dataset fallback
    if re.search(
        r"\b(coco|imagenet|pascal|cityscapes)\b", haystack, flags=re.IGNORECASE,
    ):
        return DatasetRole(
            role="generic",
            reason="generic vision dataset family",
        )

    # 5. Default: insufficient to claim topic; mark proxy
    return DatasetRole(
        role="proxy",
        reason="no direct axis match; retained as proxy/transfer evidence",
    )


# ---- baseline / parallel role ----------------------------------------------

def classify_baseline_role(
    candidate: dict[str, Any],
    *,
    topic_atoms: dict[str, list[str]] | None = None,
) -> dict[str, str]:
    """Classify a baseline candidate as direct / proxy / generic.

    Returns ``{"role": "direct|proxy|generic", "reason": "..."}``.
    """
    title = (candidate.get("title") or "").strip()
    abstract = (candidate.get("abstract") or candidate.get("snippet") or "").strip()
    haystack = (title + " " + abstract).strip().lower()
    if not haystack:
        return {"role": "generic", "reason": "insufficient_metadata"}

    # Generic framework names — universal CV scaffolding, not a
    # domain paper. These can serve as baselines but must be flagged
    # as generic in reports.
    _GENERIC_FRAMEWORKS = (
        "yolo", "faster r-cnn", "retinanet", "centernet", "efficientdet",
        "u-net", "unet", "pointnet", "pointnet++", "dgcnn", "pct:",
        "vit", "swin", "deeplab", "mask rcnn", "mask r-cnn",
        "transformer", "bert", "roberta",
    )
    title_lc = title.lower()
    for fw in _GENERIC_FRAMEWORKS:
        if fw in title_lc:
            # Still check axis — if topic atoms also match, this is
            # domain-adapted direct baseline, not generic.
            if topic_atoms:
                obj_atoms = [a.lower() for a in (topic_atoms.get("object") or [])]
                if any(a and a in title_lc for a in obj_atoms):
                    return {
                        "role": "direct",
                        "reason": f"generic framework ({fw}) adapted to topic object",
                    }
            return {
                "role": "generic",
                "reason": f"generic CV/framework paper: {fw}",
            }

    # Topic axis hit?
    if topic_atoms:
        all_atoms: list[str] = []
        for k in ("task", "object", "method", "scenario"):
            for a in (topic_atoms.get(k) or []):
                if a:
                    all_atoms.append(a.lower())
        if all_atoms:
            hits = [a for a in all_atoms if a in title_lc or a in haystack]
            if len(hits) >= 2:
                return {
                    "role": "direct",
                    "reason": f"shares {len(hits)} axis tokens with topic atoms: {hits[:3]}",
                }
            if len(hits) == 1:
                return {
                    "role": "proxy",
                    "reason": f"shares 1 axis token ({hits[0]}) — partial match",
                }

    return {
        "role": "generic",
        "reason": "no axis match — usable as scaffold only",
    }


def classify_parallel_role(
    candidate: dict[str, Any],
    *,
    topic_atoms: dict[str, list[str]] | None = None,
) -> dict[str, str]:
    """Parallel-axis candidates: same task family, different object/method.

    Returns ``{"role": "direct|proxy", "reason": "..."}``.
    """
    title = (candidate.get("title") or "").strip()
    title_lc = title.lower()
    if not title:
        return {"role": "proxy", "reason": "insufficient_metadata"}

    if not topic_atoms:
        return {"role": "proxy", "reason": "no topic atoms supplied"}

    task_atoms = [a.lower() for a in (topic_atoms.get("task") or []) if a]
    obj_atoms = [a.lower() for a in (topic_atoms.get("object") or []) if a]

    task_hit = any(a in title_lc for a in task_atoms)
    obj_hit = any(a in title_lc for a in obj_atoms)

    if task_hit and not obj_hit:
        return {
            "role": "direct",
            "reason": "shares task axis, different object — true parallel",
        }
    if task_hit and obj_hit:
        return {
            "role": "direct",
            "reason": "shares task and object — overlapping method",
        }
    return {
        "role": "proxy",
        "reason": "task axis not directly aligned",
    }