import asyncio
import json
from app.services.agents.research_agent import parse_topic
from app.services.agents.domain_scout_agent import run_domain_scout

async def test():
    topic = '基于开源SLAM框架的室内导航系统'
    
    # Step 1: parse_topic
    parsed = parse_topic(topic)
    topic_atoms = parsed.get("topic_atoms") or {}
    print("=== parse_topic ===")
    print("method:", [a.get("en") for a in topic_atoms.get("method", [])])
    print("object:", [a.get("en") for a in topic_atoms.get("object", [])])
    print("task:", [a.get("en") for a in topic_atoms.get("task", [])])
    
    # Step 2: DomainScout offline
    scout = await run_domain_scout(topic, topic_atoms, llm_client=None)
    print("\n=== DomainScout offline ===")
    print("must_search:", scout.get("must_search"))
    print("domain_kws en:", scout.get("domain_keywords", {}).get("en", [])[:5])
    print("search_notes:", scout.get("search_notes"))

asyncio.run(test())
