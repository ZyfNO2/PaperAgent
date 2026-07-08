"""Check why V-SLAM got 0 repos — look at raw_results and paper_candidates."""
import json

s = json.loads(open('tmp_re22_eval/fix2_V-SLAM/state.json', encoding='utf-8').read())
raw = s.get('raw_results', {})
if isinstance(raw, dict):
    for tool, hits in raw.items():
        if isinstance(hits, list):
            print(f"raw[{tool}]: {len(hits)} hits")
            for h in hits[:3]:
                if isinstance(h, dict):
                    title = h.get('title', '')[:40] or h.get('full_name', '')[:40] or '(empty)'
                    url = h.get('url', '') or h.get('html_url', '')[:60]
                    print(f"  title={title}, url={url[:60]}")

cands = s.get('paper_candidates', [])
print(f"\npaper_candidates: {len(cands)}")
github_cands = [c for c in cands if (c.get('source') or '').lower() == 'github']
print(f"github candidates: {len(github_cands)}")
for c in github_cands[:5]:
    print(f"  title={c.get('title','')[:40]}, url={c.get('url','')[:60]}")

verified = s.get('verified_papers', [])
print(f"\nverified_papers: {len(verified)}")
for p in verified[:5]:
    print(f"  [{p.get('source','')}] {p.get('title','')[:50]}")
