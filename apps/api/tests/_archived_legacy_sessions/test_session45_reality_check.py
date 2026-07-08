"""Session 45: RealityCheck + GoalLevel 两档化测试."""

from __future__ import annotations

from app.schemas import (
    EvidenceSummary,
    KeywordBreakdown,
    OneTopicRequest,
    PaperHit,
    DatasetHit,
    BaselineHit,
)
from app.schemas_reality import RealityCheck, get_cycle_matrix
from app.services.reality_check import (
    assess_reality,
    apply_reality_to_verdict,
    _determine_resource_tier,
    _determine_cycle,
    _is_heavy_compute,
)


# ---------- GoalLevel 两档 + 兼容映射 ---------- #


class TestGoalLevelTwoTracks:
    """Session 45: GoalLevel 从三档改为两档."""

    def test_valid_new_values(self):
        """新两档值正常通过."""
        req = OneTopicRequest(raw_topic="YOLO 钢材检测", goal_level="保毕业")
        assert req.goal_level == "保毕业"
        req = OneTopicRequest(raw_topic="YOLO 钢材检测", goal_level="已有小论文")
        assert req.goal_level == "已有小论文"

    def test_compat_steady_innovation(self):
        """旧值 '稳中求新' 兼容映射到 '保毕业'."""
        req = OneTopicRequest(raw_topic="YOLO 钢材检测", goal_level="稳中求新")
        assert req.goal_level == "保毕业"

    def test_compat_high_level(self):
        """旧值 '冲高水平' 兼容映射到 '已有小论文'."""
        req = OneTopicRequest(raw_topic="YOLO 钢材检测", goal_level="冲高水平")
        assert req.goal_level == "已有小论文"

    def test_default_is_graduation_safe(self):
        """默认值为 '保毕业'."""
        req = OneTopicRequest(raw_topic="YOLO 钢材检测")
        assert req.goal_level == "保毕业"


# ---------- RealityCheck 资源四层 ---------- #


def _make_keywords(method: list[str] | None = None, obj: list[str] | None = None) -> KeywordBreakdown:
    return KeywordBreakdown(
        method_keywords=method or ["YOLO"],
        task_keywords=["检测"],
        object_keywords=obj or ["钢材表面缺陷"],
    )


def _make_evidence(has_data: bool = True, has_baseline: bool = True) -> EvidenceSummary:
    return EvidenceSummary(
        papers=[PaperHit(paper_id="p1", title="test", relevance_score=0.8)],
        datasets=[DatasetHit(dataset_id="d1", name="NEU-DET")] if has_data else [],
        baselines=[BaselineHit(baseline_id="b1", name="YOLOv8")] if has_baseline else [],
        metrics=["mAP"],
        has_public_dataset=has_data,
        has_repro_baseline=has_baseline,
        has_metrics=True,
    )


class TestResourceTier:
    """Session 45: 资源可达性四层判断."""

    def test_existing_env(self):
        """有数据集+有baseline+非大模型 → existing_env."""
        kw = _make_keywords(method=["YOLO"])
        ev = _make_evidence(has_data=True, has_baseline=True)
        tier, reason = _determine_resource_tier(kw, ev, "基于YOLO的钢材表面缺陷检测")
        assert tier == "existing_env"
        assert "公开数据集" in reason

    def test_rent_compute_heavy_model(self):
        """有数据集+大模型方法 → rent_compute."""
        kw = _make_keywords(method=["大语言模型"])
        ev = _make_evidence(has_data=True, has_baseline=True)
        tier, reason = _determine_resource_tier(kw, ev, "基于大语言模型的钢材检测")
        assert tier == "rent_compute"
        assert "大算力" in reason

    def test_self_collect_data(self):
        """无公开数据集 → self_collect_data."""
        kw = _make_keywords(method=["YOLO"])
        ev = _make_evidence(has_data=False, has_baseline=True)
        tier, reason = _determine_resource_tier(kw, ev, "基于YOLO的自定义钢材检测")
        assert tier == "self_collect_data"
        assert "自采" in reason

    def test_infeasible(self):
        """无数据集+无baseline+极小众 → infeasible."""
        kw = _make_keywords(method=["YOLO"], obj=["自采新型材料"])
        ev = _make_evidence(has_data=False, has_baseline=False)
        tier, reason = _determine_resource_tier(kw, ev, "基于YOLO的自采新型材料检测")
        assert tier == "infeasible"
        assert "做不到" in reason


