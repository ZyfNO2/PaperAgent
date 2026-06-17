"""RiskEvaluation 持久化（Phase 05）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import RiskEvaluationRow
from packages.domain import RiskEvaluation


class RiskEvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, ev: RiskEvaluation) -> RiskEvaluationRow:
        existing = await self.session.execute(
            select(RiskEvaluationRow).where(RiskEvaluationRow.project_id == ev.project_id)
        )
        row = existing.scalar_one_or_none()
        payload = ev.model_dump(mode="json")
        if row is None:
            row = RiskEvaluationRow(
                project_id=ev.project_id,
                case_id="",
                payload=payload,
                overall_rating=ev.risk_score.overall_rating,
                decision=ev.decision,
            )
            self.session.add(row)
        else:
            row.payload = payload
            row.overall_rating = ev.risk_score.overall_rating
            row.decision = ev.decision
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_by_project_id(self, project_id: str) -> RiskEvaluation | None:
        r = await self.session.execute(
            select(RiskEvaluationRow).where(RiskEvaluationRow.project_id == project_id)
        )
        row = r.scalar_one_or_none()
        if row is None:
            return None
        return RiskEvaluation.model_validate(row.payload)
