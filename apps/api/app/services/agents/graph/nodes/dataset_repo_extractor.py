"""LangGraph node: dataset_repo_extractor — extract dataset + repo links per paper.

Replaces content.dataset_repo_extractor_node (agent C wires it in via
nodes/__init__). Same signature so a 1-line registry change picks it up.

For each verified paper (cap 8, SOP §5.7) call the LLM with
re11_dataset_repo_extractor; collect dataset_candidates and repo_candidates
deduped by url or name.

Output fields: dataset_candidates, repo_candidates, evidence_audit, trace_events.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _emit(node: str, t0: float, ins: dict, out: dict,
          tools: list, prov: str, errs: list) -> dict[str, Any]:
    return {
        "node": node,
        "started_at": _now_iso(),
        "input_summary": ins,
        "output_summary": out,
        "tool_calls": tools,
        "errors": errs,
        "provider": prov,
        "ended_at": _now_iso(),
        "elapsed_s": round(time.time() - t0, 3),
    }


def _slug_of(text: str) -> str:
    import re
    s = (text or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-") or "unknown"


def dataset_repo_extractor_node(state: ResearchState) -> dict[str, Any]:
    """Extract dataset + repo links from verified papers in parallel.

    Up to ``limit`` verified papers (default 8) are processed concurrently via
    ThreadPoolExecutor. Each extraction is an independent LLM call to
    ``re11_dataset_repo_extractor``; parallelising reduces wall-clock time
    from ~8×4s=30s to ~5-8s.
    """
    papers = list(state.get("verified_papers") or [])
    t0 = time.time()

    existing_ds = list(state.get("dataset_candidates") or [])
    existing_repo = list(state.get("repo_candidates") or [])
    audit = dict(state.get("evidence_audit") or {})

    errors: list[dict[str, Any]] = []
    tried = 0
    ok_count = 0

    ds_seen: set[str] = set()
    repo_seen: set[str] = set()

    def ds_key(d: dict[str, Any]) -> str:
        return (d.get("url") or d.get("name") or "").strip().lower()

    def repo_key(r: dict[str, Any]) -> str:
        return (r.get("url") or r.get("mentioned_repo") or "").strip().lower()

    for d in existing_ds:
        k = ds_key(d)
        if k:
            ds_seen.add(k)
    for r in existing_repo:
        k = repo_key(r)
        if k:
            repo_seen.add(k)

    limit = int(state.get("user_constraints", {}).get("max_dataset_paper_lookups", 8)
                  if isinstance(state.get("user_constraints"), dict) else 8)
    limit = max(0, min(8, limit))
    target_papers = papers[:limit]

    # Re2.2 fix: extract repos from source=github papers directly (no LLM needed)
    github_repos: list[dict[str, Any]] = []
    non_github_papers: list[dict[str, Any]] = []
    for p in target_papers:
        source = (p.get("source") or "").lower()
        title = (p.get("title") or p.get("name") or "").strip()
        url = (p.get("url") or "").strip()
        if source == "github" and (title or url):
            repo_name = title or url
            repo_url = url or f"https://github.com/{repo_name}"
            # Re2.2-fix: convert GitHub API URLs to human-readable format
            if "api.github.com/repos/" in repo_url:
                path = repo_url.split("api.github.com/repos/", 1)[-1].rstrip("/")
                repo_url = f"https://github.com/{path}"
            rrec = {
                "from_paper": title or "github_search",
                "linked_paper_id": _slug_of(repo_name),
                "kind": "repo",
                "url": repo_url,
                "mentioned_repo": repo_name,
                "source": "github_search",
                "availability": "url" if repo_url.startswith("http") else "named",
                "status": "found",
                "reproducibility_hint": "",
                "risk": "",
            }
            k = repo_key(rrec)
            if k and k not in repo_seen:
                github_repos.append(rrec)
                repo_seen.add(k)
        else:
            non_github_papers.append(p)

    # LLM extraction for non-github papers
    target_papers = non_github_papers

    def _extract_one(paper: dict[str, Any]) -> dict[str, Any]:
        """Extract datasets + repos from a single paper. Returns result dict."""
        title = (paper.get("title") or paper.get("name") or "").strip()
        if not title:
            return {"tried": 0, "ok": 0, "datasets": [], "repos": []}
        paper_slug = _slug_of(title)
        try:
            from apps.api.app.services import llm_router
            from apps.api.app.services.agents.prompts import re11_dataset_repo_extractor as P
            built = P.build(title, paper.get("abstract") or paper.get("snippet") or "")
            out = llm_router.call_json(
                built["user"], system=built["system"], profile="fast_json",
                max_tokens=700,
                timeout=max(5, _env_int("DATASET_REPO_TIMEOUT_S", 45)),
                expected="list",
                schema_hint=("list of one object with keys: dataset_name, "
                             "benchmark_name, official_code_url, project_page_url, "
                             "supplementary_url, paper_mentioned_repo, "
                             "paper_used_baselines (list[str]), missing (list[str]), "
                             "status (found|not_found_in_paper|url_missing_needs_repair)"),
            )
            item: dict[str, Any]
            if isinstance(out, list):
                item = out[0] if out else {}
                if not isinstance(item, dict):
                    item = {}
            elif isinstance(out, dict):
                wrapped = out.get("extractions") or out.get("results")
                if isinstance(wrapped, list) and wrapped:
                    item = wrapped[0] if isinstance(wrapped[0], dict) else {}
                else:
                    item = out
            else:
                item = {}

            status = (item.get("status") or "not_found_in_paper")
            ds_found: list[dict[str, Any]] = []
            repo_found: list[dict[str, Any]] = []
            if status in ("found", "url_missing_needs_repair"):
                ds_name = (item.get("dataset_name") or "").strip()
                official = (item.get("official_code_url") or "").strip()
                mentioned = (item.get("paper_mentioned_repo") or "").strip()
                proj = (item.get("project_page_url") or "").strip()
                supp = (item.get("supplementary_url") or "").strip()
                if ds_name or official:
                    rec = {
                        "from_paper": title, "linked_paper_id": paper_slug,
                        "kind": "dataset", "name": ds_name or None,
                        "url": official or None, "source": "paper_abstract",
                        "availability": "url" if official else ("named" if ds_name else "unknown"),
                        "status": status, "reproducibility_hint": "", "risk": "",
                    }
                    if ds_key(rec) and ds_key(rec) not in ds_seen:
                        ds_found.append(rec)
                if official or mentioned:
                    url = official or mentioned
                    rrec = {
                        "from_paper": title, "linked_paper_id": paper_slug,
                        "kind": "repo", "url": url,
                        "mentioned_repo": mentioned or None,
                        "source": "paper_official_link",
                        "availability": "url" if url.startswith("http") else "named",
                        "status": status, "reproducibility_hint": "", "risk": "",
                    }
                    if repo_key(rrec) and repo_key(rrec) not in repo_seen:
                        repo_found.append(rrec)
                for extra_url in (proj, supp):
                    if extra_url:
                        rrec = {
                            "from_paper": title, "linked_paper_id": paper_slug,
                            "kind": "repo", "url": extra_url,
                            "mentioned_repo": mentioned or None,
                            "source": "paper_metadata_url",
                            "availability": "url", "status": status,
                            "reproducibility_hint": "", "risk": "",
                        }
                        if repo_key(rrec) and repo_key(rrec) not in repo_seen:
                            repo_found.append(rrec)
            return {
                "tried": 1,
                "ok": 1 if (ds_found or repo_found) else 0,
                "datasets": ds_found,
                "repos": repo_found,
            }
        except BaseException as exc:
            logger.debug("dataset_repo extraction failed for %r: %s",
                         title, type(exc).__name__)
            errors.append({"node": "dataset_repo", "for_paper": title,
                           "error": type(exc).__name__})
            return {"tried": 1, "ok": 0, "datasets": [], "repos": []}

    # Parallel extraction across papers
    import concurrent.futures
    datasets: list[dict[str, Any]] = []
    repos: list[dict[str, Any]] = []
    max_workers = max(1, min(len(target_papers), _env_int("DATASET_REPO_MAX_WORKERS", 4)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_extract_one, p): p for p in target_papers}
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                tried += result.get("tried", 0)
                ok_count += result.get("ok", 0)
                for d in result.get("datasets", []):
                    k = ds_key(d)
                    if k and k not in ds_seen:
                        ds_seen.add(k)
                        datasets.append(d)
                for r in result.get("repos", []):
                    k = repo_key(r)
                    if k and k not in repo_seen:
                        repo_seen.add(k)
                        repos.append(r)
            except BaseException as exc:
                logger.warning("dataset_repo future failed: %s", exc)

    # Re2.2-fix: heuristic dataset extraction from innovation_points stitching_plan
    innovation_points = state.get("innovation_points") or []
    known_dataset_names = [
        "NEU-DET", "GC10-DET", "KITTI", "TUM RGB-D", "EuRoC", "Bonn",
        "COCO", "Pascal VOC", "ImageNet", "CIFAR", "MNIST",
        "Cityscapes", "nuScenes", "ScanNet", "DOTA", "ShapeNet",
        "Completion3D", "ModelNet", "CARLA", "GTSDB", "TT100K",
        "CrackTree", "DeepCrack", "Crack500", "PavementCrack",
    ]
    for inn in innovation_points:
        plan_text = (inn.get("stitching_plan", "") + " " +
                     inn.get("description", "")).lower()
        for ds_name in known_dataset_names:
            if ds_name.lower() in plan_text:
                rec = {
                    "from_paper": "innovation_plan",
                    "linked_paper_id": _slug_of(ds_name),
                    "kind": "dataset",
                    "name": ds_name,
                    "url": None,
                    "source": "innovation_plan_heuristic",
                    "availability": "named",
                    "status": "found",
                    "reproducibility_hint": "",
                    "risk": "",
                }
                k = ds_key(rec)
                if k and k not in ds_seen:
                    ds_seen.add(k)
                    datasets.append(rec)

    merged_ds = existing_ds + datasets
    merged_repo = existing_repo + github_repos + repos

    trace = _emit("dataset_repo", t0,
                  {"n_papers": limit, "n_github_repos": len(github_repos)},
                  {"n_dataset": len(merged_ds), "n_repo": len(merged_repo)},
                  [{"tool": "re11_dataset_repo_extractor.llm", "attempts": tried,
                    "profile": "fast_json"},
                   {"tool": "github_direct_extract", "n_repos": len(github_repos)}],
                  "fast_json", errors)

    return {
        "dataset_candidates": merged_ds,
        "repo_candidates": merged_repo,
        "evidence_audit": {
            **audit,
            "dataset_extractions_tried": tried,
            "dataset_extractions_ok": ok_count,
        },
        "trace_events": [trace],
        "errors": errors,
    }
