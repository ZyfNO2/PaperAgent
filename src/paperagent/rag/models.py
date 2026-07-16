from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SCHEMA_VERSION = "0.09.1"
FTS_SCHEMA_VERSION = "fts5-v1"

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
ParserName = Literal["markdown", "plain_text"]
MediaType = Literal["text/markdown", "text/plain"]


class FrozenContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DocumentIdentity(FrozenContract):
    schema_version: Literal["0.09.1"] = SCHEMA_VERSION
    document_id: NonEmptyStr
    source_uri: NonEmptyStr
    display_name: NonEmptyStr
    media_type: MediaType


class SourceArtifact(FrozenContract):
    schema_version: Literal["0.09.1"] = SCHEMA_VERSION
    identity: DocumentIdentity
    content: str
    encoding: Literal["utf-8"] = "utf-8"
    source_modified_at: datetime | None = None


class DocumentVersion(FrozenContract):
    schema_version: Literal["0.09.1"] = SCHEMA_VERSION
    version_id: NonEmptyStr
    document_id: NonEmptyStr
    source_hash: Sha256Hex
    parser_name: ParserName
    parser_version: NonEmptyStr
    byte_length: int = Field(ge=0)
    created_at: datetime
    source_modified_at: datetime | None = None


class ParagraphLocator(FrozenContract):
    heading_path: tuple[str, ...] = ()
    paragraph_index: int = Field(ge=0)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_line_range(self) -> ParagraphLocator:
        if self.line_end < self.line_start:
            raise ValueError("line_end must be greater than or equal to line_start")
        return self


class ParsedParagraph(FrozenContract):
    text: NonEmptyStr
    locator: ParagraphLocator


class ParsedDocument(FrozenContract):
    identity: DocumentIdentity
    parser_name: ParserName
    parser_version: NonEmptyStr
    source_hash: Sha256Hex
    byte_length: int = Field(ge=0)
    paragraphs: tuple[ParsedParagraph, ...]


class ChunkingConfig(FrozenContract):
    schema_version: Literal["0.09.1"] = SCHEMA_VERSION
    max_chars: int = Field(default=1200, ge=64, le=100_000)
    preserve_heading_boundaries: bool = True
    paragraph_separator: Literal["\n\n"] = "\n\n"


class ChunkLocator(FrozenContract):
    heading_path: tuple[str, ...] = ()
    paragraph_start: int = Field(ge=0)
    paragraph_end: int = Field(ge=0)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    start_offset: int = Field(default=0, ge=0)
    end_offset: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_ranges(self) -> ChunkLocator:
        if self.paragraph_end < self.paragraph_start:
            raise ValueError("paragraph_end must be >= paragraph_start")
        if self.line_end < self.line_start:
            raise ValueError("line_end must be >= line_start")
        return self


class Chunk(FrozenContract):
    schema_version: Literal["0.09.1"] = SCHEMA_VERSION
    chunk_id: NonEmptyStr
    document_id: NonEmptyStr
    version_id: NonEmptyStr
    ordinal: int = Field(ge=0)
    text: NonEmptyStr
    text_hash: Sha256Hex
    locator: ChunkLocator


class IndexManifest(FrozenContract):
    schema_version: Literal["0.09.1"] = SCHEMA_VERSION
    manifest_id: NonEmptyStr
    document_id: NonEmptyStr
    version_id: NonEmptyStr
    source_hash: Sha256Hex
    chunk_config_hash: Sha256Hex
    parser_name: ParserName
    parser_version: NonEmptyStr
    fts_schema_version: Literal["fts5-v1"] = FTS_SCHEMA_VERSION
    chunk_ids: tuple[str, ...]
    chunk_count: int = Field(ge=0)
    created_at: datetime

    @model_validator(mode="after")
    def validate_chunks(self) -> IndexManifest:
        if self.chunk_count != len(self.chunk_ids):
            raise ValueError("chunk_count must equal len(chunk_ids)")
        if len(set(self.chunk_ids)) != len(self.chunk_ids):
            raise ValueError("chunk_ids must be unique")
        return self


class IndexedDocument(FrozenContract):
    identity: DocumentIdentity
    version: DocumentVersion
    chunks: tuple[Chunk, ...]
    manifest: IndexManifest


class AddDocumentCommand(FrozenContract):
    action: Literal["add"] = "add"
    indexed_document: IndexedDocument


class UpdateDocumentCommand(FrozenContract):
    action: Literal["update"] = "update"
    indexed_document: IndexedDocument
    previous_version_id: NonEmptyStr


class DeleteDocumentCommand(FrozenContract):
    action: Literal["delete"] = "delete"
    document_id: NonEmptyStr
    expected_active_version_id: NonEmptyStr | None = None


class RegistryMutationResult(FrozenContract):
    schema_version: Literal["0.09.1"] = SCHEMA_VERSION
    action: Literal["add", "update", "delete"]
    document_id: NonEmptyStr
    version_id: str | None = None
    previous_version_id: str | None = None
    chunk_count: int = Field(default=0, ge=0)
