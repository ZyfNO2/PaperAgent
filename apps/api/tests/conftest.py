"""Pytest config for the S66v agent suite.

Session 66+ test files (``test_session66_*`` and earlier) import legcy
backend modules that have been archived to ``Legcy/services_legacy/``. Each such test file
now starts with ``pytest.importorskip("app.services.<legcy_module>")``
OR a top-level ``import pytest; pytest.skip(...)``; here we expose the
needed ``sys.path`` and an opt-in env var for running legcy tests.

The S66v agent tests live in ``test_s66v_agent.py`` and require no
opt-in. Running the full suite (including legcy tests) needs:

    PAPERAGENT_LEGACY_TEST=1 uv run pytest
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Make sure the agent package is importable in tests too.
sys.path.insert(0, str(ROOT / "apps" / "api"))


def pytest_collection_modifyitems(config, items):
    """Skip legcy test files unless PAPERAGENT_LEGACY_TEST=1."""
    import os

    if os.environ.get("PAPERAGENT_LEGACY_TEST") == "1":
        return
    skip_legcy = pytest.mark.skip(reason="legcy backend; set PAPERAGENT_LEGACY_TEST=1 to enable")
    for item in items:
        # any test in the old legcy-test directory or with names matching
        # ``test_session*_*`` are legcy tests.
        path = str(item.fspath)
        if "/Legcy/" in path or "/tests/Legcy/" in path:
            item.add_marker(skip_legcy)
            continue
        if item.name.startswith("test_session") and "s66v" not in item.name:
            item.add_marker(skip_legcy)
            continue
