"""WorkPackagePlan 持久化（Phase 06）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import WorkPackagePlanRow
from packages.domain import WorkPackagePlan


class WorkPackagePlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, plan: WorkPackagePlan) -> WorkPackagePlanRow:
        existing = await self.session.execute(
            select(WorkPackagePlanRow).where(WorkPackagePlanRow.project_id == plan.project_id)
        )
        row = existing.scalar_one_or_none()
        payload = plan.model_dump(mode="json")
        if row is None:
            row = WorkPackagePlanRow(
                project_id=plan.project_id,
                case_id="",
                payload=payload,
                final_topic=plan.final_topic,
                from_pivot=plan.final_topic_from_pivot,
                allow_proceed_to_phase07=plan.allow_proceed_to_phase07,
            )
            self.session.add(row)
        else:
            row.payload = payload
            row.final_topic = plan.final_topic
            row.from_pivot = plan.final_topic_from_pivot
            row.allow_proceed_to_phase07 = plan.allow_proceed_to_phase07
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_by_project_id(self, project_id: str) -> WorkPackagePlan | None:
        r = await self.session.execute(
            select(WorkPackagePlanRow).where(WorkPackagePlanRow.project_id == project_id)
        )
        row = r.scalar_one_or_none()
        if row is None:
            return None
        return WorkPackagePlan.model_validate(row.payload)
