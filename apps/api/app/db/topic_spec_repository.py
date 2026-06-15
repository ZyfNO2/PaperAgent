"""TopicSpec 持久化（Phase 02）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import TopicSpec as TopicSpecRow
from packages.domain import TopicSpec as TopicSpecDomain


class TopicSpecRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, spec: TopicSpecDomain) -> TopicSpecRow:
        """按 project_id upsert。"""

        existing = await self.session.execute(
            select(TopicSpecRow).where(TopicSpecRow.project_id == spec.project_id)
        )
        row = existing.scalar_one_or_none()
        payload = spec.model_dump(mode="json")
        if row is None:
            row = TopicSpecRow(
                project_id=spec.project_id,
                case_id=spec.source_intake_case_id,
                payload=payload,
            )
            self.session.add(row)
        else:
            row.payload = payload
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_by_project_id(self, project_id: str) -> TopicSpecDomain | None:
        r = await self.session.execute(
            select(TopicSpecRow).where(TopicSpecRow.project_id == project_id)
        )
        row = r.scalar_one_or_none()
        if row is None:
            return None
        return TopicSpecDomain.model_validate(row.payload)
