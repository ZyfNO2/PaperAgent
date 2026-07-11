# PaperAgent Re6.X：多模型与学术裁缝鲁棒性 总纲 SOP

> **制定日期**：2026-07-11  
> **承接**：Re4.0 工程化收口、Re5.X 检索反思迁移性升级。  
> **周期**：约 26 个有效开发日，以阶段门推进。  
> **终局目标**：安全接入用户自有模型；不同模型输出不破坏 Agent 合同；创新点具备
> 证据、可证伪性和独立审查；阶段结束时有跨模型、跨域、RAG 前置与未来上线的
> 可复验证据。  
> **路线图**：`Plan/PaperAgent_Re6.X_多模型与学术裁缝鲁棒性路线图.md`  
> **验收规范**：`Plan/PaperAgent_Re6.X_鲁棒性_跨域_RAG上线验收规范.md`  
> **子 SOP**：R6.0–R6.6 共 7 份。

---

## 0. 全局模型约束

**本期所有 LLM 调用只允许使用以下两个模型（均通过 OpenCode proxy 接入）：**

| 模型 | 标识 | 用途 |
|---|---|---|
| DeepSeek V4 Flash | `deepseek-v4-flash` | fast_json / structured_extract / search_control / formatter / rag_answer |
| Big Pickle | `big-pickle` | evidence_critic / novelty_draft / narrative_write / premium_review |

**约束规则**：

- 禁止引入第三个模型；ProviderProfile 只能注册这两个模型对应的 OpenCode provider。
- ModelPolicy 的 primary 和 fallback 只能从这两个模型中选择。
- Cross-model 模式（R6.4）限定为 `deepseek-v4-flash` 生成 + `big-pickle` 审查，或反过来。
- 模型发现（discovery）与能力探测（probe）仍需实现，但运行时只绑定这两个 model_id。
- 前端 Role Routing Matrix 的 model dropdown 只列出这两个模型。
- hidden 盲测和 gold set 的 model 矩阵以这两个模型为唯一变量。

---

## 1. SOP 索引

| SOP | 标题 | 周期 | 阶段门 | 文件 |
|---|---|---:|---|---|
| R6.0 | 基线冻结 | 2d | 冻结产物全部生成且 hash 可复现 | `PaperAgent_Re6.0_基线冻结_SOP.md` |
| R6.1 | Provider Core | 4d | 无 raw key 泄露 + SSRF 全绿 + API v2 可用 | `PaperAgent_Re6.1_Provider_Core_SOP.md` |
| R6.2 | Router Unification | 4d | registry 切换影响新 run + 节点专属合同 + formatter 无递归 | `PaperAgent_Re6.2_Router_Unification_SOP.md` |
| R6.3 | React Settings | 3d | 浏览器无 raw key + Wizard 全流程 + snapshot viewer | `PaperAgent_Re6.3_React_Settings_SOP.md` |
| R6.4 | 学术裁缝 2.0 | 5d | 无证据/first claim 不可通过 + 五项测试 + evolution log | `PaperAgent_Re6.4_学术裁缝2.0_SOP.md` |
| R6.5 | 鲁棒性实验室 | 5d | P0/P1 达标 + hidden 报告完成 + 无 No-go | `PaperAgent_Re6.5_鲁棒性实验室_SOP.md` |
| R6.6 | RAG 与上线前收口 | 3d | Release 清单全过 + 无阻塞项 | `PaperAgent_Re6.6_RAG与上线前收口_SOP.md` |

---

## 2. 依赖关系

```
R6.0 基线冻结
  └─→ R6.1 Provider Core
        └─→ R6.2 Router Unification
              ├─→ R6.3 React Settings
              └─→ R6.4 学术裁缝 2.0
                    └─→ R6.5 鲁棒性实验室
                          └─→ R6.6 RAG 与上线前收口
```

**关键约束**：R6.1 或 R6.2 的安全/合同门失败时，暂停 R6.3（UI）和 R6.4（学术裁缝），
优先修底座。

---

