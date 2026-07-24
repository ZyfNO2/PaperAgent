from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from paperagent.schemas import NodeErrorRecord
from paperagent.telemetry.redaction import redact


class PaperAgentError(Exception):
    code = "PAPERAGENT_ERROR"


class NodeError(PaperAgentError):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        node: str,
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.node = node
        self.retryable = retryable
        self.details = dict(details or {})

    def to_record(self) -> NodeErrorRecord:
        return NodeErrorRecord(
            code=self.code,
            message=self.message,
            node=self.node,
            retryable=self.retryable,
            details=redact(self.details),
        )


class FixtureNotFoundError(PaperAgentError):
    code = "FIXTURE_NOT_FOUND"


class ProviderError(PaperAgentError):
    def __init__(
        self,
        message: str,
        *,
        provider: str,
        task: str,
        retryable: bool,
        code: str = "PROVIDER_ERROR",
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.task = task
        self.retryable = retryable
        self.code = code


class ProviderTimeoutError(ProviderError):
    def __init__(self, *, provider: str, task: str, retryable: bool = True) -> None:
        super().__init__(
            f"{provider} timed out for {task}",
            provider=provider,
            task=task,
            retryable=retryable,
            code="PROVIDER_TIMEOUT",
        )
