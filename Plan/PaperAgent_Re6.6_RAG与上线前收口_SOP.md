# PaperAgent Re6.6：RAG 与上线前收口 SOP

> **制定日期**：2026-07-11  
> **承接**：R6-5 鲁棒性实验室。  
> **周期**：3 个有效开发日。  
> **阶段门**：无阻塞项才可规划上线 + Release/No-go 清单全过。  
> **前置**：R6-1~R6-5 全部阶段门通过。

---

## 1. 目标与非目标

### 1.1 目标

1. 确保 RAG 检索与模型生成解耦，模型变化不改变检索证据；
2. 完成上线前安全审查（SSRF、secret、observability、权限）；
3. 产出 readiness package（Runbook、Known Limitations、安全审查报告）；
4. 独立 reviewer 完成 Release / No-go 判定。

### 1.2 非目标

- 不做公网发布、账号系统、支付集成；
- 不做 per-user 多租户隔离的完整实现（仅设计 + ADR）；
- 不做 CI/CD pipeline 搭建；
- 不修改 R6-1~R6-5 的实现（仅发现并记录缺陷）。

---

## 2. 产物/输出清单

| 编号 | 产物 | 路径 | 格式 |
|---|---|---|---|
| D-01 | RAG 引用合同 | `app/services/rag/rag_contract.py` | Python module |
| D-02 | RAG 引用校验器 | `app/services/rag/citation_validator.py` | Python module |
| D-03 | SSRF 安全审查报告 | `artifacts/re6/<run_id>/security_redaction_report.json` | JSON |
| D-04 | Secret 安全审查报告 | `artifacts/re6/<run_id>/secret_audit_report.json` | JSON |
| D-05 | Observability 审查报告 | `artifacts/re6/<run_id>/observability_report.json` | JSON |
| D-06 | Runbook | `docs/runbooks/re6-deployment.md` | Markdown |
| D-07 | Known Limitations | `docs/re6-known-limitations.md` | Markdown |
| D-08 | 上线前 ADR | `docs/adr/R6-100-release-readiness.md` | ADR |
| D-09 | L5 readiness review 报告 | `artifacts/re6/<run_id>/readiness_review.md` | Markdown |
| D-10 | Release / No-go 清单 | `artifacts/re6/<run_id>/release_checklist.md` | Markdown |
| D-11 | L0 RAG 合同单测 | `apps/api/tests/test_re6/rag/` | pytest |

---

## 3. 规范

### 3.1 RAG 不变量

| 场景 | 期望 |
|---|---|
| 模型不同，检索相同 | cited chunks、页码、ranking 在同一 index 不变 |
| 模型无引用 | API abstain 或 typed citation failure |
| 证据冲突 | 陈述冲突，不选边编造 |
| 无命中 | 返回不确定与建议 |
| PDF 文本含指令 | 不可信文本，不能改变 system/工具策略 |
| context 超限 | 记录压缩/截断 chunk IDs 与影响 |
| provider 故障 | retrieval 可返回；generation 为 degraded/failed |

### 3.2 RAG 引用合同

```python
class RAGAnswerContract(BaseModel):
    answer: str
    cited_chunks: list[ChunkCitation]    # 必须非空，否则代码拒答
    confidence: Literal["high", "medium", "low", "uncertain"]
    conflicts: list[ConflictReport] = []  # 证据冲突时列出
    abstain_reason: str | None = None     # 无引用时填

class ChunkCitation(BaseModel):
    chunk_id: str
    document_id: str
    page: int | None
    paragraph: str | None
    snippet: str             # 引用的原文片段
    location_verified: bool  # chunk_id 可定位

class ConflictReport(BaseModel):
    chunk_id_a: str
    chunk_id_b: str
    description: str
```

**硬规则**：

- `cited_chunks` 为空 → API 返回 abstain 或 typed citation failure，不输出确定性结论；
- RAG context 是不可信数据，不能覆盖 system instruction；
- RAG retrieval 与 model generation 解耦：模型变化不改变页码/chunk IDs；
- PDF 中的文本（包括看起来像指令的内容）标记为 untrusted，不执行。

