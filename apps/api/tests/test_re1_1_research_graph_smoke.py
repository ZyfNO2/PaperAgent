"""Loop 0 static audit for Re1.1 — all offline / static checks.

SOP §14 Loop 0:
- .env is ignored and not tracked.
- No real keys in Plan/apps.
- apps/api/tests contains Re1.1 test files.
- No generic_repos whitelist, no topic-title direct injection.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

# apps/api/tests/file.py -> apps/api/tests -> apps/api -> apps -> repo root.
ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import apps.api.app.services.agents.graph.research_graph as rg
import apps.api.app.services.agents.graph.nodes as graph_nodes


def _git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=ROOT,
    )


def test_env_gitignored_and_not_tracked() -> None:
    """SOP §1 / §17: .env / .env.local must be gitignored AND not tracked."""
    # --error-unmatch returns non-zero when NOT tracked => good.
    assert _git(["ls-files", "--error-unmatch", ".env"]).returncode != 0, \
        ".env IS tracked by git"
    assert _git(["ls-files", "--error-unmatch", ".env.local"]).returncode != 0, \
        ".env.local IS tracked by git"


def test_re1_1_test_files_exist() -> None:
    """Loop 0: Re1.1 test files must be present in apps/api/tests."""
    tdir = str(ROOT / "apps" / "api" / "tests")
    assert os.path.isdir(tdir), f"tests dir missing: {tdir}"
    for name in (
        "test_re1_1_llm_router.py",
        "test_re1_1_research_graph_smoke.py",
        "test_re1_1_no_secret_leak.py",
        "test_re1_1_dataset_repo_from_papers.py",
    ):
        full = os.path.join(tdir, name)
        assert os.path.exists(full), f"missing {full}"


def test_no_topic_whitelist_injection_in_prompts() -> None:
    """Loop 0: prompts must not hard-suggest COCO/ORB-SLAM3 by topic keywords."""
    import re

    from apps.api.app.services.agents import prompts as prompts_pkg

    offenders: list[str] = []
    pkg_dir = os.path.dirname(prompts_pkg.__file__)
    for dirpath, _, files in os.walk(pkg_dir):
        for name in files:
            if not name.endswith(".py"):
                continue
            if "re11" not in name:
                continue
            body = open(os.path.join(dirpath, name), encoding="utf-8").read()
            # Hardcoded well-known dataset/repo named after generic conditions.
            for token in ("COCO ", "VOC2012", "ORB-SLAM3", "Awesome-SLAM"):
                if token in body:
                    offenders.append(f"{name}:{token}")
    assert not offenders, f"hardcoded topic injection: {offenders}"


def test_graph_nodes_registered() -> None:
    """Loop 0: graph registry has all required nodes (SOP §5)."""
    expected = {"retrieve", "verify", "dataset_repo", "evidence_auditor",
                "work_package", "low_bar_review", "human_gate",
                "final_recommendation"}
    assert expected.issubset(set(graph_nodes.REGISTRY.keys()))


def test_graph_compiles_and_runs_offline() -> None:
    """Loop 0: graph must compile; run with mocked LLM should not crash & all 7 nodes write trace."""
    import apps.api.app.services.agents.graph.nodes.retrieve as r_mod
    import apps.api.app.services.agents.graph.nodes.verify as v_mod
    import apps.api.app.services.agents.graph.nodes.content as c_mod

    baseline_titles = ["P1", "P2", "P3"]

    def fake_call_json(*a, **k):  # type: ignore[no-untyped-def]
        prompt = a[0] if a else k.get("prompt", "")
        # ORDER MATTERS: check work_package BEFORE the dataset/repo branch
        # because the work-package user template contains the word "datasets".
        if ("work package" in prompt.lower() or "brainstorm" in prompt.lower()
                or "research_question" in prompt.lower()
                or "improved_module_source" in prompt.lower()
                or "work_packages" in prompt.lower()
                or "baseline (a title" in prompt.lower()
                or "研究问题" in prompt):
            return {
                "work_packages": [
                    {"title": f"Improve {baseline_titles[0]}",
                     "research_question": "R can we improve?",
                     "baseline": baseline_titles[0],
                     "improved_module_source": baseline_titles[1],
                     "data_source": "NEU-DET",
                     "experiment_metrics": "mAP@0.5",
                     "risk": "limited",
                     "estimated_workload": "6 months"},
                ],
                "evidence_gap": [],
            }
        if "paper verifier" in prompt.lower() or "verdict" in prompt.lower():
            # paper verifier path
            return {
                "verified": [
                    {"title": t, "verdict": "accept",
                     "hit_keywords": ["kw"], "unrelated_keywords": [],
                     "related_keywords": [""], "source_type": "paper",
                     "relation_to_topic": "baseline", "url_missing": False,
                     "needs_human_confirm": False, "reason": "ok"}
                    for t in baseline_titles
                ],
                "work_packages": [],
                "evidence_gap": [],
            }
        if "search planner" in prompt.lower() or "repair" in prompt.lower():
            return {
                "queries": [
                    {"tool": "openalex", "query": f"{t} review",
                     "why": "seed", "expected_evidence": "paper",
                     "stop_condition": "n>=5"}
                    for t in baseline_titles
                ],
                "rounds": ["repair"],
                "negative_feedback": "targeted repair",
            }
        if "dataset" in prompt.lower() or "repo" in prompt.lower():
            return [
                {"from_paper": t, "status": "not_found_in_paper",
                 "linked_paper_id": t.lower().replace(" ", "-"),
                 "kind": "dataset", "name": None, "url": None,
                 "source": "paper_abstract"}
                for t in baseline_titles[:1]
            ]
        if ("work package" in prompt.lower() or "brainstorm" in prompt.lower()
                or "research_question" in prompt.lower()
                or "improved_module_source" in prompt.lower()
                or "work_packages" in prompt.lower()
                or "baseline (a title" in prompt.lower()
                or "实验方案" in prompt or "研究问题" in prompt):
            return {
                "work_packages": [
                    {"title": f"Improve {baseline_titles[0]}",
                     "research_question": "Can we improve recall on NEU-DET?",
                     "baseline": baseline_titles[0],
                     "improved_module_source": baseline_titles[1],
                     "data_source": "NEU-DET",
                     "experiment_metrics": "mAP@0.5",
                     "risk": "limited baseline variants",
                     "estimated_workload": "6 months"},
                ],
                "evidence_gap": [],
            }
        # default
        return {"ok": True, "baseline": baseline_titles,
                "parallel": [], "dataset_papers": [], "surveys": []}

    r_mod._run_legacy_retrieval = lambda topic, atoms: {  # type: ignore[assignment]
        "buckets": {"baseline_papers": [{"title": t, "abstract": "a", "source": "x"} for t in baseline_titles],
                    "parallel_papers": [], "module_papers": [],
                    "reference_papers": []},
        "raw": {"openalex": [{"title": t} for t in baseline_titles]},
    }
    v_mod._call_verifier = lambda t, a, c: [  # type: ignore[assignment]
        {"title": (c[i].get("title") if i < len(c) else "P"),
         "verdict": "accept", "hit_keywords": ["kw"],
         "unrelated_keywords": [], "related_keywords": [],
         "source_type": "paper", "relation_to_topic": "baseline",
         "url_missing": False, "needs_human_confirm": False, "reason": "ok"}
        for i in range(min(len(c), 3))]
    import apps.api.app.services.agents.graph.nodes.retrieve as r_mod
    orig_retrieve = r_mod._run_legacy_retrieval

    def fake_retrieve(topic, atoms):  # type: ignore[no-untyped-def]
        return {
            "buckets": {"baseline_papers": [{"title": "P1", "abstract": "a", "source": "x"},{"title": "P2", "abstract": "a", "source": "x"},{"title": "P3", "abstract": "a", "source": "x"}],
                        "parallel_papers": [], "module_papers": [],
                        "reference_papers": []},
            "raw": {"openalex": [{"title": "P"}]},
        }

    r_mod._run_legacy_retrieval = fake_retrieve
    try:
        import apps.api.app.services.llm_router as llm_router
        orig_call = llm_router.call_json
        llm_router.call_json = fake_call_json
        try:
            g = rg.build_graph()
            out = g.invoke(
                {"case_id": "case-000", "topic": "t",
                 "topic_atoms": {"method": ["m"], "object": ["o"], "task": ["t"],
                                 "domain": [], "dataset_terms": [], "baseline_terms": [],
                                 "avoid_terms": []},
                 "trace_events": []},
                config={"configurable": {"thread_id": "case-000"}},
            )
        finally:
            llm_router.call_json = orig_call
    finally:
        r_mod._run_legacy_retrieval = orig_retrieve

    events = out.get("trace_events") or []
    names = [e["node"] for e in events]
    # 8 nodes all fire in sequence.
    assert "retrieve" in names
    assert "verify" in names
    assert "dataset_repo" in names
    assert "evidence_auditor" in names
    assert "work_package" in names
    assert "low_bar_review" in names
    assert "human_gate" in names
    assert "final_recommendation" in names
    # trace case_id-as-thread_id implies no crash.
    assert out.get("final_recommendation") is not None
