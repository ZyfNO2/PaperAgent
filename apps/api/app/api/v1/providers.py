"""Provider Management API v2 — Re6.1 Provider Core.

Endpoints for the 3-step provider setup flow:
  1. validate  → URL safety + auth check
  2. discover  → fetch model list
  3. probe     → test model capabilities

Plus CRUD for provider profiles (create, list, get, update, delete).
All GET responses only expose `api_key_set: bool` — never raw keys.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from apps.api.app.services.providers import (
    ProviderProfile,
    ProviderProtocol,
    ProviderStatus,
    ProviderError,
    ProviderErrorType,
)
from apps.api.app.services.providers import secret_store as ss
from apps.api.app.services.providers import ledger
from apps.api.app.services.security import (
    validate_provider_url,
    UrlSafetyResult,
)
from apps.api.app.services.providers.discovery import discover_models
from apps.api.app.services.providers.probe import probe_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/providers", tags=["providers-v2"])

# ---------------------------------------------------------------------------
# In-memory profile store (will be replaced by persistent storage in R6.2)
# ---------------------------------------------------------------------------
_profiles: dict[str, ProviderProfile] = {}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ValidateRequest(BaseModel):
    base_url: str = ""
    local_mode: bool = False


class ValidateResponse(BaseModel):
    allowed: bool
    reason: str = ""


class DiscoverRequest(BaseModel):
    provider_id: str = ""


class DiscoverResponse(BaseModel):
    models: list[dict[str, Any]] = Field(default_factory=list)
    discovery_supported: bool = True
    error: dict[str, Any] | None = None


class ProbeRequest(BaseModel):
    provider_id: str = ""
    model_id: str = ""


class ProbeResponse(BaseModel):
    capabilities: dict[str, Any] = Field(default_factory=dict)


class CreateProfileRequest(BaseModel):
    label: str = ""
    protocol: str = "openai_compatible"
    base_url: str = ""
    api_key: str = ""  # Only used during creation, never stored in profile
    models: list[dict[str, Any]] = Field(default_factory=list)
    vault: bool = False  # If True, persist key to vault


class UpdateProfileRequest(BaseModel):
    label: str | None = None
    base_url: str | None = None
    protocol: str | None = None
    status: str | None = None
    api_key: str | None = None  # Optional: update the stored key


class ProfileSummary(BaseModel):
    """GET-safe representation — never includes raw key."""
    provider_id: str
    label: str
    protocol: str
    base_url: str
    api_key_set: bool
    secret_ref_type: str
    model_count: int
    status: str
    config_version: str
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Step 1: Validate
# ---------------------------------------------------------------------------

@router.post("/validate")
async def validate_provider(req: ValidateRequest) -> dict[str, Any]:
    """Step 1: Validate a provider URL for safety (SSRF gate)."""
    result = await validate_provider_url(req.base_url, local_mode=req.local_mode)
    return {"allowed": result.allowed, "reason": result.reason}


# ---------------------------------------------------------------------------
# Step 2: Discover models
# ---------------------------------------------------------------------------

@router.post("/discover")
async def discover_provider_models(req: DiscoverRequest) -> dict[str, Any]:
    """Step 2: Discover available models on a registered provider."""
    profile = _profiles.get(req.provider_id)
    if profile is None:
        return {"models": [], "discovery_supported": False,
                "error": {"error_type": "not_found", "detail": "provider not found"}}

    api_key = ss.get_secret(profile.secret_ref.key_id)
    if not api_key:
        return {"models": [], "discovery_supported": False,
                "error": {"error_type": "invalid_auth", "detail": "API key not set"}}

    result = await discover_models(profile.base_url, api_key, protocol=profile.protocol.value)

    if isinstance(result, ProviderError):
        if result.error_type == ProviderErrorType.discovery_unsupported:
            # Allow manual model entry
            logger.info("discovery unsupported for provider %s — manual entry allowed",
                        req.provider_id)
            return {"models": [], "discovery_supported": False,
                    "allows_manual_models": True}
        return {"models": [], "discovery_supported": False,
                "error": {"error_type": result.error_type.value, "detail": result.detail}}

    # Update profile with discovered models
    profile.models = result
    profile.touch_version()

    ledger.record_event("discovered", req.provider_id, profile.config_version,
                        details={"n_models": len(result)})

    return {
        "models": [m.model_dump(mode="json") for m in result],
        "discovery_supported": True,
    }


# ---------------------------------------------------------------------------
# Step 3: Probe model capabilities
# ---------------------------------------------------------------------------

@router.post("/probe")
async def probe_provider_model(req: ProbeRequest) -> dict[str, Any]:
    """Step 3: Probe a specific model's capabilities."""
    profile = _profiles.get(req.provider_id)
    if profile is None:
        return {"capabilities": {}, "error": "provider not found"}

    api_key = ss.get_secret(profile.secret_ref.key_id)
    if not api_key:
        return {"capabilities": {}, "error": "API key not set"}

    caps = await probe_model(
        profile.base_url, api_key, req.model_id,
        protocol=profile.protocol.value,
    )

    # Update model info with probe results
    for m in profile.models:
        if m.model_id == req.model_id:
            m.probed_capabilities = caps
    profile.touch_version()

    ledger.record_event("probed", req.provider_id, profile.config_version,
                        details={"model_id": req.model_id,
                                 "chat": caps.chat,
                                 "json_object": caps.json_object})

    return {"capabilities": caps.model_dump(mode="json")}


