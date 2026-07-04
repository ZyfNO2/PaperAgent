# PaperAgent Re10 FIX-4 静态审计报告

## 0. 审核结论

Loop 1 静态审计 **通过**。所有已知硬编码已清除，统一 axis 展开已就位。

可以进入 Loop 2（3 个微型题目）。

## 1. 审计范围

不跑网络，纯代码扫描 + 语法检查。

## 2. 发现与修复

### P0-1：具体 repo 名称硬编码 — ✅ 已清除

修复前：
- `search_reflection_loop.py:336` — `generic_repos = {"ORB_SLAM3", "open_vins", "awesome-visual-slam"}`
- `search_reflection_loop.py:338` — `is_slam_topic` 特判
- `validate_re10_reflection_search.py:341` — 同样的硬编码集合

修复后：
- 主链路改为通用 repo-only 检测：repo 候选仅命中 object/method 而不命中 task/scenario → 降级为 weak
- validator H10 改为批内统计模式：同一 title 在 ≥3 个不同 case 中作为主证据出现 + 其中某次缺少 object/task hit → 标记污染
- 无任何具体 repo/项目名黑名单

残留匹配（非主链路）：
- `run_re04_smoke_offline.py` 中的 ORB_SLAM2/ORB_SLAM3 是 mock fixture 数据（模拟 GitHub API 响应），不是过滤器
- `evidence_consistency.py`、`evidence_roles.py`、`eval/__init__.py`、`prompts/plan_tools.py` 中的 `STRONG_NOISE_TOKENS` 是文档/注释，不是运行时代码

### P0-2：topic_axis_match 使用错误的数据结构 — ✅ 已修复

修复前：
```python
method_hit = [k for k in verdict.matched_keywords if k in (topic_atoms.get("method") or [])]
```
`topic_atoms["method"]` 是 `list[dict]`（如 `{"en": "YOLOv5", "zh": "YOLOv5"}`），`k in list[dict]` 永不命中。

修复后：
- 新增 `flatten_axis_terms(topic_atoms, axis)` 在 `search_reflection_helpers.py` 中
- 统一支持 `list[str]` 和 `list[dict]`，展开 `en/zh/aliases`，去重
- `topic_axis_match` 使用 `flatten_axis_terms` + haystack substring 匹配
- `candidate_verifier._flatten_atom_text` 保持独立（内部实现），但逻辑等价

### P0-3：报告结论越过证据 — N/A（本轮不写报告）

本报告只记录静态审计结果。

### P1-1：Validator H10 硬编码 — ✅ 已清除

修复为批内统计模式（见 P0-1）。

### P1-2：[Fallback] 标记 — ✅ 已修复

修复前 (`search_reflection_helpers.py:77`)：
```python
en = [f"[Fallback] {first} dataset benchmark", f"[Fallback] {first} baseline method"]
```

修复后：
```python
en = [f"{first} dataset benchmark", f"{first} baseline method"]
```

`domain_scout_agent.py` 中的 `[Fallback]` 仅在 `search_notes` 结构化字段，不进入 query 文本。

### P1-3：并行验证 — 待 Loop 2 验证

脚本保留 `--parallel` 参数（合理），但 FIX-4 验收要求 `--parallel 1`。

### 附加修复：trace 不存储 accepted 候选

发现 `trace_ledger.py` 的 `record_round` 不存储 `accepted` 候选列表，导致 validator 读到的 `r.get("accepted")` 永远为空。

修复：
- `record_round` 新增 `accepted` 参数
- 每个 round 存储精简的 accepted 列表（title + topic_axis_match + verification_status）
- `TraceLedger.__init__` 新增 `topic_atoms` 参数，写入 trace 顶层

## 3. 语法检查

```bash
python -c "import ast; ast.parse(open('search_reflection_loop.py').read())"  # OK
python -c "import ast; ast.parse(open('validate_re10_reflection_search.py').read())"  # OK
python -c "import ast; ast.parse(open('search_reflection_helpers.py').read())"  # OK
python -c "import ast; ast.parse(open('trace_ledger.py').read())"  # OK
```

## 4. 修改文件清单

| 文件 | 改动类型 |
|------|----------|
| `search_reflection_helpers.py` | 新增 `flatten_axis_terms()`，移除 `[Fallback]` query 前缀 |
| `search_reflection_loop.py` | 删除硬编码，使用 `flatten_axis_terms`，传递 `topic_atoms` 给 TraceLedger，传递 `accepted` 给 record_round |
| `trace_ledger.py` | 新增 `topic_atoms` 存储，新增 `accepted` 参数存储候选 |
| `validate_re10_reflection_search.py` | H10 改为批内统计检测 |

## 5. 是否可进入 Loop 2

**可以。**

硬性条件核验：
- [x] 主链路代码无具体候选标题黑名单
- [x] validator 无具体候选标题黑名单
- [x] query 中不出现 `[Fallback]`
- [x] 使用统一的 `flatten_axis_terms` 函数
- [x] trace 存储了 `accepted` 候选和 `topic_atoms`
