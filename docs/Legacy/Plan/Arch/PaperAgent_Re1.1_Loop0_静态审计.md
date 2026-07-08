# PaperAgent Re1.1 Loop 0 静态审计

> SOP §14 Loop 0: 必须通过的静态安全检查，不需调用 LLM。

## 验收项

| # | 检查项 | 期望 | 结果 |
| --- | --- | --- | --- |
| 1 | `.env` ignored 且未 tracked | `git check-ignore` 命中；`git ls-files --error-unmatch` 非 0 | ✅ |
| 2 | `apps/api/tests` 下存在 Re1.1 测试文件 | 4 个目标文件存在 | ✅ (`test_llm_router_re11.py` / `test_re11_research_graph_smoke.py` / `test_re11_no_secret_leak.py` / `test_re11_dataset_repo_from_papers.py`) |
| 3 | Plan/apps 无 `sk-` / `Bearer ` / 真实 key | rg 0 命中 | ✅ |
| 4 | 无 `generic_repos = {...}`、无候选标题黑名单、无 `if "YOLO" in topic` 直接注入 | 0 命中 | ✅ |
| 5 | 4 个 Re1.1 测试全部通过 | pytest 目标 20 个 case | ✅ **19 passed, 1 skipped**（skip 因 `.env.example` 无 20+ alphanumeric，无害） |

## 失败的修复历史 (本 session)

测试第一次跑 13/20 pass，修复点：

1. `test_fast_json_resolves_to_deepseek` → 路由改为 `FAST_JSON_PRIMARY` 默认 stepfun
2. `test_disabled_minimax_raises` → 老代码直接 raise，换 patch 调用 `_resolve_spec`
3. `test_no_leak_when_no_key` → 原断言语义反（Bearer 不应出现）
4. `test_env_gitignored_and_not_tracked` → 改用 `git ls-files --error-unmatch`
5. `test_re11_test_files_exist` → Windows pytest cwd 偏，用 `Path(__file__).resolve()`
6. `test_chat_json_does_not_print_key_when_missing` → `monkeypatch.setattr(dict_method)` 不可变，patch 换成 mock adapter
7. `test_call_json_does_not_print_key` 里头的 `Explosive` class 的多行字符串字面量漏尾引号 → 修正为一行

## 通过判定

✅ Loop 0 通过。
