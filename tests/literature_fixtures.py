from __future__ import annotations

from datetime import UTC, datetime

from paperagent.schemas.literature import ProviderPaper, ProviderResult

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def provider_result(
    provider: str,
    status: str,
    papers: list[ProviderPaper] | None = None,
) -> ProviderResult:
    kwargs: dict[str, str] = {}
    if status in {"failed", "timeout", "rate_limited"}:
        kwargs = {"error_code": status.upper(), "error_message": status}
    return ProviderResult(
        provider=provider,
        request_id=f"req-{provider}-{status}",
        status=status,
        papers=papers or [],
        started_at=NOW,
        finished_at=NOW,
        **kwargs,
    )
