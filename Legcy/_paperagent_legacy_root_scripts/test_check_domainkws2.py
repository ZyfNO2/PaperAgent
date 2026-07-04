import asyncio
import json
from app.services.agents.domain_scout_agent import run_domain_scout

async def test():
    # TYPICAL-02: SLAM topic
    topic = '基于开源SLAM框架的室内导航系统'
    topic_atoms = {
        "method": [{"en": "SLAM", "zh": "同时定位与建图"}],
        "object": [{"en": "indoor environment", "zh": "室内环境"}],
        "task": [{"en": "indoor navigation", "zh": "室内导航"}],
    }
    # Test with LLM
    scout = await run_domain_scout(topic, topic_atoms, llm_client=None)
    print("=== TYPICAL-02 offline path ===")
    print("must_search:", scout.get("must_search"))
    print("domain_kws en:", scout.get("domain_keywords", {}).get("en", [])[:5])
    print("domain_kws method:", scout.get("domain_keywords", {}).get("method", [])[:5])
    print("domain_kws object:", scout.get("domain_keywords", {}).get("object", [])[:5])
    print("domain_kws task:", scout.get("domain_keywords", {}).get("task", [])[:5])
    print("search_notes:", scout.get("search_notes"))

asyncio.run(test())
