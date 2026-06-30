# Phase 64 T5: orchestrator 集成新模块 — 验收报告

**Task**: Session 64 T5 (Phase 64 — paper/dataset/repo 全链路)

## 产物

- `apps/api/app/services/retrieval/orchestrator.py` (修改, +~165 行)
- `apps/api/app/schemas_retrieval.py` (修改, `RetrievalRun` +4 个可选字段)
- `apps/api/tests/test_session64_t5_orchestrator_integration.py` (新建, 11 个测试)

## 集成点

```
normalize → score → dedupe → ledger_dedup → sort
  ↓
  ├─ 8.5 candidate_cleaner      (T1)  → clean_summary + keep_candidates
  ├─ 8.6 web_dataset_search      (T2)  → web_datasets (trigger: dataset<2 或 top_score<0.45)
  ├─ 8.7 literature_role_classifier (T3) → literature_roles
  └─ 8.8 paper_module_matrix     (T4)  → module_matrix
  ↓
  deduped = keep_candidates
  ↓
gap_report / retry (S61) → RetrievalRun → trace
```

每一步都是 optional import + try/except wrapper, **缺失任意模块都不会让 run_retrieval 挂掉**.

## RetrievalRun 新增字段

| 字段 | 类型 | 默认 | 来源 |
|------|------|------|------|
| `clean_summary` | `dict \| None` | `None` | T1 candidate_cleaner |
| `web_datasets` | `list[dict]` | `[]` | T2 web_dataset_search |
| `literature_roles` | `list[dict]` | `[]` | T3 literature_role_classifier |
| `module_matrix` | `dict \| None` | `None` | T4 paper_module_matrix |

全部都是 `extra="forbid"` 兼容 — 不破坏旧调用 / 旧测试 / 旧 JSON 序列化.

## ponytail 决策

1. **trigger 内联**: `_should_trigger` 在 web_dataset_search 是私有 (`_` 前缀), 改成在 orchestrator 内联 2 行判断 (`dataset<2 或 top_score<0.45`). 避免依赖私有 API.
2. **候选 dict 拍扁**: 加 `_candidate_to_dict` helper 把 `RetrievalCandidate` 拍成 plain dict 喂下游模块. 不动 schema (Pydantic v2 强类型).
3. **trace 全程**: 8 个新 trace action (`retrieval_candidates_cleaned`, `web_dataset_search_triggered`, `web_dataset_search_failed`, `literature_roles_classified`, `literature_role_classifier_failed`, `module_matrix_built`, `module_matrix_build_failed`, `retrieval_candidate_cleaner_failed`) 全部走 `append_trace`, 失败不阻塞主流程.
4. **可选依赖**: 4 个新模块都用 `try/except` 包成 `None`, 测试里 monkey-patch `None` 验证 fallback 路径.
5. **保持 fallback**: 原 gap_report / retry_round / 旧 summary / import 路径完全不动, `deduped = keep_candidates` 只覆盖变量, 不影响 `run.candidates` 的 schema.

## 与下游契约

- `candidates` 字段: 只有 `clean_status == "keep"` 的进入, quarantine/reject 仍计入 `clean_summary` 但不出现在 UI/import 路径
- `web_datasets`: 仅作为前端增强数据 (用户可看到 websearch 兜底结果), 不进入 import 流
- `literature_roles` / `module_matrix`: 仅作为前端增强数据 (论文角色 + 推荐组合), 不进入 import 流
- `import_candidates`: 行为不变, 仍从 `run.candidates` 取, 因为 `deduped` 已被 keep_candidates 覆盖

## 验证

- import 干净: `from app.services.retrieval.orchestrator import run_retrieval, _candidate_to_dict, _summarize_roles` → 通过
- 4 个新模块全部可独立 import, RetrievalRun 含新字段
- 单测 T5: `pytest apps/api/tests/test_session64_t5_orchestrator_integration.py -v` → **11 passed**
  - clean_summary 字段存在 + 4 个 key 完整
  - keep 数 <= 总数 (含 quarantine/reject)
  - clean_candidates 不可用时 fallback 干净
  - web_datasets / literature_roles / module_matrix 字段 + 各自 None fallback
  - gap_report / retry_round / candidates 不被破坏 (回归保护)
- 回归: S14 (19), S61 (19), S63 (13) 全部通过 — 共 **51 个测试无回归**

## 风险点 / 已知边界

- **candidate_cleaner 阈值默认**: 当前用 `domain="vision_2d"` 硬编码, 未来应从 `raw_topic` / project meta 推断. ponytail: 默认值已经能跑通 civil 题目, 真要精确 domain 判断时再扩.
- **web_dataset_search 不联网**: 按模块设计, 调用方喂 `search_payloads` 才会真解析; 否则走 `seed_known_datasets` (concrete-crack 等已知种子). 当前没有 LLM/WebSearch 调用方, 因此只能 seed 兜底.
- **module_matrix 输入简化**: literature_roles 是 `LiteratureRoleResult` 的 dict dump, orchestrator 只用 `role / base_framework / modules_added / code_url` 4 个字段. 其他字段 (risk_notes / borrowable_ideas) 丢弃. 后续若 UI 需要可补.
- **额外 trace 事件**: 8 个新 action 会让 trace 文件稍微变大. 每个 action 平均 4-7 个字段, 可控.

## 后续 (T6+)

- T6 (前端): 渲染 `module_matrix.recommended_combinations` + `literature_roles` 角色徽章
- T7 (前端): 在检索结果列表加 clean_status 标签 (keep/quarantine/reject/needs_manual)
- T8: 把 clean_candidates 的 `domain` 从 `raw_topic` 推断, 替代硬编码 `vision_2d`