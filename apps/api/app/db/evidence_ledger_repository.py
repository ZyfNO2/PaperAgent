"""EvidenceLedger 持久化（Phase 04）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import EvidenceLedgerRow
from packages.domain import EvidenceLedger


class EvidenceLedgerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, ledger: EvidenceLedger) -> EvidenceLedgerRow:
        existing = await self.session.execute(
            select(EvidenceLedgerRow).where(EvidenceLedgerRow.project_id == ledger.project_id)
        )
        row = existing.scalar_one_or_none()
        payload = ledger.model_dump(mode="json")
        if row is None:
            row = EvidenceLedgerRow(
                project_id=ledger.project_id,
                case_id="",
                payload=payload,
                evidence_rating=ledger.evidence_rating,
            )
            self.session.add(row)
        else:
            row.payload = payload
            row.evidence_rating = ledger.evidence_rating
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_by_project_id(self, project_id: str) -> EvidenceLedger | None:
        r = await self.session.execute(
            select(EvidenceLedgerRow).where(EvidenceLedgerRow.project_id == project_id)
        )
        row = r.scalar_one_or_none()
        if row is None:
            return None
        return EvidenceLedger.model_validate(row.payload)
