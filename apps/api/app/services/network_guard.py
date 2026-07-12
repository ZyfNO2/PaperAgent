"""Global Network Policy Guard (Re8.0 P0-3).

When ``network_policy=offline`` (Offline Replay mode), the guard blocks ALL
outbound HTTP from retrieval adapters by raising ``NetworkPolicyViolation``
at adapter entry — before any ``httpx`` call is made.

Design notes:
  - Singleton via class variables — no module-level state mutation on import.
  - Opt-in: if ``configure()`` is never called, ``is_offline()`` returns
    ``False`` and everything works as before (backward compatible).
  - Per-invocation configuration: ``intake_node`` calls ``configure()`` with
    ``state['network_policy']`` at graph startup, so each run gets the right
    policy without global side effects leaking across runs.
  - Assertion-check style (not client wrapping): each adapter calls
    ``assert_online(name)`` at the start of its request method. Simpler and
    less invasive than monkey-patching ``httpx``.
"""

from __future__ import annotations


class NetworkPolicyViolation(RuntimeError):
    """Raised when an HTTP call is attempted in offline mode."""
    pass


class NetworkPolicyGuard:
    """Singleton guard that blocks HTTP calls when ``network_policy=offline``.

    Usage::

        # At graph startup (intake_node):
        NetworkPolicyGuard.configure(state.get("network_policy", "online"))

        # At each adapter entry:
        NetworkPolicyGuard.assert_online("arxiv")
    """

    _instance: "NetworkPolicyGuard | None" = None
    _offline: bool = False

    @classmethod
    def configure(cls, network_policy: str) -> None:
        """Call this at graph startup with ``state['network_policy']``.

        ``network_policy == "offline"`` enables the guard; any other value
        (including ``"online"``) disables it.
        """
        cls._instance = cls()
        cls._instance._offline = (network_policy == "offline")

    @classmethod
    def is_offline(cls) -> bool:
        """Whether the guard is currently blocking HTTP calls."""
        return cls._instance is not None and cls._instance._offline

    @classmethod
    def assert_online(cls, context: str = "") -> None:
        """Call before any HTTP request. Raises ``NetworkPolicyViolation`` if offline."""
        if cls.is_offline():
            raise NetworkPolicyViolation(
                f"HTTP call blocked in offline mode (context={context})"
            )

    @classmethod
    def _reset(cls) -> None:
        """Reset to default (unconfigured) state. Test helper only."""
        cls._instance = None
        cls._offline = False
