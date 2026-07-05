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
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)


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
    papers = list(state.get("verified_papers") or [])
    t0 = time.time()

    existing_ds = list(state.get("dataset_candidates") or [])
    existing_repo = list(state.get("repo_candidates") or [])
    audit = dict(state.get("evidence_audit") or {})

    datasets: list[dict[str, Any]] = []
    repos: list[dict[str, Any]] = []
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

    for p in papers[:limit]:
        title = (p.get("title") or p.get("name") or "").strip()
        if not title:
            continue
        paper_slug = _slug_of(title)
        try:
            from apps.api.app.services import llm_router
            from apps.api.app.services.agents.prompts import re11_dataset_repo_extractor as P
            built = P.build(title, p.get("abstract") or p.get("snippet") or "")
            out = llm_router.call_json(
                built["user"], system=built["system"], profile="fast_json",
                max_tokens=700, expected="list",
                schema_hint=("list of one object with keys: dataset_name, "
                             "benchmark_name, official_code_url, project_page_url, "
                             "supplementary_url, paper_mentioned_repo, "
                             "paper_used_baselines (list[str]), missing (list[str]), "
                             "status (found|not_found_in_paper|url_missing_needs_repair)"),
            )
            tried += 1
            item: dict[str, Any]
            if isinstance(out, list):
                item = out[0] if out else {}
                if not isinstance(item, dict):
                    item = {}
            elif isinstance(out, dict):
                # sometimes wrapped as {"extractions": [...]} or bare object
                wrapped = out.get("extractions") or out.get("results")
                if isinstance(wrapped, list) and wrapped:
                    item = wrapped[0] if isinstance(wrapped[0], dict) else {}
                else:
                    item = out
            else:
                item = {}

            status = (item.get("status") or "not_found_in_paper")
            if status in ("found", "url_missing_needs_repair"):
                ok_count += 1
                ds_name = (item.get("dataset_name") or "").strip()
                official = (item.get("official_code_url") or "").strip()
                mentioned = (item.get("paper_mentioned_repo") or "").strip()
                proj = (item.get("project_page_url") or "").strip()
                supp = (item.get("supplementary_url") or "").strip()
                if ds_name or official:
                    rec = {
                        "from_paper": title,
                        "linked_paper_id": paper_slug,
                        "kind": "dataset",
                        "name": ds_name or None,
                        "url": official or None,
                        "source": "paper_abstract",
                        "availability": "url" if official else ("named" if ds_name else "unknown"),
                        "status": status,
                        "reproducibility_hint": "",
                        "risk": "",
                    }
                    k = ds_key(rec)
                    if k and k not in ds_seen:
                        ds_seen.add(k)
                        datasets.append(rec)
                if official or mentioned:
                    url = official or mentioned
                    rrec = {
                        "from_paper": title,
                        "linked_paper_id": paper_slug,
                        "kind": "repo",
                        "url": url,
                        "mentioned_repo": mentioned or None,
                        "source": "paper_official_link",
                        "availability": "url" if url.startswith("http") else "named",
                        "status": status,
                        "reproducibility_hint": "",
                        "risk": "",
                    }
                    k = repo_key(rrec)
                    if k and k not in repo_seen:
                        repo_seen.add(k)
                        repos.append(rrec)
                # extra project / supplementary URL become repo records too
                for extra_url in (proj, supp):
                    if extra_url:
                        rrec = {
                            "from_paper": title,
                            "linked_paper_id": paper_slug,
                            "kind": "repo",
                            "url": extra_url,
                            "mentioned_repo": mentioned or None,
                            "source": "paper_metadata_url",
                            "availability": "url",
                            "status": status,
                            "reproducibility_hint": "",
                            "risk": "",
                        }
                        k = repo_key(rrec)
                        if k and k not in repo_seen:
                            repo_seen.add(k)
                            repos.append(rrec)
            # not_found_in_paper: drop silently per SOP
        except BaseException as exc:
            logger.debug("dataset_repo extraction failed for %r: %s",
                         title, type(exc).__name__)
            errors.append({"node": "dataset_repo", "for_paper": title,
                           "error": type(exc).__name__})

    merged_ds = existing_ds + datasets
    merged_repo = existing_repo + repos

    trace = _emit("dataset_repo", t0,
                  {"n_papers": limit},
                  {"n_dataset": len(merged_ds), "n_repo": len(merged_repo)},
                  [{"tool": "re11_dataset_repo_extractor.llm", "attempts": tried,
                    "profile": "fast_json"}],
                  "fast_json", errors)

    return {
        "dataset_candidates": merged_ds,
        "repo_candidates": merged_repo,
        "evidence_audit": {
            **audit,
            "dataset_extractions_tried": tried,
            "dataset_extractions_ok": ok_count,
        },
        "trace_events": list(state.get("trace_events") or []) + [trace],
        "errors": list(state.get("errors") or []) + errors,
    }
