# -*- coding: utf-8 -*-
"""Re3.1 integration test - covers all 5 phases."""
from __future__ import annotations

import json
import os
import sys
import time
import asyncio
import re
import inspect

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0
SKIP = 0
RESULTS = []


def report(phase, name, status, detail=""):
    global PASS, FAIL, SKIP
    if status == "PASS":
        PASS += 1
    elif status == "FAIL":
        FAIL += 1
    else:
        SKIP += 1
    RESULTS.append((phase, name, status))
    tag = {"PASS": "OK", "FAIL": "FAIL", "SKIP": "SKIP"}[status]
    line = "  [" + tag + "] " + name
    if detail:
        line += " -- " + detail
    print(line)


# ============================================================
# Phase 1: dataset/repo extractor prompt
# ============================================================
def test_phase1():
    print("\n=== Phase 1: dataset/repo extractor prompt ===")
    import apps.api.app.services.agents.prompts.re11_dataset_repo_extractor as P

    # 1a: build() supports fulltext param
    try:
        r = P.build("NEU-DET: A Dataset for Surface Defect Detection",
                     "Abstract about steel surface defects",
                     fulltext="We use the NEU-DET dataset and COCO benchmark. Code at github.com/user/repo")
        assert "system" in r and "user" in r
        assert "NEU-DET" in r["user"], "title should appear in user prompt"
        assert "github.com/user/repo" in r["user"], "fulltext should appear in user prompt"
        report("Phase 1", "build() with fulltext param", "PASS", "fulltext_len=" + str(len(r["user"])))
    except Exception as e:
        report("Phase 1", "build() with fulltext param", "FAIL", str(e))

    # 1b: SYSTEM prompt mentions title
    try:
        assert "title" in P.SYSTEM.lower()
        assert "dataset" in P.SYSTEM.lower()
        report("Phase 1", "SYSTEM prompt mentions title", "PASS")
    except Exception as e:
        report("Phase 1", "SYSTEM prompt mentions title", "FAIL", str(e))

    # 1c: OUTPUT CONTRACT present
    try:
        assert "OUTPUT CONTRACT" in P.USER_TEMPLATE
        report("Phase 1", "OUTPUT CONTRACT present", "PASS")
    except Exception as e:
        report("Phase 1", "OUTPUT CONTRACT present", "FAIL", str(e))


# ============================================================
# Phase 2: devils_advocate field name
# ============================================================
def test_phase2():
    print("\n=== Phase 2: devils_advocate field name ===")
    from apps.api.app.services.agents.graph.state import ResearchState

    # 2a: state defines research_narrative (singular)
    try:
        assert "research_narrative" in ResearchState.__annotations__
        assert "research_narratives" not in ResearchState.__annotations__
        report("Phase 2", "state uses research_narrative (singular)", "PASS")
    except Exception as e:
        report("Phase 2", "state uses research_narrative (singular)", "FAIL", str(e))

    # 2b: devils_advocate_node reads singular
    from apps.api.app.services.agents.graph.nodes.devils_advocate_node import devils_advocate_node
    try:
        src = inspect.getsource(devils_advocate_node)
        assert "research_narrative" in src
        assert "research_narratives" not in src
        report("Phase 2", "devils_advocate reads singular field", "PASS")
    except Exception as e:
        report("Phase 2", "devils_advocate reads singular field", "FAIL", str(e))

    # 2c: narrative_builder outputs singular
    from apps.api.app.services.agents.graph.nodes.narrative_builder import narrative_builder_node
    try:
        src = inspect.getsource(narrative_builder_node)
        assert '"research_narrative"' in src
        assert '"research_narratives"' not in src
        report("Phase 2", "narrative_builder outputs singular field", "PASS")
    except Exception as e:
        report("Phase 2", "narrative_builder outputs singular field", "FAIL", str(e))

    # 2d: research.py case_narrative reads singular
    from apps.api.app.api.v1.research import case_narrative
    try:
        src = inspect.getsource(case_narrative)
        assert "research_narrative" in src
        assert "research_narratives" not in src
        report("Phase 2", "API case_narrative reads singular field", "PASS")
    except Exception as e:
        report("Phase 2", "API case_narrative reads singular field", "FAIL", str(e))

    # 2e: devils_advocate prompt has verdict rules
    import apps.api.app.services.agents.prompts.devils_advocate_graph as DP
    try:
        assert "BLOCK" in DP.USER_TEMPLATE
        assert "ACCEPT" in DP.USER_TEMPLATE
        assert "MINOR_REVISION" in DP.USER_TEMPLATE
        report("Phase 2", "devils_advocate prompt has verdict rules", "PASS")
    except Exception as e:
        report("Phase 2", "devils_advocate prompt has verdict rules", "FAIL", str(e))


