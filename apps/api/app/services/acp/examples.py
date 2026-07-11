"""Re4.4: ACP call examples for external AI tools."""
from __future__ import annotations

CODEX_EXAMPLE = '''# Codex (OpenAI) — ACP 调用示例
import requests

BASE = "http://127.0.0.1:18181/api/v1/acp"

# 1. 列出所有能力
resp = requests.get(f"{BASE}/capabilities")
capabilities = resp.json()["capabilities"]
print(f"可用能力: {[c['name'] for c in capabilities]}")

# 2. 只读：获取 case 状态
resp = requests.post(f"{BASE}/invoke", json={
    "capability": "get_run_status",
    "params": {"case_id": "re41-verify-001"}
})
print(f"状态: {resp.json()}")

# 3. 写操作：提交题目检索（需要 write 权限）
resp = requests.post(f"{BASE}/invoke", json={
    "capability": "search_literature",
    "params": {"topic": "基于YOLO的钢材表面缺陷检测"}
}, headers={"X-ACP-Capability": "write"})
print(f"提交结果: {resp.json()}")
'''

CLAUDE_CODE_EXAMPLE = '''# Claude Code — ACP 调用示例 (curl)

# 1. 列出所有能力
curl http://127.0.0.1:18181/api/v1/acp/capabilities

# 2. 只读：获取工作包 DAG
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \\
  -H "Content-Type: application/json" \\
  -d '{"capability": "get_work_packages", "params": {"case_id": "re41-verify-001"}}'

# 3. 写操作：上传论文（需要 write 权限）
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \\
  -H "Content-Type: application/json" \\
  -H "X-ACP-Capability: write" \\
  -d '{"capability": "upload_paper", "params": {"case_id": "re41-verify-001", "doi": "10.1234/example"}}'

# 4. [未接通] RAG 问答
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \\
  -H "Content-Type: application/json" \\
  -d '{"capability": "query_rag", "params": {"question": "What datasets are used?"}}'
'''

TRAE_EXAMPLE = '''# Trae — ACP 调用示例 (Python async)
import httpx
import asyncio

async def main():
    base = "http://127.0.0.1:18181/api/v1/acp"
    async with httpx.AsyncClient() as client:
        # 1. 列出能力
        resp = await client.get(f"{base}/capabilities")
        print(f"共 {resp.json()['n']} 个能力")

        # 2. 只读：获取创新点
        resp = await client.post(f"{base}/invoke", json={
            "capability": "get_innovation",
            "params": {"case_id": "re41-verify-001"}
        })
        print(f"创新点: {resp.json()}")

        # 3. 写操作：提交检索
        resp = await client.post(f"{base}/invoke", json={
            "capability": "search_literature",
            "params": {"topic": "医学问答可信度评估"}
        }, headers={"X-ACP-Capability": "write"})
        result = resp.json()
        if result["success"]:
            print(f"Case ID: {result['result']['case_id']}")

asyncio.run(main())
'''


def get_examples() -> dict[str, str]:
    return {
        "codex": CODEX_EXAMPLE,
        "claude_code": CLAUDE_CODE_EXAMPLE,
        "trae": TRAE_EXAMPLE,
    }
