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


engine = create_async_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """创建所有表。Phase 01 用法：FastAPI 启动钩子调用。"""

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