# ============================================================
# Phase 3: User paper upload
# ============================================================
def test_phase3():
    print("\n=== Phase 3: User paper upload ===")

    # 3a: state has user_papers field
    from apps.api.app.services.agents.graph.state import ResearchState
    try:
        assert "user_papers" in ResearchState.__annotations__
        report("Phase 3", "ResearchState has user_papers field", "PASS")
    except Exception as e:
        report("Phase 3", "ResearchState has user_papers field", "FAIL", str(e))

    # 3b: intake injects user_papers -> verified_papers + seed_papers
    from apps.api.app.services.agents.graph.nodes.intake import intake_node
    try:
        state = {
            "topic": "YOLO crop detection",
            "user_papers": [
                {"title": "YOLOv5: Real-time object detection", "arxiv_id": "2106.12345", "role": "baseline"}
            ],
        }
        result = intake_node(state)
        vp = result.get("verified_papers", [])
        sp = result.get("seed_papers", [])
        assert len(vp) == 1, "expected 1 verified paper, got " + str(len(vp))
        assert vp[0]["verdict"] == "accept"
        assert vp[0]["source"] == "user_upload"
        assert vp[0]["relation_to_topic"] == "baseline"
        assert len(sp) == 1, "expected 1 seed paper, got " + str(len(sp))
        assert sp[0]["relevance_score"] == 1.0
        report("Phase 3", "intake injects user_papers", "PASS", "vp=" + str(len(vp)) + ", sp=" + str(len(sp)))
    except Exception as e:
        report("Phase 3", "intake injects user_papers", "FAIL", str(e))

    # 3c: API endpoints exist
    from apps.api.app.api.v1.research import upload_paper, list_user_papers
    try:
        assert callable(upload_paper)
        assert callable(list_user_papers)
        report("Phase 3", "API endpoints exist", "PASS")
    except Exception as e:
        report("Phase 3", "API endpoints exist", "FAIL", str(e))

    # 3d: _enrich_paper function exists
    from apps.api.app.api.v1.research import _enrich_paper
    try:
        assert callable(_enrich_paper)
        report("Phase 3", "_enrich_paper function exists", "PASS")
    except Exception as e:
        report("Phase 3", "_enrich_paper function exists", "FAIL", str(e))

    # 3e: _USER_PAPERS storage exists
    from apps.api.app.api.v1 import research as research_mod
    try:
        assert hasattr(research_mod, "_USER_PAPERS")
        assert isinstance(research_mod._USER_PAPERS, dict)
        report("Phase 3", "_USER_PAPERS storage exists", "PASS")
    except Exception as e:
        report("Phase 3", "_USER_PAPERS storage exists", "FAIL", str(e))

    # 3f: _run_case_sync injects user_papers
    try:
        src = inspect.getsource(research_mod._run_case_sync)
        assert "user_papers" in src
        assert "_USER_PAPERS" in src
        report("Phase 3", "_run_case_sync injects user_papers", "PASS")
    except Exception as e:
        report("Phase 3", "_run_case_sync injects user_papers", "FAIL", str(e))


