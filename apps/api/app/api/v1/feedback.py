"""Re7.4 Feedback API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from apps.api.app.services.feedback_store import (
    FeedbackCreate, FeedbackRecord, FeedbackStore, FeedbackSummary,
)

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])

_store: FeedbackStore | None = None


def get_store() -> FeedbackStore:
    global _store
    if _store is None:
        _store = FeedbackStore()
    return _store


@router.post("/", response_model=FeedbackRecord)
async def submit_feedback(fb: FeedbackCreate):
    store = get_store()
    return store.save(fb)


@router.get("/")
async def list_feedback(case_id: str = Query(...)):
    store = get_store()
    return store.list_by_case(case_id)


@router.get("/summary", response_model=FeedbackSummary)
async def get_summary(from_date: str = Query(""), to_date: str = Query("")):
    store = get_store()
    return store.get_summary(from_date, to_date)


@router.delete("/{case_id}")
async def delete_feedback(case_id: str):
    store = get_store()
    deleted = store.delete_by_case(case_id)
    return {"deleted": deleted}
