from __future__ import annotations

import base64
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, cast

from paperagent.api.models import TaskRecord, TaskStatus
from paperagent.api.repository import SQLiteTaskRepository, TaskNotFoundError, utc_now
from paperagent.api.review_models import (
    ExportDocument,
    ExportFormat,
    ExportManifest,
    ExportSelection,
    PaperCardPage,
    PaperReview,
    PaperReviewUpdate,
    ReviewDecision,
    ReviewPaperCard,
)


class ReviewConflictError(ValueError):
    pass


class ReviewValidationError(ValueError):
    pass


class ReviewTaskNotReadyError(RuntimeError):
    pass


def _encode_cursor(paper_id: str) -> str:
    return base64.urlsafe_b64encode(paper_id.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str | None) -> str | None:
    if cursor is None:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except (UnicodeDecodeError, ValueError) as exc:
        raise ReviewValidationError("invalid paper cursor") from exc


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


class SQLiteReviewRepository:
    def __init__(self, task_repository: SQLiteTaskRepository) -> None:
        self.task_repository = task_repository
        self.database_path = Path(task_repository.database_path)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path), timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        if self.database_path != Path(":memory:"):
            connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS paper_reviews (
                    task_id TEXT NOT NULL,
                    paper_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    favorite INTEGER NOT NULL DEFAULT 0,
                    version INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (task_id, paper_id),
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_paper_reviews_task_decision
                    ON paper_reviews(task_id, decision, favorite, paper_id);
                """
            )

    def list_cards(
        self,
        task_id: str,
        *,
        cursor: str | None = None,
        limit: int = 20,
        decision: ReviewDecision | None = None,
        favorite_only: bool = False,
    ) -> PaperCardPage:
        if not 1 <= limit <= 100:
            raise ReviewValidationError("limit must be between 1 and 100")
        after_id = _decode_cursor(cursor)
        record = self.task_repository.get_task(task_id)
        cards = self._cards_from_task(record)
        reviews = self._reviews_for_task(task_id)
        merged: list[ReviewPaperCard] = []
        for card in cards:
            review = reviews.get(card.paper_id)
            if review is not None:
                card = card.model_copy(
                    update={
                        "decision": review.decision,
                        "favorite": review.favorite,
                        "review_version": review.version,
                    }
                )
            if after_id is not None and card.paper_id <= after_id:
                continue
            if decision is not None and card.decision is not decision:
                continue
            if favorite_only and not card.favorite:
                continue
            merged.append(card)
        merged.sort(key=lambda item: item.paper_id)
        page_items = merged[:limit]
        next_cursor = _encode_cursor(page_items[-1].paper_id) if len(merged) > limit else None
        return PaperCardPage(task_id=task_id, items=page_items, next_cursor=next_cursor)

    def update_review(
        self,
        task_id: str,
        paper_id: str,
        update: PaperReviewUpdate,
    ) -> PaperReview:
        record = self.task_repository.get_task(task_id)
        cards = {card.paper_id: card for card in self._cards_from_task(record)}
        card = cards.get(paper_id)
        if card is None:
            raise TaskNotFoundError(f"{task_id}/{paper_id}")
        if update.decision is ReviewDecision.ACCEPTED and card.verification_status in {
            "rejected",
            "failed_verification",
        }:
            raise ReviewValidationError(
                "rejected or failed-verification evidence cannot be accepted in the MVP"
            )

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT decision, favorite, version FROM paper_reviews WHERE task_id = ? AND paper_id = ?",
                (task_id, paper_id),
            ).fetchone()
            current = (
                PaperReview(
                    task_id=task_id,
                    paper_id=paper_id,
                    decision=ReviewDecision(cast(str, row["decision"])),
                    favorite=bool(row["favorite"]),
                    version=int(row["version"]),
                )
                if row is not None
                else PaperReview(task_id=task_id, paper_id=paper_id)
            )
            if update.expected_version != current.version:
                raise ReviewConflictError(
                    f"stale review version: expected {update.expected_version}, current {current.version}"
                )
            if current.decision is update.decision and current.favorite is update.favorite:
                return current

            next_review = PaperReview(
                task_id=task_id,
                paper_id=paper_id,
                decision=update.decision,
                favorite=update.favorite,
                version=current.version + 1,
            )
            connection.execute(
                """
                INSERT INTO paper_reviews (task_id, paper_id, decision, favorite, version, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id, paper_id) DO UPDATE SET
                    decision = excluded.decision,
                    favorite = excluded.favorite,
                    version = excluded.version,
                    updated_at = excluded.updated_at
                """,
                (
                    task_id,
                    paper_id,
                    next_review.decision.value,
                    int(next_review.favorite),
                    next_review.version,
                    utc_now().isoformat(),
                ),
            )
            return next_review

    def all_cards(self, task_id: str) -> list[ReviewPaperCard]:
        page = self.list_cards(task_id, limit=100)
        if page.next_cursor is not None:  # v0.2 final bundle is capped at 12 papers
            raise ReviewValidationError("paper set exceeds the v0.4 MVP bound")
        return page.items

    def _reviews_for_task(self, task_id: str) -> dict[str, PaperReview]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT task_id, paper_id, decision, favorite, version
                FROM paper_reviews WHERE task_id = ? ORDER BY paper_id
                """,
                (task_id,),
            ).fetchall()
        return {
            cast(str, row["paper_id"]): PaperReview(
                task_id=cast(str, row["task_id"]),
                paper_id=cast(str, row["paper_id"]),
                decision=ReviewDecision(cast(str, row["decision"])),
                favorite=bool(row["favorite"]),
                version=int(row["version"]),
            )
            for row in rows
        }

    @staticmethod
    def _cards_from_task(record: TaskRecord) -> list[ReviewPaperCard]:
        if record.status is not TaskStatus.SUCCEEDED or record.result is None:
            raise ReviewTaskNotReadyError("paper review requires a succeeded task")
        evidence = record.result.get("evidence")
        if not isinstance(evidence, dict):
            return []
        items = evidence.get("items", [])
        if not isinstance(items, list):
            return []
        cards: list[ReviewPaperCard] = []
        for raw in items:
            if not isinstance(raw, dict) or raw.get("source_type") != "paper":
                continue
            paper_id = raw.get("evidence_id")
            title = raw.get("title")
            locator = raw.get("locator")
            if not all(isinstance(value, str) and value for value in (paper_id, title, locator)):
                continue
            summary = raw.get("summary")
            status = raw.get("verification_status")
            gaps = raw.get("supports_gap_ids")
            cards.append(
                ReviewPaperCard(
                    task_id=record.task_id,
                    paper_id=cast(str, paper_id),
                    title=cast(str, title),
                    locator=cast(str, locator),
                    summary=summary if isinstance(summary, str) else "",
                    verification_status=status if isinstance(status, str) else "pending",
                    gap_ids=[value for value in gaps if isinstance(value, str)]
                    if isinstance(gaps, list)
                    else [],
                )
            )
        return sorted(cards, key=lambda item: item.paper_id)


