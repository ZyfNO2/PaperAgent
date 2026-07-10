"""URL safety / SSRF protection for provider endpoint validation.

Re6.1 Provider Core — validates that provider base URLs are safe before
any network request is made. Protects against Server-Side Request Forgery
where a malicious provider URL could be used to probe internal networks.
"""
from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Private / special-use IPv4 ranges
_LOOPBACK_V4 = ipaddress.IPv4Network("127.0.0.0/8")
_PRIVATE_V4 = [
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
]
_LINK_LOCAL_V4 = ipaddress.IPv4Network("169.254.0.0/16")
_METADATA_IPS = {"169.254.169.254"}

# Private IPv6 ranges
_LOOPBACK_V6 = ipaddress.IPv6Network("::1/128")
_LINK_LOCAL_V6 = ipaddress.IPv6Network("fe80::/10")
_UNIQUE_LOCAL_V6 = ipaddress.IPv6Network("fc00::/7")

# Allowed schemes
_ALLOWED_SCHEMES = frozenset({"https", "http"})

# Default timeouts
_CONNECT_TIMEOUT_S = 5
_READ_TIMEOUT_S = 30

# Max response size for discovery endpoints
_MAX_RESPONSE_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB

# Max redirect hops
_MAX_REDIRECT_HOPS = 3

# Default allowed ports
_DEFAULT_ALLOWED_PORTS = frozenset({443, 80})
_LOCAL_MODE_EXTRA_PORTS = {11434, 8000, 8080, 3000, 5000}


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

@dataclass
class UrlSafetyResult:
    """Outcome of a URL safety check."""
    allowed: bool
    reason: str = ""
    resolved_ips: list[str] = field(default_factory=list)
    redirect_chain: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Safety checker
# ---------------------------------------------------------------------------

def _is_private_ip(ip_str: str) -> tuple[bool, str]:
    """Check if an IP address resolves to a private/special-use range.

    Returns (is_private, category).
    """
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True, "unparseable"

    # IPv4 checks
    if isinstance(addr, ipaddress.IPv4Address):
        if addr == _METADATA_IPS or str(addr) in _METADATA_IPS:
            return True, "metadata"
        if addr in _LOOPBACK_V4:
            return True, "loopback"
        for net in _PRIVATE_V4:
            if addr in net:
                return True, "private"
        if addr in _LINK_LOCAL_V4:
            return True, "link_local"
        return False, "public"

    # IPv6 checks
    if addr in _LOOPBACK_V6:
        return True, "loopback_v6"
    if addr in _LINK_LOCAL_V6:
        return True, "link_local_v6"
    if addr in _UNIQUE_LOCAL_V6:
        return True, "unique_local_v6"
    return False, "public"


def check_url_safety(
    url: str,
    *,
    local_mode: bool = False,
    allowed_ports: frozenset[int] | None = None,
) -> UrlSafetyResult:
    """Perform a static URL safety check (scheme, hostname pattern, port).

    Does NOT perform DNS resolution — use `check_url_safety_with_resolve` for
    the full SSRF check that resolves hostnames to IP addresses.
    """
    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception:
        return UrlSafetyResult(allowed=False, reason="unparseable URL")

    # Scheme check
    scheme = parsed.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        return UrlSafetyResult(allowed=False, reason=f"disallowed scheme: {scheme}")

    # HTTP only in local_mode
    if scheme == "http" and not local_mode:
        return UrlSafetyResult(
            allowed=False,
            reason="HTTP only allowed in local_mode",
        )

    # Hostname must be present
    hostname = parsed.hostname
    if not hostname:
        return UrlSafetyResult(allowed=False, reason="missing hostname")

    # Port check
    port = parsed.port
    effective_allowed = set(_DEFAULT_ALLOWED_PORTS)
    if local_mode:
        effective_allowed.update(_LOCAL_MODE_EXTRA_PORTS)

    if port is not None and port not in effective_allowed:
        return UrlSafetyResult(
            allowed=False,
            reason=f"disallowed port {port} (allowed: {sorted(effective_allowed)})",
        )

    # Static hostname check: block raw IP literals that are private
    # (DNS resolution is done later in check_url_safety_with_resolve)
    try:
        ipaddress.ip_address(hostname)
        is_ip_literal = True
    except ValueError:
        is_ip_literal = False

    if is_ip_literal:
        is_private, category = _is_private_ip(hostname)
        if is_private:
            if hostname in ("127.0.0.1", "::1") and local_mode:
                # localhost allowed in local_mode
                pass
            else:
                return UrlSafetyResult(
                    allowed=False,
                    reason=f"IP literal resolves to {category} address: {hostname}",
                )

    # localhost hostname check (not IP literal)
    if not local_mode and hostname in ("localhost", "localhost.localdomain"):
        return UrlSafetyResult(
            allowed=False,
            reason="localhost only allowed in local_mode",
        )

    return UrlSafetyResult(allowed=True, reason="static URL safety check passed")


