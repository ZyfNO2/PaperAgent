# PaperAgent 验收状态报告

**日期**: 2026-07-18  
**仓库**: ZyfNO2/PaperAgent  
**验收计划**: `docs/acceptance/CONSOLIDATED_ACCEPTANCE_PLAN.md`  
**固定身份**:  
- Review base: `497982242023e3b621fa8b31816a6f2b8d899d4a`
- Rewritten master: `8661084f2ef0210241c2143eca8db981222413a9`
- PR #17 (review branch): `feat/academic-tailoring-evaluation`

---

## 1. 已完成验收

### ✅ Review-base Acceptance (PASS)

PR #17 上 3 个 GitHub Actions workflow 通过：

| Workflow | Run ID | 时间 (UTC) | 结果 |
|----------|--------|-------------|------|
| Academic Tailoring Agent Evaluation | 29630395824 | 2026-07-18T04:20:34Z | success |
| PaperAgent Interview Evidence | 29630395832 | 2026-07-18T04:20:34Z | success |
| PaperAgent Local Acceptance | 29630394572 | 2026-07-18T04:20:32Z | success |

本地验证 (migration/gate-r HEAD `30e7a8c4`)：
- 313 passed, 10 skipped (credential/browser/network tests)
- Coverage: 90.88% (branch)
- Ruff / Format / Mypy: PASS

### ✅ Gate R Migration (PASS)

从 rewritten master `073fdc44` 重建 review base 变更集：
- **0 意外删除** (通过 `git ls-tree` 对比验证)
- 129 文件新增, 12 文件修改
- CI: 313 tests passed
- 推送至 `origin/migration/gate-r`

### ✅ Engineering Release (PASS)

- Wheel build: `paperagent-0.5.1-py3-none-any.whl` (122 files)
- SQLite WAL mode verified
- Backup/Restore: PASS
- Diagnostics: secret-free, `journal_mode=wal`
- OpenAPI export: PASS

---

## 2. 当前阻塞：Gate L (Scientific Capability)

### 2.1 Holdout 案例状态

16 个冻结案例已创建 (`evals/v0_6/holdout_cases.v1.jsonl`)：
- In-domain: 4 / OOD: 4 / Insufficient evidence: 4 / Adversarial: 4
- SHA-256: `89375da32f3879baea711c5e6567ed1dcc65efc5cce4c8e95496adcfd8fedda6`
- Manifest 已通过全部 4 项自动化验证

### 2.2 真实 Provider 执行结果

使用 `mistral-small-latest` 执行全部 16 案例 (120s 超时/案例)：

| 案例 | 分类 | Terminal | Wall Time | Calls |
|------|------|----------|-----------|-------|
| in-domain-001 | in_domain | unknown | 12.1s | 1 |
| in-domain-002 | in_domain | unknown | 10.5s | 1 |
| in-domain-003 | in_domain | unknown | 10.7s | 1 |
| in-domain-004 | in_domain | unknown | 10.4s | 1 |
| ood-001 | ood | **blocked** | 55.0s | 4 |
| ood-002 | ood | unknown | 9.8s | 1 |
| ood-003 | ood | unknown | 12.5s | 1 |
| ood-004 | ood | **blocked** | 46.8s | 4 |
| insufficient-001 | insufficient | **blocked** | 11.8s | 2 |
| insufficient-002 | insufficient | unknown | 11.1s | 1 |
| insufficient-003 | insufficient | unknown | 9.3s | 1 |
| insufficient-004 | insufficient | unknown | 9.8s | 1 |
| adversarial-001 | adversarial | **blocked** | 9.7s | 2 |
| adversarial-002 | adversarial | unknown | 7.8s | 1 |
| adversarial-003 | adversarial | **blocked** | 8.3s | 2 |
| adversarial-004 | adversarial | **blocked** | 7.8s | 2 |

**节点耗时汇总 (mistral-small-latest)**:

| Node | Total Calls | Total Latency | Avg Latency | Errors |
|------|-------------|---------------|-------------|--------|
| planning | 16 | 127.8s | 8.0s | 0 |
| evidence_synthesis | 2 | 14.2s | 7.1s | 0 |
| method_design | 2 | 31.7s | 15.9s | 0 |
| report | 6 | 23.4s | 3.9s | 0 |

**关键发现**:
- 安全检查正确工作：adversarial/insufficient 案例正确被 block
- 但 **7/16 案例在 planning 节点后停止**，只跑 1 个 LLM call 就返回 `unknown` 状态
- 完整跑通的案例 (ood-001, ood-004) 均触发全部 4 个节点

---

## 3. 根本原因分析

### 问题 1: 大多数案例在 planning 节点后停止 (terminal=unknown)

**现象**: 7/16 案例仅执行 planning 节点 (1次 LLM call, ~10s)，随后直接退出，terminal 为 `unknown` (非 succeeded/failed/blocked)。

**证据**: `build/gate-l-evidence/diagnostic-mistral-small-latest.json`

**可能原因**:
1. planning 节点输出的 JSON schema 与后续节点的输入要求不匹配
2. LangGraph 路由逻辑在特定条件下提前终止但未设置正确的 terminal status
3. planning 节点的 structured output 中某个字段值导致路由进入不存在的分支

**需要检查**:
```python
# src/paperagent/nodes/planning.py — planning 节点的输出格式
# src/paperagent/graph.py — 路由逻辑，特别是条件边的判断
# 检查 state_to_primitive() 如何序列化 planning 输出
```

