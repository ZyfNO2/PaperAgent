from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response, status

from paperagent.api.repository import TaskNotFoundError
from paperagent.api.review import (
    ReviewConflictError,
    ReviewExportService,
    ReviewTaskNotReadyError,
    ReviewValidationError,
    SQLiteReviewRepository,
)
from paperagent.api.review_models import (
    ExportFormat,
    ExportSelection,
    PaperCardPage,
    PaperReview,
    PaperReviewUpdate,
    ReviewDecision,
)


def register_review_routes(app: FastAPI, repository: SQLiteReviewRepository) -> None:
    exporter = ReviewExportService(repository)

    @app.get("/v1/tasks/{task_id}/papers", response_model=PaperCardPage)
    async def list_papers(
        task_id: str,
        cursor: str | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        decision: ReviewDecision | None = None,
        favorite: bool = False,
    ) -> PaperCardPage:
        try:
            return await asyncio.to_thread(
                repository.list_cards,
                task_id,
                cursor=cursor,
                limit=limit,
                decision=decision,
                favorite_only=favorite,
            )
        except TaskNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="task not found"
            ) from exc
        except ReviewTaskNotReadyError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except ReviewValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc

    @app.put("/v1/tasks/{task_id}/papers/{paper_id}/review", response_model=PaperReview)
    async def update_paper_review(
        task_id: str,
        paper_id: str,
        update: PaperReviewUpdate,
    ) -> PaperReview:
        try:
            return await asyncio.to_thread(repository.update_review, task_id, paper_id, update)
        except TaskNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="paper not found"
            ) from exc
        except ReviewConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except ReviewValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        except ReviewTaskNotReadyError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    @app.get("/v1/tasks/{task_id}/exports/{format}")
    async def export_papers(
        task_id: str,
        format: ExportFormat,
        selection: ExportSelection = "accepted",
    ) -> Response:
        try:
            document = await asyncio.to_thread(
                exporter.export,
                task_id,
                format=format,
                selection=selection,
            )
        except TaskNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="task not found"
            ) from exc
        except ReviewTaskNotReadyError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        response = Response(content=document.content, media_type=document.media_type)
        response.headers["Content-Disposition"] = f'attachment; filename="{document.filename}"'
        response.headers["X-PaperAgent-SHA256"] = document.manifest.sha256
        response.headers["X-PaperAgent-Item-Count"] = str(document.manifest.item_count)
        response.headers["X-PaperAgent-Selection"] = document.manifest.selection
        return response
