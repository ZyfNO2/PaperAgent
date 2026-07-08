"""Check github repos in FIX-048 state."""
import json
s = json.loads(open('tmp_re22_eval/fix_test_FIX-048/state.json', encoding='utf-8').read())
repos = s.get('repo_candidates') or []
print(f"n_repos: {len(repos)}")
for r in repos:
    print(f"  source={r.get('source','')}, url={r.get('url','')[:60]}, mentioned={r.get('mentioned_repo','')[:60]}")

# Check verified_papers sources
verified = s.get('verified_papers') or []
print("\nverified_papers sources:")
for p in verified:
    print(f"  [{p.get('source','')}] {p.get('title','')[:60]}")

# Check paper_candidates for github source
cands = s.get('paper_candidates') or []
github_cands = [c for c in cands if (c.get('source') or '').lower() == 'github']
print(f"\ngithub candidates: {len(github_cands)}")
for c in github_cands[:5]:
    print(f"  title={c.get('title','')[:60]}, url={c.get('url','')[:60]}")

# Check raw_results for github
raw = s.get('raw_results', {})
if isinstance(raw, dict):
    gh = raw.get('github', [])
    print(f"\nraw github hits: {len(gh)}")
    for h in gh[:5]:
        if isinstance(h, dict):
            print(f"  title={h.get('title','')[:40]}, url={h.get('url','') or h.get('html_url','')[:60]}")
