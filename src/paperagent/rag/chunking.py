from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .errors import RegistryIntegrityError
from .hashing import canonical_hash, canonical_json, sha256_text, stable_id
from .models import (
    Chunk,
    ChunkingConfig,
    ChunkLocator,
    DocumentVersion,
    IndexManifest,
    IndexedDocument,
    ParsedDocument,
    ParsedParagraph,
    SourceArtifact,
)
from .parsers import parse_source


@dataclass(frozen=True, slots=True)
class _Segment:
    text: str
    paragraph: ParsedParagraph
    start_offset: int
    end_offset: int


def chunk_config_hash(config: ChunkingConfig) -> str:
    return canonical_hash(config)


def _split_paragraph(paragraph: ParsedParagraph, max_chars: int) -> list[_Segment]:
    text = paragraph.text
    if len(text) <= max_chars:
        return [_Segment(text, paragraph, 0, len(text))]

    segments: list[_Segment] = []
    cursor = 0
    while cursor < len(text):
        hard_end = min(cursor + max_chars, len(text))
        end = hard_end
        if hard_end < len(text):
            boundary = max(
                text.rfind("\n", cursor + 1, hard_end + 1),
                text.rfind(" ", cursor + 1, hard_end + 1),
            )
            if boundary > cursor:
                end = boundary
        piece = text[cursor:end].strip()
        leading = len(text[cursor:end]) - len(text[cursor:end].lstrip())
        trailing = len(text[cursor:end].rstrip())
        actual_start = cursor + leading
        actual_end = cursor + trailing
        if piece:
            segments.append(_Segment(piece, paragraph, actual_start, actual_end))
        cursor = end
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
    return segments


def _build_chunk(
    *,
    segments: list[_Segment],
    parsed: ParsedDocument,
    version: DocumentVersion,
    config: ChunkingConfig,
    config_hash: str,
    ordinal: int,
) -> Chunk:
    text = config.paragraph_separator.join(segment.text for segment in segments)
    first = segments[0]
    last = segments[-1]
    locator = ChunkLocator(
        heading_path=first.paragraph.locator.heading_path,
        paragraph_start=first.paragraph.locator.paragraph_index,
        paragraph_end=last.paragraph.locator.paragraph_index,
        line_start=first.paragraph.locator.line_start,
        line_end=last.paragraph.locator.line_end,
        start_offset=first.start_offset,
        end_offset=last.end_offset,
    )
    text_hash = sha256_text(text)
    chunk_id = stable_id(
        "chk",
        version.version_id,
        config_hash,
        str(ordinal),
        text_hash,
        canonical_json(locator),
    )
    return Chunk(
        chunk_id=chunk_id,
        document_id=parsed.identity.document_id,
        version_id=version.version_id,
        ordinal=ordinal,
        text=text,
        text_hash=text_hash,
        locator=locator,
    )


def build_document_version(
    parsed: ParsedDocument,
    *,
    created_at: datetime,
    source_modified_at: datetime | None = None,
) -> DocumentVersion:
    version_id = stable_id(
        "ver",
        parsed.identity.document_id,
        parsed.source_hash,
        parsed.parser_name,
        parsed.parser_version,
    )
    return DocumentVersion(
        version_id=version_id,
        document_id=parsed.identity.document_id,
        source_hash=parsed.source_hash,
        parser_name=parsed.parser_name,
        parser_version=parsed.parser_version,
        byte_length=parsed.byte_length,
        created_at=created_at,
        source_modified_at=source_modified_at,
    )


def chunk_document(
    parsed: ParsedDocument,
    version: DocumentVersion,
    config: ChunkingConfig,
) -> tuple[Chunk, ...]:
    if version.document_id != parsed.identity.document_id:
        raise RegistryIntegrityError("version document_id does not match parsed document")
    if version.source_hash != parsed.source_hash:
        raise RegistryIntegrityError("version source_hash does not match parsed document")

    config_hash = chunk_config_hash(config)
    chunks: list[Chunk] = []
    current: list[_Segment] = []
    current_length = 0
    current_heading: tuple[str, ...] | None = None

    def flush() -> None:
        nonlocal current, current_length, current_heading
        if not current:
            return
        chunks.append(
            _build_chunk(
                segments=current,
                parsed=parsed,
                version=version,
                config=config,
                config_hash=config_hash,
                ordinal=len(chunks),
            )
        )
        current = []
        current_length = 0
        current_heading = None

    for paragraph in parsed.paragraphs:
        for segment in _split_paragraph(paragraph, config.max_chars):
            heading = segment.paragraph.locator.heading_path
            separator_cost = len(config.paragraph_separator) if current else 0
            heading_changed = (
                config.preserve_heading_boundaries
                and current_heading is not None
                and heading != current_heading
            )
            would_overflow = current_length + separator_cost + len(segment.text) > config.max_chars
            if current and (heading_changed or would_overflow):
                flush()
            current.append(segment)
            current_heading = heading
            current_length = len(segment.text) if len(current) == 1 else (
                current_length + len(config.paragraph_separator) + len(segment.text)
            )
    flush()
    return tuple(chunks)


def build_manifest(
    *,
    version: DocumentVersion,
    chunks: tuple[Chunk, ...],
    config: ChunkingConfig,
    created_at: datetime,
) -> IndexManifest:
    if any(chunk.document_id != version.document_id for chunk in chunks):
        raise RegistryIntegrityError("all chunks must match the manifest document_id")
    if any(chunk.version_id != version.version_id for chunk in chunks):
        raise RegistryIntegrityError("all chunks must match the manifest version_id")
    if tuple(chunk.ordinal for chunk in chunks) != tuple(range(len(chunks))):
        raise RegistryIntegrityError("chunk ordinals must be contiguous and zero-based")

    config_hash = chunk_config_hash(config)
    chunk_ids = tuple(chunk.chunk_id for chunk in chunks)
    manifest_id = stable_id(
        "man",
        version.version_id,
        config_hash,
        canonical_json(chunk_ids),
    )
    return IndexManifest(
        manifest_id=manifest_id,
        document_id=version.document_id,
        version_id=version.version_id,
        source_hash=version.source_hash,
        chunk_config_hash=config_hash,
        parser_name=version.parser_name,
        parser_version=version.parser_version,
        chunk_ids=chunk_ids,
        chunk_count=len(chunk_ids),
        created_at=created_at,
    )


def build_indexed_document(
    artifact: SourceArtifact,
    *,
    config: ChunkingConfig,
    created_at: datetime,
) -> IndexedDocument:
    parsed = parse_source(artifact)
    version = build_document_version(
        parsed,
        created_at=created_at,
        source_modified_at=artifact.source_modified_at,
    )
    chunks = chunk_document(parsed, version, config)
    manifest = build_manifest(
        version=version,
        chunks=chunks,
        config=config,
        created_at=created_at,
    )
    return IndexedDocument(
        identity=artifact.identity,
        version=version,
        chunks=chunks,
        manifest=manifest,
    )
