import asyncio, json
from app.services.agents.research_agent import run_research_agent_re02, reset_counter

reset_counter()
topic = '基于多时相遥感数据的作物早期识别'
res = asyncio.run(run_research_agent_re02(topic, auto_low_bar=True))
d = res.to_dict()

with open(r'G:/PaperAgent/tmp_s66v_traces/re02_caseD_llm_online.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=1)

print('=== parsed_topic ===')
print('  domain_route:', d['parsed_topic'].get('domain_route'))
print('  query_atoms_en:', d['parsed_topic'].get('query_atoms_en'))
print('  query_atoms_zh:', d['parsed_topic'].get('query_atoms_zh'))
print('  method_terms:', d['parsed_topic'].get('method_terms'))
print('  object_terms:', d['parsed_topic'].get('object_terms'))
print('  task_terms:', d['parsed_topic'].get('task_terms'))
print()
print('=== Plan rounds ===')
for r in d['plan']['rounds']:
    print(f'  Round {r["round"]} {r["name"]}:')
    for c in r['calls']:
        print(f'    - {c.get("tool")}: query={c.get("query")!r} role={c.get("target_role")}')
print()
print('=== SourceLedger stats ===')
print(json.dumps(d['source_ledger']['stats'], ensure_ascii=False))
print()
print('=== CandidatePool ===')
print(f'  total: {len(d["candidate_pool"])}')
from collections import Counter
print(f'  types: {dict(Counter(c.get("evidence_type") for c in d["candidate_pool"]))}')
print()
print('=== First 30 candidates ===')
for c in d['candidate_pool'][:30]:
    print(f'  - [{c.get("evidence_type") or "?":8s}] {(c.get("title") or "")[:90]} | {c.get("sources")}')
print()
print('=== EvidenceReview ===')
print(' ', dict(Counter(r['status'] for r in d['evidence_review'])))
print()
print('=== Low-bar ===')
print('  verdict:', d['low_bar_verdict']['review_verdict'])
print('  can_continue:', d['low_bar_verdict']['can_continue_to_opening_report'])
print('  summary:', d['low_bar_verdict']['summary'])
print()
print('=== direction_recommendation ===')
print(d['synthesis']['direction_recommendation'])
print()
print('=== baseline_options ===')
print(d['synthesis']['baseline_options'])
print()
print('=== paper_groups ===')
for cat, rows in d['synthesis']['paper_groups'].items():
    print(f'  [{cat}] n={len(rows)}')
    for r in rows[:5]:
        print(f'    - {r.get("title")[:90]}')
print()
print('=== raw_tool_results counts ===')
for k, v in d['raw_tool_results'].items():
    if isinstance(v, list):
        print(f'  {k}: {len(v)}')
print()
print('=== llm_calls ===')
print(f'  {d["llm_calls"]} / {d["llm_budget"]}')
print()
print('=== full dump saved to tmp_s66v_traces/re02_caseD_llm_online.json ===')