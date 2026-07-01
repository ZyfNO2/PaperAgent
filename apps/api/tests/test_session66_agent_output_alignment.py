from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.services.research_planner_agent import (
    assemble_research_output,
    build_tool_plan,
    run_research_plan,
)
from app.services.retrieval.tool_orchestrator import (
    TOOL_WHITELIST,
    ToolExecutionBundle,
    ToolExecutionResult,
)


def test_build_tool_plan_filters_non_whitelist(monkeypatch):
    from app.services import research_planner_agent as planner

    monkeypatch.setattr(
        planner,
        "_llm_or_empty",
        lambda *args, **kwargs: {
            "topic_atoms": {"raw": "test"},
            "calls": [
                {
                    "call_id": "ok1",
                    "tool": "search_openalex",
                    "target": "paper",
                    "query": "test paper",
                    "when_to_call": "round_1",
                    "why_call": "papers",
                    "how_call": {"top_k": 5},
                    "expected_output": "papers",
                    "stop_condition": "done",
                },
                {
                    "call_id": "bad1",
                    "tool": "rm_rf",
                    "target": "paper",
                    "query": "hack",
                    "when_to_call": "round_1",
                    "why_call": "bad",
                    "how_call": {"top_k": 5},
                    "expected_output": "none",
                    "stop_condition": "done",
                },
            ],
            "human_gate_after": "round_1",
        },
    )

    plan = build_tool_plan(
        {"raw_topic": "test", "domain_route": "vision_2d"},
        {"search_strategies": [{"name": "core", "target_type": "paper", "queries": ["a"]}]},
    )

    assert plan.calls
    assert all(call.tool in TOOL_WHITELIST for call in plan.calls)
    assert {call.call_id for call in plan.calls} == {"ok1"}


def test_assemble_research_output_separates_baseline_parallel_and_gaps():
    topic_parse = {
        "raw_topic": "YOLO steel surface defect detection",
        "method_terms": ["yolov8"],
        "task_terms": ["defect detection"],
        "object_terms": ["steel surface"],
    }
    candidates = [
        {
            "candidate_id": "p1",
            "candidate_type": "paper",
            "title": "YOLOv8: Real-Time Object Detection",
            "abstract": "We introduce YOLOv8 as a new framework for object detection.",
            "url": "https://arxiv.org/abs/1",
        },
        {
            "candidate_id": "p2",
            "candidate_type": "paper",
            "title": "Improved YOLOv8 for Steel Surface Defect Detection",
            "abstract": "Based on YOLOv8, we add attention and feature fusion for steel surface defect detection on NEU-DET.",
            "url": "https://arxiv.org/abs/2",
        },
        {
            "candidate_id": "d1",
            "candidate_type": "dataset",
            "title": "NEU-DET",
            "url": "https://dataset.test/neu-det",
        },
    ]
    screening = {
        "shortlist": [
            {"candidate_id": "p1"},
            {"candidate_id": "p2"},
            {"candidate_id": "d1"},
        ]
    }

    summary = assemble_research_output(topic_parse, candidates, screening, tool_execution={})

    assert len(summary["baseline_candidates"]) == 1
    assert len(summary["parallel_reference_papers"]) == 1
    assert summary["baseline_candidates"][0]["candidate_id"] != summary["parallel_reference_papers"][0]["candidate_id"]
    assert summary["dataset_candidates"][0]["candidate_id"] == "d1"
    assert "未找到可复现仓库" in summary["evidence_gaps"]


