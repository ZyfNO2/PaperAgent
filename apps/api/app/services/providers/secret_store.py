"""SecretStore — secure API key storage for provider credentials.

Re6.1 Provider Core. Default: session-only (in-memory). Optional: OS keyring
or encrypted file vault. GET APIs only expose api_key_set boolean — raw keys
are never returned.

Design goals:
  - Default session-only (process memory dict, lost on restart).
  - Windows: Credential Manager via keyring library (optional dependency).
  - Encrypted file fallback (AES-GCM with key from environment variable).
  - Delete profile → secret purged; ledger keeps tombstone (no key).
"""
from __future__ import annotations

import base64
import logging
import os
import secrets
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory store (always available, session-only)
# ---------------------------------------------------------------------------

_session_store: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Optional: OS keyring backend
# ---------------------------------------------------------------------------

def _keyring_available() -> bool:
    try:
        import keyring  # type: ignore[import-untyped]
        return True
    except ImportError:
        return False


def _keyring_get(service: str, key_id: str) -> str | None:
    """Retrieve a secret from OS keyring. Returns None if unavailable."""
    if not _keyring_available():
        return None
    import keyring  # type: ignore[import-untyped]
    try:
        return keyring.get_password(service, key_id)
    except Exception:
        return None


def _keyring_set(service: str, key_id: str, secret: str) -> bool:
    """Store a secret in OS keyring. Returns True on success."""
    if not _keyring_available():
        return False
    import keyring  # type: ignore[import-untyped]
    try:
        keyring.set_password(service, key_id, secret)
        return True
    except Exception as exc:
        logger.warning("keyring set failed: %s", exc)
        return False


def _keyring_delete(service: str, key_id: str) -> bool:
    """Delete a secret from OS keyring. Returns True on success."""
    if not _keyring_available():
        return False
    import keyring  # type: ignore[import-untyped]
    try:
        keyring.delete_password(service, key_id)
        return True
    except Exception as exc:
        logger.warning("keyring delete failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Optional: Encrypted file vault (AES-GCM)
# ---------------------------------------------------------------------------

def _derive_vault_key() -> bytes | None:
    """Derive a 32-byte key from env var PAPERAGENT_VAULT_KEY."""
    raw = os.environ.get("PAPERAGENT_VAULT_KEY", "").strip()
    if not raw:
        return None
    from hashlib import sha256
    return sha256(raw.encode("utf-8")).digest()


def _vault_path() -> str:
    """Path to the encrypted vault file."""
    data_dir = os.environ.get("PAPERAGENT_DATA_DIR", "data")
    return os.path.join(data_dir, "provider_vault.enc")


def _vault_load() -> dict[str, str]:
    """Load + decrypt vault file. Returns empty dict if file missing."""
    key = _derive_vault_key()
    if key is None:
        return {}

    vpath = _vault_path()
    if not os.path.exists(vpath):
        return {}

    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        with open(vpath, "rb") as fh:
            nonce = fh.read(12)
            ciphertext = fh.read()
        aesgcm = AESGCM(key)
        plain = aesgcm.decrypt(nonce, ciphertext, None)
        import json
        data = json.loads(plain.decode("utf-8"))
        if isinstance(data, dict):
            return {k: str(v) for k, v in data.items()}
        return {}
    except Exception as exc:
        logger.warning("vault decrypt failed: %s", exc)
        return {}


def _vault_save(secrets_dict: dict[str, str]) -> bool:
    """Encrypt + write vault file. Creates parent dir if needed."""
    key = _derive_vault_key()
    if key is None:
        logger.warning("PAPERAGENT_VAULT_KEY not set — cannot persist vault")
        return False

    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import json
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        plain = json.dumps(secrets_dict).encode("utf-8")
        ciphertext = aesgcm.encrypt(nonce, plain, None)

        vpath = _vault_path()
        os.makedirs(os.path.dirname(vpath) or ".", exist_ok=True)
        with open(vpath, "wb") as fh:
            fh.write(nonce)
            fh.write(ciphertext)
        return True
    except Exception as exc:
        logger.warning("vault encrypt failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def store_secret(
    provider_id: str,
    api_key: str,
    *,
    vault: bool = False,
) -> str:
    """Store an API key for a provider.

    Args:
        provider_id: The provider's unique ID.
        api_key: The raw API key to store.
        vault: If True, also persist to vault (OS keyring or encrypted file).
               Default False = session-only.

    Returns:
        The key_id used to reference this secret.
    """
    if not api_key or not api_key.strip():
        raise ValueError("api_key must be a non-empty string")

    key_id = f"pa_{provider_id}_{secrets.token_hex(8)}"

    # Always store in session memory
    _session_store[key_id] = api_key.strip()

    if vault:
        # Try OS keyring first, then encrypted file
        service = "PaperAgent/ProviderKeys"
        kr_ok = _keyring_set(service, key_id, api_key.strip())
        if not kr_ok:
            vault_data = _vault_load()
            vault_data[key_id] = api_key.strip()
            _vault_save(vault_data)

    logger.info("secret stored for provider=%s key_id=%s vault=%s",
                provider_id, key_id, vault)
    return key_id


def get_secret(key_id: str) -> str | None:
    """Retrieve an API key by key_id. Tries session store, then vault.

    Returns None if the key is not found or has been purged.
    """
    # Session store first
    if key_id in _session_store:
        return _session_store[key_id]

    # Try OS keyring
    kr_val = _keyring_get("PaperAgent/ProviderKeys", key_id)
    if kr_val:
        return kr_val

    # Try encrypted file vault
    vault_data = _vault_load()
    return vault_data.get(key_id)


def delete_secret(provider_id: str, key_id: str | None = None) -> bool:
    """Delete a stored API key. Returns True if any key was removed.

    Purges from all storage backends (session, keyring, vault).
    """
    removed = False

    # Session store
    if key_id and key_id in _session_store:
        del _session_store[key_id]
        removed = True
    elif not key_id:
        # Delete all keys for this provider
        to_delete = [k for k in _session_store if k.startswith(f"pa_{provider_id}_")]
        for k in to_delete:
            del _session_store[k]
        if to_delete:
            removed = True

    # OS keyring
    if key_id:
        if _keyring_delete("PaperAgent/ProviderKeys", key_id):
            removed = True

    # Encrypted vault
    vault_data = _vault_load()
    changed = False
    if key_id and key_id in vault_data:
        del vault_data[key_id]
        changed = True
    elif not key_id:
        to_delete = [k for k in vault_data if k.startswith(f"pa_{provider_id}_")]
        for k in to_delete:
            del vault_data[k]
        if to_delete:
            changed = True
    if changed:
        _vault_save(vault_data)
        removed = True

    if removed:
        logger.info("secret deleted for provider=%s key_id=%s", provider_id, key_id)
    return removed


def secret_is_set(key_id: str) -> bool:
    """Check whether a secret exists without revealing it."""
    return (
        key_id in _session_store
        or _keyring_get("PaperAgent/ProviderKeys", key_id) is not None
        or key_id in _vault_load()
    )