async def check_url_safety_with_resolve(
    url: str,
    *,
    local_mode: bool = False,
    allowed_ports: frozenset[int] | None = None,
) -> UrlSafetyResult:
    """Full SSRF safety check: static URL check + DNS resolution + redirect check.

    1. Static URL scheme/hostname/port validation.
    2. DNS resolution: resolve hostname → IP, check for private/special-use.
    3. HTTP request (HEAD) to detect redirects; re-check each hop's target IP.
    """
    # Step 1: static check
    static = check_url_safety(url, local_mode=local_mode, allowed_ports=allowed_ports)
    if not static.allowed:
        return static

    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return UrlSafetyResult(allowed=False, reason="missing hostname (resolve)")

    # Step 2: DNS resolution
    resolved_ips: list[str] = []
    try:
        import socket
        addrs = socket.getaddrinfo(hostname, parsed.port or 443,
                                   socket.AF_UNSPEC, socket.SOCK_STREAM)
        for addr_info in addrs:
            ip_str = addr_info[4][0]
            if ip_str not in resolved_ips:
                resolved_ips.append(ip_str)
    except socket.gaierror as exc:
        return UrlSafetyResult(
            allowed=False,
            reason=f"DNS resolution failed for {hostname}: {exc}",
        )

    if not resolved_ips:
        return UrlSafetyResult(allowed=False, reason=f"DNS resolved 0 IPs for {hostname}")

    for ip_str in resolved_ips:
        is_private, category = _is_private_ip(ip_str)
        if is_private:
            # In local_mode, allow loopback only
            if local_mode and category == "loopback":
                continue
            return UrlSafetyResult(
                allowed=False,
                reason=f"DNS resolves {hostname} → {ip_str} ({category}); rejected",
                resolved_ips=resolved_ips,
            )

    # Step 3: validate redirect chain (limited hops)
    redirect_chain: list[str] = []
    current_url = url

    for _ in range(_MAX_REDIRECT_HOPS + 1):
        redirect_chain.append(current_url)

        try:
            async with httpx.AsyncClient(
                follow_redirects=False,
                timeout=httpx.Timeout(connect=_CONNECT_TIMEOUT_S, read=_READ_TIMEOUT_S),
                max_redirects=0,
            ) as client:
                # HEAD first (cheap), fall back to GET if HEAD not allowed
                for method in ("HEAD", "GET"):
                    try:
                        resp = await client.request(method, current_url)
                        break
                    except httpx.HTTPError:
                        continue

            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("location", "")
                if not location:
                    return UrlSafetyResult(
                        allowed=False,
                        reason="redirect with no Location header",
                        redirect_chain=redirect_chain,
                        resolved_ips=resolved_ips,
                    )

                # Resolve relative URLs
                from urllib.parse import urljoin
                next_url = urljoin(current_url, location)

                # Re-check the redirect target
                redirect_check = check_url_safety(
                    next_url, local_mode=local_mode, allowed_ports=allowed_ports
                )
                if not redirect_check.allowed:
                    return UrlSafetyResult(
                        allowed=False,
                        reason=f"redirect target rejected: {redirect_check.reason}",
                        redirect_chain=redirect_chain,
                        resolved_ips=resolved_ips,
                    )

                # DNS check on redirect target
                rp = urlparse(next_url)
                if rp.hostname:
                    try:
                        r_addrs = socket.getaddrinfo(rp.hostname, rp.port or 443,
                                                     socket.AF_UNSPEC, socket.SOCK_STREAM)
                        for rai in r_addrs:
                            rip = rai[4][0]
                            is_p, cat = _is_private_ip(rip)
                            if is_p:
                                return UrlSafetyResult(
                                    allowed=False,
                                    reason=f"redirect {current_url} → {next_url} resolves to {rip} ({cat})",
                                    redirect_chain=redirect_chain,
                                    resolved_ips=resolved_ips,
                                )
                    except socket.gaierror as exc:
                        return UrlSafetyResult(
                            allowed=False,
                            reason=f"redirect target DNS failed: {exc}",
                            redirect_chain=redirect_chain,
                            resolved_ips=resolved_ips,
                        )

                current_url = next_url
            else:
                # Not a redirect — chain ends here
                return UrlSafetyResult(
                    allowed=True,
                    reason="URL safety + DNS + redirect chain check passed",
                    resolved_ips=resolved_ips,
                    redirect_chain=redirect_chain,
                )
        except httpx.HTTPError as exc:
            # Network error on the redirect hop — not a safety issue, per se
            logger.warning("URL safety redirect check failed on hop %s: %s",
                           current_url, exc)
            return UrlSafetyResult(
                allowed=True,
                reason=f"redirect check encountered network error (not a safety block): {exc}",
                resolved_ips=resolved_ips,
                redirect_chain=redirect_chain,
            )

    # Exceeded max redirect hops
    return UrlSafetyResult(
        allowed=False,
        reason=f"exceeded max redirect hops ({_MAX_REDIRECT_HOPS})",
        redirect_chain=redirect_chain,
        resolved_ips=resolved_ips,
    )


def redact_error_body(body: str, max_len: int = 200) -> str:
    """Truncate and redact potentially sensitive headers/keys from error bodies.

    Removes patterns like 'Authorization: Bearer sk-...', 'x-api-key: ...', etc.
    """
    import re

    # Truncate first
    if len(body) > max_len:
        body = body[:max_len] + "..."

    # Redact common key-bearing headers in response bodies
    patterns = [
        (r'(?i)Authorization:\s*Bearer\s+\S+', 'Authorization: Bearer [REDACTED]'),
        (r'(?i)Authorization:\s*Basic\s+\S+', 'Authorization: Basic [REDACTED]'),
        (r'(?i)x-api-key:\s*\S+', 'x-api-key: [REDACTED]'),
        (r'(?i)api[_-]?key["\s:=]+\S+', 'api_key: [REDACTED]'),
        (r'sk-[a-zA-Z0-9]{20,}', 'sk-[REDACTED]'),
    ]
    for pat, repl in patterns:
        body = re.sub(pat, repl, body)

    return body


# ---------------------------------------------------------------------------
# Convenience: validate a provider URL end-to-end
# ---------------------------------------------------------------------------

async def validate_provider_url(
    base_url: str,
    *,
    local_mode: bool = False,
) -> UrlSafetyResult:
    """Full end-to-end provider URL validation (SSRF gate).

    Used by the Provider Wizard step 1 (validate).
    """
    return await check_url_safety_with_resolve(base_url, local_mode=local_mode)
