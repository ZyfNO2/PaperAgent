# PaperAgent Academic RAG Batch 5 收口任务书

## 1. 任务定位

本任务只完成 PaperAgent 对 PaperClaw Batch 5 正式 RetrievalService REST/OpenAPI 契约的消费、验证和跨仓 fixture 闭环，不进入 Query Planner、高级 Evidence Reasoning、补救检索策略、Relation Graph、Coding Worker、真实论文 Benchmark 或 P0 Release 宣告。

当前基线：

- 仓库：`ZyfNO2/PaperAgent`
- 分支：`codex/academic-rag-h3-reasoning`
- 文档 head：`acd7f0530bd61edef920e457953ae0e8380cd6c8`
- 已验证实现 head：`7faaabd6989fd92d8eb3b9cbadf30fc73484a5cd`
- 当前 adapter：`PaperClawAcademicEvidenceSource`
- 当前优先 seam：正式 `RetrievalService.search/resolve_locator`
- 旧 `AcademicRuntime` seam：仅短期兼容，不得继续扩展为平行接口
- 当前真实 PDF tracer：parse → index → RetrievalService → Evidence Ledger → locator resolve → PNG SHA-256 readback

开始开发前必须重新检查分支 HEAD、adapter、contracts、tests、OpenAPI/HTTP client 现状、Handoff 和受保护文件，不能用本任务书覆盖更晚实现。

## 2. 本批次目标

在 PaperClaw 先冻结 Batch 5 REST/OpenAPI 后，完成以下能力：

1. 消费 canonical RetrievalService REST/OpenAPI；
2. 将 REST 响应规范化为现有 PaperAgent evidence/domain 对象；
3. 对 schema/index/hash/locator/asset integrity 异常 fail closed；
4. 冻结与 PaperClaw 对应的跨仓 canonical fixtures；
5. 保持 in-process Python seam 与 REST seam 的语义一致性；
6. 完成真实 PDF 跨仓 REST tracer 和重启验证。

完成后状态仍应是：

```text
Batch 5: COMPLETE
P0 Release: NO-GO / pending real benchmark and human acceptance
```

## 3. 强制边界

### 3.1 禁止提前实现

本批次不得新增或扩展：

- Query classification、decomposition、rewrite、routing policy；
- bounded corrective retrieval 的决策逻辑；
- LLM/VLM Provider 调用；
- baseline/module/gap/compatibility/experiment reasoning；
- Relation Graph；
- Coding Worker；
- 真实论文 Benchmark、专家 adjudication 或质量分数；
- 与 RetrievalService 消费无关的任务编排、Web UI 或 Runtime 重构。

现有 Evidence Ledger 只用于验证入口和 locator 绑定，不在本批扩展高级判定语义。

### 3.2 受保护内容

不得提交：

- `.venv-paperagent/` 或其他虚拟环境；
- `output/`；
- 真实或受保护 PDF；
- `data/`；
- `academic/claims.py`；
- `academic/factory.py`；
- `academic/planner.py`；
- Secret、Token、API Key；
- 与本任务无关的生成产物。

提交前必须检查 tracked/untracked 状态并运行待发布范围 secret scan。

### 3.3 依赖顺序

- PaperClaw 是 RetrievalService 业务语义、REST 字段和 OpenAPI 的唯一真源。
- PaperAgent 不得先行发明字段后要求 PaperClaw 适配。
- PaperClaw 契约未冻结时，可以准备 adapter skeleton、validator 和测试工具，但不得手写并宣称 canonical fixture 已完成。
- 任何跨仓差异必须以验证后的 PaperClaw endpoint/OpenAPI 为准，并记录为 blocked 或 contract mismatch。

## 4. Workstream A：REST/OpenAPI client seam

### 4.1 设计原则

先检查仓库现有 HTTP client、Provider adapter、retry/timeout/budget、Pydantic/dataclass、error taxonomy 和 dependency injection 方式。复用既有架构，不引入第二套通用 SDK。

建立一个窄接口消费 PaperClaw 已冻结的 RetrievalService REST。命名按现有项目风格确定，可为 `PaperClawRetrievalClient`、`PaperClawRetrievalServiceClient` 或等价类型。

REST client 只负责：

- request validation 与 canonical serialization；
- bounded timeout/retry；
- HTTP status/error payload 映射；
- response schema validation；
- 转换为现有 PaperAgent evidence/domain contracts；
- trace 中记录可公开的 request/response metadata；
- 不复制 PaperClaw 检索、rerank、neighbor、asset budget 或 locator resolve 业务逻辑。

