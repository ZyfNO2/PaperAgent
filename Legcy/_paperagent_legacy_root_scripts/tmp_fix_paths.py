import json
s = json.load(open('tmp_re04_eval/re10_fix2_iter3_combined/summary.json', encoding='utf-8'))
SEP = chr(92)  # backslash
for c in s.get('per_case', []):
    tp = c.get('trace_path') or ''
    if SEP in tp:
        c['trace_path'] = tp.replace(SEP + SEP, '/').replace(SEP, '/')
open('tmp_re04_eval/re10_fix2_iter3_combined/summary.json', 'w', encoding='utf-8').write(json.dumps(s, ensure_ascii=False, indent=2))
print('normalised', sum(1 for c in s['per_case'] if c.get('trace_path')))
