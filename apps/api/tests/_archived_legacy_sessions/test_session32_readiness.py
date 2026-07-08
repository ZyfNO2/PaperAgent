"""Session 32: 学校模板合规与导出前检查 — 8 backend tests.

S32-1: 完整报告 readiness pass
S32-2: 缺技术路线 fail
S32-3: 缺 EvidenceRef fail
S32-4: 夸大创新词 fail
S32-5: cv_ai 缺数据集 fail
S32-6: engineering 模板检查技术路线
S32-7: default 模板允许轻量但不允许空证据
S32-8: readiness 可序列化
"""

from __future__ import annotations

import json

from app.schemas_readiness import (
    ReadinessDimension,
    ReadinessStatus,
)
from app.services.readiness import check_readiness


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def _full_sections() -> list[dict]:
    """All 12 sections present with non-empty content."""
    return [
        {"section_id": "topic_direction", "content": "题目方向", "evidence_refs": ["E1"]},
        {"section_id": "background", "content": "研究背景内容" * 10, "evidence_refs": ["E1"]},
        {"section_id": "literature_review", "content": "国内外研究现状" * 10, "evidence_refs": ["E1"]},
        {"section_id": "research_objectives", "content": "研究目标内容" * 5},
        {"section_id": "research_content", "content": "研究内容" * 10, "evidence_refs": ["E1"]},
        {"section_id": "technical_approach", "content": "技术路线内容" * 10, "evidence_refs": ["E1"]},
        {"section_id": "dataset_experiment", "content": "数据集与实验" * 5},
        {"section_id": "innovation", "content": "创新点1: 改进算法效率\n创新点2: 多尺度融合"},
        {"section_id": "workload", "content": "- 阶段1: 文献调研\n- 阶段2: 数据收集\n- 阶段3: 模型训练\n- 阶段4: 实验验证\n- 阶段5: 论文撰写"},
        {"section_id": "feasibility_risk", "content": "风险: 数据不足; 备选: 使用公开数据集"},
        {"section_id": "reference_resources", "content": "参考资源列表", "evidence_refs": ["E1"]},
        {"section_id": "missing_evidence", "content": "待补: 开源代码"},
    ]


def _verified_citations() -> list[dict]:
    return [
        {"ref_no": "E1", "evidence_id": "auto_001", "review_status": "accepted", "title": "Paper A"},
        {"ref_no": "D1", "evidence_id": "auto_002", "review_status": "core", "title": "Dataset B"},
    ]


# -------------------------------------------------------------------
# S32-1: 完整报告 readiness pass
# -------------------------------------------------------------------


class TestFullReportPass:
    def test_full_report_all_pass(self):
        report = check_readiness(
            sections=_full_sections(),
            citations=_verified_citations(),
            template_key="default",
            proposal_markdown="# 开题报告\n" + "内容" * 200,
            project_id="test_full",
        )
        assert report.overall_status == ReadinessStatus.pass_
        assert report.export_allowed is True
        assert len(report.hard_blocks) == 0
        for dim in report.dimensions:
            assert dim.status == ReadinessStatus.pass_, f"{dim.dimension}: {dim.message}"


# -------------------------------------------------------------------
# S32-2: 缺技术路线 fail
# -------------------------------------------------------------------


class TestMissingTechnicalApproach:
    def test_missing_technical_approach_fails(self):
        sections = _full_sections()
        sections = [s for s in sections if s["section_id"] != "technical_approach"]
        report = check_readiness(
            sections=sections,
            citations=_verified_citations(),
            template_key="default",
            project_id="test_no_ta",
        )
        assert report.overall_status == ReadinessStatus.fail
        assert report.export_allowed is False
        assert "section_completeness" in report.hard_blocks


# -------------------------------------------------------------------
# S32-3: 缺 EvidenceRef fail
# -------------------------------------------------------------------


class TestNoEvidenceRef:
    def test_empty_citations_fails(self):
        report = check_readiness(
            sections=_full_sections(),
            citations=[],
            template_key="default",
            proposal_markdown="# 报告\n" + "内容" * 200,
            project_id="test_no_ev",
        )
        assert report.overall_status == ReadinessStatus.fail
        assert report.export_allowed is False
        assert "reference_integrity" in report.hard_blocks


# -------------------------------------------------------------------
# S32-4: 夸大创新词 fail
# -------------------------------------------------------------------


class TestInflatedInnovation:
    def test_hype_word_fails(self):
        sections = _full_sections()
        # Inject hype word into innovation
        for s in sections:
            if s["section_id"] == "innovation":
                s["content"] = "本研究首次提出了一种全新框架"
        report = check_readiness(
            sections=sections,
            citations=_verified_citations(),
            template_key="default",
            proposal_markdown="# 报告\n" + "内容" * 200,
            project_id="test_hype",
        )
        assert report.overall_status == ReadinessStatus.fail
        assert report.export_allowed is False
        assert "innovation_claim_safety" in report.hard_blocks
        innov_dim = next(d for d in report.dimensions if d.dimension == "innovation_claim_safety")
        assert "首次" in innov_dim.message