### 4.2 必须支持的能力

依据 PaperClaw 最终 OpenAPI，至少消费：

1. search；
2. locator resolve；
3. page/region asset readback；
4. index status/manifest inspection。

请求必须保留并验证：

- project identity；
- query；
- paper/version/object filters；
- bounded top-k；
- neighbor count；
- asset byte budget；
- schema/index version；
- 调用预算和 timeout。

响应必须保留并验证：

- `EvidenceBundle` canonical identity；
- paper/version/source hash；
- object identity/type/page/reading order；
- locator；
- asset metadata/hash；
- truncation/budget state；
- generation/index/schema metadata；
- trace/stop reason 中允许公开的字段。

## 5. Workstream B：错误与完整性 fail-closed

### 5.1 错误映射

将 PaperClaw 稳定错误模型映射为 PaperAgent 可区分的 typed failure，至少包括：

- project/paper/version/object not found；
- locator stale/not found；
- index not ready；
- stale academic schema；
- stale index version；
- model/encoder fingerprint mismatch；
- manifest/content hash mismatch；
- asset SHA-256 mismatch；
- invalid request/budget；
- timeout；
- transport failure；
- malformed or unknown response schema。

不得将这些状态统一吞为 `[]`、`None` 或“证据不足”。技术完整性失败与正常 zero-hit 必须分开。

### 5.2 身份校验

在 evidence 进入 Ledger 前至少验证：

```text
paper_id
version_id
source_hash
object_id
object_type
page_number
locator identity
asset hash
schema version
index version
```

REST payload 与 locator、resolved object 或 asset metadata 冲突时必须拒绝整个相关 evidence item；关键 bundle-level metadata 冲突时拒绝整个 bundle。

### 5.3 预算与截断

- 尊重 PaperClaw 返回的 asset byte budget 和 truncation state；
- 不自动二次下载被预算截断的资产；
- 不把 truncated asset 当作完整 PNG；
- neighbor expansion 数量不得在 PaperAgent 侧隐式放大；
- retry 不得重复产生有副作用调用；
- trace 中记录 retry、timeout、bytes、truncation 和失败原因，但不得记录 Secret 或本地绝对路径。

## 6. Workstream C：Python seam 与 REST seam 语义一致性

现有 in-process 正式 `RetrievalService` seam 仍可用于离线/同进程测试。REST seam 必须与它共享同一 PaperAgent normalization path，避免两套 evidence 解释。

要求：

- 同一个 canonical fixture 经 Python seam 和 REST seam 进入 PaperAgent 后，标准化 evidence、locator identity、Ledger binding 和可见 trace 语义一致；
- 差异只允许存在于 transport metadata；
- 旧 `AcademicRuntime` 兼容 seam 不新增功能；
- 如果保留 fallback，必须显式配置且默认不掩盖正式 RetrievalService/REST 错误；
- stale/integrity failure 不得 fallback 到旧 runtime 后伪装成功；
- 为未来删除旧 seam 记录清晰 deprecation 边界，但本批不做无关大重构。

## 7. Workstream D：跨仓 canonical fixtures

### 7.1 fixture 来源

fixture 必须由 PaperClaw 真实 serializer/endpoint test 生成或验证，PaperAgent 不得自行编造。

至少消费并冻结：

1. successful search `EvidenceBundle`；
2. locator resolve；
3. index status/manifest；
4. stale schema/index error；
5. integrity/hash failure；
6. asset byte budget/truncation；
7. zero-hit but healthy response；
8. page/region asset metadata/readback。

### 7.2 一致性方式

优先使用 byte-equivalent canonical JSON；若因仓库格式化或包裹结构只能 canonical-equivalent，必须：

- 定义稳定 JSON canonicalization；
- 排序和数字/布尔/null 语义固定；
- 计算并记录 SHA-256；
- 测试中比较 canonical bytes/hash；
- Handoff 明确说明不是原始文件 byte-equivalent 的原因。

OpenAPI contract 需要对应 schema/golden 校验，确保 PaperClaw `$ref` 与 PaperAgent client model 不漂移。

## 8. Workstream E：真实 PDF 跨仓 REST tracer

在不提交真实 PDF 的前提下，使用仓库现有临时/生成 fixture 或测试时创建的最小真实 PDF，完成：

```text
PaperClaw import
→ parse
→ incremental sync/upsert
→ REST search
→ PaperAgent client validation
→ evidence normalization
→ Evidence Ledger binding
→ REST locator resolve
→ page/region asset readback
→ PNG SHA-256 verification
→ service/client restart
→ repeat search/resolve
```