## 3. 产物总览

### 3.1 代码产物

| 模块 | SOP | 说明 |
|---|---|---|
| `security/url_safety.py` | R6.1 | SSRF 防护 |
| `providers/profile.py` | R6.1 | ProviderProfile schema |
| `providers/secret_store.py` | R6.1 | 密钥安全存储 |
| `providers/adapters/` | R6.1 | 协议适配器 |
| `providers/discovery.py` | R6.1 | 模型发现 |
| `providers/probe.py` | R6.1 | 能力探测 |
| `providers/errors.py` | R6.1 | 错误类型枚举 |
| `providers/ledger.py` | R6.1 | Provider ledger |
| `api/v1/providers.py` | R6.1 | Provider 管理 API v2 |
| `router/model_policy.py` | R6.2 | ModelPolicy schema |
| `router/envelope.py` | R6.2 | ResponseEnvelope |
| `router/contracts.py` | R6.2 | StructuredOutputContract 注册表 |
| `router/unified_router.py` | R6.2 | 统一路由器 |
| `router/repair.py` | R6.2 | 有界 repair |
| `router/snapshot.py` | R6.2 | Run snapshot |
| `router/validators/` | R6.2 | 语义校验器 |
| `agents/graph/schemas/evidence_schema.py` | R6.4 | 创新点 schema |
| `agents/graph/nodes/novelty_*.py` | R6.4 | 学术裁缝节点 |
| `agents/prompts/novelty_*.md` | R6.4 | Prompt A/B/C |
| `rag/rag_contract.py` | R6.6 | RAG 引用合同 |
| `rag/citation_validator.py` | R6.6 | RAG 引用校验 |
| `web-react/src/pages/Settings.tsx` | R6.3 | 前端设置页 |
| `web-react/src/components/settings/` | R6.3 | 前端组件 |

### 3.2 文档产物

| 文档 | SOP |
|---|---|
| 基线报告 + 风险清单 | R6.0 |
| ADR R6-000（基线冻结） | R6.0 |
| ADR R6-100（上线前 readiness） | R6.6 |
| Runbook | R6.6 |
| Known Limitations | R6.6 |
| THIRD_PARTY_NOTICES 更新 | R6.4 |

### 3.3 测试产物

| 产物 | SOP | 层级 |
|---|---|---|
| Provider L0 单测 | R6.1 | L0 |
| Provider L1 emulator 测试 | R6.1 | L1 |
| Router L0 合同单测 | R6.2 | L0 |
| Router L1 emulator 测试 | R6.2 | L1 |
| Router L2 replay 测试 | R6.2 | L2 |
| Settings Playwright e2e | R6.3 | — |
| Novelty L0 单测 | R6.4 | L0 |
| Novelty gold set | R6.4 | — |
| Emulator 套件 | R6.5 | L1 |
| Hidden-OOD 跨域集 | R6.5 | L3 |
| Failure 注入集 | R6.5 | L3 |
| RAG gold set | R6.5 | L3 |
| L2 replay 对比报告 | R6.5 | L2 |
| L3 hidden 盲测报告 | R6.5 | L3 |
| Fallback chaos 报告 | R6.5 | L3 |
| RAG 合同单测 | R6.6 | L0 |
| L5 readiness review | R6.6 | L5 |

### 3.4 试验报告目录

```
artifacts/re6/<run_id>/
  manifest.json
  provider_snapshot.json
  model_policy.json
  prompt_hashes.json
  contract_versions.json
  fixture_hashes.json
  per_case_results.jsonl
  fallback_ledger.jsonl
  security_redaction_report.json
  secret_audit_report.json
  observability_report.json
  novelty_review_report.json
  rag_citation_report.json
  aggregate_metrics.md
  failures.md
  readiness_review.md
  release_checklist.md
```

---

## 4. 测试分层总览