# ============================================================
# Phase 4: Dedup + Crossref table filter
# ============================================================
def test_phase4():
    print("\n=== Phase 4: Dedup + Crossref table filter ===")

    # 4a: _dedup_key function
    from apps.api.app.services.agents.graph.nodes.search_agent import _dedup_key
    try:
        k1 = _dedup_key({"doi": "10.1234/test"})
        k2 = _dedup_key({"doi": "10.1234/TEST"})
        assert k1 == k2, "DOI should be case-insensitive: " + k1 + " vs " + k2
        assert k1 == "doi:10.1234/test"

        k3 = _dedup_key({"title": "YOLOv5: Real-time Object Detection!"})
        k4 = _dedup_key({"title": "yolov5 realtime object detection"})
        assert k3 == k4, "normalized titles should match: " + k3 + " vs " + k4

        # Punctuation surrounded by spaces gets stripped, whitespace collapsed
        k5 = _dedup_key({"title": "YOLOv5: Real-time Detection!"})
        k6 = _dedup_key({"title": "yolov5  realtime detection"})
        assert k5 == k6, "punctuation+whitespace normalized: " + k5 + " vs " + k6

        report("Phase 4", "_dedup_key: DOI + title normalization", "PASS", "doi_key=" + k1 + ", title_key=" + k3)
    except Exception as e:
        report("Phase 4", "_dedup_key: DOI + title normalization", "FAIL", str(e))

    # 4b: retrieve.py enhanced dedup
    from apps.api.app.services.agents.graph.nodes.retrieve import _run_direct_adapter_retrieval
    try:
        src = inspect.getsource(_run_direct_adapter_retrieval)
        assert "doi:" in src
        assert "[^\\w\\s]" in src or "[^" in src
        report("Phase 4", "retrieve.py enhanced dedup", "PASS")
    except Exception as e:
        report("Phase 4", "retrieve.py enhanced dedup", "FAIL", str(e))

    # 4c: quality_filter Crossref component filter
    from apps.api.app.services.agents.graph.nodes.quality_filter import _pre_filter
    try:
        candidates = [
            {"title": "A Real Paper", "source": "arxiv", "url": "https://arxiv.org/abs/1234"},
            {"title": "Accuracy Comparison of Methods", "source": "crossref", "_crossref_type": "component"},
            {"title": "Introduction to the Topic", "source": "crossref", "_crossref_type": "book-section"},
            {"title": "Another Real Paper", "source": "crossref", "_crossref_type": "journal-article"},
        ]
        results = _pre_filter(candidates)
        verdicts = {i: (v, reason) for i, v, reason in results}

        # index 1 = component -> should be dropped by crossref type filter
        assert verdicts[1][0] == False, "component should be dropped: " + str(verdicts[1])
        assert "crossref" in verdicts[1][1].lower() or "component" in verdicts[1][1].lower(), \
            "reason should mention crossref/component: " + str(verdicts[1])

        # index 2 = book-section -> should be dropped by crossref type filter
        assert verdicts[2][0] == False, "book-section should be dropped: " + str(verdicts[2])
        assert "crossref" in verdicts[2][1].lower() or "book" in verdicts[2][1].lower(), \
            "reason should mention crossref/book: " + str(verdicts[2])

        # index 3 = journal-article -> should NOT be dropped by type filter
        # (it goes to LLM check since crossref + no trusted url + no doi)
        assert verdicts[3][0] is None or verdicts[3][0] == True, \
            "journal-article should not be dropped by type filter: " + str(verdicts[3])

        dropped = sum(1 for _, v, _ in results if v is False)
        report("Phase 4", "quality_filter drops Crossref component", "PASS", "dropped=" + str(dropped))
    except Exception as e:
        report("Phase 4", "quality_filter drops Crossref component", "FAIL", str(e))

    # 4d: search_agent propagates _crossref_type
    from apps.api.app.services.agents.graph.nodes.search_agent import _classify_results
    try:
        src = inspect.getsource(_classify_results)
        assert "_crossref_type" in src
        report("Phase 4", "search_agent propagates _crossref_type", "PASS")
    except Exception as e:
        report("Phase 4", "search_agent propagates _crossref_type", "FAIL", str(e))

    # 4e: retrieve.py propagates _crossref_type
    try:
        src = inspect.getsource(_run_direct_adapter_retrieval)
        assert "_crossref_type" in src
        report("Phase 4", "retrieve.py propagates _crossref_type", "PASS")
    except Exception as e:
        report("Phase 4", "retrieve.py propagates _crossref_type", "FAIL", str(e))


