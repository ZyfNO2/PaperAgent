# PaperAgent v0.1 验收标准

> Version: `v0.1`  
> Status: `RELEASE GATE`

## 1. 验收目标

v0.1 的发布目标不是功能完整，而是证明以下命题：

```text
PaperAgent 已从零建立一个测试驱动、可运行、可恢复、可审计且有界终止的 LangGraph 骨架。
```

只有全部 P0 条件通过，才允许将 `v0.1` 合并回 `master`。

## 2. P0 必须通过

### 2.1 仓库与隔离

- [ ] 新实现不导入 backup 分支代码；
- [ ] 不存在旧节点 alias、旧 ResearchState、Re1—Re8 字段；
- [ ] 不复制旧 Prompt 和测试 fixture；
- [ ] 依赖和目录符合 v0.1 文档；
- [ ] 所有生产代码位于 `src/paperagent/`。

### 2.2 TDD 证据

- [ ] 每个工作包存在先失败后通过的测试提交；
- [ ] Bug 修复均有复现测试；
- [ ] LLM 节点使用固定 fixture 完成离线测试；
- [ ] Fake Provider 不按 Prompt 关键词选答案；
- [ ] 未知 fixture key 明确失败；
- [ ] 默认测试不访问网络。

### 2.3 Schema 与 State

- [ ] 所有 Pydantic schema `extra="forbid"`；
- [ ] schema_version 和 engine_version 正确；
- [ ] 跨字段不变量有测试；
- [ ] State patch 不原地修改输入；
- [ ] Trace 使用 append reducer；
- [ ] Artifact 使用明确 replace 语义；
- [ ] State 可 JSON round trip；
- [ ] State 不包含 secret、Provider 实例或原始 CoT。

### 2.4 Node 合同

每个节点：

- [ ] happy path；
- [ ] invalid input；
- [ ] Provider/tool failure；
- [ ] Trace start/completed/failed；
- [ ] deterministic repeat；
- [ ] no input mutation；
- [ ] only allowed State fields；
- [ ] typed error。

### 2.5 Graph 路径

以下路径必须以真实 compiled LangGraph + Fake Providers 通过：

- [ ] happy_path；
- [ ] planning_need_human；
- [ ] planning_blocked；
- [ ] retrieval_retry；
- [ ] retrieval_exhausted；
- [ ] repair_method；
- [ ] repair_retrieval；
- [ ] provider_timeout；
- [ ] checkpoint_resume；
- [ ] budget_hard_stop。

每个路径断言：

- [ ] visited node sequence；
- [ ] LLM call count；
- [ ] Search call count；
- [ ] terminal status；
- [ ] route Trace；
- [ ] 最终 Artifact schema。

### 2.6 有界执行

- [ ] 正常路径核心 LLM 调用不超过 4；
- [ ] 总核心 LLM 调用不超过 6；
- [ ] Retrieval 不超过 2 轮；
- [ ] Method repair 不超过 1 次；
- [ ] 同时最多 1 个 active human interrupt；
- [ ] 达到预算后明确 blocked/partial，不无限循环；
- [ ] LangGraph recursion limit 有配置和测试。

### 2.7 Evidence 安全

- [ ] synthesis 只接收 accepted evidence；
- [ ] rejected/pending/failed evidence 不进入 LLM context；
- [ ] 所有输出 Evidence ID 可解析；
- [ ] report 不引入新 locator；
- [ ] method status 固定 proposed；
- [ ] 无证据时不生成确定性实验结论；
- [ ] blocked report 明确限制。

### 2.8 Trace 与 Checkpoint

- [ ] 每个节点有 started/completed/failed；
- [ ] 每次路由有 route.decided；
- [ ] LLM Trace 含 task、prompt/schema version、usage；
- [ ] Tool Trace 含 query、attempt、error metadata；
- [ ] payload 只保存 hash 或脱敏摘要；
- [ ] interrupt 前状态可恢复；
- [ ] resume 不重复已完成副作用；
- [ ] final snapshot 可读取。

### 2.9 OOD 与泄漏

OOD 至少覆盖：

- [ ] CV；
- [ ] NLP；
- [ ] 推荐系统；
- [ ] 时间序列；
- [ ] 数据库；
- [ ] 软件工程；
- [ ] 信息不足；
- [ ] 不可完成请求。

全部要求：

