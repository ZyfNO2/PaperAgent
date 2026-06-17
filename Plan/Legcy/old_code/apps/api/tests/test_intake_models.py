"""Phase 01 验收 §7.2：ProjectIntake + 评级阻断。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.domain import (
    InheritedResource,
    MissingField,
    ProjectIntake,
    StudentResourceProfile,
    ValidationOutcome,
    compute_intake_rating,
    derive_missing_fields,
    validate_intake,
)


# ----------------------------- helper payloads ----------------------------- #


def _complete_payload(**overrides) -> ProjectIntake:
    """构造一个应当评级为 A 的最小完整 payload。"""

    payload = ProjectIntake.model_construct()  # 跳过校验以便填缺省
    data = {
        "case_id": "20260616_AI_test",
        "major": "计算机科学与技术",
        "degree_type": "硕士",
        "goal_level": "保毕业",
        "thesis_deadline": "2027-06-01",
        "proposal_deadline": "2026-10-15",
        "first_result_deadline": "2026-12-31",
        "advisor_direction": "图神经网络",
        "school_requirements": ["必须中文文献", "开题模板见附录"],
        "inherited_resources": [
            InheritedResource(
                kind="同门毕业论文",
                description="师兄 2024 届硕士论文",
                available=True,
                authorization_or_attribution_risk="低",
            )
        ],
        "student_resources": StudentResourceProfile(
            programming_level="熟练",
            dl_or_algorithm_foundation="中",
            paper_reading_ability="中",
            english_reading_ability="中",
            compute_resource="笔记本 3060",
            weekly_hours=25,
            data_collection_ability="中",
            data_annotation_ability="中",
            code_reproduction_ability="中",
            system_dev_ability="中",
        ),
        "raw_topic": "基于图神经网络的学术论文推荐",
        "must_keep": ["图神经网络", "推荐"],
        "can_drop": [],
        "missing_fields": [],
        "intake_rating": "A",
    }
    data.update(overrides)
    # 用 model_validate 跑校验，触发模型层不变量
    return ProjectIntake.model_validate(data)


def _placeholder_payload() -> ProjectIntake:
    """完全空白的占位 payload：期望评级为 D（多 P0 + 多 P1）。"""

    return ProjectIntake.model_validate(
        {
            "case_id": "TBD_AI_开题选题助手",
            "goal_level": "保毕业",
            "raw_topic": "TBD",
            "intake_rating": "A",  # 会被覆盖
        }
    )


# ----------------------------- 验收 §7.2 第 1 条 ----------------------------- #


def test_project_intake_validates_via_pydantic() -> None:
    intake = _complete_payload()
    assert intake.case_id == "20260616_AI_test"
    assert intake.degree_type == "硕士"


# ----------------------------- 验收 §7.2 第 2 条 ----------------------------- #


def test_goal_level_required() -> None:
    with pytest.raises(ValidationError):
        ProjectIntake.model_validate(
            {
                "case_id": "x",
                "raw_topic": "y",
                "intake_rating": "A",
                # goal_level 缺失
            }
        )


# ----------------------------- 验收 §7.2 第 3 条 ----------------------------- #


def test_raw_topic_required() -> None:
    with pytest.raises(ValidationError):
        ProjectIntake.model_validate(
            {
                "case_id": "x",
                "goal_level": "保毕业",
                "intake_rating": "A",
                "raw_topic": "",
            }
        )

    with pytest.raises(ValidationError):
        ProjectIntake.model_validate(
            {
                "case_id": "x",
                "goal_level": "保毕业",
                "intake_rating": "A",
                "raw_topic": "   ",
            }
        )


# ----------------------------- 验收 §7.2 第 4 条 ----------------------------- #


def test_missing_fields_is_readable_list() -> None:
    payload = _placeholder_payload()
    missing = derive_missing_fields(payload)
    assert isinstance(missing, list)
    assert all(isinstance(m, MissingField) for m in missing)
    # 占位 payload 应当至少记录 P0 major/proposal_deadline/thesis_deadline/
    # first_result_deadline/advisor_direction/raw_topic。
    names = {m.field_name for m in missing}
    assert "major" in names
    assert "advisor_direction" in names


# ----------------------------- 验收 §7.2 第 5 条 ----------------------------- #


def test_rating_A_and_B_allow_phase02() -> None:
    # A：完整
    complete = _complete_payload()
    outcome, rating, _ = validate_intake(complete)
    assert outcome == ValidationOutcome.OK
    assert rating == "A"

    # B：仅丢 P2 must_keep
    partial = _complete_payload(must_keep=[])
    outcome, rating, _ = validate_intake(partial)
    assert outcome == ValidationOutcome.OK
    assert rating == "B"


def test_rating_C_requires_clarification() -> None:
    # 丢一个 P0 → 评级 C
    payload = _complete_payload(proposal_deadline=None)
    outcome, rating, missing = validate_intake(payload)
    assert rating == "C"
    assert outcome == ValidationOutcome.NEED_CLARIFICATION
    assert any(m.field_name == "proposal_deadline" for m in missing)


def test_rating_D_blocks_phase02() -> None:
    payload = _placeholder_payload()
    outcome, rating, missing = validate_intake(payload)
    assert rating == "D"
    assert outcome == ValidationOutcome.BLOCKED
    # D 至少要看到多个 P1 或一个 P0 都触发；占位 payload 同时有 P0 与 P1
    assert any(m.priority == "P0" for m in missing)
    assert any(m.priority == "P1" for m in missing)


# ----------------------------- 额外回归 ----------------------------- #


def test_compute_intake_rating_thresholds() -> None:
    payload = _complete_payload()

    # 零缺失 → A
    assert compute_intake_rating(payload, []) == "A"

    # 单 P2 → B（非关键缺失，仍基本可用）
    assert compute_intake_rating(payload, [MissingField(field_name="x", why_required="y",
                                                       impact_if_missing="z", priority="P2")]) == "B"

    # 单 P1 → B
    assert compute_intake_rating(payload, [MissingField(field_name="x", why_required="y",
                                                       impact_if_missing="z", priority="P1")]) == "B"

    # 单 P0 → C
    assert compute_intake_rating(payload, [MissingField(field_name="x", why_required="y",
                                                       impact_if_missing="z", priority="P0")]) == "C"

    # 三 P1 → D
    p1_list = [MissingField(field_name=f"f{i}", why_required="y", impact_if_missing="z",
                            priority="P1") for i in range(3)]
    assert compute_intake_rating(payload, p1_list) == "D"

    # raw_topic 是占位 → D
    placeholder_payload = payload.model_copy(update={"raw_topic": "TBD"})
    assert compute_intake_rating(placeholder_payload, []) == "D"


def test_iso_deadline_validator() -> None:
    # 接受 YYYY-MM-DD
    intake = _complete_payload(thesis_deadline="2027-06-01")
    assert intake.thesis_deadline == "2027-06-01"

    # 接受 ISO datetime
    intake = _complete_payload(thesis_deadline="2027-06-01T09:00:00")
    assert intake.thesis_deadline == "2027-06-01T09:00:00"

    # 拒绝乱七八糟
    with pytest.raises(ValidationError):
        _complete_payload(thesis_deadline="not-a-date")


def test_placeholder_payload_is_D_even_when_raw_topic_typed() -> None:
    """即使用户在 00_input.md 把 raw_topic 写成 'TBD'，也必须保持 D 评级直到 P0 补齐。"""

    intake = ProjectIntake.model_validate(
        {
            "case_id": "TBD",
            "goal_level": "保毕业",
            "raw_topic": "TBD",
            "intake_rating": "A",
        }
    )
    outcome, rating, _ = validate_intake(intake)
    assert rating == "D"
    assert outcome == ValidationOutcome.BLOCKED