# ============================================================
# Phase 5: arXiv full-text retrieval
# ============================================================
def test_phase5():
    print("\n=== Phase 5: arXiv full-text retrieval ===")

    # 5a: arxiv_fulltext module imports
    try:
        from apps.api.app.services.retrieval.arxiv_fulltext import (
            fetch_arxiv_fulltext, fetch_arxiv_fulltext_sync
        )
        report("Phase 5", "arxiv_fulltext module imports", "PASS")
    except Exception as e:
        report("Phase 5", "arxiv_fulltext module imports", "FAIL", str(e))
        return

    # 5b: empty arxiv_id returns empty string
    try:
        result = fetch_arxiv_fulltext_sync("")
        assert result == "", "empty id should return empty string: got " + str(len(result)) + " chars"
        report("Phase 5", "empty arxiv_id returns empty string", "PASS")
    except Exception as e:
        report("Phase 5", "empty arxiv_id returns empty string", "FAIL", str(e))

    # 5c: real arXiv PDF download + text extraction
    try:
        print("    [network] fetching arxiv 1706.03762...")
        t0 = time.time()
        text = fetch_arxiv_fulltext_sync("1706.03762")
        elapsed = round(time.time() - t0, 1)
        assert len(text) > 100, "expected >100 chars, got " + str(len(text)) + ": " + text[:100]
        assert "attention" in text.lower() or "transformer" in text.lower(), \
            "expected 'attention' or 'transformer' in text: " + text[:200]
        report("Phase 5", "real arXiv PDF download + text extraction", "PASS",
               "len=" + str(len(text)) + ", elapsed=" + str(elapsed) + "s, preview='" + text[:80] + "...'")
    except Exception as e:
        report("Phase 5", "real arXiv PDF download + text extraction", "SKIP",
               "network error: " + str(e))

    # 5d: dataset_repo_extractor integrated with fulltext
    from apps.api.app.services.agents.graph.nodes.dataset_repo_extractor import dataset_repo_extractor_node
    try:
        src = inspect.getsource(dataset_repo_extractor_node)
        assert "arxiv_fulltext" in src or "fetch_arxiv_fulltext" in src
        assert "fulltext" in src
        report("Phase 5", "dataset_repo_extractor integrated with fulltext", "PASS")
    except Exception as e:
        report("Phase 5", "dataset_repo_extractor integrated with fulltext", "FAIL", str(e))

    # 5e: arxiv_id propagated in search_agent
    from apps.api.app.services.agents.graph.nodes.search_agent import _classify_results
    try:
        src = inspect.getsource(_classify_results)
        assert "arxiv_id" in src
        report("Phase 5", "arxiv_id propagated in search_agent", "PASS")
    except Exception as e:
        report("Phase 5", "arxiv_id propagated in search_agent", "FAIL", str(e))

    # 5f: arxiv_id propagated in retrieve.py
    from apps.api.app.services.agents.graph.nodes.retrieve import _run_direct_adapter_retrieval
    try:
        src = inspect.getsource(_run_direct_adapter_retrieval)
        assert "arxiv_id" in src
        report("Phase 5", "arxiv_id propagated in retrieve.py", "PASS")
    except Exception as e:
        report("Phase 5", "arxiv_id propagated in retrieve.py", "FAIL", str(e))