class ReviewExportService:
    def __init__(self, repository: SQLiteReviewRepository) -> None:
        self.repository = repository

    def export(
        self,
        task_id: str,
        *,
        format: ExportFormat,
        selection: ExportSelection = "accepted",
    ) -> ExportDocument:
        cards = self.repository.all_cards(task_id)
        selected = self._select(cards, selection)
        if format == "json":
            content = self._json(task_id, selected)
            media_type = "application/json"
            extension = "json"
        elif format == "markdown":
            content = self._markdown(task_id, selected)
            media_type = "text/markdown; charset=utf-8"
            extension = "md"
        else:
            content = self._bibtex(selected)
            media_type = "application/x-bibtex; charset=utf-8"
            extension = "bib"
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        manifest = ExportManifest(
            task_id=task_id,
            format=format,
            selection=selection,
            item_count=len(selected),
            sha256=digest,
        )
        return ExportDocument(
            manifest=manifest,
            media_type=media_type,
            filename=f"paperagent-{task_id}-{selection}.{extension}",
            content=content,
        )

    @staticmethod
    def _select(
        cards: list[ReviewPaperCard], selection: ExportSelection
    ) -> list[ReviewPaperCard]:
        if selection == "accepted":
            return [card for card in cards if card.decision is ReviewDecision.ACCEPTED]
        if selection == "favorite":
            return [card for card in cards if card.favorite]
        return list(cards)

    @staticmethod
    def _json(task_id: str, cards: list[ReviewPaperCard]) -> str:
        return _canonical_json(
            {
                "task_id": task_id,
                "papers": [card.model_dump(mode="json") for card in cards],
            }
        )

    @staticmethod
    def _markdown(task_id: str, cards: list[ReviewPaperCard]) -> str:
        lines = [f"# PaperAgent Evidence Export — {task_id}", ""]
        for card in cards:
            lines.extend(
                [
                    f"## {card.title}",
                    "",
                    f"- Paper ID: `{card.paper_id}`",
                    f"- Locator: {card.locator}",
                    f"- Verification: {card.verification_status}",
                    f"- Review: {card.decision.value}",
                    f"- Favorite: {'yes' if card.favorite else 'no'}",
                    f"- Evidence gaps: {', '.join(card.gap_ids) or 'none'}",
                    "",
                    card.summary,
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    @classmethod
    def _bibtex(cls, cards: list[ReviewPaperCard]) -> str:
        entries: list[str] = []
        for index, card in enumerate(cards, start=1):
            key = cls._bib_key(card, index)
            fields = [f"  title = {{{cls._escape_bib(card.title)}}}"]
            locator = card.locator
            if locator.startswith("doi:"):
                fields.append(f"  doi = {{{cls._escape_bib(locator[4:])}}}")
            elif "arxiv.org/abs/" in locator:
                fields.extend(
                    [
                        f"  eprint = {{{cls._escape_bib(locator.rsplit('/', 1)[-1])}}}",
                        "  archivePrefix = {arXiv}",
                    ]
                )
            else:
                fields.append(f"  url = {{{cls._escape_bib(locator)}}}")
            if card.summary:
                fields.append(f"  note = {{{cls._escape_bib(card.summary)}}}")
            entries.append(f"@misc{{{key},\n" + ",\n".join(fields) + "\n}")
        return "\n\n".join(entries) + ("\n" if entries else "")

    @staticmethod
    def _bib_key(card: ReviewPaperCard, index: int) -> str:
        base = re.sub(r"[^A-Za-z0-9]+", "", card.title)[:24] or "paper"
        return f"{base}{index:02d}"

    @staticmethod
    def _escape_bib(value: str) -> str:
        return value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