def _fake_llm(prompt: str, system: str, *, profile: str = "default", **_: object) -> dict:
    if profile == "topic_understand":
        raw = prompt.split("【学生题目】", 1)[-1].splitlines()[0].strip() if "【学生题目】" in prompt else "unknown"
        return {
            "raw_topic": raw,
            "normalized_topic": raw,
            "domain_route": "vision_2d" if "柴油车" not in raw and "FDTD" not in raw else (
                "energy_power" if "柴油车" in raw else "signal_timeseries"
            ),
            "domain_confidence": 0.8,
            "method_terms": ["YOLO"] if "水声" not in raw and "FDTD" not in raw else (
                ["FDTD"] if "FDTD" in raw else ["machine learning"]
            ),
            "task_terms": ["缺陷检测"] if "柴油车" not in raw and "FDTD" not in raw and "水声" not in raw else (
                ["排放监控"] if "柴油车" in raw else (["微波传输建模"] if "FDTD" in raw else ["分类识别"])
            ),
            "object_terms": ["钢材表面"] if "柴油车" not in raw and "FDTD" not in raw and "水声" not in raw else (
                ["重型柴油车"] if "柴油车" in raw else (["微波传输线"] if "FDTD" in raw else ["水声数据"])
            ),
            "negative_domains": [],
            "needs_clarification": [],
            "query_atoms_en": ["baseline", "dataset", "github"],
            "query_atoms_zh": ["基线", "数据集", "仓库"],
            "llm_output_repaired": False,
            "domain_route_conflict": False,
        }
    if profile == "problem_decompose":
        return {
            "sub_questions": [
                {"id": "sq1", "question": "核心论文有哪些", "priority": 1, "search_intent": "core_papers"},
                {"id": "sq2", "question": "公开数据集有哪些", "priority": 2, "search_intent": "datasets"},
                {"id": "sq3", "question": "可复现仓库有哪些", "priority": 3, "search_intent": "github_repos"},
            ],
            "graduation_safe_path": "复现 baseline",
            "high_risk_path": "提出新方法",
            "human_checkpoints": [],
        }
    if profile == "search_strategy":
        return {
            "topic": "test",
            "domain_route": "vision_2d",
            "search_strategies": [
                {"name": "core_papers", "target_type": "paper", "queries": ["paper query"], "max_results_per_query": 5},
                {"name": "datasets", "target_type": "dataset", "queries": ["dataset query"], "max_results_per_query": 5},
                {"name": "github_repos", "target_type": "repo", "queries": ["repo query"], "max_results_per_query": 5},
            ],
        }
    if profile == "tool_plan":
        return {
            "topic_atoms": {"raw": "test"},
            "calls": [
                {
                    "call_id": "c1",
                    "tool": "search_openalex",
                    "target": "paper",
                    "query": "paper query",
                    "when_to_call": "round_1",
                    "why_call": "papers",
                    "how_call": {"top_k": 5},
                    "expected_output": "papers",
                    "stop_condition": "done",
                },
                {
                    "call_id": "c2",
                    "tool": "search_dataset_web",
                    "target": "dataset",
                    "query": "dataset query",
                    "when_to_call": "round_1",
                    "why_call": "datasets",
                    "how_call": {"top_k": 5},
                    "expected_output": "datasets",
                    "stop_condition": "done",
                },
                {
                    "call_id": "c3",
                    "tool": "search_github",
                    "target": "repo",
                    "query": "repo query",
                    "when_to_call": "round_1",
                    "why_call": "repos",
                    "how_call": {"top_k": 5},
                    "expected_output": "repos",
                    "stop_condition": "done",
                },
            ],
            "human_gate_after": "round_1",
        }
    if profile == "candidate_screen":
        return {
            "shortlist": [
                {
                    "candidate_id": "paper_baseline",
                    "candidate_type": "paper",
                    "relevance_score": 0.9,
                    "quality_score": 0.8,
                    "graduation_fit": "high",
                    "matched_atoms": ["baseline"],
                    "keep_reason": "baseline",
                    "risk_reason": "",
                    "must_verify": [],
                },
                {
                    "candidate_id": "paper_parallel",
                    "candidate_type": "paper",
                    "relevance_score": 0.88,
                    "quality_score": 0.8,
                    "graduation_fit": "high",
                    "matched_atoms": ["parallel"],
                    "keep_reason": "parallel",
                    "risk_reason": "",
                    "must_verify": [],
                },
                {
                    "candidate_id": "dataset_1",
                    "candidate_type": "dataset",
                    "relevance_score": 0.8,
                    "quality_score": 0.7,
                    "graduation_fit": "medium",
                    "matched_atoms": ["dataset"],
                    "keep_reason": "dataset",
                    "risk_reason": "",
                    "must_verify": [],
                },
                {
                    "candidate_id": "repo_1",
                    "candidate_type": "repo",
                    "relevance_score": 0.8,
                    "quality_score": 0.7,
                    "graduation_fit": "medium",
                    "matched_atoms": ["repo"],
                    "keep_reason": "repo",
                    "risk_reason": "",
                    "must_verify": [],
                },
            ],
            "rejected": [],
            "need_retry_queries": [],
            "need_human_confirmation": False,
        }
    if profile == "direction_advice":
        return {
            "directions": [
                {
                    "id": "dir_safe",
                    "title": "复现 baseline 并做轻量改进",
                    "route_type": "graduation_safe",
                    "graduation_fit": "high",
                    "confidence": 0.82,
                    "bound_evidence_ids": ["paper_baseline", "paper_parallel"],
                    "recommended_baselines": ["paper_baseline"],
                    "suggested_modules": ["attention"],
                    "why_graduation_friendly": "证据齐全",
                    "risk_reasons": [],
                    "user_must_confirm": [],
                }
            ],
            "stop_reason": "ready",
        }
    return {}


