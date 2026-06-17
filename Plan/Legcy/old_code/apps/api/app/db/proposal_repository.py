"""ProposalDraft + CommitteeReview 持久化（Phase 07）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import CommitteeReviewRow, ProposalDraftRow
from packages.domain import CommitteeReview, ProposalDraft


class ProposalDraftRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, draft: ProposalDraft) -> ProposalDraftRow:
        existing = await self.session.execute(
            select(ProposalDraftRow).where(ProposalDraftRow.project_id == draft.project_id)
        )
        row = existing.scalar_one_or_none()
        payload = draft.model_dump(mode="json")
        if row is None:
            row = ProposalDraftRow(
                project_id=draft.project_id,
                case_id="",
                payload=payload,
                final_topic=draft.final_topic,
            )
            self.session.add(row)
        else:
            row.payload = payload
            row.final_topic = draft.final_topic
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_by_project_id(self, project_id: str) -> ProposalDraft | None:
        r = await self.session.execute(
            select(ProposalDraftRow).where(ProposalDraftRow.project_id == project_id)
        )
        row = r.scalar_one_or_none()
        if row is None:
            return None
        return ProposalDraft.model_validate(row.payload)


class CommitteeReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, review: CommitteeReview) -> CommitteeReviewRow:
        existing = await self.session.execute(
            select(CommitteeReviewRow).where(CommitteeReviewRow.project_id == review.project_id)
        )
        row = existing.scalar_one_or_none()
        payload = review.model_dump(mode="json")
        if row is None:
            row = CommitteeReviewRow(
                project_id=review.project_id,
                case_id="",
                payload=payload,
                overall_verdict=review.overall_verdict,
                proposal_maturity=review.proposal_maturity,
                allow_proceed_to_phase08=review.allow_proceed_to_phase08,
            )
            self.session.add(row)
        else:
            row.payload = payload
            row.overall_verdict = review.overall_verdict
            row.proposal_maturity = review.proposal_maturity
            row.allow_proceed_to_phase08 = review.allow_proceed_to_phase08
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_by_project_id(self, project_id: str) -> CommitteeReview | None:
        r = await self.session.execute(
            select(CommitteeReviewRow).where(CommitteeReviewRow.project_id == project_id)
        )
        row = r.scalar_one_or_none()
        if row is None:
            return None
        return CommitteeReview.model_validate(row.payload)