- [ ] schema valid；
- [ ] 路由合理；
- [ ] 有界终止；
- [ ] 不出现 legacy fixture 专有实体；
- [ ] 不引用未知 Evidence ID；
- [ ] 不通过领域关键词选择固定输出。

## 3. 覆盖率门禁

| 范围 | Line | Branch |
|---|---:|---:|
| schemas / validators | ≥95% | ≥90% |
| routers / gates | 100% | 100% |
| nodes | ≥90% | ≥85% |
| retrieval subgraph | ≥90% | ≥90% |
| graph orchestration | ≥85% | ≥85% |
| overall | ≥90% | ≥85% |

覆盖率不替代行为测试。即使覆盖率达标，缺少关键路径仍验收失败。

## 4. 静态质量门禁

- [ ] ruff check；
- [ ] ruff format check；
- [ ] typecheck；
- [ ] 无循环 import；
- [ ] 无未使用 Provider 依赖；
- [ ] 无硬编码 API key；
- [ ] Prompt/fixture 泄漏扫描；
- [ ] 依赖最小化；
- [ ] package 可安装和导入。

## 5. 性能与确定性

离线 Fake Provider 基准：

- [ ] happy path 运行结果完全确定；
- [ ] 相同输入、相同 fixture 得到相同最终 State hash；
- [ ] 单次 full graph offline test 不依赖 sleep；
- [ ] 单元测试组应保持秒级；
- [ ] 无随机 flaky test；
- [ ] 失败测试可重复复现。

v0.1 不规定真实模型延迟 SLA，但必须记录调用次数、token 和 duration metadata。

## 6. Fixture 验收

- [ ] `planning/happy_path`；
- [ ] `planning/need_human`；
- [ ] `planning/blocked`；
- [ ] `evidence_synthesis/happy_path`；
- [ ] `method_design/happy_path`；
- [ ] `method_design/gate_repair_method` call 0/1；
- [ ] `report/happy_path`；
- [ ] `report/blocked`；
- [ ] malformed JSON；
- [ ] unknown field；
- [ ] unknown Evidence ID；
- [ ] Provider timeout；
- [ ] Fake Search success/empty/partial failure/timeout。

Fixture 必须和 `LLM_TEST_FIXTURES.md` 一致。

## 7. 文档验收

- [ ] README 文档索引完整；
- [ ] EXECUTION_PLAN 与实现顺序一致；
- [ ] GRAPH_AND_NODES 与 compiled graph 一致；
- [ ] STATE_CONTRACTS 与 Pydantic/TypedDict 一致；
- [ ] TDD_STRATEGY 与测试目录一致；
- [ ] LLM_TEST_FIXTURES 与 fixture 文件一致；
- [ ] DEVELOPMENT_WORKFLOW 与提交历史一致；
- [ ] ACCEPTANCE 可被逐项验证。

## 8. P1 建议通过

P1 不阻塞 v0.1 骨架发布，但建议完成：

- [ ] README 中提供一个 Fake Provider demo；
- [ ] 生成 Mermaid graph 或 ASCII graph；
- [ ] 提供一次 checkpoint/resume 演示；
- [ ] 提供测试输出示例；
- [ ] 一个真实 LLM adapter smoke test；
- [ ] 一个真实 Search adapter smoke test；
- [ ] 简单调用成本报告。

## 9. 明确不作为 v0.1 验收项

- Web UI；
- 多用户生产部署；
- Postgres checkpoint；
- Multi-Agent；
- 长期记忆；
- 自动运行用户代码；
- 自动写完整论文；
- LangSmith/RAGAS 深度集成；
- 复杂并发和任务队列；
- 真实学术效果优于 baseline。

## 10. 合并前最终命令

实现阶段确定工具后，至少提供等价命令：

```bash
ruff check .
ruff format --check .
pytest tests/unit tests/contracts tests/nodes -q
pytest tests/graph tests/integration -q
pytest tests/ood -q
pytest --cov=paperagent --cov-branch --cov-report=term-missing
```

真实 Provider 测试必须单独运行，不能混入默认验收。

## 11. Release Decision

仅允许三种结论：

```text
PASS
PASS WITH P1 DEBT
FAIL
```

不允许使用“基本通过”掩盖 P0 缺失。

合并记录必须包含：

- commit SHA；
- 测试命令和结果；
- coverage；
- graph path matrix；
- fixture version；
- 已知 P1 debt；
- rollback 指向 `backup/legacy-pre-v0.1-20260716` 或上一个 master SHA。
