from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .errors import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    RegistryIntegrityError,
    VersionConflictError,
)
from .models import (
    AddDocumentCommand,
    Chunk,
    DeleteDocumentCommand,
    DocumentIdentity,
    DocumentVersion,
    IndexManifest,
    IndexedDocument,
    RegistryMutationResult,
    UpdateDocumentCommand,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    source_uri TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    media_type TEXT NOT NULL,
    active_version_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_versions (
    version_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    source_hash TEXT NOT NULL,
    parser_name TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    byte_length INTEGER NOT NULL CHECK (byte_length >= 0),
    source_modified_at TEXT,
    created_at TEXT NOT NULL,
    is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),
    UNIQUE(document_id, source_hash, parser_name, parser_version)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_document_versions_active
ON document_versions(document_id)
WHERE is_active = 1;

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    version_id TEXT NOT NULL REFERENCES document_versions(version_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    text TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    heading_path_json TEXT NOT NULL,
    paragraph_start INTEGER NOT NULL,
    paragraph_end INTEGER NOT NULL,
    line_start INTEGER NOT NULL,
    line_end INTEGER NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    UNIQUE(version_id, ordinal)
);

CREATE TABLE IF NOT EXISTS index_manifests (
    manifest_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    version_id TEXT NOT NULL UNIQUE REFERENCES document_versions(version_id) ON DELETE CASCADE,
    source_hash TEXT NOT NULL,
    chunk_config_hash TEXT NOT NULL,
    parser_name TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    fts_schema_version TEXT NOT NULL,
    chunk_ids_json TEXT NOT NULL,
    chunk_count INTEGER NOT NULL CHECK (chunk_count >= 0),
    created_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    document_id UNINDEXED,
    version_id UNINDEXED,
    title_path,
    text,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


class SQLiteDocumentRegistry:
    """Transactional registry for deterministic document/index artifacts.

    The FTS table mirrors only active-version chunks. This class deliberately
    exposes no ranked query API in v0.09.1.
    """

    def __init__(self, database: str | Path | sqlite3.Connection) -> None:
        if isinstance(database, sqlite3.Connection):
            self._connection = database
            self._owns_connection = False
        else:
            self._connection = sqlite3.connect(str(database), isolation_level=None)
            self._owns_connection = True
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.executescript(_SCHEMA)

    def close(self) -> None:
        if self._owns_connection:
            self._connection.close()

    def __enter__(self) -> SQLiteDocumentRegistry:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self._connection.execute("ROLLBACK")
            raise
        else:
            self._connection.execute("COMMIT")

    def add(self, command: AddDocumentCommand) -> RegistryMutationResult:
        indexed = command.indexed_document
        self._validate_indexed_document(indexed)
        with self._transaction():
            existing = self._connection.execute(
                "SELECT 1 FROM documents WHERE document_id = ? OR source_uri = ?",
                (indexed.identity.document_id, indexed.identity.source_uri),
            ).fetchone()
            if existing is not None:
                raise DocumentAlreadyExistsError(indexed.identity.document_id)
            self._insert_document(indexed)
            self._insert_version(indexed.version, is_active=True)
            self._insert_chunks(indexed.chunks)
            self._insert_manifest(indexed.manifest)
            self._insert_fts(indexed.chunks)
            self._connection.execute(
                "UPDATE documents SET active_version_id = ? WHERE document_id = ?",
                (indexed.version.version_id, indexed.identity.document_id),
            )
        return RegistryMutationResult(
            action="add",
            document_id=indexed.identity.document_id,
            version_id=indexed.version.version_id,
            chunk_count=len(indexed.chunks),
        )

    def update(self, command: UpdateDocumentCommand) -> RegistryMutationResult:
        indexed = command.indexed_document
        self._validate_indexed_document(indexed)
        with self._transaction():
            row = self._connection.execute(
                """
                SELECT source_uri, display_name, media_type, active_version_id
                FROM documents WHERE document_id = ?
                """,
                (indexed.identity.document_id,),
            ).fetchone()
            if row is None:
                raise DocumentNotFoundError(indexed.identity.document_id)
            persisted_identity = DocumentIdentity(
                document_id=indexed.identity.document_id,
                source_uri=row["source_uri"],
                display_name=row["display_name"],
                media_type=row["media_type"],
            )
            if persisted_identity != indexed.identity:
                raise RegistryIntegrityError(
                    "document identity is immutable; update only the source content"
                )
            if row["active_version_id"] != command.previous_version_id:
                raise VersionConflictError(
                    f"expected {command.previous_version_id}, "
                    f"found {row['active_version_id']}"
                )
            if indexed.version.version_id == command.previous_version_id:
                raise VersionConflictError("update must create a new version")

            self._connection.execute(
                "UPDATE document_versions SET is_active = 0 WHERE version_id = ?",
                (command.previous_version_id,),
            )
            self._connection.execute(
                "DELETE FROM chunks_fts WHERE document_id = ?",
                (indexed.identity.document_id,),
            )
            self._insert_version(indexed.version, is_active=True)
            self._insert_chunks(indexed.chunks)
            self._insert_manifest(indexed.manifest)
            self._insert_fts(indexed.chunks)
            self._connection.execute(
                """
                UPDATE documents
                SET active_version_id = ?, updated_at = ?
                WHERE document_id = ?
                """,
                (
                    indexed.version.version_id,
                    indexed.version.created_at.isoformat(),
                    indexed.identity.document_id,
                ),
            )
        return RegistryMutationResult(
            action="update",
            document_id=indexed.identity.document_id,
            version_id=indexed.version.version_id,
            previous_version_id=command.previous_version_id,
            chunk_count=len(indexed.chunks),
        )

    def delete(self, command: DeleteDocumentCommand) -> RegistryMutationResult:
        with self._transaction():
            row = self._connection.execute(
                "SELECT active_version_id FROM documents WHERE document_id = ?",
                (command.document_id,),
            ).fetchone()
            if row is None:
                raise DocumentNotFoundError(command.document_id)
            active_version_id = row["active_version_id"]
            if (
                command.expected_active_version_id is not None
                and active_version_id != command.expected_active_version_id
            ):
                raise VersionConflictError(
                    f"expected {command.expected_active_version_id}, "
                    f"found {active_version_id}"
                )
            self._connection.execute(
                "DELETE FROM chunks_fts WHERE document_id = ?",
                (command.document_id,),
            )
            self._connection.execute(
                "DELETE FROM documents WHERE document_id = ?",
                (command.document_id,),
            )
        return RegistryMutationResult(
            action="delete",
            document_id=command.document_id,
            previous_version_id=active_version_id,
        )

    def get_identity(self, document_id: str) -> DocumentIdentity | None:
        row = self._connection.execute(
            """
            SELECT document_id, source_uri, display_name, media_type
            FROM documents WHERE document_id = ?
            """,
            (document_id,),
        ).fetchone()
        if row is None:
            return None
        return DocumentIdentity(**dict(row))

    def get_active_version(self, document_id: str) -> DocumentVersion | None:
        row = self._connection.execute(
            """
            SELECT v.version_id, v.document_id, v.source_hash, v.parser_name,
                   v.parser_version, v.byte_length, v.created_at,
                   v.source_modified_at
            FROM document_versions AS v
            WHERE v.document_id = ? AND v.is_active = 1
            """,
            (document_id,),
        ).fetchone()
        if row is None:
            return None
        return DocumentVersion(**dict(row))

    def list_chunks(self, version_id: str) -> tuple[Chunk, ...]:
        rows = self._connection.execute(
            """
            SELECT chunk_id, document_id, version_id, ordinal, text, text_hash,
                   heading_path_json, paragraph_start, paragraph_end,
                   line_start, line_end, start_offset, end_offset
            FROM chunks WHERE version_id = ? ORDER BY ordinal
            """,
            (version_id,),
        ).fetchall()
        chunks: list[Chunk] = []
        for row in rows:
            chunks.append(
                Chunk(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    version_id=row["version_id"],
                    ordinal=row["ordinal"],
                    text=row["text"],
                    text_hash=row["text_hash"],
                    locator={
                        "heading_path": tuple(json.loads(row["heading_path_json"])),
                        "paragraph_start": row["paragraph_start"],
                        "paragraph_end": row["paragraph_end"],
                        "line_start": row["line_start"],
                        "line_end": row["line_end"],
                        "start_offset": row["start_offset"],
                        "end_offset": row["end_offset"],
                    },
                )
            )
        return tuple(chunks)

    def get_manifest(self, version_id: str) -> IndexManifest | None:
        row = self._connection.execute(
            "SELECT * FROM index_manifests WHERE version_id = ?",
            (version_id,),
        ).fetchone()
        if row is None:
            return None
        return IndexManifest(
            manifest_id=row["manifest_id"],
            document_id=row["document_id"],
            version_id=row["version_id"],
            source_hash=row["source_hash"],
            chunk_config_hash=row["chunk_config_hash"],
            parser_name=row["parser_name"],
            parser_version=row["parser_version"],
            fts_schema_version=row["fts_schema_version"],
            chunk_ids=tuple(json.loads(row["chunk_ids_json"])),
            chunk_count=row["chunk_count"],
            created_at=row["created_at"],
        )

    def count_fts_rows(self, document_id: str | None = None) -> int:
        if document_id is None:
            row = self._connection.execute(
                "SELECT COUNT(*) AS count FROM chunks_fts"
            ).fetchone()
        else:
            row = self._connection.execute(
                "SELECT COUNT(*) AS count FROM chunks_fts WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        assert row is not None
        return int(row["count"])

    def fts_schema_sql(self) -> str:
        row = self._connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'chunks_fts'"
        ).fetchone()
        if row is None:
            raise RegistryIntegrityError("chunks_fts schema is missing")
        return str(row["sql"])

    @staticmethod
    def _validate_indexed_document(indexed: IndexedDocument) -> None:
        document_id = indexed.identity.document_id
        version = indexed.version
        manifest = indexed.manifest
        if version.document_id != document_id:
            raise RegistryIntegrityError("version document_id mismatch")
        if manifest.document_id != document_id:
            raise RegistryIntegrityError("manifest document_id mismatch")
        if manifest.version_id != version.version_id:
            raise RegistryIntegrityError("manifest version_id mismatch")
        if manifest.source_hash != version.source_hash:
            raise RegistryIntegrityError("manifest source_hash mismatch")
        if manifest.chunk_ids != tuple(chunk.chunk_id for chunk in indexed.chunks):
            raise RegistryIntegrityError("manifest chunk_ids mismatch")
        if manifest.chunk_count != len(indexed.chunks):
            raise RegistryIntegrityError("manifest chunk_count mismatch")
        if any(chunk.document_id != document_id for chunk in indexed.chunks):
            raise RegistryIntegrityError("chunk document_id mismatch")
        if any(chunk.version_id != version.version_id for chunk in indexed.chunks):
            raise RegistryIntegrityError("chunk version_id mismatch")
        if tuple(chunk.ordinal for chunk in indexed.chunks) != tuple(
            range(len(indexed.chunks))
        ):
            raise RegistryIntegrityError("chunk ordinals must be contiguous")

    def _insert_document(self, indexed: IndexedDocument) -> None:
        identity = indexed.identity
        created_at = indexed.version.created_at.isoformat()
        self._connection.execute(
            """
            INSERT INTO documents(
                document_id, source_uri, display_name, media_type,
                active_version_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                identity.document_id,
                identity.source_uri,
                identity.display_name,
                identity.media_type,
                created_at,
                created_at,
            ),
        )

    def _insert_version(self, version: DocumentVersion, *, is_active: bool) -> None:
        self._connection.execute(
            """
            INSERT INTO document_versions(
                version_id, document_id, source_hash, parser_name,
                parser_version, byte_length, source_modified_at,
                created_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version.version_id,
                version.document_id,
                version.source_hash,
                version.parser_name,
                version.parser_version,
                version.byte_length,
                version.source_modified_at.isoformat()
                if version.source_modified_at is not None
                else None,
                version.created_at.isoformat(),
                int(is_active),
            ),
        )

    def _insert_chunks(self, chunks: tuple[Chunk, ...]) -> None:
        self._connection.executemany(
            """
            INSERT INTO chunks(
                chunk_id, document_id, version_id, ordinal, text, text_hash,
                heading_path_json, paragraph_start, paragraph_end,
                line_start, line_end, start_offset, end_offset
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    chunk.chunk_id,
                    chunk.document_id,
                    chunk.version_id,
                    chunk.ordinal,
                    chunk.text,
                    chunk.text_hash,
                    json.dumps(
                        chunk.locator.heading_path,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    chunk.locator.paragraph_start,
                    chunk.locator.paragraph_end,
                    chunk.locator.line_start,
                    chunk.locator.line_end,
                    chunk.locator.start_offset,
                    chunk.locator.end_offset,
                )
                for chunk in chunks
            ],
        )

    def _insert_manifest(self, manifest: IndexManifest) -> None:
        self._connection.execute(
            """
            INSERT INTO index_manifests(
                manifest_id, document_id, version_id, source_hash,
                chunk_config_hash, parser_name, parser_version,
                fts_schema_version, chunk_ids_json, chunk_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                manifest.manifest_id,
                manifest.document_id,
                manifest.version_id,
                manifest.source_hash,
                manifest.chunk_config_hash,
                manifest.parser_name,
                manifest.parser_version,
                manifest.fts_schema_version,
                json.dumps(manifest.chunk_ids, separators=(",", ":")),
                manifest.chunk_count,
                manifest.created_at.isoformat(),
            ),
        )

    def _insert_fts(self, chunks: tuple[Chunk, ...]) -> None:
        self._connection.executemany(
            """
            INSERT INTO chunks_fts(
                chunk_id, document_id, version_id, title_path, text
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    chunk.chunk_id,
                    chunk.document_id,
                    chunk.version_id,
                    " / ".join(chunk.locator.heading_path),
                    chunk.text,
                )
                for chunk in chunks
            ],
        )
