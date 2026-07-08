import asyncio
import json
from app.services.agents.research_agent import run_research_agent_re02, reset_counter

reset_counter()
topic = '基于三维成像的智能损伤检测'
res = asyncio.run(run_research_agent_re02(topic, auto_low_bar=True))
d = res.to_dict()

with open(r'G:\PaperAgent\tmp_s66v_traces\re02v2_caseA_llm_online.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=1)

print('=== parsed_topic ===')
print('  domain_route:', d['parsed_topic'].get('domain_route'))
print('  query_atoms_en:', d['parsed_topic'].get('query_atoms_en'))
print()
print('=== SourceLedger stats ===')
print(json.dumps(d['source_ledger']['stats'], ensure_ascii=False))
print('  total calls:', d['source_ledger']['n_calls'])
ce = [r for r in d['source_ledger']['rows'] if r.get('adapter') == 'openalex_citation']
print('  openalex_citation calls:', len(ce))
for r in ce:
    print(f'    - {r.get("status")} {r.get("result_count")} | {r.get("query")[:60]}')
print()
print('=== CandidatePool ===')
print(f'  total: {len(d["candidate_pool"])}')
from collections import Counter
print(f'  types: {dict(Counter(c.get("evidence_type") for c in d["candidate_pool"]))}')
print(f'  role_hint: {dict(Counter(c.get("role_hint") for c in d["candidate_pool"]))}')
print()
print('=== First 30 candidates (type, role_hint, sources) ===')
for c in d['candidate_pool'][:30]:
    print(f'  - [{(c.get("evidence_type") or "?"):8s}] {(c.get("role_hint") or "?"):32s}] {(c.get("title") or "")[:80]}')
print()
print('=== Citation-derived candidates (parallel_baseline_candidate) ===')
cited = [c for c in d['candidate_pool'] if c.get('role_hint') == 'parallel_baseline_candidate']
print(f'  count: {len(cited)}')
for c in cited[:20]:
    print(f'  - {c.get("title")[:90]}')
    print(f'      via_seed: {c.get("extra", {}).get("via_seed", "?")[:70]}')
print()
print('=== EvidenceReview ===')
print(' ', dict(Counter(r['status'] for r in d['evidence_review'])))
print()
print('=== Low-bar ===')
print('  verdict:', d['low_bar_verdict']['review_verdict'])
print('  can_continue:', d['low_bar_verdict']['can_continue_to_opening_report'])
print('  summary:', d['low_bar_verdict']['summary'])
print()
print('=== paper_groups (top 5 per group) ===')
for cat, rows in d['synthesis']['paper_groups'].items():
    print(f'  [{cat}] n={len(rows)}')
    for r in rows[:5]:
        print(f'    - {r.get("title")[:90]}')
print()
print('=== llm_calls ===')
print(f'  {d["llm_calls"]} / {d["llm_budget"]}')
