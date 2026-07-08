"""Re2.2 fix validation — run 2 cases and check fixes."""
import os
import sys
import json
os.environ['FAST_JSON_PRIMARY'] = 'deepseek'
sys.path.insert(0, r'G:\PaperAgent')
from pathlib import Path
from apps.api.app.services.agents.graph import research_graph as rg

cases = [
    ('FIX-048', '面向动态环境的视觉SLAM研究'),
    ('FIX-022', '基于深度学习的钢铁表面缺陷检测研究'),
]

for cid, topic in cases:
    print(f'\n=== {cid}: {topic} ===')
    state_in = {
        'case_id': cid, 'topic': topic,
        'user_constraints': {'topic_zh': topic},
        'trace_events': [], 'provider_profile': 'fast_json', 'errors': [],
    }
    g = rg.build_graph()
    out = g.invoke(state_in, config={'configurable': {'thread_id': cid}})

    verified = out.get('verified_papers') or []
    weak = out.get('weak_papers') or []
    datasets = out.get('dataset_candidates') or []
    repos = out.get('repo_candidates') or []
    feas = out.get('feasibility_report') or {}
    review = out.get('review_report') or {}
    inn = out.get('innovation_points') or []

    # Check duplicates
    titles = [p.get('title', '').lower().strip() for p in verified]
    dupes = [t for t in titles if titles.count(t) > 1]

    # Check github repos
    github_repos = [r for r in repos if r.get('source') == 'github_search']

    # Check crossref papers in verified
    crossref_verified = [p for p in verified if (p.get('source') or '').lower() == 'crossref']

    print(f'  verified: {len(verified)}, weak: {len(weak)}')
    print(f'  datasets: {len(datasets)}, repos: {len(repos)} (github: {len(github_repos)})')
    print(f'  feasibility: {feas.get("verdict")}({feas.get("score")})')
    print(f'  review: {review.get("overall_verdict")}')
    print(f'  innovation: {len(inn)}')
    print(f'  duplicates: {dupes if dupes else "none"}')
    print(f'  crossref in verified: {len(crossref_verified)}')
    if crossref_verified:
        for p in crossref_verified[:3]:
            print(f'    [{p.get("source","")}] {p.get("title","")[:60]}')
    if github_repos:
        for r in github_repos[:3]:
            print(f'    [github] {r.get("mentioned_repo","")[:60]}')

    # Save
    out_dir = Path(f'tmp_re22_eval/fix_test_{cid}')
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'state.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
