import asyncio, json, sys, os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, r"G:\PaperAgent\apps\api")

from app.services.agents.research_agent import run_research_agent_re02, reset_counter

reset_counter()
topic = '基于Unet的钢材裂缝分割'
res = asyncio.run(run_research_agent_re02(topic, auto_low_bar=True))
d = res.to_dict()

out_path = r'G:\PaperAgent\tmp_s66v_traces\re03_caseB_llm_online.json'
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=1)

print('=== parsed_topic ===')
print('  domain_route:', d['parsed_topic'].get('domain_route'))
print('  query_atoms_en:', d['parsed_topic'].get('query_atoms_en'))
print()
print('=== round_delta (NEW in Re03) ===')
print(json.dumps(d.get('round_delta', {}), ensure_ascii=False, indent=2)[:1500])
print()
print('=== SourceLedger stats ===')
print(json.dumps(d['source_ledger']['stats'], ensure_ascii=False))
ce = [r for r in d['source_ledger']['rows'] if r.get('adapter') == 'openalex_citation']
print(f'  openalex_citation ledger rows: {len(ce)}')
print(f'  per-seed statuses: {[r.get("status") for r in ce]}')
print()
print('=== citation_expand_stats (Re03) ===')
print(json.dumps(d.get('citation_expand_stats', {}), ensure_ascii=False, indent=2))
print()
print('=== CandidatePool ===')
print(f'  total: {len(d["candidate_pool"])}')
from collections import Counter
print(f'  types: {dict(Counter(c.get("evidence_type") for c in d["candidate_pool"]))}')
print(f'  role_hints (first 5): {[c.get("role_hints") for c in d["candidate_pool"][:5]]}')
print()
print('=== EvidenceReview ===')
print(' ', dict(Counter(r['status'] for r in d['evidence_review'])))
blocked = sum(1 for r in d['evidence_review'] if 'llm_blocker' in (r.get('reason') or ''))
print(f'  blocked by llm_blocker: {blocked}')
print()
print('=== Low-bar ===')
lb = d['low_bar_verdict']
print(f'  verdict: {lb["review_verdict"]}')
print(f'  can_continue: {lb["can_continue_to_opening_report"]}')
print(f'  summary: {lb["summary"]}')
weak = lb.get('weak_points') or []
print(f'  weak_points: {weak[:5]}')
print()
print('=== paper_groups ===')
for cat, rows in d['synthesis']['paper_groups'].items():
    print(f'  [{cat}] n={len(rows)}')
    for r in rows[:5]:
        print(f'    - {r.get("title")[:90]}')
print()
print(f'=== llm_calls: {d["llm_calls"]} / {d["llm_budget"]} ===')

size = os.path.getsize(out_path)
print()
print(f'=== dump file size: {size} bytes ({size/1024:.1f} KB) ===')
print(f'=== dump path: {out_path} ===')
