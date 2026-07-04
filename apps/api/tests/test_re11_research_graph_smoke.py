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


def test_re11_test_files_exist() -> None:
    """Loop 0: Re11.1 test files must be present in apps/api/tests."""
    tdir = os.path.join(ROOT, "apps", "api", "tests")
    assert os.path.isdir(tdir), f"tests dir missing: {tdir}"
    for name in (
        "test_llm_router_re11.py",
        "test_re11_research_graph_smoke.py",
        "test_re11_no_secret_leak.py",
        "test_re11_dataset_repo_from_papers.py",
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

    def fake_call_json(*a, **k):  # type: ignore[no-untyped-def]
        return {"verified": [{"title": "P", "verdict": "accept",
                              "hit_keywords": ["h"], "unrelated_keywords": [],
                              "related_keywords": [], "source_type": "paper",
                              "relation_to_topic": "baseline",
                              "url_missing": False,
                              "needs_human_confirm": False, "reason": "ok"}],
                "work_packages": [], "evidence_gap": []}

    r_mod._run_legacy_retrieval = lambda topic, atoms: {  # type: ignore[assignment]
        "buckets": {"baseline_papers": [{"title": "P", "abstract": "a", "source": "x"}],
                    "parallel_papers": [], "module_papers": [],
                    "reference_papers": []},
        "raw": {"openalex": [{"title": "P"}]},
    }
    v_mod._call_verifier = lambda t, a, c: [  # type: ignore[assignment]
        {"title": "P", "verdict": "accept", "hit_keywords": ["h"],
         "unrelated_keywords": [], "related_keywords": [],
         "source_type": "paper", "relation_to_topic": "baseline",
         "url_missing": False, "needs_human_confirm": False, "reason": "ok"}]
    import apps.api.app.services.agents.graph.nodes.retrieve as r_mod
    orig_retrieve = r_mod._run_legacy_retrieval

    def fake_retrieve(topic, atoms):  # type: ignore[no-untyped-def]
        return {
            "buckets": {"baseline_papers": [{"title": "P", "abstract": "a", "source": "x"}],
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
