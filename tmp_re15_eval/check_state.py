import json
s = json.load(open('tmp_re13_eval/re15-p0-test2/state.json', encoding='utf-8'))
print(f"trace_events: {len(s.get('trace_events', []))}")
print(f"errors: {len(s.get('errors', []))}")
print(f"verified: {len(s.get('verified_papers', []))}")
print(f"weak: {len(s.get('weak_papers', []))}")
print(f"feasibility verdict: {s.get('feasibility_report', {}).get('verdict', 'N/A')}")
print(f"review verdict: {s.get('review_report', {}).get('verdict', 'N/A')}")
print(f"final keys: {list(s.get('final_recommendation', {}).keys())}")
