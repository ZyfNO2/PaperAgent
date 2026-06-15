"""Project repository — 持久化 ProjectIntake 的 JSON 快照。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import Project
from packages.domain import ProjectIntake


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: ProjectIntake) -> Project:
        project = Project(case_id=payload.case_id, payload=payload.model_dump(mode="json"))
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def get_by_id(self, project_id: int) -> Project | None:
        result = await self.session.execute(
            select(Project).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    async def get_by_case_id(self, case_id: str) -> Project | None:
        result = await self.session.execute(
            select(Project).where(Project.case_id == case_id)
        )
        return result.scalar_one_or_none()

    async def update_payload(self, project: Project, payload: ProjectIntake) -> Project:
        project.payload = payload.model_dump(mode="json")
        await self.session.commit()
        await self.session.refresh(project)
        return project
