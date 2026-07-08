"""Deep check: find ALL irrelevant verified papers in ENG-THESIS-022 and ENG-THESIS-092."""
import json

for cid in ['ENG-THESIS-022', 'ENG-THESIS-092', 'ENG-THESIS-048']:
    s = json.loads(open(f'tmp_re22_eval/all_100/{cid}/state.json', encoding='utf-8').read())
    print(f"\n=== {cid} ===")
    print(f"topic: {s.get('topic', '')[:60]}")
    print(f"n_verified: {len(s.get('verified_papers', []))}")
    print(f"n_weak: {len(s.get('weak_papers', []))}")
    print(f"n_candidates: {len(s.get('paper_candidates', []))}")

    # Check raw_results
    raw = s.get('raw_results', {})
    if isinstance(raw, dict):
        for tool, hits in raw.items():
            if isinstance(hits, list):
                print(f"  raw[{tool}]: {len(hits)} hits")
                for h in hits[:3]:
                    title = h.get('title', '')[:60] if isinstance(h, dict) else str(h)[:60]
                    print(f"    - {title}")

    # Check search_plan queries
    plan = s.get('search_plan', {})
    queries = plan.get('queries', [])
    print(f"  search_plan queries ({len(queries)}):")
    for q in queries[:5]:
        print(f"    [{q.get('tool','')}] {q.get('query','')[:60]}")

    # List verified papers with source
    print("  verified_papers:")
    for p in s.get('verified_papers', [])[:10]:
        title = p.get('title', '')[:60]
        source = p.get('source', '')
        print(f"    [{source}] {title}")

    # Check dataset/repo
    print(f"  n_dataset: {len(s.get('dataset_candidates', []))}")
    print(f"  n_repo: {len(s.get('repo_candidates', []))}")

    # Check duplicates
    verified = s.get('verified_papers', [])
    titles = [p.get('title', '').lower().strip() for p in verified]
    seen = {}
    for i, t in enumerate(titles):
        if t in seen:
            print(f"  DUPLICATE: '{t[:50]}' at index {seen[t]} and {i}")
        else:
            seen[t] = i
