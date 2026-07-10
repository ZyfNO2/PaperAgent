"""Provider management package — Re6.1 Provider Core."""
from .errors import (
    ProviderError,
    ProviderErrorType,
    classify_http_error,
)
from .profile import (
    ProviderProfile,
    ProviderProtocol,
    ProviderStatus,
    ProviderCapabilities,
    ModelInfo,
    ProbedCapabilities,
    SecretRef,
    SecretRefType,
    DiscoverySource,
    create_default_profile,
)
from .secret_store import (
    store_secret,
    get_secret,
    delete_secret,
    secret_is_set,
)