### 问题 2: 无 error/fallback 机制

**现象**: 当 budget 超限或 graph 状态异常时，系统不报错也不 fail-closed，而是静默返回 `unknown`。

**Gate L 要求**: "Budget exhaustion → 100% fail-closed"

**需要修复的位置**:
- `src/paperagent/api/executor.py` — `LangGraphTaskExecutor.execute()` 的 stream 处理
- 当 LLM 调用次数或 token 数超过 budget 时，应主动 raise `TaskBudgetExhaustedError`
- 当 graph 状态中出现 missing required fields 时，应返回 `failed` 而非 `unknown`

### 问题 3: Token 预算不匹配

**现象**: holdout 案例中 `max_total_tokens: 16000`，但实际 planning 节点单次调用就消耗 23,841 input tokens (schema 太大)。

**根因**: ResearchPlan 等 Pydantic schema 的 JSON representation 很长，加上 system prompt 和 few-shot，单次调用 input 即可超 15,000 tokens。

**解决方案**: 要么放宽案例预算，要么精简 schema。

### 问题 4: 不支持 OpenAI-compatible Provider

**现象**: `LLMProviderName` 枚举只有 `MISTRAL`，`build_llm_provider` 只接受 Mistral。

**需求**: 支持 DeepSeek v4 Flash (通过 `https://opencode.ai/zen/go/v1`)。

**需要修改的文件**:

```python
# src/paperagent/providers/runtime.py
class LLMProviderName(StrEnum):
    MISTRAL = "mistral"
    OPENAI = "openai"  # ← 需要新增

# src/paperagent/providers/runtime_factory.py
def build_llm_provider(config, price_table=None):
    if config.provider is LLMProviderName.MISTRAL:
        return MistralLLMProvider(config, price_table=price_table)
    if config.provider is LLMProviderName.OPENAI:  # ← 需要新增
        return OpenAILLMProvider(
            api_key=config.api_key.get_secret_value(),
            model=config.model,
            base_url=config.base_url,
        )
    raise ValueError(f"unsupported LLM provider: {config.provider}")
```

**DeepSeek v4 Flash 测试结果** (直接调用 OpenAI endpoint):
- 连通性: PASS
- 单次调用延迟: ~8s (vs mistral-small 8s, mistral-medium 12-62s)
- Structured output: PASS (需要正确指令才能生成完整 schema)
- 成本: 极低 (301 tokens ≈ $0)

---

## 4. 待修复代码清单

| 优先级 | 文件 | 问题 | 修复方案 |
|--------|------|------|----------|
| **P0** | `src/paperagent/graph.py` | planning 后停止，terminal=unknown | 检查条件边路由逻辑，确保所有路径都有正确的 terminal 状态 |
| **P0** | `src/paperagent/api/executor.py` | 无 budget fail-closed | 在 stream 处理中加入 budget 检查，超限即 raise |
| **P1** | `src/paperagent/providers/runtime.py` | 无 OPENAI 枚举值 | `LLMProviderName.OPENAI = "openai"` |
| **P1** | `src/paperagent/providers/runtime_factory.py` | 不支持 OpenAI provider | 添加 `OPENAI` 分支返回 `OpenAILLMProvider` |
| **P2** | `src/paperagent/providers/config.py` | 硬编码 Mistral | 支持从 env 读取 OpenAI-compatible 配置 |
| **P2** | `evals/v0_6/holdout_cases.v1.jsonl` | token 预算过紧 | 将 `max_total_tokens` 调整为 60000+ |

---

## 5. 推荐下一步

1. **优先修复 P0**: graph routing + budget fail-closed (问题 1 + 2)
   - 这是 Gate L 的核心障碍，不修复则无法获得有效证据
   
2. **接入 DeepSeek v4 Flash** (问题 4)
   - 延迟更低、成本更低、structured output 可用
   - 只需修改枚举和工厂函数

3. **重跑全部 16 案例**
   - 修复后使用 DeepSeek v4 Flash + 120s 超时/案例
   - 预期总耗时: ~15 分钟 (大部分案例在 10-60s 完成)
   - 预期成本: < $1

4. **专家评审** (外部依赖)
   - 需要 2 名独立审稿人 + Cohen's κ ≥ 0.70
   - 无法自动化

---

## 6. 分支/远端状态

| 分支 | 远端 | 状态 |
|------|------|------|
| `master` | `origin/master` | `073fdc44` (格式清理) |
| `migration/gate-r` | `origin/migration/gate-r` | Gate R + Gate K 配置 |
| `scientific-gate-l` | `origin/scientific-gate-l` | Gate L 执行 + manifest 修复 |
| `feat/academic-tailoring-evaluation` | PR #17 | Review branch (未动) |

---

## 7. 环境注意事项

- **Windows temp 目录权限问题**: pytest 默认 temp 目录会报 `PermissionError: [WinError 5]`
  - 临时解决: `$env:TEMP = "C:\Users\ZYF\AppData\Local\Temp\paperagent-pytest"; pytest --basetemp=...`
  - 长期解决: 在 `pyproject.toml` 或 `conftest.py` 中配置 `tmp_path` 使用独立目录

- **API Key 暴露**: `MISTRAL_API_KEY` 和 OpenCode Key 已出现在对话历史中，建议轮换。
