"""Generate 12 demo ProjectIntake JSON fixtures (3 domains x 4 ratings).

每个案例是一个独立函数，返回一个经过 Pydantic 校验的 ProjectIntake
对象。dump 到 ``data/demo_cases/<rating>_<domain>.json``，作为面试
artifact、回归基线与产品演示用。

设计矩阵（3 领域 × 4 评级）：

    Domain     / Rating |       A       |       B       |       C       |       D
    --------------------+---------------+---------------+---------------+-------------
    CS_AI_GRAD           | A_CS_AI_GRAD  | B_CS_AI_GRAD  | C_CS_AI_GRAD  | D_CS_AI_GRAD
    CS_AI_TOP            | A_CS_AI_TOP   | B_CS_AI_TOP   | C_CS_AI_TOP   | D_CS_AI_TOP
    MED_UG               | A_MED_UG      | B_MED_UG      | C_MED_UG      | D_MED_UG

字段裁剪规则（与 ``compute_intake_rating`` 严格对齐）：
- A：所有 P0/P1/P2 都填齐
- B：仅 P2（must_keep）空
- C：缺 1 个 P0（proposal_deadline）
- D：raw_topic 写成字面占位符 'TBD'，直接触发 D 评级

禁止规则：
- 不调用任何 LLM
- 不读 00_input.md
- 不假设默认评分；所有 case_id 都带评级 + 领域后缀
"""

from __future__ import annotations

import json
from pathlib import Path

from packages.domain import (
    InheritedResource,
    ProjectIntake,
    StudentResourceProfile,
)


REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "demo_cases"
OUT.mkdir(parents=True, exist_ok=True)


# ----------------------------- 领域 profile ----------------------------- #


def _cs_ai_grad_profile() -> dict:
    """计算机科学硕士（保毕业型）。"""

    return {
        "major": "计算机科学与技术",
        "degree_type": "硕士",
        "advisor_direction": "图神经网络与推荐系统",
        "school_requirements": ["必须中文文献", "开题模板见附录"],
        "inherited_resources": [
            InheritedResource(
                kind="同门毕业论文",
                description="师兄 2024 届硕士论文（基于 GNN 的论文推荐）",
                available=True,
                authorization_or_attribution_risk="低",
            ),
            InheritedResource(
                kind="可合法复用开源",
                description="作者公开的 PyG 实现",
                available=True,
                authorization_or_attribution_risk="低",
            ),
        ],
        "student_resources": StudentResourceProfile(
            programming_level="熟练",
            dl_or_algorithm_foundation="中",
            paper_reading_ability="中",
            english_reading_ability="中",
            compute_resource="笔记本 RTX 3060",
            weekly_hours=25,
            data_collection_ability="中",
            data_annotation_ability="中",
            code_reproduction_ability="中",
            system_dev_ability="中",
        ),
        "raw_topic": "基于图神经网络的学术论文推荐方法研究",
    }


def _cs_ai_top_profile() -> dict:
    """计算机科学硕士（冲高水平，CV/ML）。"""

    return {
        "major": "计算机科学与技术",
        "degree_type": "硕士",
        "advisor_direction": "多模态大模型与对齐",
        "school_requirements": ["必须英文文献 20 篇以上", "顶会成果优先"],
        "inherited_resources": [
            InheritedResource(
                kind="课题组已有代码",
                description="实验室 LLaVA 风格多模态基线",
                available=True,
                authorization_or_attribution_risk="中",
                note="需要导师签字授权",
            ),
            InheritedResource(
                kind="已跑通环境",
                description="实验室 4×A100 集群",
                available=True,
                authorization_or_attribution_risk="低",
            ),
        ],
        "student_resources": StudentResourceProfile(
            programming_level="可独立工程化",
            dl_or_algorithm_foundation="强",
            paper_reading_ability="强",
            english_reading_ability="强",
            compute_resource="实验室 4×A100",
            weekly_hours=40,
            data_collection_ability="强",
            data_annotation_ability="中",
            code_reproduction_ability="强",
            system_dev_ability="中",
        ),
        "raw_topic": "面向细粒度视觉理解的视觉-语言模型提示压缩方法",
    }


