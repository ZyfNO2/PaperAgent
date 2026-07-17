from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_fake_llm__explicit_key__returns_validated_model_and_history() -> None:
    from paperagent.providers.base import FixtureKey
    from paperagent.providers.fake_llm import FakeLLMProvider
    from paperagent.schemas import Message, ResearchPlan

    key = FixtureKey(task="planning", scenario="happy_path", call_index=0)
    raw = json.dumps(
        {
            "schema_version": "0.1",
            "status": "ready",
            "problem_statement": "p",
            "scope": "s",
            "research_questions": ["q"],
            "evidence_gaps": [
                {"gap_id": "g1", "description": "d", "required": True, "minimum_accepted_items": 1}
            ],
            "search_queries": [
                {"query_id": "q1", "gap_id": "g1", "query": "query", "source_types": ["web"]}
            ],
            "success_criteria": ["c"],
            "risks": [],
            "clarification_question": None,
            "block_reason": None,
        }
    )
    provider = FakeLLMProvider(fixtures={key: raw})
    result = await provider.generate_structured(
        task="planning",
        scenario="happy_path",
        call_index=0,
        fixture_version="v0.1",
        schema=ResearchPlan,
        messages=[Message(role="user", content="ignored by fixture selection")],
    )
    assert result.status == "ready"
    assert provider.calls[0].key == key
    assert provider.calls[0].message_count == 1


@pytest.mark.asyncio
async def test_fake_llm__malformed_json__raises_typed_provider_error() -> None:
    from paperagent.errors import ProviderError
    from paperagent.providers.base import FixtureKey
    from paperagent.providers.fake_llm import FakeLLMProvider
    from paperagent.schemas import ResearchPlan

    key = FixtureKey(task="planning", scenario="bad", call_index=0)
    provider = FakeLLMProvider(fixtures={key: '{"status":'})
    with pytest.raises(ProviderError) as exc_info:
        await provider.generate_structured(
            task="planning",
            scenario="bad",
            call_index=0,
            fixture_version="v0.1",
            schema=ResearchPlan,
            messages=[],
        )
    assert exc_info.value.code == "LLM_RESPONSE_JSON_INVALID"


@pytest.mark.asyncio
async def test_fake_search__explicit_key__returns_stable_candidates() -> None:
    from paperagent.providers.fake_search import FakeSearchProvider, SearchFixtureKey
    from paperagent.schemas import SearchCandidate, SearchQuery

    query = SearchQuery(query_id="q1", gap_id="g1", query="citation support", source_types=["web"])
    key = SearchFixtureKey(scenario="happy_path", query_id="q1", call_index=0)
    candidate = SearchCandidate(
        candidate_id="c1",
        query_id="q1",
        gap_id="g1",
        source_type="web",
        title="Synthetic note",
        locator="fixture://candidate/c1",
        snippet="summary",
    )
    provider = FakeSearchProvider(fixtures={key: [candidate]})
    first = await provider.search(
        query=query,
        scenario="happy_path",
        call_index=0,
        fixture_version="v0.1",
        limit=5,
    )
    second = await provider.search(
        query=query,
        scenario="happy_path",
        call_index=0,
        fixture_version="v0.1",
        limit=5,
    )
    assert first == second == [candidate]
    assert len(provider.calls) == 2