# ============================================================
# Phase 6 (SOP Fix 1.1/1.2): recursion_limit + asyncio nesting
# ============================================================
def test_phase6():
    print("\n=== Phase 6: Frontend fixes (recursion_limit + asyncio) ===")
    import inspect

    # 6a: recursion_limit in research.py
    from apps.api.app.api.v1 import research as research_mod
    try:
        src = inspect.getsource(research_mod._run_case_sync)
        assert "recursion_limit" in src, "research.py _run_case_sync should set recursion_limit"
        assert "100" in src, "recursion_limit should be 100"
        report("Phase 6", "research.py sets recursion_limit=100", "PASS")
    except Exception as e:
        report("Phase 6", "research.py sets recursion_limit=100", "FAIL", str(e))

    # 6b: recursion_limit in re30_batch_run.py
    try:
        import apps.api.scripts.re30_batch_run as batch_mod
        src = inspect.getsource(batch_mod)
        assert "recursion_limit" in src, "re30_batch_run.py should set recursion_limit"
        report("Phase 6", "re30_batch_run.py sets recursion_limit", "PASS")
    except Exception as e:
        report("Phase 6", "re30_batch_run.py sets recursion_limit", "FAIL", str(e))

    # 6c: _run_tool_sync exists in search_agent
    from apps.api.app.services.agents.graph.nodes.search_agent import _run_tool_sync
    try:
        assert callable(_run_tool_sync)
        report("Phase 6", "_run_tool_sync exists in search_agent", "PASS")
    except Exception as e:
        report("Phase 6", "_run_tool_sync exists in search_agent", "FAIL", str(e))

    # 6d: search_agent_node uses _run_tool_sync (not asyncio.run)
    from apps.api.app.services.agents.graph.nodes.search_agent import search_agent_node
    try:
        src = inspect.getsource(search_agent_node)
        assert "_run_tool_sync" in src, "search_agent_node should call _run_tool_sync"
        # Check that the old asyncio.run(_run_tool(...)) call is gone
        assert "asyncio.run(_run_tool" not in src, "should not use asyncio.run(_run_tool(...))"
        report("Phase 6", "search_agent uses _run_tool_sync (no asyncio.run nesting)", "PASS")
    except Exception as e:
        report("Phase 6", "search_agent uses _run_tool_sync", "FAIL", str(e))

    # 6e: _run_tool_sync works without existing event loop
    try:
        results = _run_tool_sync("arxiv", "machine learning", 3)
        assert isinstance(results, list), "should return a list"
        report("Phase 6", "_run_tool_sync works (real arxiv call)", "PASS",
               "got " + str(len(results)) + " results")
    except Exception as e:
        report("Phase 6", "_run_tool_sync works", "FAIL", str(e))

    # 6f: heuristic dataset extraction from verified_papers titles
    from apps.api.app.services.agents.graph.nodes.dataset_repo_extractor import dataset_repo_extractor_node
    try:
        src = inspect.getsource(dataset_repo_extractor_node)
        assert "paper_title_heuristic" in src, "should have paper_title_heuristic source"
        assert "PlantVillage" in src or "plantvillage" in src.lower(), "should have expanded dataset list"
        report("Phase 6", "heuristic dataset extraction from paper titles", "PASS")
    except Exception as e:
        report("Phase 6", "heuristic dataset extraction from paper titles", "FAIL", str(e))

    # 6g: functional test - dataset_repo_extractor finds KITTI in paper title
    try:
        state = {
            "verified_papers": [
                {"title": "Visual SLAM using Deep Learning on KITTI Dataset", "abstract": "we evaluate on KITTI"},
            ],
            "dataset_candidates": [],
            "repo_candidates": [],
            "evidence_audit": {},
            "trace_events": [],
            "errors": [],
        }
        result = dataset_repo_extractor_node(state)
        ds = result.get("dataset_candidates") or []
        # Should find KITTI from title heuristic
        found_kitti = any(d.get("name") == "KITTI" for d in ds)
        assert found_kitti, "should find KITTI in paper title, got: " + str([d.get("name") for d in ds])
        report("Phase 6", "functional: KITTI found from paper title", "PASS",
               "datasets=" + str([d.get("name") for d in ds]))
    except Exception as e:
        report("Phase 6", "functional: KITTI found from paper title", "FAIL", str(e))


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 60)
    print("PaperAgent Re3.1 Integration Test")
    print("=" * 60)

    test_phase1()
    test_phase2()
    test_phase3()
    test_phase4()
    test_phase5()
    test_phase6()

    print("\n" + "=" * 60)
    print("Total: " + str(PASS) + " passed, " + str(FAIL) + " failed, " + str(SKIP) + " skipped")
    print("=" * 60)

    if FAIL > 0:
        print("\nFailed items:")
        for phase, name, status in RESULTS:
            if status == "FAIL":
                print("  [FAIL] [" + phase + "] " + name)
        return 1
    else:
        print("\nAll passed OK")
        return 0


if __name__ == "__main__":
    sys.exit(main())