必须验证：

- 新 version upsert 后可按 version 查询；
- 删除旧 version 后 PaperAgent 不再收到幽灵结果；
- stale index 时 client 得到 typed failure；
- rebuild 后恢复；
- restart 前后 evidence identity 和 locator 一致；
- budget 截断可见且不会被当作完整资产；
- 正常 zero-hit 与技术失败可区分。

该 tracer 仍属于离线工程验证，不得描述为真实科学质量 Benchmark。

## 9. 测试矩阵

至少包含以下测试：

### 9.1 Contract tests

- OpenAPI 可解析；
- required fields、enums、limits 和 `$ref` 符合预期；
- client request serialization 与 PaperClaw fixture 一致；
- response validation 能拒绝缺字段、未知破坏性结构和错误类型；
- schema/index version 不匹配 fail closed。

### 9.2 Adapter tests

- successful search → canonical evidence；
- zero-hit healthy response；
- locator resolve；
- page/region asset readback；
- stale locator；
- asset hash mismatch；
- malformed JSON；
- timeout/retry budget；
- server 4xx/5xx typed mapping；
- truncation/budget state 保留；
- Python seam/REST seam parity；
- 旧 seam 不掩盖 integrity failure。

### 9.3 Cross-repo tests

- PaperClaw producer fixture hash 与 PaperAgent consumer fixture hash 一致；
- real PDF REST tracer；
- version upsert；
- deletion/ghost result；
- stale/rebuild；
- restart persistence。

不得只用 Mock HTTP 返回成功 payload 来替代至少一条真实 ASGI/test-server 或实际本地服务路径。

## 10. 验证要求

### 10.1 定向验证

运行并记录：

- Academic adapter/client tests；
- OpenAPI/fixture contract tests；
- Python seam/REST seam parity tests；
- error taxonomy tests；
- real PDF cross-repo REST tracer；
- restart tests；
- mypy 对新增 client/model 全覆盖。

### 10.2 全量验证

按仓库既有方式运行：

- Ruff/lint/format；
- mypy；
- Python 3.11/3.12 tests；
- full offline pytest；
- wheel/sdist build；
- Gitleaks 待发布范围扫描。

必须明确区分：

- mock transport unit tests；
- ASGI/local service integration；
- real PDF offline tracer；
- 尚未执行的真实 Provider、真实 LLM、真实 Benchmark 和人工验收。

## 11. 完成标准

只有全部满足时 PaperAgent 的 Batch 5 消费侧才可标记完成：

- PaperClaw REST/OpenAPI 已冻结且可由 client 解析；
- 成功、zero-hit、stale、integrity、budget/truncation 语义均可区分；
- REST payload 在进入 Ledger 前完成 canonical identity 和 hash 校验；
- Python seam 与 REST seam 标准化结果一致；
- 旧 `AcademicRuntime` seam 不再扩展且不会掩盖正式错误；
- 跨仓 fixtures canonical bytes/hash 一致；
- real PDF REST tracer、version upsert、删除/幽灵结果、stale/rebuild、restart 全部通过；
- clean clone、build、CI 全绿；
- 两仓 Handoff Git blob 再次完全一致；
- Query Planner、高级推理、真实 Benchmark 和人工验收仍标记 `pending`；
- `P0 Release` 仍标记 `NO-GO`。

## 12. 提交与 Handoff

按合理节点拆分提交，建议但不强制：

1. `feat(academic): add PaperClaw retrieval REST client`
2. `fix(academic): fail closed on retrieval contract drift`
3. `test(academic): freeze cross-repo retrieval fixtures`
4. `test(academic): trace real PDF retrieval over REST`
5. `docs(academic): close Batch 5 consumer handoff`

最终 Handoff 必须记录：

- 分支和最终 SHA；
- PaperClaw OpenAPI/fixture 所绑定的 commit SHA；
- client、models、adapter、fixtures 和 tests 的主要文件；
- Python seam/REST seam/旧 seam 的最终边界；
- error taxonomy；
- canonical fixture hash；
- 所有测试、CI run、build、clean clone 和 secret scan；
- 尚未执行的真实 Benchmark、真实 LLM 和人工验收；
- 已知限制；
- 下一阶段只有在双仓 Batch 5 GO 后才能进入 Query Planner。

不要自动合并默认分支，不要删除现有分支，不要把 P0 状态写成 GO。