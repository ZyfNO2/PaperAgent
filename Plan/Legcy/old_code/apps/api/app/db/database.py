"""SQLAlchemy 2.x async engine + session factory.

Phase 01 仅包含 ``projects`` 一张表（id + payload JSON）。
后续 Phase 会在同一模块追加 papers/datasets/baselines/risk_scores/
pivots/work_packages/committee_reviews 等表。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class TopicSpec(Base):
    """Phase 02 产物表：按 project_id 唯一。"""

    __tablename__ = "topic_specs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    decomposition_rating: Mapped[str] = mapped_column(String(2), default="A")


class SearchQueryPlanRow(Base):
    """Phase 03 产物表。"""

    __tablename__ = "search_query_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    maturity_rating: Mapped[str] = mapped_column(String(2), default="A")


class EvidenceLedgerRow(Base):
    """Phase 04 产物表。"""

    __tablename__ = "evidence_ledgers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_rating: Mapped[str] = mapped_column(String(2), default="A")


class RiskEvaluationRow(Base):
    """Phase 05 产物表。"""

    __tablename__ = "risk_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    overall_rating: Mapped[str] = mapped_column(String(2), default="A")
    decision: Mapped[str] = mapped_column(String(8), default="继续")


class WorkPackagePlanRow(Base):
    """Phase 06 产物表。"""

    __tablename__ = "work_package_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    final_topic: Mapped[str] = mapped_column(String(512), default="")
    from_pivot: Mapped[bool] = mapped_column(default=False)
    allow_proceed_to_phase07: Mapped[bool] = mapped_column(default=True)


class ProposalDraftRow(Base):
    """Phase 07 产物表。"""

    __tablename__ = "proposal_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    final_topic: Mapped[str] = mapped_column(String(512), default="")


class CommitteeReviewRow(Base):
    """Phase 07 审查表。"""

    __tablename__ = "committee_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    overall_verdict: Mapped[str] = mapped_column(String(8), default="有条件通过")
    proposal_maturity: Mapped[str] = mapped_column(String(2), default="B")
    allow_proceed_to_phase08: Mapped[bool] = mapped_column(default=False)


class FinalPackageRow(Base):
    """Phase 08 产物表。"""

    __tablename__ = "final_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    final_topic: Mapped[str] = mapped_column(String(512), default="")
    ready_for_thesis: Mapped[bool] = mapped_column(default=False)
    backend_verification: Mapped[str] = mapped_column(String(8), default="BLOCKED")


engine = create_async_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """创建所有表。Phase 01 用法：FastAPI 启动钩子调用。"""

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
