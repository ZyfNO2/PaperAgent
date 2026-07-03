"""Re10 reflection-search module tests.

Six tests, one per public Re10 module.  They use no LLM and no
network — the rule layer must be the source of truth when LLM is
unavailable.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Make sure the apps/api package is importable when pytest is run from
# the apps/api directory.
_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from app.services.agents.domain_scout_agent import run_domain_scout
from app.services.agents.query_repair_agent import repair_query
from app.services.agents.reflection_critic_agent import run_reflection_critic
from app.services.agents.search_reflection_loop import run_search_reflection_loop
from app.services.agents.trace_ledger import TraceLedger
from app.services.agents.url_repair_agent import repair_candidate_url


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# 1. TraceLedger: 2 rounds + finalize
# ---------------------------------------------------------------------------


def test_trace_ledger_round_and_finalize(tmp_path):
    out_dir = tmp_path / "traces_root"
    ledger = TraceLedger(
        out_dir=str(out_dir),
        case_id="ENG-THESIS-001",
        topic="Underwater acoustic target recognition",
        seed_sources={"re08_candidates_n": 3, "re09_candidates_n": 1},
    )
    ledger.record_round(
        case_id="ENG-THESIS-001",
        round_num=1,
        agent="DomainScoutAgent",
        input_summary={"must_search_n": 2},
        actions=[{"type": "search", "tool": "arxiv", "query": "test", "status": "success"}],
        observations={"dataset_gap": True},
        reflection={"diagnosis": [], "next_round_focus": ["dataset search"]},
        new_candidates_n=2,
        accepted_n=1,
        rejected_n=1,
        url_repair_n=0,
        query_repair_n=0,
    )
    ledger.record_round(
        case_id="ENG-THESIS-001",
        round_num=2,
        agent="SearchReflectionLoop",
        input_summary={"seed_pool_n": 1},
        actions=[{"type": "search", "tool": "openalex", "query": "x", "status": "no_results"}],
        observations={"dataset_gap": False, "repo_gap": True},
        reflection={"diagnosis": [{"problem": "repo_gap", "next_action": "repair_query"}]},
        new_candidates_n=1,
        accepted_n=1,
        rejected_n=0,
        url_repair_n=1,
        query_repair_n=1,
    )
    ledger.finalize(
        case_id="ENG-THESIS-001",
        stop_reason="no_new_signal",
        paper_n=4,
        baseline_n=1,
        parallel_n=0,
        dataset_n=1,
        repo_n=1,
        remaining_gaps=["repo_gap"],
    )
    trace_file = out_dir / "traces" / "ENG-THESIS-001.json"
    assert trace_file.exists(), f"trace file missing: {trace_file}"
    data = json.loads(trace_file.read_text(encoding="utf-8"))
    assert data["case_id"] == "ENG-THESIS-001"
    assert data["seed_sources"]["re08_candidates_n"] == 3
    assert len(data["rounds"]) == 2
    assert data["rounds"][0]["round"] == 1
    assert data["rounds"][1]["round"] == 2
    assert data["rounds"][1]["url_repair_n"] == 1
    assert data["final"]["stop_reason"] == "no_new_signal"
    assert data["final"]["paper_n"] == 4
    assert data["final"]["remaining_gaps"] == ["repo_gap"]


# ---------------------------------------------------------------------------
# 2. DomainScout offline fallback (no LLM, atoms present)
# ---------------------------------------------------------------------------


def test_domain_scout_offline_fallback():
    topic = "Underwater acoustic target recognition"
    atoms = {
        "task": [{"en": "underwater acoustic recognition", "zh": "水声识别"}],
        "object": [{"en": "ship-radiated noise", "zh": "船舶辐射噪声"}],
    }
    out = _run(run_domain_scout(topic, atoms, llm_client=None))
    assert out["must_search"], "offline must_search should be non-empty when atoms are present"
    # All must_search entries must reference an axis keyword (benchmark)
    assert all("benchmark" in q for q in out["must_search"])
    # domain_keywords must include the English atom we passed in.
    assert "ship-radiated noise" in out["domain_keywords"]["en"] or any(
        "ship" in en.lower() for en in out["domain_keywords"]["en"]
    )
    # search_notes must indicate the offline mode for traceability.
    assert "offline" in out["search_notes"].lower() or "atom" in out["search_notes"].lower()


# ---------------------------------------------------------------------------
# 3. ReflectionCritic rule layer: dataset_gap
# ---------------------------------------------------------------------------


def test_reflection_critic_dataset_gap():
    out = _run(run_reflection_critic(
        "Underwater acoustic target recognition",
        {"object": [{"en": "ship-radiated noise"}]},
        observations={"dataset_gap": True, "baseline_gap": False, "repo_gap": False},
        llm_client=None,
    ))
    problems = [d["problem"] for d in out["diagnosis"]]
    assert "dataset_gap" in problems, f"expected dataset_gap in {problems}"
    # SOP §6.1 — empty URL must NEVER be tagged "noise".
    assert "noise_candidate" not in problems, (
        "ReflectionCritic must NEVER tag empty URL as noise (SOP §6.1)"
    )
    # next_round_focus must be a non-empty list.
    assert isinstance(out["next_round_focus"], list)
    assert out["next_round_focus"], "next_round_focus should be non-empty"


# ---------------------------------------------------------------------------
# 4. QueryRepair: bad query containing X must be drop / needs_clarification
# ---------------------------------------------------------------------------


def test_query_repair_drops_X():
    out = repair_query(
        "X dynamic scene dataset",
        topic_atoms={
            "object": [{"en": "underwater acoustic", "zh": "水声"}],
        },
        domain_keywords={},
    )
    assert out["status"] in ("drop", "needs_clarification"), (
        f"X-bearing query must be drop or needs_clarification, got {out['status']!r}"
    )
    # The hard rule: any repaired query must not still contain X or {.
    for q in out.get("repaired_queries") or []:
        assert "X" not in q, f"repaired query leaked X: {q!r}"
        assert "{" not in q and "}" not in q, f"repaired query leaked braces: {q!r}"


# ---------------------------------------------------------------------------
# 5. URLRepair: candidate with title + arxiv_id but no url → url_repaired
# ---------------------------------------------------------------------------


def test_url_repair_does_not_fail():
    cand = {
        "title": "Some Real Paper Title",
        "arxiv_id": "2401.01234",
        "authors": ["John Smith"],
        "year": 2024,
    }
    out = _run(repair_candidate_url(cand, retrieval_clients={}))
    assert out["url_status"] == "url_repaired"
    assert out["url"] == "https://arxiv.org/abs/2401.01234"
    assert "arxiv_id" in out["evidence"]


# ---------------------------------------------------------------------------
# 6. SearchReflectionLoop incremental merge: seeds preserved
# ---------------------------------------------------------------------------


def test_search_reflection_loop_incremental_merge(tmp_path):
    seed_paper_1 = {
        "title": "Re08 Seed Paper A",
        "url": "https://example.com/p1",
        "source_run": "re08",
        "_bucket": "paper",
    }
    seed_paper_2 = {
        "title": "Re09 Seed Paper B",
        "url": "https://example.com/p2",
        "source_run": "re09",
        "_bucket": "paper",
    }
    out = _run(run_search_reflection_loop(
        "Underwater acoustic target recognition",
        topic_atoms={
            "task": [{"en": "underwater acoustic recognition"}],
            "object": [{"en": "ship-radiated noise"}],
        },
        seed_candidates=[seed_paper_1, seed_paper_2],
        out_dir=str(tmp_path),
        max_rounds=1,
        llm_client=None,
        retrieval_clients={},  # no adapters → only seeds in final pool
    ))
    titles = {c.get("title") for c in out["final_candidate_pool"]}
    assert "Re08 Seed Paper A" in titles, "Re08 seed lost"
    assert "Re09 Seed Paper B" in titles, "Re09 seed lost"
    # Trace path is recorded.
    assert Path(out["trace_path"]).exists()
    # Summary must include paper_n >= 2 (the two seeds).
    assert out["summary"]["paper_n"] >= 2
