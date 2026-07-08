import json
cases = ["ENG-THESIS-015"]
for cid in cases:
    try:
        s = json.load(open(f"tmp_re15_eval/smoke_20/{cid}/state.json", encoding="utf-8"))
        print(f"[{cid}] trace={len(s.get('trace_events',[]))} verified={len(s.get('verified_papers',[]))} weak={len(s.get('weak_papers',[]))} feasibility={s.get('feasibility_report',{}).get('verdict','N/A')} review={s.get('review_report',{}).get('verdict','N/A')} final={bool(s.get('final_recommendation'))} errors={len(s.get('errors',[]))}")
    except Exception as e:
        print(f"[{cid}] ERROR: {e}")
