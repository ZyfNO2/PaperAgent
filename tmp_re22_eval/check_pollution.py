"""Check pollution patterns in Re2.2 results."""
import json
import re
from pathlib import Path
from collections import Counter

TABLE_FIGURE_PATTERNS = [
    re.compile(r"^Table\s*\d", re.IGNORECASE),
    re.compile(r"^Figure\s*\d", re.IGNORECASE),
    re.compile(r"^Fig\.?\s*\d", re.IGNORECASE),
    re.compile(r"^Tab\.?\s*\d", re.IGNORECASE),
]

# Check all 100 cases for Table/Figure pollution
polluted_cases = []
all_polluted_titles = []

eval_dir = Path('tmp_re22_eval/all_100')
for d in sorted(eval_dir.iterdir()):
    if not d.is_dir():
        continue
    sp = d / 'state.json'
    if not sp.exists():
        continue
    s = json.loads(sp.read_text(encoding='utf-8'))
    verified = s.get('verified_papers') or []
    weak = s.get('weak_papers') or []

    for p in verified + weak:
        title = p.get('title', '')
        for pat in TABLE_FIGURE_PATTERNS:
            if pat.search(title):
                polluted_cases.append((d.name, title[:80], p.get('source', '')))
                all_polluted_titles.append(title[:60])
                break

print(f"Cases with Table/Figure pollution: {len(set(c[0] for c in polluted_cases))}")
print(f"Total polluted entries: {len(polluted_cases)}")
print()
for cid, title, source in polluted_cases[:20]:
    print(f"  {cid}: [{source}] {title}")

# Also check ENG-THESIS-022 irrelevant papers
print("\n=== ENG-THESIS-022 verified_papers ===")
s022 = json.loads(open('tmp_re22_eval/all_100/ENG-THESIS-022/state.json', encoding='utf-8').read())
for p in s022.get('verified_papers', []):
    print(f"  [{p.get('source','')}] {p.get('title','')[:80]}")

# Check source distribution of verified_papers across all cases
print("\n=== Source distribution ===")
source_counts = Counter()
for d in sorted(eval_dir.iterdir()):
    if not d.is_dir():
        continue
    sp = d / 'state.json'
    if not sp.exists():
        continue
    s = json.loads(sp.read_text(encoding='utf-8'))
    for p in s.get('verified_papers') or []:
        source_counts[p.get('source', 'unknown')] += 1
for src, count in source_counts.most_common():
    print(f"  {src}: {count}")
