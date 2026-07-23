from __future__ import annotations

import hashlib
import mimetypes
import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader

from paperagent.projects.models import CitationLocator, EvidenceUnit, IngestionResult, PaperVersion
from paperagent.projects.repository import SQLiteProjectRepository, utc_now

_SECTION_PATTERN = re.compile(r"^(?:#+\s+|(?:\d+(?:\.\d+)*)\s+)(.+)$")
_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_+.-]{2,}|[\u4e00-\u9fff]{2,}")


class PaperIngestionService:
    def __init__(self, repository: SQLiteProjectRepository) -> None:
        self.repository = repository

    def ingest_file(
        self,
        *,
        project_id: str,
        path: str | Path,
        title: str | None = None,
        paper_id: str | None = None,
        metadata: dict[str, object] | None = None,
        now: datetime | None = None,
    ) -> IngestionResult:
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(source)
        raw_bytes = source.read_bytes()
        if not raw_bytes:
            raise ValueError("paper file is empty")
        identifier = paper_id or f"paper-{uuid4().hex}"
        version = self.repository.next_ingestion_version(project_id=project_id, paper_id=identifier)
        instant = now or utc_now()
        pages = self._extract_pages(source)
        clean_title = (title or self._infer_title(pages, source.stem)).strip()
        if not clean_title:
            raise ValueError("paper title must not be empty")
        media_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        paper = PaperVersion(
            paper_id=identifier,
            project_id=project_id,
            title=clean_title,
            source_path=source,
            content_sha256=hashlib.sha256(raw_bytes).hexdigest(),
            ingestion_version=version,
            media_type=media_type,
            metadata=dict(metadata or {}),
            ingested_at=instant,
        )
        units = tuple(
            self._build_units(
                project_id=project_id,
                paper_id=identifier,
                ingestion_version=version,
                pages=pages,
            )
        )
        if not units:
            raise ValueError("paper contains no extractable textual evidence")
        self.repository.persist_ingestion(paper, units)
        return IngestionResult(paper=paper, evidence_units=units)

    @staticmethod
    def _extract_pages(path: Path) -> tuple[tuple[int | None, str], ...]:
        suffix = path.suffix.casefold()
        if suffix == ".pdf":
            reader = PdfReader(str(path))
            extracted = tuple(
                (index, (page.extract_text() or "").strip())
                for index, page in enumerate(reader.pages, start=1)
            )
            return tuple(item for item in extracted if item[1])
        if suffix not in {".txt", ".md", ".markdown"}:
            raise ValueError(f"unsupported paper format: {path.suffix or '<none>'}")
        text = path.read_text(encoding="utf-8")
        return ((None, text),)

    @staticmethod
    def _infer_title(pages: Iterable[tuple[int | None, str]], fallback: str) -> str:
        for _, text in pages:
            for line in text.splitlines():
                clean = line.strip().lstrip("#").strip()
                if clean:
                    return clean[:300]
        return fallback

    def _build_units(
        self,
        *,
        project_id: str,
        paper_id: str,
        ingestion_version: int,
        pages: Iterable[tuple[int | None, str]],
    ) -> Iterable[EvidenceUnit]:
        for page_number, page_text in pages:
            section: str | None = None
            paragraph_number = 0
            for match in re.finditer(r"(?:^|\n\s*\n)(.*?)(?=\n\s*\n|\Z)", page_text, re.DOTALL):
                block = match.group(1).strip()
                if not block:
                    continue
                lines = block.splitlines()
                first_line = lines[0].strip()
                section_match = _SECTION_PATTERN.match(first_line)
                if section_match:
                    section = section_match.group(1).strip()
                    block = "\n".join(lines[1:]).strip()
                    if not block:
                        continue
                content = " ".join(block.split()).strip()
                if not content:
                    continue
                paragraph_number += 1
                char_start = match.start(1)
                char_end = match.end(1)
                locator = CitationLocator(
                    paper_id=paper_id,
                    ingestion_version=ingestion_version,
                    section=section,
                    page=page_number,
                    paragraph=paragraph_number,
                    char_start=char_start,
                    char_end=char_end,
                    quote=content[:500],
                )
                yield EvidenceUnit(
                    unit_id=(
                        f"eu-{paper_id}-{ingestion_version}-{paragraph_number}-{uuid4().hex[:8]}"
                    ),
                    project_id=project_id,
                    paper_id=paper_id,
                    ingestion_version=ingestion_version,
                    content=content,
                    section=section,
                    page=page_number,
                    paragraph=paragraph_number,
                    keywords=self._keywords(content),
                    locator=locator,
                )

    @staticmethod
    def _keywords(content: str) -> tuple[str, ...]:
        tokens = [token.casefold() for token in _TOKEN_PATTERN.findall(content)]
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        ranked = sorted(counts, key=lambda token: (-counts[token], token))
        return tuple(ranked[:16])
