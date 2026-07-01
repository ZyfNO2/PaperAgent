"""Lightweight research skill bridge inspired by AutoResearchClaw.

This module does two practical things for the research planner:
1. Build a stage-specific prompt overlay from the internal skill registry.
2. Backfill / filter candidates with deterministic, skill-like rules when
   live retrieval is weak or partially unavailable.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from ..schemas_retrieval import RetrievalCandidate
from .research_baselines import search_baselines
from .research_datasets import search_datasets
from .retrieval.dataset_enhancer import enhance_dataset
from .retrieval.repo_enhancer import enhance_repo
from .retrieval.web_dataset_search import search_web_datasets
from .skill_registry import get_skill


_STAGE_TO_SKILLS: dict[str, list[str]] = {
    "topic_understand": ["paper-card"],
    "problem_decompose": ["paper-card"],
    "search_strategy": ["paper-card", "dataset-validation", "github-baseline"],
    "tool_plan": ["paper-card", "dataset-validation", "github-baseline"],
    "candidate_screen": ["paper-card", "dataset-validation", "github-baseline"],
    "direction_advice": ["paper-card", "dataset-validation", "github-baseline"],
}


def build_skill_overlay(stage: str) -> str:
    """Return a compact prompt overlay assembled from internal skills."""
    skill_names = _STAGE_TO_SKILLS.get(stage, [])
    lines = [
        "Internal skill overlay for this stage:",
    ]
    for name in skill_names:
        meta = get_skill(name)
        if not meta:
            continue
        lines.append(f"- {name}: {meta.description}")
    lines.extend(
        [
            "- Do not fabricate references, datasets, or repos.",
            "- When evidence is weak, output explicit gaps instead of guessing.",
            "- Prefer reproducible baselines, public datasets, and runnable repos.",
        ]
    )
    return "\n".join(lines)


def repair_topic_parse_with_skill(topic_parse: dict) -> dict:
    """Fix obvious domain-routing misses before retrieval starts."""
    raw_topic = str(topic_parse.get("raw_topic") or "")
    text = raw_topic.lower()
    patched = dict(topic_parse)

    if any(token in raw_topic for token in (
        "\u6c34\u58f0",
        "\u58f0\u7eb3",
        "\u56de\u6ce2",
        "\u58f0\u5450",
    )) or any(
        token in text for token in ("underwater acoustic", "sonar", "acoustic", "shipsear", "deepship")
    ):
        patched["domain_route"] = "signal_timeseries"
        patched["domain_confidence"] = max(float(patched.get("domain_confidence") or 0.0), 0.72)
        patched["normalized_topic"] = raw_topic
        patched["task_terms"] = list(dict.fromkeys(list(patched.get("task_terms") or []) + [
            "\u5206\u7c7b",
            "\u8bc6\u522b",
        ]))
        patched["query_atoms_en"] = list(
            dict.fromkeys(list(patched.get("query_atoms_en") or []) + [
                "underwater acoustic classification",
                "acoustic classification",
                "sonar",
                "ShipsEar",
                "DeepShip",
            ])
        )
        patched["object_terms"] = list(dict.fromkeys(list(patched.get("object_terms") or []) + [
            "\u6c34\u58f0\u6570\u636e",
        ]))
        if not patched.get("method_terms"):
            patched["method_terms"] = ["PANNs", "AST", "CNN"]

    if "fdtd" in text or any(token in raw_topic for token in (
        "\u5fae\u6ce2",
        "\u4f20\u8f93\u7ebf",
        "\u7535\u78c1",
        "\u7535\u78c1\u573a",
    )):
        patched["domain_route"] = "energy_power"
        patched["domain_confidence"] = max(float(patched.get("domain_confidence") or 0.0), 0.75)
        patched["normalized_topic"] = raw_topic
        patched["query_atoms_en"] = list(
            dict.fromkeys(list(patched.get("query_atoms_en") or []) + ["FDTD", "microwave transmission line"])
        )
        patched["task_terms"] = list(dict.fromkeys(list(patched.get("task_terms") or []) + [
            "\u6570\u503c\u6a21\u62df",
        ]))
        patched["object_terms"] = list(dict.fromkeys(list(patched.get("object_terms") or []) + [
            "\u5fae\u6ce2\u4f20\u8f93\u7ebf",
        ]))
        if not patched.get("method_terms"):
            patched["method_terms"] = ["FDTD", "openEMS", "Meep"]

    if any(token in raw_topic for token in (
        "\u56fd\u516d",
        "\u67f4\u6cb9\u8f66",
        "\u6392\u653e",
        "\u8fdc\u7a0b\u76d1\u63a7",
        "\u91cd\u578b\u67f4\u6cb9\u8f66",
    )) or any(
        token in text for token in ("diesel", "emission", "obd", "remote monitoring", "telematics")
    ):
        patched["domain_route"] = "control_monitoring"
        patched["domain_confidence"] = max(float(patched.get("domain_confidence") or 0.0), 0.74)
        patched["normalized_topic"] = raw_topic
        patched["task_terms"] = list(dict.fromkeys(list(patched.get("task_terms") or []) + [
            "\u6392\u653e\u76d1\u63a7",
            "\u8fdc\u7a0b\u76d1\u6d4b",
        ]))
        patched["query_atoms_en"] = list(
            dict.fromkeys(list(patched.get("query_atoms_en") or []) + [
                "heavy-duty diesel emission monitoring",
                "remote OBD emissions monitoring",
                "vehicle telematics",
            ])
        )
        patched["object_terms"] = list(dict.fromkeys(list(patched.get("object_terms") or []) + [
            "\u91cd\u578b\u67f4\u6cb9\u8f66",
        ]))
        if not patched.get("method_terms"):
            patched["method_terms"] = ["OBD", "CAN", "telematics"]

    return patched


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return cleaned[:48] or uuid.uuid4().hex[:8]


def _skill_candidate(
    *,
    project_id: str,
    candidate_type: str,
    title: str,
    url: str | None,
    abstract: str | None,
    source: str = "manual_fallback",
    matched_keywords: list[str] | None = None,
    raw: dict[str, Any] | None = None,
    license: str | None = None,
    stars: int | None = None,
) -> dict[str, Any]:
    candidate = RetrievalCandidate(
        candidate_id=f"skill_{candidate_type}_{_slug(title)}",
        project_id=project_id,
        candidate_type=candidate_type,  # type: ignore[arg-type]
        source=source,  # type: ignore[arg-type]
        title=title,
        url=url,
        abstract=abstract,
        matched_keywords=matched_keywords or [],
        retrieval_score=0.72,
        license=license,
        stars=stars,
        raw=raw or {},
    )
    dumped = candidate.model_dump()
    dumped["skill_sources"] = []
    return dumped


def _derive_web_dataset_atoms(topic_parse: dict) -> dict:
    raw_topic = str(topic_parse.get("raw_topic", ""))
    object_terms = list(topic_parse.get("object_terms") or [])
    object_cn = object_terms[0] if object_terms else raw_topic
    object_en = ""
    for token in topic_parse.get("query_atoms_en", []) or []:
        if token and token.lower() not in {"dataset", "benchmark", "github", "baseline", "survey"}:
            object_en = token
            break
    return {
        "object_cn": object_cn,
        "object_en": object_en,
        "engineering_objects": object_terms,
    }


def _repo_topic_score(topic_parse: dict, candidate: dict) -> float:
    text_parts = [
        str(candidate.get("title") or ""),
        str(candidate.get("abstract") or ""),
        str((candidate.get("repo_full_name") or "")),
    ]
    raw = candidate.get("raw") or {}
    if isinstance(raw, dict):
        text_parts.append(" ".join(str(t) for t in raw.get("topics", []) or []))
        text_parts.append(str(raw.get("description") or ""))
    haystack = " ".join(text_parts).lower()

    signals = 0
    total = 0
    for key in ("method_terms", "task_terms", "object_terms", "query_atoms_en", "query_atoms_zh"):
        for token in topic_parse.get(key, []) or []:
            token_l = str(token).strip().lower()
            if not token_l or len(token_l) < 2:
                continue
            total += 1
            if token_l in haystack:
                signals += 1
    if total == 0:
        return 0.0
    return round(signals / total, 3)


def apply_skill_backfill(topic_parse: dict, candidates: list[dict]) -> list[dict]:
    """Inject deterministic baseline/dataset candidates when live retrieval is weak."""
    project_id = str(topic_parse.get("_project_id") or "skill-backfill")
    domain = str(topic_parse.get("domain_route") or "unknown")
    existing_ids = {str(c.get("candidate_id", "")) for c in candidates}

    out = list(candidates)

    # 1) dataset catalog fallback
    if not any(c.get("candidate_type") == "dataset" for c in candidates):
        for entry in search_datasets(domain)[:3]:
            cand = _skill_candidate(
                project_id=project_id,
                candidate_type="dataset",
                title=entry["name"],
                url=entry.get("url"),
                abstract=f"Curated dataset fallback for {domain}: {entry.get('task', '')}",
                matched_keywords=list(topic_parse.get("task_terms") or []),
                raw={"skill_role": "dataset_catalog", **entry},
                license=entry.get("license"),
            )
            if cand["candidate_id"] not in existing_ids:
                cand["skill_sources"] = ["dataset-validation"]
                out.append(cand)
                existing_ids.add(cand["candidate_id"])

    # 2) web dataset fallback for weak domains
    if not any(c.get("candidate_type") == "dataset" for c in out):
        for web_ds in search_web_datasets(_derive_web_dataset_atoms(topic_parse), domain=domain)[:3]:
            cand = _skill_candidate(
                project_id=project_id,
                candidate_type="dataset",
                title=web_ds.name,
                url=web_ds.url,
                abstract=f"Web dataset fallback from {web_ds.source}: {web_ds.task_type or ''}",
                matched_keywords=list(topic_parse.get("task_terms") or []),
                raw={"skill_role": "web_dataset_seed", **web_ds.model_dump()},
                license=web_ds.license,
            )
            if cand["candidate_id"] not in existing_ids:
                cand["skill_sources"] = ["dataset-validation"]
                out.append(cand)
                existing_ids.add(cand["candidate_id"])

    # 3) baseline catalog fallback
    has_baseline_seed = any(
        (c.get("raw") or {}).get("skill_role") == "baseline_catalog"
        for c in out
    )
    if not has_baseline_seed:
        for entry in search_baselines(domain)[:3]:
            cand = _skill_candidate(
                project_id=project_id,
                candidate_type="repo",
                title=entry["name"],
                url=entry.get("url"),
                abstract=f"Curated baseline fallback for {domain}: {entry.get('description', '')}",
                matched_keywords=list(topic_parse.get("method_terms") or []),
                raw={"skill_role": "baseline_catalog", **entry},
                license=entry.get("license"),
            )
            if cand["candidate_id"] not in existing_ids:
                cand["skill_sources"] = ["github-baseline"]
                out.append(cand)
                existing_ids.add(cand["candidate_id"])

    return out


def filter_repo_candidates_with_skill(topic_parse: dict, candidates: list[dict]) -> list[dict]:
    """Drop generic GitHub repos that do not match the topic well."""
    filtered: list[dict] = []
    for candidate in candidates:
        if candidate.get("candidate_type") != "repo":
            filtered.append(candidate)
            continue

        raw = candidate.get("raw") or {}
        if isinstance(raw, dict) and raw.get("skill_role") == "baseline_catalog":
            filtered.append(candidate)
            continue

        try:
            repo = RetrievalCandidate.model_validate(candidate)
            enhancement = enhance_repo(repo)
        except Exception:  # noqa: BLE001
            filtered.append(candidate)
            continue

        topic_score = _repo_topic_score(topic_parse, candidate)
        warnings = list(candidate.get("warnings") or [])
        warnings.extend(enhancement.warnings)
        candidate["warnings"] = warnings
        candidate["quality_hints"] = list(candidate.get("quality_hints") or []) + [
            f"repo_topic_score:{topic_score}",
            "skill:github-baseline",
        ]

        generic_name = str(candidate.get("title") or "").lower()
        too_generic = generic_name in {
            "tensorflow",
            "transformers",
            "awesome-machine-learning",
            "pytorch",
        }
        if too_generic and topic_score < 0.2:
            continue
        if topic_score < 0.12 and "unclear_training_script" in enhancement.warnings:
            continue
        filtered.append(candidate)
    return filtered


def enrich_dataset_candidates_with_skill(candidates: list[dict]) -> list[dict]:
    """Annotate dataset candidates with dataset-validation style hints."""
    out: list[dict] = []
    for candidate in candidates:
        if candidate.get("candidate_type") != "dataset":
            out.append(candidate)
            continue
        try:
            dataset = RetrievalCandidate.model_validate(candidate)
            enhancement = enhance_dataset(dataset)
        except Exception:  # noqa: BLE001
            out.append(candidate)
            continue
        candidate["warnings"] = list(candidate.get("warnings") or []) + list(enhancement.warnings)
        candidate["quality_hints"] = list(candidate.get("quality_hints") or []) + [
            f"dataset_task_match:{enhancement.task_match_score}",
            "skill:dataset-validation",
        ]
        if enhancement.license:
            candidate["license"] = enhancement.license
        out.append(candidate)
    return out