class TestExperimentCycle:
    """Session 45: 实验周期判断."""

    def test_existing_env_week(self):
        ev = _make_evidence(has_data=True, has_baseline=True)
        cycle, reason = _determine_cycle("existing_env", ev)
        assert cycle == "week"

    def test_rent_compute_month(self):
        ev = _make_evidence(has_data=True, has_baseline=True)
        cycle, reason = _determine_cycle("rent_compute", ev)
        assert cycle == "month"

    def test_self_collect_year_no_baseline(self):
        ev = _make_evidence(has_data=False, has_baseline=False)
        cycle, reason = _determine_cycle("self_collect_data", ev)
        assert cycle == "year"

    def test_infeasible_year(self):
        ev = _make_evidence(has_data=False, has_baseline=False)
        cycle, reason = _determine_cycle("infeasible", ev)
        assert cycle == "year"


# ---------- 实验轮数矩阵 ---------- #


class TestCycleMatrix:
    """Session 45: goal_level + cycle → max_rounds + risk."""

    def test_graduation_safe_week(self):
        rounds, risk = get_cycle_matrix("保毕业", "week")
        assert rounds == 5
        assert risk == "low"

    def test_graduation_safe_year_high_risk(self):
        rounds, risk = get_cycle_matrix("保毕业", "year")
        assert rounds == 1
        assert risk == "high"

    def test_paper_extension_year_medium_risk(self):
        """已有小论文 + year → medium (有兜底)."""
        rounds, risk = get_cycle_matrix("已有小论文", "year")
        assert rounds == 1
        assert risk == "medium"

    def test_paper_extension_month_low_risk(self):
        rounds, risk = get_cycle_matrix("已有小论文", "month")
        assert rounds == 3
        assert risk == "low"


# ---------- assess_reality 集成 ---------- #


class TestAssessReality:
    """Session 45: assess_reality 完整流程."""

    def test_full_assess_existing_env(self):
        kw = _make_keywords(method=["YOLO"])
        ev = _make_evidence(has_data=True, has_baseline=True)
        rc = assess_reality(kw, ev, "保毕业", "基于YOLO的钢材表面缺陷检测")
        assert rc.resource_tier == "existing_env"
        assert rc.experiment_cycle == "week"
        assert rc.max_experiment_rounds == 5
        assert rc.graduation_risk == "low"
        assert rc.score >= 80

    def test_full_assess_infeasible(self):
        kw = _make_keywords(method=["YOLO"], obj=["自采新型材料"])
        ev = _make_evidence(has_data=False, has_baseline=False)
        rc = assess_reality(kw, ev, "保毕业", "基于YOLO的自采新型材料检测")
        assert rc.resource_tier == "infeasible"
        assert rc.experiment_cycle == "year"
        assert rc.graduation_risk == "high"
        assert rc.score <= 10

    def test_paper_extension_reduces_risk(self):
        """已有小论文路线, year 周期风险降为 medium."""
        kw = _make_keywords(method=["YOLO"], obj=["自采新型材料"])
        ev = _make_evidence(has_data=False, has_baseline=False)
        rc = assess_reality(kw, ev, "已有小论文", "基于YOLO的自采新型材料检测")
        assert rc.graduation_risk == "medium"


# ---------- 融合降级 ---------- #


class TestVerdictDowngrade:
    """Session 45: RealityCheck 融合降级."""

    def test_high_risk_downgrades_go(self):
        """high 风险 → 可做 降级为 收缩后可做."""
        rc = RealityCheck(
            resource_tier="self_collect_data",
            experiment_cycle="year",
            max_experiment_rounds=1,
            graduation_risk="high",
            score=20,
        )
        assert apply_reality_to_verdict("可做", rc) == "收缩后可做"

    def test_infeasible_force_stop(self):
        """infeasible → 直接 不建议."""
        rc = RealityCheck(
            resource_tier="infeasible",
            experiment_cycle="year",
            max_experiment_rounds=0,
            graduation_risk="high",
            score=5,
        )
        assert apply_reality_to_verdict("可做", rc) == "不建议"

    def test_low_risk_no_downgrade(self):
        """low 风险 → 不降级."""
        rc = RealityCheck(
            resource_tier="existing_env",
            experiment_cycle="week",
            max_experiment_rounds=5,
            graduation_risk="low",
            score=90,
        )
        assert apply_reality_to_verdict("可做", rc) == "可做"

    def test_medium_risk_no_downgrade(self):
        """medium 风险 → 不降级 (只有 high 才降)."""
        rc = RealityCheck(
            resource_tier="rent_compute",
            experiment_cycle="month",
            max_experiment_rounds=3,
            graduation_risk="medium",
            score=55,
        )
        assert apply_reality_to_verdict("可做", rc) == "可做"


# ---------- 大模型判断 ---------- #


class TestHeavyCompute:
    """Session 45: 大算力方法判断."""

    def test_yolo_not_heavy(self):
        kw = _make_keywords(method=["YOLO"])
        assert not _is_heavy_compute(kw)

    def test_llm_heavy(self):
        kw = _make_keywords(method=["大语言模型"])
        assert _is_heavy_compute(kw)

    def test_transformer_heavy(self):
        kw = _make_keywords(method=["Transformer"])
        assert _is_heavy_compute(kw)