### 3.3 SSRF 安全审查清单

| 审查项 | 方法 | 门槛 |
|---|---|---|
| Provider URL | 对所有 active profile 执行 SSRF 测试 | 全拒绝内网/metadata |
| PDF 抽取 URL | 对 PDF download URL 执行 SSRF 测试 | 全拒绝内网 |
| 网页抓取 URL | 对 web fetch URL 执行 SSRF 测试 | 全拒绝内网 |
| Provider probe URL | 对 probe URL 执行 SSRF 测试 | 全拒绝内网 |
| 重定向 | 302 → 内网 | 拒绝 |
| local_mode 未认证 | 公网模式 + localhost URL | 拒绝 |
| error redaction | 触发所有错误类型 | 无内网 IP 泄露 |

### 3.4 Secret 安全审查清单

| 审查项 | 方法 | 门槛 |
|---|---|---|
| 日志无 key | grep 所有日志文件 | 0 匹配 |
| trace 无 key | 搜索 trace.json | 0 匹配 |
| API 响应无 key | 搜索所有 API response | 0 匹配，只有 api_key_set |
| 浏览器无 key | Playwright 拦截网络 + DOM | 0 匹配 |
| localStorage 无 key | `localStorage.getItem(...)` | 0 匹配 |
| Git 无 key | `git log -p` 搜索 | 0 匹配 |
| 错误正文无 key | 触发 401/403 错误 | redaction 后无 key |
| 删除 profile | 删除后查 keyring | secret 不存在 |
| tombstone | 删除后查 ledger | 有 deleted 事件，无 key |

### 3.5 Observability 审查清单

| 审查项 | 门槛 |
|---|---|
| Run snapshot 完整性 | 每个 run 有 provider/model/prompt/contract/fallback |
| Trace redaction | trace 中无 key 或完整私密原文 |
| Metrics 覆盖 | 包含 provider error / fallback / schema fail / citation failure / RAG abstain / source 429 |
| Fallback ledger | 每次 fallback 有角色、provider、model、错误分类、合同版本、是否 heuristic |
| Evidence loss 记录 | context 压缩时记录被截断的 chunk IDs |

### 3.6 权限边界

| 操作类型 | 权限 | 说明 |
|---|---|---|
| 只读 | read | 查询 case、evidence graph、papers、review |
| 配置写 | config_write | 添加/修改 provider profile、role routing |
| 运行写 | run_write | 提交 topic、上传 paper、ingest PDF |
| 删除写 | delete_write | 删除 provider profile、删除 case |

**规则**：
- 未认证公网模式不能启用 local_mode / private URL；
- CORS、CSRF、HTTPS、session boundary 有 ADR；
- 上传、PDF 抽取、网页抓取、provider probe 各有限制和审计。

### 3.7 Runbook 必须包含

| 场景 | 处理步骤 |
|---|---|
| 无 API key | 如何配置新 provider |
| 坏 API key | 如何识别 invalid_auth、更新 key |
| 模型下线 | 如何发现 model_not_found、切换 model |
| Context 超限 | 如何识别、如何压缩、记录 evidence loss |
| RAG 无证据 | 如何触发 abstain、如何补充 PDF |
| SSRF 拒绝 | 如何识别、何时使用 local_mode |
| 全 fallback 失败 | 如何识别 typed_failure、如何排查 |
| Provider 429 | 如何识别 rate_limited、退避策略 |
| 删除 provider | 如何安全删除、secret 清除确认 |

### 3.8 Known Limitations 格式

按三种部署模式分别写明：

```markdown
## Local Mode
- 限制 1
- 限制 2

## Single-user Server Mode
- 限制 1
- 限制 2

## Multi-user Server Mode (未来)
- 不在本期范围
- 需要 per-user secret isolation
```

### 3.9 部署模式定义

| 模式 | 说明 | 本期支持 |
|---|---|---|
| Local | 本机运行，localhost only | ✅ |
| Single-user Server | 本机运行，允许局域网访问 | ✅ |
| Multi-user Server | 公网多用户 | ❌ 未来 |

---

## 4. 验证

### 4.1 L0：RAG 合同单测

