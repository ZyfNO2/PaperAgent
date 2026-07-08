"""Re2.3 validation — 3 cases."""
import os
import sys
import json
import time
os.environ['FAST_JSON_PRIMARY'] = 'deepseek'
sys.path.insert(0, r'G:\PaperAgent')
from pathlib import Path
from apps.api.app.services.agents.graph import research_graph as rg

V_CASES = [
    ("V-SLAM", "基于深度学习的视觉SLAM语义地图的研究"),
    ("V-CRACK", "基于深度学习的混凝土桥梁裂缝检测研究"),
    ("V-MED", "基于大语言模型的医学问答可信度评估方法研究"),
]

# Re2.2-fix baseline for comparison
RE22_BASELINE = {
    "V-SLAM": {"candidates": 2, "verified": 0, "github_repos": 0},
    "V-CRACK": {"candidates": 2, "verified": 0, "github_repos": 0},
    "V-MED": {"candidates": 8, "verified": 9, "github_repos": 0},
}

results = []
for vid, topic in V_CASES:
    t0 = time.time()
    print(f'\n=== {vid}: {topic} ===')
    state_in = {
        'case_id': f're23-{vid}', 'topic': topic,
        'user_constraints': {'topic_zh': topic},
        'trace_events': [], 'provider_profile': 'fast_json', 'errors': [],
    }
    g = rg.build_graph()
    out = g.invoke(state_in, config={'configurable': {'thread_id': f're23-{vid}'}, 'recursion_limit': 100})
    elapsed = round(time.time() - t0, 2)

    raw = out.get('raw_results', {}) or {}
    verified = out.get('verified_papers') or []
    weak = out.get('weak_papers') or []
    candidates = out.get('paper_candidates') or []
    repos = out.get('repo_candidates') or []
    datasets = out.get('dataset_candidates') or []

    # Check raw results per tool
    raw_counts = {tool: len(hits) if isinstance(hits, list) else 0 for tool, hits in raw.items()} if isinstance(raw, dict) else {}

    # Check github hits for SLAM repos
    github_hits = raw.get('github', []) if isinstance(raw, dict) else []
    slam_repos = [h for h in github_hits if isinstance(h, dict) and 'slam' in (h.get('full_name', '') + h.get('description', '')).lower()]

    # Check crossref hit count (should be > 8 if multi-query worked)
    crossref_count = raw_counts.get('crossref', 0)
    github_count = raw_counts.get('github', 0)

    baseline = RE22_BASELINE.get(vid, {})
    improved = len(candidates) >= int(baseline.get('candidates', 0) * 1.3)

    print(f'  elapsed: {elapsed}s')
    print(f'  raw_counts: {raw_counts}')
    print(f'  candidates: {len(candidates)} (baseline: {baseline.get("candidates",0)}, 1.3x: {int(baseline.get("candidates",0)*1.3)}, improved: {improved})')
    print(f'  verified: {len(verified)}, weak: {len(weak)}')
    print(f'  repos: {len(repos)}, datasets: {len(datasets)}')
    print(f'  crossref_count: {crossref_count} (>8 means multi-query worked: {crossref_count > 8})')
    print(f'  github_count: {github_count} (>8 means multi-query worked: {github_count > 8})')
    if slam_repos:
        print(f'  SLAM repos found: {[h.get("full_name","")[:40] for h in slam_repos[:3]]}')
    else:
        print('  SLAM repos: none')
    if github_hits:
        for h in github_hits[:3]:
            if isinstance(h, dict):
                print(f'    github: {h.get("full_name","")[:40]}')

    feas = out.get('feasibility_report') or {}
    review = out.get('review_report') or {}
    inn = out.get('innovation_points') or []
    print(f'  feasibility: {feas.get("verdict")}({feas.get("score")})')
    print(f'  review: {review.get("overall_verdict")}')
    print(f'  innovation: {len(inn)}')
    print(f'  has_final: {bool(out.get("final_recommendation"))}')

    results.append({
        'vid': vid,
        'elapsed': elapsed,
        'n_candidates': len(candidates),
        'n_verified': len(verified),
        'crossref_count': crossref_count,
        'github_count': github_count,
        'has_slam_repo': bool(slam_repos),
        'improved': improved,
        'has_final': bool(out.get('final_recommendation')),
    })

    # Save state
    out_dir = Path(f'tmp_re23_eval/{vid}')
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'state.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding='utf-8')

print('\n=== Validation Summary ===')
n_improved = sum(1 for r in results if r['improved'])
n_crossref_multi = sum(1 for r in results if r['crossref_count'] > 8)
n_github_multi = sum(1 for r in results if r['github_count'] > 8)
n_final = sum(1 for r in results if r['has_final'])
print(f'candidates improved (≥1.3x): {n_improved}/3')
print(f'crossref multi-query (>8): {n_crossref_multi}/3')
print(f'github multi-query (>8): {n_github_multi}/3')
print(f'graph completed: {n_final}/3')
slam = [r for r in results if r['vid'] == 'V-SLAM'][0]
print(f'V-SLAM has SLAM repo: {slam["has_slam_repo"]}')
