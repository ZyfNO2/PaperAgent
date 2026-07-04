import asyncio
import json
from app.services.agents.domain_scout_agent import run_domain_scout
from app.services.agents.search_reflection_helpers import build_round_plan, build_axis_bound_queries, _axis_query_bases
from app.services.agents.search_reflection_loop import _topic_atoms_to_domain_kws
from app.services.agents.research_agent import parse_topic

async def test():
    # Step 1: parse_topic
    title = '基于大语言模型的医学问答答案可信度评估'
    parsed = parse_topic(title)
    topic_atoms = parsed.get("topic_atoms") or {}
    print("=== parse_topic result ===")
    print("method:", [a.get("en") for a in topic_atoms.get("method", [])])
    print("object:", [a.get("en") for a in topic_atoms.get("object", [])])
    print("task:", [a.get("en") for a in topic_atoms.get("task", [])])
    
    # Step 2: DomainScout (offline)
    scout = await run_domain_scout(title, topic_atoms, llm_client=None)
    domain_kws = scout.get("domain_keywords") or {}
    must_search = scout.get("must_search") or []
    print("\n=== DomainScout result ===")
    print("must_search:", must_search)
    print("domain_kws en:", domain_kws.get("en"))
    print("domain_kws method:", domain_kws.get("method"))
    print("domain_kws object:", domain_kws.get("object"))
    print("domain_kws task:", domain_kws.get("task"))
    
    # Step 3: _topic_atoms_to_domain_kws
    axis_kws = _topic_atoms_to_domain_kws(topic_atoms)
    print("\n=== _topic_atoms_to_domain_kws ===")
    print("en:", axis_kws.get("en"))
    print("method:", axis_kws.get("method"))
    print("object:", axis_kws.get("object"))
    print("task:", axis_kws.get("task"))
    
    # Step 4: build_round_plan
    plan = build_round_plan(domain_kws, {}, must_search)
    print("\n=== build_round_plan ===")
    for p in plan:
        print(f"  query: {p.get('query')}")
        print(f"  tool: {p.get('tool')}")
        print(f"  why: {p.get('why')}")
        print()

asyncio.run(test())