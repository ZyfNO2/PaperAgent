"""Generate smoke-test JSON payloads using Pydantic (avoid hand-writing nested schemas)."""

from __future__ import annotations

import json
from pathlib import Path

from packages.domain import InheritedResource, ProjectIntake, StudentResourceProfile


TMP = Path(__file__).resolve().parents[1] / "tmp"
TMP.mkdir(parents=True, exist_ok=True)


def placeholder() -> ProjectIntake:
    return ProjectIntake.model_validate(
        {
            "case_id": "SMOKE_TBD_AI",
            "goal_level": "保毕业",
            "raw_topic": "TBD",
            "intake_rating": "A",
        }
    )


def complete() -> ProjectIntake:
    return ProjectIntake.model_validate(
        {
            "case_id": "SMOKE_FULL_AI",
            "major": "计算机科学与技术",
            "degree_type": "硕士",
            "goal_level": "保毕业",
            "thesis_deadline": "2027-06-01",
            "proposal_deadline": "2026-10-15",
            "first_result_deadline": "2026-12-31",
            "advisor_direction": "图神经网络",
            "school_requirements": ["必须中文文献"],
            "inherited_resources": [
                InheritedResource(
                    kind="同门毕业论文",
                    description="师兄 2024 届硕士论文",
                    available=True,
                )
            ],
            "student_resources": StudentResourceProfile(
                programming_level="熟练",
                compute_resource="笔记本 3060",
                weekly_hours=25,
            ),
            "raw_topic": "基于图神经网络的学术论文推荐",
            "must_keep": ["图神经网络"],
            "can_drop": [],
            "missing_fields": [],
            "intake_rating": "A",
        }
    )


def main() -> None:
    (TMP / "smoke_placeholder.json").write_text(
        json.dumps({"intake": placeholder().model_dump(mode="json")}, ensure_ascii=False),
        encoding="utf-8",
    )
    (TMP / "smoke_complete.json").write_text(
        json.dumps({"intake": complete().model_dump(mode="json")}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"wrote {TMP / 'smoke_placeholder.json'}")
    print(f"wrote {TMP / 'smoke_complete.json'}")


if __name__ == "__main__":
    main()
