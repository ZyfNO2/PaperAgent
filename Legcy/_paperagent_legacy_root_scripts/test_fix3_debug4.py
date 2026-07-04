import asyncio
import json
from app.services.agents.research_agent import parse_topic
from app.services.agents.domain_scout_agent import run_domain_scout
from app.services.agents.search_reflection_helpers import build_round_plan

async def test():
    # Only run Case 3 - no Case 1
    title = '基于大语言模型的医学问答答案可信度评估'
    parsed = parse_topic(title)
    topic_atoms = parsed.get("topic_atoms") or {}
    scout = await run_domain_scout(title, topic_atoms, llm_client=None)
    domain_kws = scout.get("domain_keywords") or {}
    must_search = scout.get("must_search") or []
    plan = build_round_plan(domain_kws, {}, must_search)
    queries = [p.get("query") for p in plan]
    print("=== TYPICAL-03 only (no Case 1) ===")
    print("queries:", queries)
    print("object:", domain_kws.get("object"))
    print("task:", domain_kws.get("task"))
    
    for q in queries:
        if 'steel' in q.lower() or 'surface' in q.lower():
            print(f"!!! CONTAMINATION: {q}")

asyncio.run(test())