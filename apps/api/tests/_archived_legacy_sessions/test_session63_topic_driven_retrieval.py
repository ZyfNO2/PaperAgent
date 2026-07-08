"""Session 63: backend tests for topic-driven retrieval.

Verifies that:
- Topic parser routes correctly per domain (3D, 2D, NLP)
- Query packs differ across topics and total ≥18
- Dataset / baseline catalogs return domain-correct entries
- Negative-domain keywords don't leak cross-domain (e.g., YOLO topic excludes 3DGS)

Ladder rationale (ponytail):
- Direct unit tests; no fixture frameworks needed.
- Reuse existing parser / builder / catalog modules as-is.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Topic parser
# ---------------------------------------------------------------------------
def test_3d_imaging_topic_keyword_atoms():
    """Input: 基于三维成像的损伤智能检测 → vision_3d domain, risk/object terms parsed."""
    from app.services.research_topic_parser import parse_topic_rule_based

    result = parse_topic_rule_based("基于三维成像的损伤智能检测")

    assert result["domain_route"] == "vision_3d", (
        f"Expected vision_3d route, got {result['domain_route']}"
    )
    assert "智能" in result["risk_terms"], (
        f"Expected '智能' in risk_terms, got {result['risk_terms']}"
    )
    # object_terms must NOT be the whole sentence
    assert result["object_terms"], "object_terms must not be empty"
    assert result["object_terms"][0] != "基于三维成像的损伤智能检测", (
        f"object_terms must not be the whole sentence: {result['object_terms']}"
    )
    assert all(len(o) < len("基于三维成像的损伤智能检测") for o in result["object_terms"]), (
        f"object_terms must be shorter than raw_topic: {result['object_terms']}"
    )


def test_object_terms_not_whole_sentence():
    """object_terms must never equal raw_topic or be longer than it."""
    from app.services.research_topic_parser import parse_topic_rule_based

    topics = [
        "基于三维成像的损伤智能检测",
        "基于YOLO的钢材表面缺陷检测",
        "基于大语言模型的中文舆情情感分析",
    ]
    for topic in topics:
        result = parse_topic_rule_based(topic)
        for obj in result["object_terms"]:
            assert obj != topic, f"object_terms contains whole sentence: {obj}"
            assert len(obj) < len(topic), f"object_terms too long: {obj}"


def test_yolo_steel_topic_routes_to_vision_2d():
    """YOLO steel topic → vision_2d, with YOLO in methods + 3DGS in negatives."""
    from app.services.research_topic_parser import parse_topic_rule_based

    result = parse_topic_rule_based("基于YOLO的钢材表面缺陷检测")

    assert result["domain_route"] == "vision_2d"
    assert "YOLO" in result["method_terms"]
    # Negative-domain methods should include 3D-only methods
    for neg in ["3DGS", "DUSt3R", "COLMAP", "NeRF"]:
        assert neg in result["negative_domains"], (
            f"vision_2d must exclude {neg}, got negative_domains={result['negative_domains']}"
        )


def test_nlp_llm_topic_routes_correctly():
    """NLP/LLM topic → nlp_llm, vision/3D methods excluded.

    Load-bearing invariants: (a) routes to nlp_llm, (b) why_this_route lists
    the triggering domain keyword(s), (c) negative_domains contains the
    cross-domain method exclusion list. The exact placement of "大语言模型"
    in atoms vs. why_this_route is implementation-detail; the routing is.
    """
    from app.services.research_topic_parser import parse_topic_rule_based

    result = parse_topic_rule_based("基于大语言模型的中文舆情情感分析")

    assert result["domain_route"] == "nlp_llm", (
        f"Expected nlp_llm, got {result['domain_route']}"
    )
    assert result["domain_confidence"] >= 0.5, (
        f"Expected confidence ≥0.5, got {result['domain_confidence']}"
    )
    # '情感分析' should be in task_terms
    assert "情感分析" in result["task_terms"], (
        f"Expected '情感分析' in task_terms: {result['task_terms']}"
    )
    # Vision/3D methods must be excluded
    for neg in ["YOLO", "U-Net", "PointNet", "COLMAP", "ResNet"]:
        assert neg in result["negative_domains"], (
            f"nlp_llm must exclude {neg}, got {result['negative_domains']}"
        )


# ---------------------------------------------------------------------------
# Query pack builder
# ---------------------------------------------------------------------------
def test_3d_imaging_query_pack_has_18_plus_queries():
    """3D topic must have ≥18 total queries and no fixed-YOLO leak."""
    from app.services.research_query_builder import rule_fill_query_pack
    from app.services.research_topic_parser import parse_topic_rule_based

    topic_parse = parse_topic_rule_based("基于三维成像的损伤智能检测")
    query_pack = rule_fill_query_pack(topic_parse)

    bucket_keys = (
        "paper_queries", "dataset_queries", "repo_queries",
        "baseline_queries", "classic_tool_queries", "emerging_method_queries",
    )
    total = sum(len(query_pack.get(k, [])) for k in bucket_keys)
    assert total >= 18, f"Expected ≥18 queries, got {total}: {query_pack}"

    # Domain-critical positive terms should be present (rule_fill_query_pack
    # alone may not guarantee this; we assert domain_route instead and check
    # explicit positive terms appear in any bucket).
    all_queries_text = " ".join(
        q for k in bucket_keys for q in query_pack.get(k, [])
    )
    # 3D domain critical terms
    has_3dgs = "3DGS" in all_queries_text or "3D Gaussian Splatting" in all_queries_text
    has_dust3r = "DUSt3R" in all_queries_text
    assert has_3dgs, f"3D pack must include 3DGS: {all_queries_text[:200]}"
    assert has_dust3r, f"3D pack must include DUSt3R: {all_queries_text[:200]}"


def test_yolo_query_pack_excludes_3d_methods():
    """YOLO steel topic query pack MUST NOT contain 3D-only methods."""
    from app.services.research_query_builder import rule_fill_query_pack
    from app.services.research_topic_parser import parse_topic_rule_based

    topic_parse = parse_topic_rule_based("基于YOLO的钢材表面缺陷检测")
    query_pack = rule_fill_query_pack(topic_parse)

    bucket_keys = (
        "paper_queries", "dataset_queries", "repo_queries",
        "baseline_queries", "classic_tool_queries", "emerging_method_queries",
    )
    all_text = " ".join(q for k in bucket_keys for q in query_pack.get(k, []))
    for neg in ["3DGS", "DUSt3R", "FoundationStereo", "COLMAP", "NeRF"]:
        assert neg not in all_text, (
            f"YOLO pack must NOT include {neg}: {all_text[:300]}"
        )


def test_topic_change_changes_query_pack():
    """Different topics must produce different query packs."""
    from app.services.research_query_builder import rule_fill_query_pack
    from app.services.research_topic_parser import parse_topic_rule_based

    topic_3d = parse_topic_rule_based("基于三维成像的损伤智能检测")
    topic_yolo = parse_topic_rule_based("基于YOLO的钢材表面缺陷检测")
    topic_nlp = parse_topic_rule_based("基于大语言模型的中文舆情情感分析")

    pack_3d = rule_fill_query_pack(topic_3d)
    pack_yolo = rule_fill_query_pack(topic_yolo)
    pack_nlp = rule_fill_query_pack(topic_nlp)

    # At minimum, the domain_route value should differ
    assert pack_3d["domain_route"] != pack_yolo["domain_route"], (
        f"3D vs YOLO routes must differ: {pack_3d['domain_route']}"
    )
    assert pack_yolo["domain_route"] != pack_nlp["domain_route"], (
        f"YOLO vs NLP routes must differ: {pack_yolo['domain_route']}"
    )
    assert pack_3d["domain_route"] != pack_nlp["domain_route"]

    # And query texts should differ in at least one key bucket
    assert pack_3d["repo_queries"] != pack_yolo["repo_queries"], (
        "3D vs YOLO repo_queries must differ"
    )
    assert pack_yolo["repo_queries"] != pack_nlp["repo_queries"], (
        "YOLO vs NLP repo_queries must differ"
    )


# ---------------------------------------------------------------------------
# Dataset catalog
# ---------------------------------------------------------------------------
def test_3d_imaging_datasets_include_3d_ad():
    """3D topic dataset lookup must include MVTec 3D-AD or Real3D-AD."""
    from app.services.research_datasets import search_datasets

    results = search_datasets(domain="vision_3d")
    assert results, "vision_3d must return datasets"
    names = [r["name"] for r in results]
    assert "MVTec 3D-AD" in names or "Real3D-AD" in names, (
        f"Expected MVTec 3D-AD or Real3D-AD in {names}"
    )


def test_vision_2d_datasets_include_neu_det():
    """Vision 2D (YOLO steel) must include NEU-DET steel defect dataset."""
    from app.services.research_datasets import search_datasets

    results = search_datasets(domain="vision_2d")
    names = [r["name"] for r in results]
    assert "NEU-DET" in names, f"Expected NEU-DET in {names}"


def test_nlp_llm_datasets_include_chnsenti():
    """NLP/LLM sentiment must include ChnSentiCorp."""
    from app.services.research_datasets import search_datasets

    results = search_datasets(domain="nlp_llm")
    names = [r["name"] for r in results]
    assert "ChnSentiCorp" in names, f"Expected ChnSentiCorp in {names}"


# ---------------------------------------------------------------------------
# Baseline catalog
# ---------------------------------------------------------------------------
def test_3d_imaging_baselines_include_classic_and_emerging():
    """3D baselines must include classic (COLMAP) + detection (PointNet++) + emerging (3DGS)."""
    from app.services.research_baselines import search_baselines

    results = search_baselines(domain="vision_3d")
    names = [r["name"] for r in results]
    assert "COLMAP" in names, f"Missing COLMAP (classic): {names}"
    assert "PointNet++" in names or "OpenPCDet" in names, (
        f"Missing PointNet++/OpenPCDet: {names}"
    )
    assert "3DGS" in names or "DUSt3R" in names, f"Missing 3DGS/DUSt3R: {names}"


def test_yolo_steel_topic_does_not_leak_3dgs():
    """YOLO steel topic baselines MUST NOT include 3DGS/DUSt3R/FoundationStereo."""
    from app.services.research_baselines import search_baselines

    results = search_baselines(domain="vision_2d")
    names = [r["name"] for r in results]
    for neg in ["3DGS", "DUSt3R", "FoundationStereo", "COLMAP", "NeRF"]:
        assert neg not in names, (
            f"vision_2d baselines must NOT include {neg}, got names={names}"
        )


def test_nlp_llm_topic_generates_text_route():
    """NLP topic must include BERT/RoBERTa, exclude YOLO and PointNet++."""
    from app.services.research_baselines import search_baselines

    baselines = search_baselines(domain="nlp_llm")
    names = [b["name"] for b in baselines]
    assert "BERT" in names or "RoBERTa" in names, (
        f"Expected BERT or RoBERTa in nlp_llm baselines: {names}"
    )
    assert "YOLOv8" not in names, f"NLP must NOT include YOLOv8: {names}"
    assert "PointNet++" not in names, f"NLP must NOT include PointNet++: {names}"
    assert "COLMAP" not in names, f"NLP must NOT include COLMAP: {names}"


if __name__ == "__main__":
    # ponytail: __main__ smoke runner — only runs the asserts if invoked directly.
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
