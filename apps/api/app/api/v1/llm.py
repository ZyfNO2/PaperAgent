"""Re5.X: LLM Provider management REST endpoints.

Allows frontend to:
  - List available providers
  - Switch active provider
  - Register a new provider at runtime
  - Test a provider's connectivity
"""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Header
from pydantic import BaseModel

from apps.api.app.services.llm_provider_registry import (
    get_provider_registry, ProviderConfig,
)

router = APIRouter(prefix="/api/v1/llm", tags=["llm-v1"])


class RegisterProviderRequest(BaseModel):
    name: str
    api_key: str
    base_url: str
    model: str
    is_reasoner: bool = False
    rpm_limit: int = 0
    label: str = ""


class SetActiveRequest(BaseModel):
    primary: str
    fallbacks: list[str] | None = None


class TestProviderRequest(BaseModel):
    name: str | None = None  # None = test active provider


@router.get("/providers")
def list_providers() -> dict[str, Any]:
    """List all registered LLM providers."""
    registry = get_provider_registry()
    providers = [p.to_dict() for p in registry.list_providers()]
    chain = registry.get_active_chain()
    return {
        "providers": providers,
        "n": len(providers),
        "active_primary": chain.primary,
        "fallbacks": chain.fallbacks,
    }


@router.post("/providers")
def register_provider(
    req: RegisterProviderRequest,
    x_acp_capability: str | None = Header(default=None, alias="X-ACP-Capability"),
) -> dict[str, Any]:
    """Register a new LLM provider at runtime."""
    if (x_acp_capability or "").lower() != "write":
        return {"success": False, "error": {"error_code": "PERMISSION_DENIED",
                "message": "requires X-ACP-Capability: write"}}
    registry = get_provider_registry()
    config = ProviderConfig(
        name=req.name,
        api_key=req.api_key,
        base_url=req.base_url,
        model=req.model,
        is_reasoner=req.is_reasoner,
        rpm_limit=req.rpm_limit,
        label=req.label or req.name,
        source="runtime",
    )
    registry.register(config)
    return {"success": True, "provider": config.to_dict()}


@router.post("/active")
def set_active_provider(
    req: SetActiveRequest,
    x_acp_capability: str | None = Header(default=None, alias="X-ACP-Capability"),
) -> dict[str, Any]:
    """Set the active LLM provider and optional fallback chain."""
    if (x_acp_capability or "").lower() != "write":
        return {"success": False, "error": {"error_code": "PERMISSION_DENIED",
                "message": "requires X-ACP-Capability: write"}}
    registry = get_provider_registry()
    try:
        registry.set_active(req.primary, req.fallbacks)
        chain = registry.get_active_chain()
        return {"success": True, "active_primary": chain.primary, "fallbacks": chain.fallbacks}
    except ValueError as e:
        return {"success": False, "error": {"error_code": "INVALID_PARAMS", "message": str(e)}}


@router.post("/test")
def test_provider(req: TestProviderRequest) -> dict[str, Any]:
    """Test a provider's connectivity with a simple JSON call."""
    import sys
    sys.path.insert(0, ".")
    from apps.api.app.services.llm import _chat_openai_compat_once, LLMUnavailable

    registry = get_provider_registry()
    name = req.name
    if name:
        cfg = registry.get_provider(name)
        if cfg is None:
            return {"success": False, "error": f"provider '{name}' not found"}
    else:
        providers = registry.get_ordered_providers()
        if not providers:
            return {"success": False, "error": "no providers registered"}
        cfg = providers[0]

    try:
        raw = _chat_openai_compat_once(
            'Return exactly: {"status":"ok"}',
            system="You are a test bot. Only output JSON.",
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            temperature=0.1,
            max_tokens=50,
            timeout=15,
            rate_limit_bucket=cfg.name.upper(),
        )
        import json
        cleaned = raw.strip()
        try:
            result = json.loads(cleaned)
            return {"success": True, "provider": cfg.name, "model": cfg.model,
                    "response": result}
        except json.JSONDecodeError:
            return {"success": True, "provider": cfg.name, "model": cfg.model,
                    "response": cleaned[:200], "note": "non-JSON response (reasoner model)"}
    except LLMUnavailable as e:
        return {"success": False, "provider": cfg.name, "error": str(e)}
    except Exception as e:
        return {"success": False, "provider": cfg.name, "error": f"{type(e).__name__}: {e}"}