# ---------------------------------------------------------------------------
# CRUD: Create / List / Get / Update / Delete
# ---------------------------------------------------------------------------

@router.post("/")
def create_profile(
    req: CreateProfileRequest,
    x_acp_capability: str | None = Header(default=None, alias="X-ACP-Capability"),
) -> dict[str, Any]:
    """Create a new provider profile with API key stored in SecretStore."""
    if (x_acp_capability or "").lower() != "write":
        return {"success": False, "error": {"error_code": "PERMISSION_DENIED",
                "message": "requires X-ACP-Capability: write"}}

    profile = ProviderProfile(
        label=req.label,
        protocol=ProviderProtocol(req.protocol),
        base_url=req.base_url,
    )

    if req.api_key:
        key_id = ss.store_secret(profile.provider_id, req.api_key, vault=req.vault)
        profile.secret_ref.key_id = key_id
        profile.secret_ref.api_key_set = True

    for m in req.models:
        from apps.api.app.services.providers.profile import ModelInfo
        profile.models.append(ModelInfo(**m) if isinstance(m, dict) else m)

    _profiles[profile.provider_id] = profile

    ledger.record_event("created", profile.provider_id, profile.config_version,
                        details={"protocol": req.protocol, "vault": req.vault})

    return {"success": True, "profile": profile.api_view()}


@router.get("/")
def list_profiles() -> dict[str, Any]:
    """List all registered provider profiles (no raw keys)."""
    summaries = []
    for p in _profiles.values():
        summaries.append(_profile_summary(p).model_dump())
    return {"profiles": summaries, "n": len(summaries)}


@router.get("/{provider_id}")
def get_profile(provider_id: str) -> dict[str, Any]:
    """Get a single provider profile (no raw key)."""
    profile = _profiles.get(provider_id)
    if profile is None:
        return {"profile": None, "error": "not found"}
    return {"profile": profile.api_view()}


@router.put("/{provider_id}")
def update_profile(
    provider_id: str,
    req: UpdateProfileRequest,
    x_acp_capability: str | None = Header(default=None, alias="X-ACP-Capability"),
) -> dict[str, Any]:
    """Update a provider profile's metadata and/or API key."""
    if (x_acp_capability or "").lower() != "write":
        return {"success": False, "error": {"error_code": "PERMISSION_DENIED",
                "message": "requires X-ACP-Capability: write"}}

    profile = _profiles.get(provider_id)
    if profile is None:
        return {"success": False, "error": "provider not found"}

    if req.label is not None:
        profile.label = req.label
    if req.base_url is not None:
        profile.base_url = req.base_url
    if req.protocol is not None:
        profile.protocol = ProviderProtocol(req.protocol)
    if req.status is not None:
        profile.status = ProviderStatus(req.status)

    if req.api_key and req.api_key.strip():
        # Delete old key, store new
        ss.delete_secret(provider_id, profile.secret_ref.key_id)
        new_key_id = ss.store_secret(provider_id, req.api_key.strip())
        profile.secret_ref.key_id = new_key_id
        profile.secret_ref.api_key_set = True

    profile.touch_version()

    ledger.record_event("updated", provider_id, profile.config_version)

    return {"success": True, "profile": profile.api_view()}


@router.delete("/{provider_id}")
def delete_profile(
    provider_id: str,
    x_acp_capability: str | None = Header(default=None, alias="X-ACP-Capability"),
) -> dict[str, Any]:
    """Delete a provider profile and its stored API key."""
    if (x_acp_capability or "").lower() != "write":
        return {"success": False, "error": {"error_code": "PERMISSION_DENIED",
                "message": "requires X-ACP-Capability: write"}}

    profile = _profiles.pop(provider_id, None)
    if profile is None:
        return {"success": False, "error": "provider not found"}

    # Purge secrets
    ss.delete_secret(provider_id, profile.secret_ref.key_id)

    # Ledger tombstone
    ledger.record_deleted_tombstone(provider_id, profile.config_version)

    return {"success": True, "provider_id": provider_id, "secret_purged": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile_summary(profile: ProviderProfile) -> ProfileSummary:
    return ProfileSummary(
        provider_id=profile.provider_id,
        label=profile.label,
        protocol=profile.protocol.value,
        base_url=profile.base_url,
        api_key_set=profile.secret_ref.api_key_set,
        secret_ref_type=profile.secret_ref.type.value,
        model_count=len(profile.models),
        status=profile.status.value,
        config_version=profile.config_version,
        created_at=profile.created_at.isoformat(),
        updated_at=profile.updated_at.isoformat(),
    )
