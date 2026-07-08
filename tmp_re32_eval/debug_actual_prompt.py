"""Debug: call topic_parser with actual prompt and check result."""
import os, sys, json
from dotenv import load_dotenv
load_dotenv('.env')

import httpx
from apps.api.app.services.agents.prompts import re11_parser as P

key = os.environ.get('DEEPSEEK_API_KEY', '')
url = 'https://api.deepseek.com/v1/chat/completions'
headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}

built = P.build('基于大语言模型的医学问答可信度评估方法研究')
body = {
    'model': 'deepseek-chat',
    'messages': [
        {'role': 'system', 'content': built['system']},
        {'role': 'user', 'content': built['user']},
    ],
    'temperature': 0.2,
    'response_format': {'type': 'json_object'},
}

r = httpx.post(url, json=body, headers=headers, timeout=30)
data = r.json()
content = data['choices'][0]['message']['content']

with open('tmp_re32_eval/actual_prompt_test.txt', 'w', encoding='utf-8') as f:
    f.write(f'System prompt length: {len(built["system"])}\n')
    f.write(f'System has rule 6: {"For Chinese topics" in built["system"]}\n')
    f.write(f'Content: {content}\n')
    f.write(f'Content has CJK: {any(0x4e00 <= ord(c) <= 0x9fff for c in content)}\n')
    
    try:
        parsed = json.loads(content)
        f.write(f'Parsed: {json.dumps(parsed, ensure_ascii=False, indent=2)}\n')
        method = parsed.get('method', [])
        f.write(f'Method: {method}\n')
        if isinstance(method, list):
            for m in method:
                f.write(f'  item: {m} | has_cjk: {any(0x4e00 <= ord(c) <= 0x9fff for c in str(m))}\n')
    except Exception as e:
        f.write(f'Parse error: {e}\n')

print('done')
