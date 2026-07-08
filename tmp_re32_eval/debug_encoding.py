"""Debug: call DeepSeek API directly and check encoding of response."""
import os, sys, json
from dotenv import load_dotenv
load_dotenv('.env')

import httpx

key = os.environ.get('DEEPSEEK_API_KEY', '')
url = 'https://api.deepseek.com/v1/chat/completions'
headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
body = {
    'model': 'deepseek-chat',
    'messages': [
        {'role': 'system', 'content': 'Parse the topic into English keywords. Return JSON.'},
        {'role': 'user', 'content': 'Topic: 基于大语言模型的医学问答可信度评估方法研究'},
    ],
    'temperature': 0.2,
    'response_format': {'type': 'json_object'},
}

r = httpx.post(url, json=body, headers=headers, timeout=30)

# Check response encoding
with open('tmp_re32_eval/encoding_debug.txt', 'w', encoding='utf-8') as f:
    f.write(f'Status: {r.status_code}\n')
    f.write(f'Headers: {dict(r.headers)}\n')
    f.write(f'Encoding: {r.encoding}\n')
    f.write(f'Charset from headers: {r.charset_encoding}\n')
    
    # Raw bytes
    f.write(f'Raw bytes (first 500): {r.content[:500]}\n')
    
    # Parsed JSON
    data = r.json()
    content = data['choices'][0]['message']['content']
    f.write(f'Content: {content}\n')
    f.write(f'Content type: {type(content)}\n')
    
    # Check if content has CJK
    has_cjk = any(0x4e00 <= ord(c) <= 0x9fff for c in content)
    f.write(f'Has CJK in content: {has_cjk}\n')
    
    # Parse JSON from content
    try:
        parsed = json.loads(content)
        method = parsed.get('method', '')
        f.write(f'Method: {method}\n')
        f.write(f'Method type: {type(method)}\n')
        if isinstance(method, str):
            f.write(f'Method bytes: {method.encode("utf-8")}\n')
            has_cjk_method = any(0x4e00 <= ord(c) <= 0x9fff for c in method)
            f.write(f'Method has CJK: {has_cjk_method}\n')
    except Exception as e:
        f.write(f'JSON parse error: {e}\n')

print('done')