def _med_ug_profile() -> dict:
    """临床医学本科（保毕业，要系统原型）。"""

    return {
        "major": "临床医学",
        "degree_type": "本科",
        "advisor_direction": "医学信息学",
        "school_requirements": [
            "必须中文文献",
            "必须包含系统原型或可演示工程",
            "学院开题模板见教务在线",
        ],
        "inherited_resources": [
            InheritedResource(
                kind="同门毕业论文",
                description="学姐 2023 届本科论文（电子病历文本分类）",
                available=True,
                authorization_or_attribution_risk="低",
            ),
        ],
        "student_resources": StudentResourceProfile(
            programming_level="入门",
            dl_or_algorithm_foundation="弱",
            paper_reading_ability="中",
            english_reading_ability="中",
            compute_resource="笔记本无独显",
            weekly_hours=15,
            data_collection_ability="中",
            data_annotation_ability="中",
            code_reproduction_ability="弱",
            system_dev_ability="弱",
        ),
        "raw_topic": "面向临床实习的医学影像报告自动校对系统",
    }


DOMAIN_PROFILES = {
    "CS_AI_GRAD": _cs_ai_grad_profile,
    "CS_AI_TOP": _cs_ai_top_profile,
    "MED_UG": _med_ug_profile,
}


# ----------------------------- 12 个工厂函数 ----------------------------- #


def _make_intake(domain: str, rating: str) -> ProjectIntake:
    """根据 domain × rating 构造一个 ProjectIntake。"""

    profile = DOMAIN_PROFILES[domain]()

    # 基础时间字段：所有评级默认填齐，D 评级额外写 TBD 题目
    payload: dict = {
        "case_id": f"{rating}_{domain}_20260616",
        "thesis_deadline": "2027-06-01",
        "proposal_deadline": "2026-10-15",
        "first_result_deadline": "2026-12-31",
        "goal_level": "保毕业" if domain in {"CS_AI_GRAD", "MED_UG"} else "冲高水平",
        "must_keep": [],
        "can_drop": [],
        "missing_fields": [],
        "intake_rating": "A",  # 验证覆盖
    }
    payload.update(profile)

    if rating == "A":
        payload["must_keep"] = [
            payload["raw_topic"].split("的")[0] if "的" in payload["raw_topic"] else payload["raw_topic"][:6]
        ]
    elif rating == "B":
        # 唯一缺：must_keep 空（P2 缺失）→ B
        payload["must_keep"] = []
    elif rating == "C":
        # 缺 1 个 P0：proposal_deadline 留空
        payload["proposal_deadline"] = None
    elif rating == "D":
        # raw_topic 写成 TBD → D 直接触发，不依赖其他缺失
        payload["raw_topic"] = "TBD"
    else:
        raise ValueError(f"unknown rating: {rating}")

    return ProjectIntake.model_validate(payload)


# ----------------------------- 主流程 ----------------------------- #


def main() -> None:
    from packages.domain import compute_intake_rating, derive_missing_fields

    for domain in DOMAIN_PROFILES:
        for rating in ("A", "B", "C", "D"):
            intake = _make_intake(domain, rating)
            # 重算评级写回 JSON（payload.intake_rating 必须与实际规约一致）
            missing = derive_missing_fields(intake)
            actual_rating = compute_intake_rating(intake, missing)
            intake = intake.model_copy(
                update={"intake_rating": actual_rating, "missing_fields": missing}
            )
            out_path = OUT / f"{rating}_{domain}.json"
            out_path.write_text(
                json.dumps({"intake": intake.model_dump(mode="json")}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"  wrote {out_path.relative_to(REPO)}  expected={rating}  actual={actual_rating}")


if __name__ == "__main__":
    main()
