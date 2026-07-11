"""Re4.4: Unified ACP error structure."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ACPError(BaseModel):
    """Unified error response for all ACP operations."""
    success: bool = False
    error_code: str
    message: str
    capability: str | None = None
    details: dict[str, Any] | None = None


UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"
PERMISSION_DENIED = "PERMISSION_DENIED"
INVALID_PARAMS = "INVALID_PARAMS"
INTERNAL_ERROR = "INTERNAL_ERROR"
NOT_FOUND = "NOT_FOUND"
NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


def unknown_capability(name: str) -> ACPError:
    return ACPError(error_code=UNKNOWN_CAPABILITY,
                    message=f"Unknown capability: {name}", capability=name)


def permission_denied(name: str, required: str) -> ACPError:
    return ACPError(error_code=PERMISSION_DENIED,
                    message=f"Capability '{name}' requires '{required}' permission",
                    capability=name, details={"required_permission": required})


def invalid_params(name: str, missing: list[str]) -> ACPError:
    return ACPError(error_code=INVALID_PARAMS,
                    message=f"Missing required parameters: {missing}",
                    capability=name, details={"missing": missing})


def not_found(name: str, resource: str) -> ACPError:
    return ACPError(error_code=NOT_FOUND,
                    message=f"Resource not found: {resource}",
                    capability=name)


def internal_error(name: str, detail: str) -> ACPError:
    return ACPError(error_code=INTERNAL_ERROR,
                    message=f"Internal error: {detail}",
                    capability=name)
