# PaperAgent Re1.1 环境与密钥安全检查（Loop 0 前置）

> SOP §1 已完成的环境与密钥检查（基线）。本轮（Re1.1 骨架 + loop 验证）再次核验。

## 1. `.env` 安全性

```
git check-ignore -v .env .env.local
  .gitignore:39:.env	.env
  .gitignore:40:.env.local	.env.local

git ls-files .env .env.local
  (返回空，确认不可跟踪)

git ls-files --error-unmatch .env
  (returncode != 0 => 未被跟踪)
```

**结论**: ✅ `.env` / `.env.local` 已 gitignore 且未跟踪。

## 2. 密钥类别（.env）

| 类别 | provider env | 用途 | 本轮状态 |
| --- | --- | --- | --- |
| primary fast-json | `DEEPSEEK_API_KEY` / `DEEPSEEK_FLASH_MODEL` | topic parse / planner / verifier | **key 已过期**（API 返回 invalid_request_error） |
| execution | `STEPFUN_API_KEY` / `STEPFUN_BASE_URL` / `STEPFUN_MODEL` | 连通 / 成本低 / exec | ✅ 通（step-1v-32k, base=api.stepfun.com） |
| premium review | `VOAPI_API_KEY` | 最终抽样复核 | ✅ 通 |
| disabled | `MINIMAX_API_KEY` | MiniMax 默认停用 | 已通过 `MINIMAX_DISABLED=true` 禁用 |

## 3. 代码审计：无 key 泄漏

- `apps/api/services/llm_router.py:_redact()` 在异常文本遇到 Bearer/x-api-key/Authorization 时替换为 `<REDACTED>`.
- 验证：`test_re11_no_secret_leak.py::test_chat_json_does_not_print_key_when_missing` 通过。
- `apps/api/services/agents/prompts/re11_*.py` 扫一遍：无 `sk-xxx` 字符串（`test_re11_no_secret_leak.py::test_no_secrets_in_re11_code` 通过）。

## 4. FAT-RAW 检查

`.env.example` 只含 placeholder。长字符串（20+ alphanumeric）grep 结果：0 命中（`pytest test_re11_no_secret_leak.py::test_env_example_is_placeholder` SKIP，因无满足条件的行）。

## 5. Git 泄露检查（新代码）

```bash
cd G:/PaperAgent
rg -n "sk-|Bearer |Authorization|DEEPSEEK_API_KEY=.*[A-Za-z0-9]" Plan apps
```

- 现实：多数密钥字面量不会出现在代码中（网关在 env），test patch mock 除外。
- test patch 内的 mock key 形式为 `key-should-not-leak-fake` / `test-not-real-fake` — 不是真实 key。

## 6. 本轮新增依赖

| 包 | 版本 | 用途 |
| --- | --- | --- |
| langgraph | 1.2.7 | StateGraph + START/END + MemorySaver |
| langgraph-checkpoint | 4.1.1 | Graph checkpointer 抽象 |
| langgraph-checkpoint-sqlite | 3.1.0 | 持久化（可选，本轮默认 memory） |
| langsmith | 0.9.7 | Tracing（`LANGSMITH_TRACING=false`） |

`pyproject.toml` + `uv.lock` 已同步：✅

## 7. 最终判定

- `.env` 未被跟踪 ✅
- 无硬编码真实 key ✅
- Legacy mini defaults 全部被 env override ✅
- 新增依赖已在 lockfile ✅
