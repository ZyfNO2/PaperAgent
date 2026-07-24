from pathlib import Path

path = Path("tests/projects/test_cli.py")
text = path.read_text(encoding="utf-8")
old = """    plan = _run(
        parser,
        capsys,
        [
            \"tailor\",
"""
new = """    tailor_args = parser.parse_args(
        [
            \"tailor\",
"""
if text.count(old) != 1:
    raise RuntimeError("tailor invocation block not found exactly once")
text = text.replace(old, new)
old_tail = """        ],
    )
    assert plan[\"decision\"] == \"REVISE\"
    assert {module[\"paper_id\"] for module in plan[\"modules\"]} == {\"eca\", \"mixup\"}
    assert plan[\"citations\"]
"""
new_tail = """        ]
    )
    assert run_memory_rag_cli(tailor_args) == 3
    plan = json.loads(capsys.readouterr().out)
    assert plan[\"decision\"] == \"BLOCKED\"
    assert plan[\"reason_code\"] == \"compatibility_contract_not_independently_verified\"
    assert {module[\"paper_id\"] for module in plan[\"modules\"]} == {\"eca\", \"mixup\"}
    assert plan[\"citations\"]
"""
if text.count(old_tail) != 1:
    raise RuntimeError("tailor assertion block not found exactly once")
path.write_text(text.replace(old_tail, new_tail), encoding="utf-8")
