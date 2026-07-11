"""Re4.4: ACP REST endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header
from pydantic import BaseModel

from apps.api.app.services.acp.server import get_acp_server

router = APIRouter(prefix="/api/v1/acp", tags=["acp-v1"])


class InvokeRequest(BaseModel):
    capability: str
    params: dict[str, Any] = {}


@router.get("/capabilities")
def list_capabilities() -> dict[str, Any]:
    """List all declared ACP capabilities with full JSON Schema."""
    server = get_acp_server()
    caps = server.list_capabilities()
    return {"capabilities": caps, "n": len(caps)}


@router.post("/invoke")
def invoke_capability(
    req: InvokeRequest,
    x_acp_capability: str | None = Header(default=None, alias="X-ACP-Capability"),
) -> dict[str, Any]:
    """Invoke an ACP capability.

    For write capabilities, include header: X-ACP-Capability: write
    """
    server = get_acp_server()
    has_write = (x_acp_capability or "").lower() == "write"
    return server.invoke(req.capability, req.params, has_write_permission=has_write)


@router.get("/examples")
def get_call_examples() -> dict[str, str]:
    """Return example call snippets for external AI tools."""
    from apps.api.app.services.acp.examples import get_examples
    return get_examples()