async def _fake_execute_tool_plan(plan, project_id: str):
    raw_topic = str(plan.topic_atoms.get("raw", ""))
    if "柴油车" in raw_topic:
        baseline_title = "Heavy-duty diesel emission monitoring framework"
        parallel_title = "Remote on-board diagnostics for China VI diesel vehicles"
        dataset_title = "Remote Emission Monitoring Dataset"
        repo_title = "diesel-emission-monitoring"
    elif "FDTD" in raw_topic:
        baseline_title = "FDTD Method for Microwave Transmission Lines"
        parallel_title = "Unconditionally stable FDTD for transmission line analysis"
        dataset_title = "Microwave line simulation benchmark"
        repo_title = "fdtd-microwave-lines"
    else:
        baseline_title = "Machine Learning for Underwater Acoustic Classification"
        parallel_title = "Deep acoustic signal classification with public sonar benchmarks"
        dataset_title = "ShipsEar sonar dataset"
        repo_title = "underwater-acoustic-classification"

    return ToolExecutionBundle(
        project_id=project_id,
        results=[
            ToolExecutionResult(
                call_id="c1",
                tool="search_openalex",
                status="ok",
                result_count=2,
                accepted_count=2,
                candidates=[
                    {
                        "candidate_id": "paper_baseline",
                        "candidate_type": "paper",
                        "title": baseline_title,
                        "abstract": "We introduce a baseline framework and reproducible method with code.",
                        "url": "https://paper.test/baseline",
                        "matched_atoms": ["baseline"],
                    },
                    {
                        "candidate_id": "paper_parallel",
                        "candidate_type": "paper",
                        "title": parallel_title,
                        "abstract": "Based on YOLOv8 we add attention and feature fusion on a benchmark dataset with code.",
                        "url": "https://paper.test/parallel",
                        "matched_atoms": ["parallel"],
                    },
                ],
            ),
            ToolExecutionResult(
                call_id="c2",
                tool="search_dataset_web",
                status="ok",
                result_count=1,
                accepted_count=1,
                candidates=[
                    {
                        "candidate_id": "dataset_1",
                        "candidate_type": "dataset",
                        "title": dataset_title,
                        "url": "https://dataset.test/1",
                    }
                ],
            ),
            ToolExecutionResult(
                call_id="c3",
                tool="search_github",
                status="ok",
                result_count=1,
                accepted_count=1,
                candidates=[
                    {
                        "candidate_id": "repo_1",
                        "candidate_type": "repo",
                        "title": repo_title,
                        "url": "https://github.com/test/repo",
                    }
                ],
            ),
        ],
    )


def _make_clean_result(candidate_id: str):
    payload = {
        "candidate_id": candidate_id,
        "clean_status": "keep",
        "reason": "",
    }
    return SimpleNamespace(
        candidate_id=candidate_id,
        clean_status="keep",
        reason="",
        model_dump=lambda payload=payload: payload,
    )


@pytest.mark.parametrize(
    "topic",
    [
        "53 基于国六标准的重型柴油车远程排放监控系统研发",
        "55 无条件稳定FDTD在微波传输线中的应用研究",
        "59 机器学习在水声数据分类识别中的应用",
    ],
)
def test_three_topic_golden_alignment(monkeypatch, topic: str):
    from app.services import research_planner_agent as planner

    monkeypatch.setattr(planner, "_llm_or_empty", _fake_llm)
    monkeypatch.setattr(planner, "execute_tool_plan", _fake_execute_tool_plan)
    monkeypatch.setattr(
        planner,
        "clean_candidates",
        lambda candidates, topic_atoms, domain="unknown": [
            _make_clean_result(c["candidate_id"])
            for c in candidates
        ],
    )

    result = asyncio.run(run_research_plan(topic, auto_confirm_for_test=True))
    summary = result["research_summary"]

    assert result["_status"] == "ok"
    assert len(summary["reference_papers"]) >= 2 or "参考论文不足，当前少于 2 条已验证论文候选" in summary["evidence_gaps"]
    assert len(summary["baseline_candidates"]) >= 1 or "未找到 baseline，需人工确认可复现基线" in summary["evidence_gaps"]
    assert len(summary["parallel_reference_papers"]) >= 1 or "未找到平行参考，需补充同任务同对象论文" in summary["evidence_gaps"]
    assert len(summary["dataset_candidates"]) >= 1 or "未找到公开数据集或需自采" in summary["evidence_gaps"]
    assert len(summary["repo_candidates"]) >= 1 or "未找到可复现仓库" in summary["evidence_gaps"]

    baseline_ids = {item["candidate_id"] for item in summary["baseline_candidates"]}
    parallel_ids = {item["candidate_id"] for item in summary["parallel_reference_papers"]}
    assert baseline_ids.isdisjoint(parallel_ids)
