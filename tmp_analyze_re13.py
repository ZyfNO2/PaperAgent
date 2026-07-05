"""Analyze Re1.3 E2E results."""
import json, os

for case in ['re13-steel-yolov5','re13-semantic-slam','re13-medical-llm']:
    p = f'tmp_re13_eval/{case}/state.json'
    if not os.path.exists(p):
        continue
    with open(p, encoding='utf-8') as f:
        st = json.load(f)
    vp = st.get('verified_papers') or []
    fr = st.get('filter_results') or {}
    sp = st.get('seed_papers') or []
    ep = st.get('expanded_papers') or []

    print(f'=== {case} ===')
    print(f'  filter: kept={fr.get("kept",0)} dropped={fr.get("dropped",0)}')

    if fr.get('dropped_items'):
        print('  dropped by quality_filter:')
        for d in fr['dropped_items'][:8]:
            t = d.get('title','')[:60]
            r = d.get('reason','')[:60]
            print(f'    - {t} | reason: {r}')

    print(f'  verified_papers: {len(vp)}')
    for i, p2 in enumerate(vp[:10]):
        t = p2.get('title','')[:65]
        v = p2.get('verdict','')
        has_id = bool(p2.get('paper_id') or p2.get('doi') or p2.get('arxiv_id'))
        print(f'    [{i}] [{v:8s}] {t}')
        print(f'        has_id={has_id} | keys={list(p2.keys())}')

    print(f'  seed_papers: {len(sp)}')
    print(f'  expanded_papers: {len(ep)}')

    # Diagnose why no seeds
    if vp and not sp:
        print('  >>> ROOT CAUSE: verified_papers lack paper_id/doi/arxiv_id')
        print('  >>> verify_node strips identifiers from paper_candidates')
        # Check what keys verify outputs
        if vp:
            print(f'  >>> verified_papers keys: {list(vp[0].keys())}')
        # Check original paper_candidates
        pc = st.get('paper_candidates') or []
        if pc:
            print(f'  >>> paper_candidates[0] keys: {list(pc[0].keys())}')
            # Check if paper_candidates have doi
            for p2 in pc[:5]:
                doi = p2.get('doi','')
                url = p2.get('url','')[:50]
                print(f'      candidate: {p2.get("title","")[:40]} | doi={doi} | url={url}')

    # Trace summary
    traces = st.get('trace_events') or []
    print(f'  trace ({len(traces)} events):')
    for t in traces:
        node = t.get('node','')
        el = t.get('elapsed_s',0)
        out = t.get('output_summary',{})
        errs = t.get('errors',[])
        err_str = f' errors={len(errs)}' if errs else ''
        print(f'    {node:30s} {el:8.1f}s {out}{err_str}')

    print()
