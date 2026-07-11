# PaperAgent Re6.0：基线冻结 SOP

> **制定日期**：2026-07-11  
> **承接**：Re5.X 检索反思链路迁移性升级。  
> **周期**：2 个有效开发日。  
> **阶段门**：未冻结不得调整 prompt、router 或 provider 逻辑。  
> **后继**：R6-1 Provider Core、R6-2 Router Unification。

---

## 1. 目标与非目标

### 1.1 目标

冻结当前 provider/router、Re5 检索链路、prompt 模板与测试基线，形成可复现的
对照锚点。后续所有 Re6.X 改动均与此基线对比。

### 1.2 非目标

- 不修复基线中发现的 bug（记入风险清单，由后续阶段处理）；
- 不改变生产默认路径；
- 不做性能优化；
- 不冻结 hidden 测试集（hidden 集在 R6-5 冻结）。

---

## 2. 产物/输出清单

| 编号 | 产物 | 路径 | 格式 |
|---|---|---|---|
| D-01 | 基线报告 | `artifacts/re6/baseline/baseline_report.md` | Markdown |
| D-02 | 风险清单 | `artifacts/re6/baseline/risk_register.md` | Markdown |
| D-03 | 架构决策记录 | `docs/adr/R6-000-baseline-freeze.md` | ADR |
| D-04 | Provider/Router 快照 | `artifacts/re6/baseline/provider_router_snapshot.json` | JSON |
| D-05 | Prompt hash 清单 | `artifacts/re6/baseline/prompt_hashes.json` | JSON |
| D-06 | Fixture hash 清单 | `artifacts/re6/baseline/fixture_hashes.json` | JSON |
| D-07 | 测试结果快照 | `artifacts/re6/baseline/test_results.json` | JSON |

---

## 3. 规范

### 3.0 全局模型约束（Re6.X 全期）

**只允许使用以下两个模型（均通过 OpenCode proxy），禁止第三个模型：**

| model_id | 标识 | 用途 |
|---|---|---|
| `deepseek-v4-flash` | DeepSeek V4 Flash | structured_extract / search_control / formatter / rag_answer |
| `big-pickle` | Big Pickle | evidence_critic / novelty_draft / narrative_write / premium_review |

基线快照必须记录这两个模型为唯一允许的 model_id 白名单。

### 3.1 冻结范围

| 对象 | 冻结内容 | 冻结方式 |
|---|---|---|
| Provider Registry | 当前 `.env` 默认 provider、model、base_url | 记录 config_version |
| llm_router | `llm_router.py` 当前的 provider→provider 映射 | git commit hash |
| call_json | `llm.py` 当前的调用入口与 fallback 逻辑 | git commit hash |
| JSON repair | `json_repair.py` 3-phase 解析逻辑 | git commit hash |
| Re5 检索 | SearchController、SourceCatalog、query_ledger | git commit hash |
| Prompt 模板 | `agents/prompts/` 下所有模板文件 | SHA-256 逐文件 |
| 测试 fixture | Re5.X replay fixture、Re4 端到端 fixture | SHA-256 逐文件 |

### 3.2 基线报告必须包含

1. 当前 provider 配置摘要（不含 key）；
2. provider registry 与生产 llm_router 的关系现状（是否已统一）；
3. 已知双轨问题清单（registry vs router、formatter 专用字段等）；
4. Re5 检索链路的状态（template/llm/experiment 当前 arm）；
5. 测试通过率与已知跳过项；
6. 本期不可改动的文件列表。

### 3.3 风险清单格式

```markdown
| ID | 风险 | 影响 | 建议处理阶段 | 严重度 |
|---|---|---|---|---|
| R-001 | registry 切换不影响生产 call_json | 模型切换无效 | R6-2 | 高 |
```

### 3.4 Prompt hash 清单格式

```json
{
  "frozen_at": "2026-07-11T12:00:00Z",
  "files": {
    "agents/prompts/topic_parser.md": "sha256:abc123...",
    "agents/prompts/verifier.md": "sha256:def456..."
  }
}
```

### 3.5 ADR 必须说明

- 冻结的边界与例外；
- 后续阶段可修改冻结项的条件（须更新 ADR 并记录 diff）；
- 基线测试集与 hidden 集的隔离规则。

---

## 4. 验证

### 4.1 冻结完整性验证

| 验证项 | 方法 | 门槛 |
|---|---|---|
| Prompt hash 可复现 | 重新计算所有 prompt 文件 SHA-256 | 与清单完全一致 |
| Fixture hash 可复现 | 重新计算所有 fixture 文件 SHA-256 | 与清单完全一致 |
| git commit 可检出到当前状态 | `git checkout <baseline_commit>` 后运行 | 无 error |
| 基线测试可运行 | `pytest apps/api/tests -v` | 通过率与报告一致 |

### 4.2 基线报告审查

- [ ] 基线报告覆盖 §3.2 全部 6 项；
- [ ] 风险清单每条有严重度标注和阶段归属；
- [ ] ADR 经至少一人审查并签字；
- [ ] 快照 JSON 无 raw key（只含 `api_key_set: true/false`）。

### 4.3 阶段门

- 冻结产物全部生成且 hash 可复现 → 可进入 R6-1；
- 任一 hash 不可复现或基线测试无法运行 → 重新冻结。
