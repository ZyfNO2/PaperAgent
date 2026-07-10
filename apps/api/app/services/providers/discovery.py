"""Model discovery service — fetch available models from a provider.

Re6.1 Provider Core. Uses protocol adapters to query /v1/models or
equivalent endpoints and returns a structured model list.
"""
from __future__ import annotations

import logging
from typing import Any

from .errors import ProviderError, ProviderErrorType
from .profile import ModelInfo, DiscoverySource

logger = logging.getLogger(__name__)

# Global model whitelist — models outside this set are filtered out
_ALLOWED_MODEL_IDS = frozenset({"deepseek-v4-flash", "big-pickle"})


async def discover_models(
    base_url: str,
    api_key: str,
    protocol: str = "openai_compatible",
) -> list[ModelInfo] | ProviderError:
    """Discover available models from a provider.

    1. Try GET /v1/models (OpenAI-compatible)
    2. 200 → parse model list, filter to whitelist
    3. 404/405 → discovery_unsupported, allow manual entry
    4. 401 → invalid_auth, stop
    5. Other → typed error

    Args:
        base_url: Provider base URL.
        api_key: Raw API key for authentication.
        protocol: "openai_compatible" or "anthropic_like".

    Returns:
        List of ModelInfo objects (filtered to whitelist) or ProviderError.
    """
    from .adapters.openai_adapter import openai_list_models

    result = await openai_list_models(base_url, api_key)

    if isinstance(result, ProviderError):
        if result.error_type == ProviderErrorType.discovery_unsupported:
            # 404/405 — discovery not supported, user can manually add models
            return result  # Caller should allow manual model entry
        # Other errors (401, etc.) — propagate
        return result

    if not isinstance(result, list):
        return ProviderError(
            error_type=ProviderErrorType.malformed_output,
            detail="models endpoint returned non-list data",
        )

    # Filter to allowed models only
    models: list[ModelInfo] = []
    for model_id in result:
        if model_id in _ALLOWED_MODEL_IDS:
            models.append(ModelInfo(
                model_id=model_id,
                label=_model_label(model_id),
                discovery_source=DiscoverySource.auto,
            ))
        else:
            logger.debug("discovery: filtered out non-whitelist model: %s", model_id)

    if not models:
        logger.info(
            "discovery: no whitelist models found in provider list (got %d total). "
            "Allowed: %s",
            len(result), sorted(_ALLOWED_MODEL_IDS),
        )

    return models


def _model_label(model_id: str) -> str:
    """Return a human-readable label for a known model_id."""
    labels = {
        "deepseek-v4-flash": "DeepSeek V4 Flash",
        "big-pickle": "Big Pickle",
    }
    return labels.get(model_id, model_id)
