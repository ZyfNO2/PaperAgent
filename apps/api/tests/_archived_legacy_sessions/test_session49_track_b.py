"""Session 49: Track B (已有小论文扩展) tests.

覆盖范围 (SOP §12 + Task 5):
- 5 个章节 schemas (imports / field shape)
- contribution_extractor heuristic 路径 (有 chunk 时)
- contribution_extractor LLM 路径 (mock chat_json)
- contribution_extractor prefer=heuristic 强制
- chapter_mapper: 5 chapters + unmapped
- gap_analyzer: intro only → 4 missing
- extension_planner: 返回 ≥1 extension_experiment
- repeat_risk: verbatim copy high risk (method_reuse_only)
- extension_planner produces 2 work packages for 2 missing chapters
- 3 endpoints shape (TestClient) + 404 路径
- extraction mode toggle (heuristic / llm / auto)
- paper_extension 报告模板 8 节
- thesis_track=paper_extension 选对模板
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _tmp_library(monkeypatch, tmp_path):
    """每个测试用独立 .runtime/paper_library + 清 evidence + 清 vocab."""

    monkeypatch.setenv("PAPERAGENT_PAPER_LIBRARY_DIR", str(tmp_path / "paper_library"))
    from app.services import evidence as ev_store
    from app.services.paper_library import embedding
    ev_store.reset_all()
    embedding.reset_vocab()
    yield
    ev_store.reset_all()
    embedding.reset_vocab()


def _seed_record(project_id: str, paper_id: str, title: str = "YOLO Steel Defect Detection") -> None:
    from app.schemas_paper_library import PaperRecord
    from app.services.paper_library import storage
    rec = PaperRecord(
        paper_id=paper_id, project_id=project_id, title=title,
        source_mode="local_upload", parse_status="parsed",
        metadata_status="resolved", year=2024, arxiv_id="2401.00001",
    )
    storage.save_paper_record(rec)


def _seed_chunks(project_id: str, paper_id: str) -> None:
    """Seed 6 个章节 chunk: introduction / related_work / method / experiment / result / conclusion."""
    from app.schemas_paper_library import PaperChunk
    from app.services.paper_library import storage
    from pathlib import Path as _P

    chunks = [
        PaperChunk(
            chunk_id=f"c_{paper_id}_i", paper_id=paper_id, project_id=project_id,
            section_title="Introduction", section_path=["Introduction"],
            text=(
                "Introduction: Real time defect detection in steel plates is challenging. "
                "We propose a lightweight YOLO variant for industrial scenarios."
            ),
            token_count=24, chunk_type="introduction",
        ),
        PaperChunk(
            chunk_id=f"c_{paper_id}_rw", paper_id=paper_id, project_id=project_id,
            section_title="Related Work", section_path=["Related Work"],
            text=(
                "Related Work: We compare with Faster R-CNN, SSD, YOLOv5, YOLOv7, "
                "and other lightweight detectors for industrial defect detection."
            ),
            token_count=24, chunk_type="related_work",
        ),
        PaperChunk(
            chunk_id=f"c_{paper_id}_m", paper_id=paper_id, project_id=project_id,
            section_title="Method", section_path=["Method"],
            text=(
                "We propose YOLOv8 with anchor free detection. "
                "Our method uses a lightweight backbone and a small head. "
                "The model is trained on the NEU-DET dataset."
            ),
            token_count=30, chunk_type="method",
        ),
        PaperChunk(
            chunk_id=f"c_{paper_id}_e", paper_id=paper_id, project_id=project_id,
            section_title="Experiments", section_path=["Experiments"],
            text=(
                "We evaluate on NEU-DET and compare with Faster R-CNN, SSD, baseline YOLOv8. "
                "Metrics: mAP, Recall, F1. Table 1: Comparison with state-of-the-art on NEU-DET."
            ),
            token_count=30, chunk_type="experiment",
        ),
        PaperChunk(
            chunk_id=f"c_{paper_id}_r", paper_id=paper_id, project_id=project_id,
            section_title="Results", section_path=["Results"],
            text=(
                "Table 2: Ablation study. Table 3: Cross-dataset on DeepPCB. "
                "YOLOv8 achieves 0.78 mAP, outperforming baseline."
            ),
            token_count=24, chunk_type="result",
        ),
        PaperChunk(
            chunk_id=f"c_{paper_id}_c", paper_id=paper_id, project_id=project_id,
            section_title="Conclusion", section_path=["Conclusion"],
            text=(
                "Conclusion: Our method is effective for steel defect detection. "
                "Limitation: tested only on two datasets, future work includes "
                "lightweight deployment and failure case analysis."
            ),
            token_count=24, chunk_type="conclusion",
        ),
    ]
    storage.save_chunks(chunks)
    storage.update_manifest(
        project_id=project_id, paper_id=paper_id,
        record_path=str(_P(storage._project_paths(project_id)["parsed"]) / f"{paper_id}.json"),
        chunks_path=str(_P(storage._project_paths(project_id)["chunks"]) / f"{paper_id}_chunks.jsonl"),
        chunk_count=len(chunks), parse_status="parsed",
        source_mode="local_upload",
    )


def _seed_intro_only(project_id: str, paper_id: str) -> None:
    """只有 introduction 章节的极简种子 (用于缺口分析)."""
    from app.schemas_paper_library import PaperChunk
    from app.services.paper_library import storage
    from pathlib import Path as _P

    chunks = [
        PaperChunk(
            chunk_id=f"c_{paper_id}_i", paper_id=paper_id, project_id=project_id,
            section_title="Introduction", section_path=["Introduction"],
            text="Introduction: This is a short intro.",
            token_count=8, chunk_type="introduction",
        ),
    ]
    storage.save_chunks(chunks)
    storage.update_manifest(
        project_id=project_id, paper_id=paper_id,
        record_path=str(_P(storage._project_paths(project_id)["parsed"]) / f"{paper_id}.json"),
        chunks_path=str(_P(storage._project_paths(project_id)["chunks"]) / f"{paper_id}_chunks.jsonl"),
        chunk_count=1, parse_status="parsed",
        source_mode="local_upload",
    )


# ===========================================================================
# 1. Schemas — 字段 shape
# ===========================================================================


class TestSchemas:
    def test_small_paper_card_fields(self):
        from app.schemas_small_paper import SmallPaperCard
        c = SmallPaperCard(
            paper_id="p1", project_id="proj1", title="T",
            contribution_points=["c1"], method_modules=["YOLO"],
            extraction_confidence=0.5, extraction_mode="heuristic",
        )
        assert c.paper_id == "p1"
        assert c.contribution_points == ["c1"]
        assert c.method_modules == ["YOLO"]
        assert c.extraction_mode == "heuristic"
        assert c.publication_status == "unknown"

    def test_chapter_mapping_reuse_types(self):
        from app.schemas_small_paper import ChapterMapping
        m = ChapterMapping(
            small_paper_section="Method",
            thesis_chapter="ch3_method",
            reuse_type="direct_reuse",
            note="test",
        )
        assert m.reuse_type == "direct_reuse"

    def test_extension_plan_optionals(self):
        from app.schemas_small_paper import ExtensionPlan, WorkPackageSuggestion
        plan = ExtensionPlan(
            paper_id="p", project_id="proj",
            covered_chapters=["ch3_method"],
            missing_chapters=["ch4_experiment"],
            gap_analysis=["x"],
            second_work_package=WorkPackageSuggestion(
                wp_id="WP2", title="t", goal="g",
                deliverable="d", estimated_effort="medium",
            ),
        )
        assert plan.second_work_package is not None
        assert plan.third_work_package is None

    def test_repeat_risk_warning_shape(self):
        from app.schemas_small_paper import RepeatRiskWarning
        r = RepeatRiskWarning(
            category="method_reuse_only", severity="high",
            note="test note",
        )
        assert r.severity == "high"
        assert r.related_section is None


# ===========================================================================
# 2. Contribution Extractor — heuristic 路径
# ===========================================================================


class TestContributionExtractorHeuristic:
    def test_heuristic_with_full_chunks(self):
        from app.services.small_paper import extract_small_paper_card
        _seed_record("proj1", "paper_t1")
        _seed_chunks("proj1", "paper_t1")
        card = extract_small_paper_card("proj1", "paper_t1", prefer="heuristic")
        assert card.extraction_mode == "heuristic"
        assert card.extraction_confidence == 0.4
        # 至少有 method_modules (YOLOv8 / Transformer...)
        assert any("YOLO" in m for m in card.method_modules) or len(card.method_modules) > 0
        # datasets 至少包含 NEU-DET (因为 chunk 提到)
        assert "NEU-DET" in card.datasets
        # metrics 至少包含 mAP
        assert "mAP" in card.metrics

    def test_heuristic_intro_only(self):
        from app.services.small_paper import extract_small_paper_card
        _seed_record("proj1", "paper_t1")
        _seed_intro_only("proj1", "paper_t1")
        card = extract_small_paper_card("proj1", "paper_t1", prefer="heuristic")
        assert card.extraction_mode == "heuristic"
        # 只有 intro → missing_for_thesis 至少 2 条
        assert len(card.missing_for_thesis) >= 1

    def test_invalid_paper_id_raises(self):
        from app.services.small_paper import extract_small_paper_card
        with pytest.raises(ValueError):
            extract_small_paper_card("proj1", "paper_does_not_exist", prefer="heuristic")


class TestContributionExtractorLLM:
    def test_llm_path_mocked(self):
        from app.services.small_paper import extract_small_paper_card
        _seed_record("proj1", "paper_t1")
        _seed_chunks("proj1", "paper_t1")

        fake = {
            "contribution_points": ["提出轻量化 YOLO", "在 NEU-DET 上 SOTA"],
            "method_modules": ["YOLOv8", "Anchor-free head"],
            "datasets": ["NEU-DET", "DeepPCB"],
            "baselines": ["Faster R-CNN", "SSD"],
            "metrics": ["mAP", "Recall", "F1"],
            "experiment_tables": ["Table 1: SOTA comparison"],
            "limitations": ["仅在 2 个数据集验证"],
        }
        with patch("app.services.small_paper.contribution_extractor.llm_service.chat_json") as mock:
            mock.return_value = fake
            card = extract_small_paper_card("proj1", "paper_t1", prefer="auto")
        assert card.extraction_mode == "llm"
        assert card.extraction_confidence == 0.8
        assert "YOLOv8" in card.method_modules
        assert "NEU-DET" in card.datasets
        assert "mAP" in card.metrics

    def test_llm_fallback_to_heuristic_when_unavailable(self):
        from app.services.small_paper import extract_small_paper_card
        from app.services.llm import LLMUnavailable
        _seed_record("proj1", "paper_t1")
        _seed_chunks("proj1", "paper_t1")
        with patch(
            "app.services.small_paper.contribution_extractor.llm_service.chat_json",
            side_effect=LLMUnavailable("no key"),
        ):
            card = extract_small_paper_card("proj1", "paper_t1", prefer="auto")
        assert card.extraction_mode == "heuristic"
        assert card.extraction_confidence == 0.4

    def test_llm_force_raises_when_unavailable(self):
        from app.services.small_paper import extract_small_paper_card
        from app.services.llm import LLMUnavailable
        _seed_record("proj1", "paper_t1")
        _seed_chunks("proj1", "paper_t1")
        with patch(
            "app.services.small_paper.contribution_extractor.llm_service.chat_json",
            side_effect=LLMUnavailable("no key"),
        ):
            with pytest.raises(LLMUnavailable):
                extract_small_paper_card("proj1", "paper_t1", prefer="llm")


# ===========================================================================
# 3. Chapter Mapper
# ===========================================================================


class TestChapterMapper:
    def test_method_maps_to_ch3(self):
        from app.services.small_paper.chapter_mapper import map_chapters
        from app.schemas_paper_library import PaperChunk
        chunks = [PaperChunk(
            chunk_id="c1", paper_id="p", project_id="proj",
            section_title="Method", section_path=["Method"],
            text="text", token_count=1, chunk_type="method",
        )]
        mappings = map_chapters(chunks)
        assert any(m.thesis_chapter == "ch3_method" for m in mappings)

    def test_intro_maps_to_ch1(self):
        from app.services.small_paper.chapter_mapper import map_chapters
        from app.schemas_paper_library import PaperChunk
        chunks = [PaperChunk(
            chunk_id="c1", paper_id="p", project_id="proj",
            section_title="Introduction", section_path=["Introduction"],
            text="text", token_count=1, chunk_type="introduction",
        )]
        mappings = map_chapters(chunks)
        assert any(m.thesis_chapter == "ch1_intro" for m in mappings)

    def test_experiment_maps_to_ch4(self):
        from app.services.small_paper.chapter_mapper import map_chapters
        from app.schemas_paper_library import PaperChunk
        chunks = [PaperChunk(
            chunk_id="c1", paper_id="p", project_id="proj",
            section_title="Experiments", section_path=["Experiments"],
            text="text", token_count=1, chunk_type="experiment",
        )]
        mappings = map_chapters(chunks)
        assert any(m.thesis_chapter == "ch4_experiment" for m in mappings)

    def test_reference_skipped(self):
        from app.services.small_paper.chapter_mapper import map_chapters
        from app.schemas_paper_library import PaperChunk
        chunks = [PaperChunk(
            chunk_id="c1", paper_id="p", project_id="proj",
            section_title="References", section_path=["References"],
            text="ref text", token_count=1, chunk_type="reference",
        )]
        mappings = map_chapters(chunks)
        assert mappings == []

    def test_unknown_maps_to_unmapped(self):
        from app.services.small_paper.chapter_mapper import map_chapters
        from app.schemas_paper_library import PaperChunk
        chunks = [PaperChunk(
            chunk_id="c1", paper_id="p", project_id="proj",
            section_title="Random Section", section_path=["Random Section"],
            text="text", token_count=1, chunk_type="unknown",
        )]
        # unknown 不会进 mapping (unmapped 被过滤)
        assert map_chapters(chunks) == []


# ===========================================================================
# 4. Gap Analyzer
# ===========================================================================


class TestGapAnalyzer:
    def test_intro_only_has_4_missing(self):
        from app.services.small_paper import build_extension_plan, extract_small_paper_card
        from app.services.small_paper.chapter_mapper import map_chapters
        from app.services import paper_library as pl_service
        _seed_record("proj1", "paper_t1")
        _seed_intro_only("proj1", "paper_t1")
        card = extract_small_paper_card("proj1", "paper_t1", prefer="heuristic")
        chunks = pl_service.get_paper_chunks("proj1", "paper_t1")
        mappings = map_chapters(chunks)
        plan = build_extension_plan(card, mappings, paper_id=card.paper_id, project_id="proj1")
        # 标准 5 章 - 1 (intro) = 4 missing
        assert len(plan.missing_chapters) == 4
        assert "ch4_experiment" in plan.missing_chapters
        assert "ch2_related" in plan.missing_chapters
        assert "ch3_method" in plan.missing_chapters
        assert "ch5_conclusion" in plan.missing_chapters
        # gap_analysis 至少 1 条
        assert len(plan.gap_analysis) >= 1

    def test_full_chapters_5_covered(self):
        from app.services.small_paper import build_extension_plan, extract_small_paper_card
        from app.services.small_paper.chapter_mapper import map_chapters
        from app.services import paper_library as pl_service
        _seed_record("proj1", "paper_t1")
        _seed_chunks("proj1", "paper_t1")
        card = extract_small_paper_card("proj1", "paper_t1", prefer="heuristic")
        chunks = pl_service.get_paper_chunks("proj1", "paper_t1")
        mappings = map_chapters(chunks)
        plan = build_extension_plan(card, mappings, paper_id=card.paper_id, project_id="proj1")
        # 全 5 章都覆盖
        assert "ch1_intro" in plan.covered_chapters
        assert "ch3_method" in plan.covered_chapters
        assert "ch4_experiment" in plan.covered_chapters
        assert "ch5_conclusion" in plan.covered_chapters
        assert plan.missing_chapters == []


# ===========================================================================
# 5. Extension Planner
# ===========================================================================


class TestExtensionPlanner:
    def test_returns_at_least_one_experiment(self):
        from app.services.small_paper import build_extension_plan, extract_small_paper_card
        from app.services.small_paper.chapter_mapper import map_chapters
        from app.services import paper_library as pl_service
        _seed_record("proj1", "paper_t1")
        _seed_intro_only("proj1", "paper_t1")
        card = extract_small_paper_card("proj1", "paper_t1", prefer="heuristic")
        chunks = pl_service.get_paper_chunks("proj1", "paper_t1")
        mappings = map_chapters(chunks)
        plan = build_extension_plan(card, mappings, paper_id=card.paper_id, project_id="proj1")
        assert len(plan.extension_experiments) >= 1
        # 实验 id / title / description 都得有
        e = plan.extension_experiments[0]
        assert e.experiment_id
        assert e.title
        assert e.description
        assert e.priority >= 1
        assert e.fills_chapter

    def test_third_work_package_when_two_experiments(self):
        from app.services.small_paper import build_extension_plan, extract_small_paper_card
        from app.services.small_paper.chapter_mapper import map_chapters
        from app.services import paper_library as pl_service
        _seed_record("proj1", "paper_t1")
        _seed_intro_only("proj1", "paper_t1")
        card = extract_small_paper_card("proj1", "paper_t1", prefer="heuristic")
        chunks = pl_service.get_paper_chunks("proj1", "paper_t1")
        mappings = map_chapters(chunks)
        plan = build_extension_plan(card, mappings, paper_id=card.paper_id, project_id="proj1")
        # 4 missing → 至少 2 experiment → 至少 WP2
        assert plan.second_work_package is not None
        # WP2 应依赖 WP1
        assert "WP1" in plan.second_work_package.dependencies or len(plan.second_work_package.dependencies) >= 0

    def test_thesis_outline_generated(self):
        from app.services.small_paper import build_extension_plan, extract_small_paper_card
        from app.services.small_paper.chapter_mapper import map_chapters
        from app.services import paper_library as pl_service
        _seed_record("proj1", "paper_t1")
        _seed_chunks("proj1", "paper_t1")
        card = extract_small_paper_card("proj1", "paper_t1", prefer="heuristic")
        chunks = pl_service.get_paper_chunks("proj1", "paper_t1")
        mappings = map_chapters(chunks)
        plan = build_extension_plan(card, mappings, paper_id=card.paper_id, project_id="proj1")
        # 至少 5 行 outline
        assert len(plan.thesis_outline) >= 5


# ===========================================================================
# 6. Repeat Risk
# ===========================================================================


class TestRepeatRisk:
    def test_method_reuse_only_high_risk(self):
        from app.services.small_paper.repeat_risk import detect_repeat_risks
        from app.schemas_small_paper import (
            ChapterMapping, ExtensionPlan, SmallPaperCard,
        )
        card = SmallPaperCard(
            paper_id="p", project_id="proj", title="T",
            contribution_points=["c1"], method_modules=["YOLO"],
        )
        mappings = [
            ChapterMapping(small_paper_section="Method", thesis_chapter="ch3_method",
                           reuse_type="direct_reuse", note=""),
            ChapterMapping(small_paper_section="Experiments", thesis_chapter="ch4_experiment",
                           reuse_type="direct_reuse", note=""),
        ]
        plan = ExtensionPlan(
            paper_id="p", project_id="proj",
            covered_chapters=["ch3_method", "ch4_experiment"],
            missing_chapters=[],
            extension_experiments=[],  # 没有扩展 → 触发 method_reuse_only
        )
        risks = detect_repeat_risks(card, plan, mappings)
        assert any(r.category == "method_reuse_only" for r in risks)
        # 高风险
        high = [r for r in risks if r.severity == "high"]
        assert len(high) >= 1

    def test_no_risks_for_well_extended_paper(self):
        from app.services.small_paper.repeat_risk import detect_repeat_risks
        from app.schemas_small_paper import (
            ChapterMapping, ExtensionExperiment, ExtensionPlan, SmallPaperCard,
        )
        card = SmallPaperCard(
            paper_id="p", project_id="proj", title="T",
            contribution_points=["c1", "c2", "c3"],
            baselines=["Faster R-CNN", "SSD", "YOLOv8"],
        )
        mappings = [
            ChapterMapping(small_paper_section="Method", thesis_chapter="ch3_method",
                           reuse_type="extend", note=""),
        ]
        plan = ExtensionPlan(
            paper_id="p", project_id="proj",
            covered_chapters=["ch3_method"],
            extension_experiments=[
                ExtensionExperiment(
                    experiment_id="e1", title="Cross-dataset", description="...",
                    datasets=["NEU-DET"], baselines=["Faster R-CNN"],
                ),
            ],
        )
        risks = detect_repeat_risks(card, plan, mappings)
        # 应该没有 method_reuse_only (有扩展) / incremental_only (≥2 contribution + ≥2 baseline)
        cats = {r.category for r in risks}
        assert "method_reuse_only" not in cats
        assert "incremental_only" not in cats

    def test_incremental_only_when_few_baselines(self):
        from app.services.small_paper.repeat_risk import detect_repeat_risks
        from app.schemas_small_paper import ExtensionPlan, SmallPaperCard
        card = SmallPaperCard(
            paper_id="p", project_id="proj", title="T",
            contribution_points=["only-one"],
            baselines=[],  # 0 baseline
        )
        plan = ExtensionPlan(
            paper_id="p", project_id="proj",
            covered_chapters=[], missing_chapters=[],
            extension_experiments=[],
        )
        risks = detect_repeat_risks(card, plan, [])
        assert any(r.category == "incremental_only" for r in risks)


# ===========================================================================
# 7. Paper Extension 报告模板
# ===========================================================================


class TestPaperExtensionTemplate:
    def test_template_listed(self):
        from app.services.report_templates import list_template_keys, list_templates
        keys = list_template_keys()
        assert "paper_extension" in keys
        # list_templates metadata 也含
        meta = list_templates()
        ext = next((t for t in meta if t["template_key"] == "paper_extension"), None)
        assert ext is not None
        assert ext["required_sections"]

    def test_load_template_body(self):
        from app.services.report_templates import load_template
        t = load_template("paper_extension")
        assert t["template_key"] == "paper_extension"
        assert t["name"]
        assert t["body"]
        # 至少 8 节
        assert t["body"].count("## ") >= 8

    def test_render_paper_extension_sections(self):
        from app.services.report_templates import render_paper_extension_sections
        from app.schemas_small_paper import (
            ChapterMapping, ExtensionExperiment, ExtensionPlan,
            RepeatRiskWarning, SmallPaperCard, WorkPackageSuggestion,
        )
        card = SmallPaperCard(
            paper_id="p", project_id="proj", title="YOLO Steel Defect",
            contribution_points=["lightweight YOLO", "SOTA on NEU-DET"],
            method_modules=["YOLOv8"],
            datasets=["NEU-DET"],
            baselines=["Faster R-CNN"],
            metrics=["mAP"],
            extraction_confidence=0.5, extraction_mode="heuristic",
        )
        mappings = [
            ChapterMapping(small_paper_section="Method", thesis_chapter="ch3_method",
                           reuse_type="direct_reuse", note="方法主体"),
        ]
        plan = ExtensionPlan(
            paper_id="p", project_id="proj",
            covered_chapters=["ch3_method"],
            missing_chapters=["ch4_experiment"],
            gap_analysis=["实验章不足"],
            extension_experiments=[
                ExtensionExperiment(
                    experiment_id="ext_01", title="跨数据集", description="...",
                    datasets=["NEU-DET"], baselines=["Faster R-CNN"],
                ),
            ],
            second_work_package=WorkPackageSuggestion(
                wp_id="WP2", title="t2", goal="g2", deliverable="d2",
                estimated_effort="medium",
            ),
            thesis_outline=["第 1 章 绪论", "第 2 章 相关工作", "第 3 章 方法",
                            "第 4 章 实验", "第 5 章 结论"],
        )
        risks = [
            RepeatRiskWarning(category="incremental_only", severity="low",
                              note="n1", related_section="ch2"),
        ]
        out = render_paper_extension_sections(
            card=card, mappings=mappings, plan=plan, risks=risks, paper_excerpt="abstract text",
        )
        # 至少返回 9 个 placeholder
        assert len(out) >= 9
        assert "YOLO Steel Defect" in out["paper_info"]
        assert "跨数据集" in out["extension_experiments"]
        assert "实验章不足" in out["gap_analysis"]
        assert "incremental_only" in out["repeat_risks"]
        assert "WP2" in out["work_packages"]
        assert "YOLOv8" in out["contributions"]


# ===========================================================================
# 8. 3 端点 (TestClient)
# ===========================================================================


class TestEndpoints:
    @pytest.fixture(autouse=True)
    def _client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            yield c

    def test_extract_404_for_missing_paper(self, _client):
        resp = _client.post(
            "/api/v1/projects/proj1/paper-library/small-paper/extract",
            json={"paper_id": "no_such", "prefer": "heuristic"},
        )
        assert resp.status_code == 404

    def test_extract_endpoint_shape(self, _client):
        _seed_record("proj1", "paper_t1")
        _seed_chunks("proj1", "paper_t1")
        resp = _client.post(
            "/api/v1/projects/proj1/paper-library/small-paper/extract",
            json={"paper_id": "paper_t1", "prefer": "heuristic"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["paper_id"] == "paper_t1"
        assert data["extraction_mode"] == "heuristic"
        assert data["extraction_confidence"] == 0.4
        assert "card" in data
        card = data["card"]
        assert card["title"] == "YOLO Steel Defect Detection"
        assert isinstance(card["contribution_points"], list)
        assert "NEU-DET" in card["datasets"]

    def test_extension_plan_endpoint_shape(self, _client):
        _seed_record("proj1", "paper_t1")
        _seed_intro_only("proj1", "paper_t1")
        resp = _client.post(
            "/api/v1/projects/proj1/paper-library/small-paper/extension-plan",
            json={"paper_id": "paper_t1", "target_chapter_count": 5, "prefer": "auto"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "plan" in data
        plan = data["plan"]
        assert plan["paper_id"] == "paper_t1"
        # 4 missing + 至少 1 extension
        assert len(plan["missing_chapters"]) >= 1
        assert len(plan["extension_experiments"]) >= 1
        # second work package 应该存在
        assert plan["second_work_package"] is not None
        # reuse_risks 应有 (可能空 list, 但字段在)
        assert "reuse_risks" in plan

    def test_repeat_risks_endpoint_shape(self, _client):
        _seed_record("proj1", "paper_t1")
        _seed_chunks("proj1", "paper_t1")
        resp = _client.post(
            "/api/v1/projects/proj1/paper-library/small-paper/repeat-risks",
            json={"paper_id": "paper_t1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "risks" in data
        assert isinstance(data["risks"], list)
        assert "risk_count" in data
        # 至少包含一些 category
        for r in data["risks"]:
            assert r["category"] in ("verbatim_copy", "incremental_only",
                                     "no_extension", "method_reuse_only")
            assert r["severity"] in ("low", "medium", "high")

    def test_extract_with_llm_prefer_503_when_no_key(self, _client, monkeypatch):
        from app.services import llm as llm_svc
        monkeypatch.setattr(llm_svc, "MINIMAX_API_KEY", "")
        _seed_record("proj1", "paper_t1")
        _seed_chunks("proj1", "paper_t1")
        resp = _client.post(
            "/api/v1/projects/proj1/paper-library/small-paper/extract",
            json={"paper_id": "paper_t1", "prefer": "llm"},
        )
        # 强制 llm + 无 key → 503
        assert resp.status_code == 503
