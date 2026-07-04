import asyncio
import json
from app.services.agents.search_reflection_loop import _topic_atoms_to_domain_kws
from app.services.agents.search_reflection_helpers import build_axis_bound_queries, _en_queries_only

# TYPICAL-02 topic atoms
topic_atoms = {
    "method": [{"en": "SLAM", "zh": "同时定位与建图"}],
    "object": [{"en": "indoor environment", "zh": "室内环境"}],
    "task": [{"en": "indoor navigation", "zh": "室内导航"}],
}

# Convert to domain_kws
domain_kws = _topic_atoms_to_domain_kws(topic_atoms)
print("=== domain_kws ===")
print("en:", domain_kws.get("en"))
print("method:", domain_kws.get("method"))
print("object:", domain_kws.get("object"))
print("task:", domain_kws.get("task"))

# Build axis-bound queries
for role in ["dataset", "repo", "baseline", "core_paper"]:
    queries = build_axis_bound_queries(domain_kws, role)
    print(f"\n{role} queries: {queries}")

# Test _en_queries_only with Chinese queries
chinese_queries = ["室内导航 dataset benchmark", "室内环境 object benchmark"]
print("\n=== _en_queries_only with Chinese queries ===")
result = _en_queries_only(chinese_queries, domain_kws)
print("result:", result)
