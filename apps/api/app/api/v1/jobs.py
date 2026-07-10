"""Re7.1 Job API endpoints — submit/list/status/cancel/resume/events."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from apps.api.app.services.job_repository import JobCreate, JobRepository

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

_repo: JobRepository | None = None


def get_repo() -> JobRepository:
    global _repo
    if _repo is None:
        _repo = JobRepository()
    return _repo


def reset_repo() -> None:
    global _repo
    _repo = None


class JobResponse(BaseModel):
    job_id: str
    case_id: str
    topic: str
    status: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    tokens_used: int = 0
    budget_tokens: int = 50000
    idempotency_key: str = ""


class JobCreateRequest(BaseModel):
    topic: str
    idempotency_key: str = ""
    budget_tokens: int = 50000
    budget_timeout_s: int = 1800


class JobListResponse(BaseModel):
    jobs: list[JobResponse]


class JobEventResponse(BaseModel):
    events: list[dict[str, Any]]
    latest_seq: int = 0


@router.post("/", response_model=JobResponse)
async def create_job(req: JobCreateRequest):
    if not req.idempotency_key:
        import uuid
        req.idempotency_key = uuid.uuid4().hex[:16]
    repo = get_repo()
    try:
        record = repo.create_job(JobCreate(**req.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _to_response(record)


@router.get("/", response_model=JobListResponse)
async def list_jobs(status: str | None = Query(None)):
    repo = get_repo()
    records = repo.list_jobs(status=status)
    return JobListResponse(jobs=[_to_response(r) for r in records])


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    repo = get_repo()
    record = repo.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _to_response(record)


@router.get("/{job_id}/events", response_model=JobEventResponse)
async def get_job_events(job_id: str, after: int = Query(0, alias="after_seq")):
    repo = get_repo()
    record = repo.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="job not found")
    events = repo.get_events(job_id, after_seq=after)
    latest = events[-1]["seq"] if events else 0
    return JobEventResponse(events=events, latest_seq=latest)


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str):
    repo = get_repo()
    ok = repo.cancel_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="job not found or already completed")
    return {"success": True, "message": "job cancelled"}


@router.post("/{job_id}/resume")
async def resume_job(job_id: str):
    repo = get_repo()
    record = repo.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="job not found")
    if record.status not in ("failed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"cannot resume job in status {record.status}")
    repo.update_status(job_id, "resumable")
    return {"success": True, "message": "job marked resumable"}


def _to_response(r) -> JobResponse:
    from apps.api.app.services.job_repository import JobRecord
    if isinstance(r, JobRecord):
        return JobResponse(
            job_id=r.job_id, case_id=r.case_id, topic=r.topic,
            status=r.status, created_at=r.created_at,
            started_at=r.started_at, completed_at=r.completed_at,
            error=r.error, tokens_used=r.tokens_used,
            budget_tokens=r.budget_tokens, idempotency_key=r.idempotency_key,
        )
    return r
