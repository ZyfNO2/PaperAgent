import json, sys, subprocess
# Simulate harness stdin
payload = json.dumps({
    "tool_name": "Write",
    "tool_input": {
        "file_path": "G:\PaperAgent\tmp_s66v_traces\run_re02v2_caseA.py",
        "content": "x = 1\n"
    }
})
result = subprocess.run(
    ["uv", "run", "python", ".claude/hooks/pre_report_audit.py"],
    input=payload, capture_output=True, text=True, cwd="G:/PaperAgent"
)
print("returncode:", result.returncode)
print("stdout:", result.stdout[:500])
print("stderr:", result.stderr[:2000])
