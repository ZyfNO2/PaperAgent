import asyncio
import json
from app.services.agents.research_agent import parse_topic
from app.services.agents.domain_scout_agent import run_domain_scout
from app.services.agents.search_reflection_helpers import build_round_plan

async def run_case(title, cid):
    parsed = parse_topic(title)
    topic_atoms = parsed.get("topic_atoms") or {}
    scout = await run_domain_scout(title, topic_atoms, llm_client=None)
    domain_kws = scout.get("domain_keywords") or {}
    must_search = scout.get("must_search") or []
    plan = build_round_plan(domain_kws, {}, must_search)
    queries = [p.get("query") for p in plan]
    return domain_kws, queries

async def test():
    # Case 1: steel surface
    print("=== Case 1: TYPICAL-01 ===")
    dk1, q1 = await run_case('基于YOLOv5的钢铁表面缺陷检测研究', 'TYPICAL-01')
    print("queries:", q1)
    
    # Case 3: medical QA
    print("\n=== Case 3: TYPICAL-03 ===")
    dk3, q3 = await run_case('基于大语言模型的医学问答答案可信度评估', 'TYPICAL-03')
    print("queries:", q3)
    
    # Check if steel surface appears in Case 3
    for q in q3:
        if 'steel' in q.lower() or 'surface' in q.lower():
            print(f"\n!!! CONTAMINATION FOUND: {q}")
    
    # Check if domain_kws leaked
    print("\n=== Check domain_kws for Case 3 ===")
    print("object:", dk3.get("object"))
    print("task:", dk3.get("task"))

asyncio.run(test())