# -------------------------------------------------------------------
# S32-5: cv_ai 缺数据集 fail
# -------------------------------------------------------------------


class TestCvAiMissingDataset:
    def test_cv_ai_no_dataset_fails(self):
        sections = _full_sections()
        sections = [s for s in sections if s["section_id"] != "dataset_experiment"]
        report = check_readiness(
            sections=sections,
            citations=_verified_citations(),
            template_key="cv_ai",
            project_id="test_cv_ai",
        )
        assert report.overall_status == ReadinessStatus.fail
        assert report.export_allowed is False
        assert "school_template_fit" in report.hard_blocks


# -------------------------------------------------------------------
# S32-6: engineering 模板检查技术路线
# -------------------------------------------------------------------


class TestEngineeringTemplate:
    def test_engineering_requires_technical_approach(self):
        sections = _full_sections()
        sections = [s for s in sections if s["section_id"] != "technical_approach"]
        report = check_readiness(
            sections=sections,
            citations=_verified_citations(),
            template_key="engineering",
            project_id="test_eng",
        )
        assert report.overall_status == ReadinessStatus.fail
        fit_dim = next(d for d in report.dimensions if d.dimension == "school_template_fit")
        assert "technical_approach" in fit_dim.section_refs

    def test_engineering_full_passes(self):
        report = check_readiness(
            sections=_full_sections(),
            citations=_verified_citations(),
            template_key="engineering",
            proposal_markdown="# 报告\n" + "内容" * 200,
            project_id="test_eng_ok",
        )
        fit_dim = next(d for d in report.dimensions if d.dimension == "school_template_fit")
        assert fit_dim.status == ReadinessStatus.pass_


# -------------------------------------------------------------------
# S32-7: default 模板允许轻量但不允许空证据
# -------------------------------------------------------------------


class TestDefaultTemplateLightweight:
    def test_default_allows_light_sections_but_not_empty_evidence(self):
        """Default template: fewer sections OK but reference_integrity still required."""
        sections = [
            {"section_id": "topic_direction", "content": "方向", "evidence_refs": ["E1"]},
            {"section_id": "background", "content": "背景" * 20, "evidence_refs": ["E1"]},
            {"section_id": "literature_review", "content": "综述" * 20, "evidence_refs": ["E1"]},
            {"section_id": "research_objectives", "content": "目标" * 10},
            {"section_id": "research_content", "content": "内容" * 20, "evidence_refs": ["E1"]},
            {"section_id": "technical_approach", "content": "路线" * 20, "evidence_refs": ["E1"]},
            {"section_id": "dataset_experiment", "content": "数据集" * 10},
            {"section_id": "innovation", "content": "改进效率\n轻量化设计"},
            {"section_id": "workload", "content": "- 阶段1\n- 阶段2\n- 阶段3\n- 阶段4\n- 阶段5"},
            {"section_id": "feasibility_risk", "content": "风险可控"},
            {"section_id": "reference_resources", "content": "资源列表"},
            {"section_id": "missing_evidence", "content": "无"},
        ]
        report = check_readiness(
            sections=sections,
            citations=[],  # No verified citations
            template_key="default",
            proposal_markdown="# 报告\n" + "内容" * 200,
            project_id="test_default_light",
        )
        assert report.export_allowed is False
        assert "reference_integrity" in report.hard_blocks


# -------------------------------------------------------------------
# S32-8: readiness 可序列化
# -------------------------------------------------------------------


class TestReadinessSerializable:
    def test_report_json_roundtrip(self):
        report = check_readiness(
            sections=_full_sections(),
            citations=_verified_citations(),
            template_key="default",
            proposal_markdown="# 报告\n" + "内容" * 200,
            project_id="test_ser",
        )
        data = report.model_dump()
        assert isinstance(data, dict)
        # JSON roundtrip
        json_str = json.dumps(data, ensure_ascii=False)
        restored = json.loads(json_str)
        assert restored["project_id"] == "test_ser"
        assert restored["overall_status"] == "pass"
        assert len(restored["dimensions"]) == 8

    def test_dimension_json_roundtrip(self):
        dim = ReadinessDimension(
            dimension="test",
            status=ReadinessStatus.warn,
            message="测试",
            required_fix="修复",
            section_refs=["a", "b"],
        )
        data = dim.model_dump()
        json_str = json.dumps(data, ensure_ascii=False)
        restored = json.loads(json_str)
        assert restored["dimension"] == "test"
        assert restored["status"] == "warn"
        assert restored["section_refs"] == ["a", "b"]
