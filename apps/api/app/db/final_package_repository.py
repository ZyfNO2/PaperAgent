"""FinalPackage 持久化（Phase 08）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import FinalPackageRow
from packages.domain import FinalPackage


class FinalPackageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, pkg: FinalPackage) -> FinalPackageRow:
        existing = await self.session.execute(
            select(FinalPackageRow).where(FinalPackageRow.project_id == pkg.project_id)
        )
        row = existing.scalar_one_or_none()
        payload = pkg.model_dump(mode="json")
        if row is None:
            row = FinalPackageRow(
                project_id=pkg.project_id,
                case_id="",
                payload=payload,
                final_topic=pkg.final_topic.topic_zh,
                ready_for_thesis=pkg.ready_for_thesis,
                backend_verification=pkg.backend_verification,
            )
            self.session.add(row)
        else:
            row.payload = payload
            row.final_topic = pkg.final_topic.topic_zh
            row.ready_for_thesis = pkg.ready_for_thesis
            row.backend_verification = pkg.backend_verification
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_by_project_id(self, project_id: str) -> FinalPackage | None:
        r = await self.session.execute(
            select(FinalPackageRow).where(FinalPackageRow.project_id == project_id)
        )
        row = r.scalar_one_or_none()
        if row is None:
            return None
        return FinalPackage.model_validate(row.payload)
