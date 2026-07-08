"""Re2.2-fix validation — 3 cases."""
import os
import sys
import json
import re
os.environ['FAST_JSON_PRIMARY'] = 'deepseek'
sys.path.insert(0, r'G:\PaperAgent')
from pathlib import Path
from apps.api.app.services.agents.graph import research_graph as rg

V_CASES = [
    ("V-SLAM", "基于深度学习的视觉SLAM语义地图的研究"),
    ("V-CRACK", "基于深度学习的混凝土桥梁裂缝检测研究"),
    ("V-MED", "基于大语言模型的医学问答可信度评估方法研究"),
]

TABLE_FIGURE_PATTERNS = [
    re.compile(r"^Table\s*\d", re.IGNORECASE),
    re.compile(r"^Figure\s*\d", re.IGNORECASE),
    re.compile(r"^Fig\.?\s*\d", re.IGNORECASE),
    re.compile(r"^Tab\.?\s*\d", re.IGNORECASE),
]

for vid, topic in V_CASES:
    print(f'\n=== {vid}: {topic} ===')
    state_in = {
        'case_id': vid, 'topic': topic,
        'user_constraints': {'topic_zh': topic},
        'trace_events': [], 'provider_profile': 'fast_json', 'errors': [],
    }
    g = rg.build_graph()
    out = g.invoke(state_in, config={'configurable': {'thread_id': vid}})

    verified = out.get('verified_papers') or []
    weak = out.get('weak_papers') or []
    datasets = out.get('dataset_candidates') or []
    repos = out.get('repo_candidates') or []

    # Check 1: repo URL not api.github.com
    bad_urls = [r for r in repos if 'api.github.com' in (r.get('url') or '')]
    print(f'  repos: {len(repos)} (bad_urls: {len(bad_urls)})')
    for r in repos[:3]:
        print(f'    url={r.get("url","")[:60]}, source={r.get("source","")}')

    # Check 2: no duplicates
    titles = [p.get('title', '').lower().strip() for p in verified]
    dupes = set(t for t in titles if titles.count(t) > 1)
    print(f'  duplicates: {dupes if dupes else "none"}')

    # Check 3: no Table/Figure titles
    polluted = [p.get('title', '')[:40] for p in verified + weak
                if any(pat.search(p.get('title', '')) for pat in TABLE_FIGURE_PATTERNS)]
    print(f'  table/figure pollution: {len(polluted)}')

    # Check 4: datasets
    print(f'  datasets: {len(datasets)}')
    for d in datasets[:3]:
        print(f'    name={d.get("name","")[:40]}, source={d.get("source","")}')

    # Check 5: evidence_graph github nodes type=repo
    eg = out.get('evidence_graph') or {}
    nodes = eg.get('nodes', [])
    github_nodes = [n for n in nodes if n.get('type') == 'repo' and 'github' in (n.get('title', '').lower())]
    print(f'  evidence_graph: {len(nodes)} nodes, github-as-repo: {len(github_nodes)}')

    # Feasibility + review
    feas = out.get('feasibility_report') or {}
    review = out.get('review_report') or {}
    inn = out.get('innovation_points') or []
    print(f'  feasibility: {feas.get("verdict")}({feas.get("score")})')
    print(f'  review: {review.get("overall_verdict")}')
    print(f'  innovation: {len(inn)}')

    # Save
    out_dir = Path(f'tmp_re22_eval/fix2_{vid}')
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'state.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding='utf-8')

print('\n=== Validation Summary ===')
print('Checks: repo URL, duplicates, table/figure, datasets, graph type')
