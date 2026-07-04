import asyncio
import json
from app.services.agents.search_reflection_loop import run_search_reflection_loop

async def test():
    topic = '基于大语言模型的医学问答答案可信度评估'
    topic_atoms = {
        'task': [{'en': 'answer credibility evaluation', 'zh': '答案可信度评估'}],
        'object': [{'en': 'medical QA answers', 'zh': '医学问答答案'}],
        'method': [{'en': 'large language models', 'zh': '大语言模型'}],
    }
    result = await run_search_reflection_loop(
        topic=topic,
        topic_atoms=topic_atoms,
        seed_candidates=[],
        out_dir='tmp_re04_eval/test_fix3',
        case_id='TEST-001',
        max_rounds=1,
        llm_client=None,
        retrieval_clients={},
    )
    trace_path = result.get('trace_path')
    print('trace_path:', trace_path)
    if trace_path:
        with open(trace_path, 'r', encoding='utf-8') as f:
            trace = json.load(f)
        print('Trace actions:')
        for r in trace.get('rounds', []):
            for a in r.get('actions', []):
                print(f'  query: {a.get("query")}')
                print(f'  tool: {a.get("tool")}')
                print(f'  why: {a.get("why")}')
                print()

asyncio.run(test())