| 层级 | 内容 | 负责SOP | 门槛 |
|---|---|---|---|
| L0 | 静态合同 / 安全单测 | R6.1/R6.2/R6.4/R6.6 | 100% 全绿 |
| L1 | Provider emulator 集成 | R6.1/R6.2 | error class + trace 一致 |
| L2 | 固定 replay 端到端 | R6.2/R6.5 | 同 fixture 下对比 |
| L3 | 跨模型 / 跨域 hidden 盲测 | R6.5 | prompt 冻结后不可调 |
| L4 | 小规模 live smoke | R6.5 | 限 token / 限并发 |
| L5 | Readiness review | R6.6 | 独立 reviewer 审查 |

---

## 5. 验收指标汇总

### 5.1 P0（硬门，100%）

| 指标 | SOP | 门槛 |
|---|---|---|
| Raw key 泄露 | R6.1/R6.3/R6.6 | 0%（日志/trace/响应/浏览器/Git） |
| SSRF 拒绝 | R6.1/R6.6 | 全绿（loopback/private/metadata/redirect） |
| Silent degradation | R6.2/R6.5 | 0% |
| Repair recursion | R6.2/R6.5 | 0% |
| Attribution completeness | R6.2/R6.5 | 100% |
| Semantic contract pass | R6.2/R6.5 | 100% 或 typed failure |
| Evidence ID binding | R6.4 | Problem/Method/Insight 各至少一个 |
| First claim 降级 | R6.4 | 100% |
| 无证据强 claim | R6.4 | 0% 误放行 |
| Evolution log append-only | R6.4 | 不覆盖历史 |
| RAG citation validity | R6.5/R6.6 | 100% |
| RAG 无证据强回答 | R6.5/R6.6 | 0% |
| Error redaction | R6.6 | 全绿 |
| Profile/secret 删除 | R6.1/R6.6 | 同步删除 |

### 5.2 P1（质量门）

| 指标 | SOP | 门槛 |
|---|---|---|
| P-M-I 完整且逻辑连通 | R6.4/R6.5 | ≥ 85% |
| 伪创新风险召回 | R6.4/R6.5 | ≥ 80% |
| 可证伪命题可执行率 | R6.4/R6.5 | ≥ 85% |
| 相邻工作重叠识别 | R6.4/R6.5 | 比 control 高 ≥ 10pp |
| reviewer independence 标注 | R6.4/R6.5 | 100% |
| No-answer precision | R6.5/R6.6 | ≥ 90% |
| Supporting chunk recall@5 | R6.5/R6.6 | ≥ 80% |
| Hidden role coverage@budget | R6.5 | 比 control 高 ≥ 10pp |
| Provider timeout/并发/retry | R6.6 | 有配置 |
| Metrics 覆盖 | R6.6 | 6 项全覆盖 |

---

## 6. No-go 硬条件

任一触发即禁止进入上线设计：

1. 任何位置可读 raw API key；
2. 前端选择和 production router 实际 provider 不一致；
3. formatter 可递归，或把 semantic fail 伪装 schema success；
4. 自定义 URL 可访问私网/metadata；
5. 模型故障后返回未标记 heuristic 或无引用答案；
6. 无证据、first claim、相邻工作重叠仍被创新模块强 accept；
7. hidden 被用于逐题调 prompt 后仍宣称泛化；
8. RAG 无 cited chunks 仍输出确定性结论。

---

## 7. 完成标准

- [ ] 用户可完成 URL/key/protocol/model 的 validate、discover、probe 与 role binding。
- [ ] provider registry 和生产 router 已统一；新 run 有不可变 snapshot。
- [ ] 所有 structured node 使用节点专属输出合同；formatter 无递归和字段污染。
- [ ] fallback 可解释；不可恢复错误不静默变成功。
- [ ] NoveltyReviewAdapter 已实现三层主张、伪创新、可证伪、演化日志方法。
- [ ] 创新点均有 evidence binding；无证据/first claim 不能包装为已证实。
- [ ] 跨模型、跨域、fallback、RAG、密钥与 URL 安全验收通过。
- [ ] 测试证据、模型版本、prompt hash、fixture hash 和已知限制已归档。
