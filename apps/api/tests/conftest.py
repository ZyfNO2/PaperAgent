"""Shared pytest fixtures for end-to-end Phase 01 tests."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Project-local tmp dir so we don't fight Windows for AppData\Local\Temp
# if a previous pytest run crashed mid-test and left stale lock files.
PROJECT_TMP = Path(__file__).resolve().parents[3] / "tmp" / "pytest"
PROJECT_TMP.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def e2e_db_path() -> str:
    """Per-test SQLite path under <repo>/tmp/pytest/."""

    fd, path = tempfile.mkstemp(prefix="tp_e2e_", suffix=".db", dir=str(PROJECT_TMP))
    os.close(fd)
    os.environ["TOPICPILOT_SQLITE_PATH"] = path
    return path


@pytest_asyncio.fixture
async def app_with_db(e2e_db_path: str) -> AsyncIterator:
    """Build a fresh FastAPI app backed by an isolated SQLite DB.

    We re-import the db modules so ``engine`` / ``SessionLocal`` / ``Base``
    pick up the test-time ``TOPICPILOT_SQLITE_PATH`` env var.
    """

    # Force re-import of app modules so config + engine are bound to the
    # per-test SQLite path.
    import importlib

    import app.core.config as cfg_mod
    importlib.reload(cfg_mod)
    import app.db.database as db_mod
    importlib.reload(db_mod)
    import app.db.repository as repo_mod
    importlib.reload(repo_mod)
    import app.api.v1.schemas as schemas_mod
    importlib.reload(schemas_mod)
    import app.api.v1.projects as projects_mod
    importlib.reload(projects_mod)
    import app.main as main_mod
    importlib.reload(main_mod)

    # Build schema in the fresh DB.
    await db_mod.init_db()

    # Patch the get_session dependency to point at the reloaded SessionLocal.
    from fastapi import Depends
    from sqlalchemy.ext.asyncio import AsyncSession

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with db_mod.SessionLocal() as session:
            yield session

    main_mod.app.dependency_overrides[db_mod.get_session] = _override_get_session

    try:
        yield main_mod.app
    finally:
        main_mod.app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app_with_db) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def _cleanup_test_db_files():
    """Best-effort cleanup of test DBs after each test.

    The pytest tmp dir on Windows is occasionally locked and inaccessible,
    so we don't fail the test if cleanup raises.
    """

    yield
    for f in PROJECT_TMP.glob("tp_e2e_*.db"):
        try:
            f.unlink()
        except OSError:
            pass
