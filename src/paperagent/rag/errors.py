from __future__ import annotations


class RagFoundationError(Exception):
    """Base exception for the deterministic RAG foundation."""


class UnsupportedSourceTypeError(RagFoundationError):
    """Raised when no parser is registered for a source media type."""


class DocumentAlreadyExistsError(RagFoundationError):
    """Raised when an add command targets an existing document."""


class DocumentNotFoundError(RagFoundationError):
    """Raised when a registry mutation targets a missing document."""


class VersionConflictError(RagFoundationError):
    """Raised when an update/delete optimistic version check fails."""


class RegistryIntegrityError(RagFoundationError):
    """Raised when cross-artifact invariants are violated."""
