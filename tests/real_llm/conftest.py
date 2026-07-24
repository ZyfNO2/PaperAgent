"""Shared fixtures for real-LLM tests.

These tests are skipped unless ``PAPERAGENT_RUN_REAL_LLM=1`` and a
``PAPERAGENT_OPENAI_API_KEY`` are set. They cost real API tokens and reach the
network, so they are intentionally opt-in and excluded from the default run.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from paperagent.providers.openai_llm import OpenAILLMProvider
from paperagent.testing import FixedClock, SequenceIdFactory

RUN_REAL_LLM = os.getenv("PAPERAGENT_RUN_REAL_LLM") == "1"
OPENAI_API_KEY = os.getenv("PAPERAGENT_OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("PAPERAGENT_OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("PAPERAGENT_OPENAI_MODEL", "gpt-4o-mini")

# Apply to every test collected under this directory. Tests additionally skip
# themselves via ``skipif_no_real_llm`` until the env gates are satisfied.
pytestmark = pytest.mark.llm

skipif_no_real_llm = pytest.mark.skipif(
    not RUN_REAL_LLM or not OPENAI_API_KEY,
    reason="set PAPERAGENT_RUN_REAL_LLM=1 and PAPERAGENT_OPENAI_API_KEY",
)


@pytest.fixture
def real_llm_provider() -> OpenAILLMProvider:
    """Return a configured OpenAILLMProvider, skipping when no key is present."""
    if not OPENAI_API_KEY:
        pytest.skip("PAPERAGENT_OPENAI_API_KEY is not set")
    return OpenAILLMProvider(
        api_key=OPENAI_API_KEY,
        model=OPENAI_MODEL,
        base_url=OPENAI_BASE_URL,
        timeout_seconds=90.0,
    )


@pytest.fixture
def fixed_clock() -> FixedClock:
    return FixedClock(datetime(2026, 1, 1, tzinfo=UTC))


@pytest.fixture
def id_factory() -> SequenceIdFactory:
    return SequenceIdFactory("real-llm")