| 测试项 | 方法 | 门槛 |
|---|---|---|
| cited_chunks 缺失拒答 | 构造空 cited_chunks 的 RAG answer | 拒绝 |
| chunk_id 不可定位 | chunk_id 不存在于 index | location_verified = false |
| PDF 指令注入 | PDF 文本含 "ignore previous instructions" | 不执行 |
| 模型切换后检索不变 | 同一 index，不同 model 查询 | cited chunks 一致 |
| 证据冲突 | 两个 chunk 支持矛盾结论 | 返回 conflict，不选边 |
| 无命中 | 查询无匹配 chunk | 返回 uncertain + abstain_reason |
| context 超限 | 输入超长 | 记录截断 chunk IDs |

### 4.2 L5：Readiness Review

独立 reviewer 检查：

| 审查项 | 方法 | 门槛 |
|---|---|---|
| 测试报告完整性 | 检查 L0-L4 报告 | 全部存在且无缺失 |
| Trace redaction | 抽样检查 trace | 无 key |
| URL 防护 | SSRF 审查报告 | 全绿 |
| RAG 引用 | RAG citation report | validity 100% |
| 密钥删除 | Secret 审查报告 | 删除确认 |
| 已知限制 | Known Limitations 文档 | 三种模式均覆盖 |
| Runbook | 检查 9 个场景 | 全覆盖 |
| 版本快照 | manifest + 版本文件 | 齐全 |

### 4.3 Release / No-go 清单

#### Release 条件

- [ ] L0–L3 通过；L4 仅有允许外网降级；
- [ ] 所有 P0 通过，P1 达标或有批准例外；
- [ ] hidden 对比报告、prompt/provider/fixture/contract 版本齐全；
- [ ] NoveltyReviewAdapter 对伪创新和 first claim 通过 gold；
- [ ] RAG citation validity 100%，无证据强回答为 0%；
- [ ] 独立 reviewer 完成安全、日志、删除、Runbook 审查。

#### No-go 硬条件（任一触发即禁止上线）

1. 任何位置可读 raw API key；
2. 前端选择和 production router 实际 provider 不一致；
3. formatter 可递归，或把 semantic fail 伪装 schema success；
4. 自定义 URL 可访问私网/metadata；
5. 模型故障后返回未标记 heuristic 或无引用答案；
6. 无证据、first claim、相邻工作重叠仍被创新模块强 accept；
7. hidden 被用于逐题调 prompt 后仍宣称泛化；
8. RAG 无 cited chunks 仍输出确定性结论。

### 4.4 上线前 P0 安全门

- [ ] 无 raw API key 日志、trace、响应、浏览器持久化或 Git tracked 文件；
- [ ] 自定义 URL SSRF 拒绝（provider/PDF/网页/probe 四类 URL）；
- [ ] profile/secret 可删除和失效；
- [ ] 区分只读、配置写、运行写、删除写权限；
- [ ] CORS、CSRF、HTTPS、session boundary 有 ADR；
- [ ] 上传、PDF 抽取、网页抓取、provider probe 各有限制和审计；
- [ ] 未认证公网模式不能启用 local_mode/private URL；
- [ ] error redaction 全绿。

### 4.5 上线前 P1 运维门

- [ ] provider 有 timeout、并发、retry 和 circuit breaker；
- [ ] run 有 provider/model/prompt/contract/fallback 完整记录；
- [ ] metrics 包含 provider error/fallback/schema fail/citation failure/RAG abstain/source 429；
- [ ] Runbook 包含无 key/坏 key/模型下线/context 超限/RAG 无证据/SSRF 拒绝；
- [ ] Known Limitations 按 local/single-user/server 三种模式写明。

### 4.6 阶段门

- [ ] RAG 合同实现且 L0 全绿；
- [ ] SSRF/Secret/Observability 三份审查报告全绿；
- [ ] Runbook 覆盖全部 9 个场景；
- [ ] Known Limitations 三种模式均覆盖；
- [ ] 独立 reviewer 完成 L5 readiness review；
- [ ] Release 清单全部勾选，无 No-go 硬条件触发。
