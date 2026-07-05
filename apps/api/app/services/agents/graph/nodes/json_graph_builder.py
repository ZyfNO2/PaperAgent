"""LangGraph node: json_graph_builder — formalise evidence_graph.

Pure function (no LLM). Builds the Re1.1 front-end contract (SOP §5.8) from
state: paper / repo / dataset / baseline / parallel / work-package nodes and
their relations. Node id prefixes are fixed so edge wiring stays consistent.

Output fields: evidence_graph, evidence_audit (graph_built), trace_events.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)

# Allowed edge types — keep in sync with SOP §5.8 enum.
_EDGE_TYPES = frozenset({
    "uses_dataset",
    "has_official_repo",
    "implements",
    "extends_baseline",
    "compares_with",
    "mentions",
    "cites",
    "needs_repair",
    "quarantined_as_noise",
})


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


def _kebab(text: str) -> str:
    """Sanitize a title/name into a kebab-case id fragment."""
    s = (text or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-") or "unknown"


def _owner_repo(url_or_name: str) -> str:
    """Normalise a repo reference to owner/repo when possible."""
    s = (url_or_name or "").strip().rstrip("/")
    # e.g. https://github.com/owner/repo  -> owner/repo
    m = re.search(r"github\.com/([^/]+/[^/#?]+)", s)
    if m:
        return re.sub(r"\.git$", "", m.group(1)).lower()
    if "/" in s and not s.startswith("http"):
        return s.lower()
    return _kebab(s)


def json_graph_builder_node(state: ResearchState) -> dict[str, Any]:
    t0 = time.time()

    verified = list(state.get("verified_papers") or [])
    repos = list(state.get("repo_candidates") or [])
    datasets = list(state.get("dataset_candidates") or [])
    baselines = list(state.get("baseline_candidates") or [])
    parallels = list(state.get("parallel_candidates") or [])
    work_packages = list(state.get("work_packages") or [])
    audit = dict(state.get("evidence_audit") or {})

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()

    def add_node(nid: str, ntype: str, title: str, role: str) -> None:
        if not nid or nid in seen_nodes:
            return
        seen_nodes.add(nid)
        nodes.append({"id": nid, "type": ntype, "title": title, "role": role})

    def add_edge(src: str, tgt: str, etype: str) -> None:
        if not src or not tgt or etype not in _EDGE_TYPES:
            return
        key = (src, tgt, etype)
        if key in seen_edges or src == tgt:
            return
        seen_edges.add(key)
        edges.append({"source": src, "target": tgt, "type": etype})

    # Papers (covers baseline / parallel which are drawn from verified_papers)
    for p in verified:
        title = (p.get("title") or p.get("name") or "").strip()
        role = p.get("relation_to_topic") or "unknown"
        add_node(f"paper:<{_kebab(title)}>", "paper", title, role)

    # Datasets
    for d in datasets:
        name = (d.get("name") or d.get("from_paper") or "").strip()
        add_node(f"dataset:<{_kebab(name)}>", "dataset", name, "dataset")
        lp = d.get("linked_paper_id") or ""
        if lp:
            add_edge(f"paper:<{_kebab(lp)}>", f"dataset:<{_kebab(name)}>", "uses_dataset")

    # Repos
    for r in repos:
        url = (r.get("url") or r.get("mentioned_repo") or "").strip()
        owner_repo = _owner_repo(url or r.get("from_paper") or "")
        title = r.get("mentioned_repo") or owner_repo or r.get("from_paper") or "repo"
        add_node(f"repo:<{owner_repo}>", "repo", title, "repo")
        lp = r.get("linked_paper_id") or ""
        if lp:
            add_edge(f"paper:<{_kebab(lp)}>", f"repo:<{owner_repo}>", "has_official_repo")

    # Baseline / parallel explicit nodes (inherit paper id)
    for p in baselines:
        title = (p.get("title") or p.get("name") or "").strip()
        add_node(f"baseline:<{_kebab(title)}>", "baseline", title, "baseline")
    for p in parallels:
        title = (p.get("title") or p.get("name") or "").strip()
        add_node(f"parallel:<{_kebab(title)}>", "parallel", title, "parallel")

    # Parallel inheritance edges
    for p in parallels:
        title = (p.get("title") or p.get("name") or "").strip()
        src_id = f"parallel:<{_kebab(title)}>"
        baseline_title = (p.get("improved_module_source") or "").strip()
        if baseline_title:
            add_edge(src_id, f"baseline:<{_kebab(baseline_title)}>", "implements")
        extends = (p.get("extends_baseline") or "").strip()
        if extends:
            add_edge(src_id, f"baseline:<{_kebab(extends)}>", "extends_baseline")

    # mentions edges between verified papers via citation list
    for p in verified:
        title = (p.get("title") or p.get("name") or "").strip()
        for cited in (p.get("mentions") or []) if isinstance(p.get("mentions"), list) else []:
            ct = (cited.get("title") if isinstance(cited, dict) else cited)
            if ct:
                add_edge(f"paper:<{_kebab(title)}>", f"paper:<{_kebab(str(ct))}>", "mentions")

    repair_rounds = int(audit.get("repair_rounds", 0))

    # Work packages
    for wp in work_packages:
        slug = _kebab(wp.get("slug") or wp.get("id") or wp.get("title") or "")
        if not slug:
            continue
        wp_id = f"workpkg:<{slug}>"
        add_node(wp_id, "workpkg", wp.get("title") or slug, "work_package")
        for field in ("baseline", "improved_module_source", "data_source", "experiment_metrics"):
            ref = (wp.get(field) or "").strip()
            if not ref:
                # candidate_only / non-string metrics skipped
                continue
            if field == "data_source":
                add_edge(wp_id, f"dataset:<{_kebab(ref)}>", "cites")
            elif field == "experiment_metrics":
                add_edge(wp_id, f"paper:<{_kebab(ref)}>", "cites")
            else:
                add_edge(wp_id, f"paper:<{_kebab(ref)}>", "cites")
                add_edge(wp_id, f"baseline:<{_kebab(ref)}>", "cites")
        # needs_repair: any source still unresolved flagged by audit
        if repair_rounds > 0:
            for need in (wp.get("missing_sources") or []) if isinstance(wp.get("missing_sources"), list) else []:
                nkind = need.get("kind") if isinstance(need, dict) else "baseline"
                nname = (need.get("name") if isinstance(need, dict) else str(need))
                if not nname:
                    continue
                if nkind == "dataset":
                    add_edge(wp_id, f"dataset:<{_kebab(nname)}>", "needs_repair")
                elif nkind == "repo":
                    add_edge(wp_id, f"repo:<{_owner_repo(nname)}>", "needs_repair")
                else:
                    add_edge(wp_id, f"baseline:<{_kebab(nname)}>", "needs_repair")

    # Quarantine edges: any candidate flagged needs_audit / quarantined
    def _quarantine_candidates(kind: str, lst: list[dict[str, Any]]) -> None:
        for c in lst:
            if not (c.get("needs_audit") or c.get("quarantined")):
                continue
            name = (c.get("title") or c.get("name") or "").strip()
            qid = f"quarantine:<{_kebab(name)}>"
            add_node(qid, "quarantine", name, "noise")
            if kind == "paper":
                add_edge(qid, f"paper:<{_kebab(name)}>", "quarantined_as_noise")
            elif kind == "dataset":
                add_edge(qid, f"dataset:<{_kebab(name)}>", "quarantined_as_noise")
            elif kind == "repo":
                add_edge(qid, f"repo:<{_kebab(name)}>", "quarantined_as_noise")

    _quarantine_candidates("paper", verified)
    _quarantine_candidates("dataset", datasets)
    _quarantine_candidates("repo", repos)

    graph = {"nodes": nodes, "edges": edges}
    trace = _emit("json_graph_builder", t0,
                  {"papers": len(verified)},
                  {"nodes": len(nodes), "edges": len(edges)},
                  ["local.classifier"], "local", [])

    return {
        "evidence_graph": graph,
        "evidence_audit": {**audit, "graph_built": True},
        "trace_events": list(state.get("trace_events") or []) + [trace],
    }
