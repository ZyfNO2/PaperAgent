import httpx, json

r = httpx.get('http://127.0.0.1:18181/api/v1/research/V-MED-32i/state')
state = r.json()
atoms = state.get('topic_atoms', {})
method = atoms.get('method', [])
task = atoms.get('task', [])
domain = atoms.get('domain')

with open('tmp_re32_eval/atoms_check.txt', 'w', encoding='utf-8') as f:
    f.write(f'method: {method}\n')
    f.write(f'task: {task}\n')
    f.write(f'domain: {domain}\n')
    for m in method:
        f.write(f'method item bytes: {m.encode("utf-8")}\n')
        f.write(f'has_cjk: {any(0x4e00 <= ord(c) <= 0x9fff for c in m)}\n')
print('done')
