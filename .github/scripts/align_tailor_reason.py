from pathlib import Path

path = Path("tests/projects/test_cli.py")
text = path.read_text(encoding="utf-8")
old = '    assert plan["reason_code"] == "compatibility_contract_not_independently_verified"\n'
new = (
    '    assert plan["reason_code"] == '
    '"module_design_deferred:insufficient_independent_evidence"\n'
)
if text.count(old) != 1:
    raise RuntimeError("tailor reason assertion not found exactly once")
path.write_text(text.replace(old, new), encoding="utf-8")
