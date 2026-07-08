# PaperAgent Re2 — 执行简报

> **本文件是给执行 AI (Coding AI) 的唯一入口文档。**
> 完整设计见 `docs/design/PaperAgent_Re2_FullChain_Design.md`。

---

## 你是谁、要做什么

你是 PaperAgent Re2 的执行 AI。你的任务是在现有 Re1.2 的 14 节点 LangGraph 管道上，新增 6 个节点 + 性能优化 + 简易前端 + 自测框架，让系统从"只能搜论文"升级为"输入题目 → 输出保毕业工作方案"。

---

## 最终目标

用户输入一个研究生题目（如"基于YOLOv5的钢材表面缺陷检测研究"），系统在 **5 分钟内** 输出：

1. **搜索结果** — 论文 / repo / dataset，已验证可访问
2. **可行性判断** — 能不能保毕业？100+1+1+1 评分
3. **创新点** — A+B+C 缝合方案，具体怎么缝
4. **SOTA 对比** — 该和谁比、比什么指标
5. **叙事** — "3个问题 + 1个Nick模型"的故事
6. **退化路线** — 做不了怎么退
7. **审查** — 5 维评分，有没有编造

用户通过一个简易 HTML 页面操作，搜索结果逐条流入显示。

---

## 约束参考 — 你必须读的文件

### 🔴 必读（不读不能开工）

| 文件 | 路径 | 为什么要读 |
|---|---|---|
| **完整设计文档** | `docs/design/PaperAgent_Re2_FullChain_Design.md` | 你要实现的全部内容都在这里 |
| **AGENTS.md** | `AGENTS.md` | 项目工程规则：并发优先、API 兼容扩展、工程决策透明化 |

### 🟡 应读（实现前需了解现状）

| 文件 | 路径 | 你需要从中提取什么 |
|---|---|---|
| **现有 Graph** | `apps/api/app/services/agents/graph/research_graph.py` | 现有 14 节点怎么连的、条件边怎么写的 |
| **现有 State** | `apps/api/app/services/agents/graph/state.py` | ResearchState 当前字段，你要扩展它 |
| **节点注册表** | `apps/api/app/services/agents/graph/nodes/__init__.py` | 节点怎么注册的、REGISTRY 格式 |
| **现有 verify 节点** | `apps/api/app/services/agents/graph/nodes/verify.py` | 你要把它改成批量验证 |
| **现有 retrieve 节点** | `apps/api/app/services/agents/graph/nodes/retrieve.py` | 你要优化并发 |
| **现有 work_package** | `apps/api/app/services/agents/graph/nodes/content.py` | work_package_node 函数，你要改它的下游 |
| **LLM router** | `apps/api/app/services/llm_router.py` | call_json 的用法、profile 路由、expected 参数 |
| **LLM client** | `apps/api/app/services/llm.py` | 多 provider 调用方式 |
| **现有 prompt 目录** | `apps/api/app/services/agents/prompts/` | prompt 的写法风格、build() 函数模式 |
| **API router** | `apps/api/app/api/v1/research.py` | 现有端点格式，你要加新端点 |
| **main.py** | `apps/api/app/main.py` | FastAPI 入口，你要挂载静态文件 |

### 🟢 参考（遇到具体问题时查）

| 文件 | 路径 | 什么时候查 |
|---|---|---|
| **research_agent.py** | `apps/api/app/services/agents/research_agent.py` | 需要复用 S66v 的熔断器、缓存、survey 检测、dataset 白名单等逻辑时 |
| **devils_advocate prompt** | `apps/api/app/services/agents/prompts/devils_advocate.py` | 实现 graph 版 devils_advocate 节点时复用 system prompt |
| **synthesize prompt** | `apps/api/app/services/agents/prompts/synthesize.py` | 理解现有 EvidenceReview / LowBarReviewer 的 prompt 设计 |
| **Re1.2 SOP** | `Plan/PaperAgent_Re1.2_LangGraph全链路完善与候选关系网_SOP.md` | 理解为什么现有 graph 是这样设计的 |
| **Re1.2 完工报告** | `Plan/PaperAgent_Re2_完工报告.md` | 了解 Re1.2 的性能数据和已知问题 |
| **检索适配器** | `apps/api/app/services/retrieval/adapters/` | 需要修改适配器行为时（一般不需要） |
| **_http.py** | `apps/api/app/services/retrieval/_http.py` | HTTP 工具函数，自测验证器会用到 |

### 📚 外部参考项目（不需要读源码，设计文档里已总结）

| 项目 | 路径 | 设计文档中的总结 |
|---|---|---|
| Academic Research Skills (ARS) | `C:\Users\ZYF\Desktop\Paper\academic-research-skills` | §1.1 |
| AutoResearchClaw (ARC) | `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw` | §1.2 |
| B站毕业论文合集 | `G:\Agent\bilibili-analysis\v5-毕业论文合集` | §1.3 |

---

## 本期范围限定

### ✅ 做的

- 只做"保毕业"档，不区分档位
- 6 个新节点
- verify 批量化
- 搜索并发优化
- SSE 流式返回
- 简易 HTML 前端
- 自测框架 (4 个 validator)
- 默认 DeepSeek provider

### ❌ 不做的

- 不做"稳中求新"/"冲高水平"档位
- 不做实验执行（只建议实验设计，不跑代码）
- 不做论文正文生成（只生成大纲）
- 不做降重/润色
- 不做投稿期刊推荐
- 不引入新依赖
- 不重写现有 14 节点（只扩展）

---

## 关键工程约束

1. **System prompt ≤ 100 token**（StepFun 兼容，虽然默认用 DeepSeek）
2. **每个新节点最多 1 次 LLM 调用**，fallback 到确定性逻辑
3. **所有推荐必须绑定 candidate_id** — 禁止编造论文/repo/dataset
4. **ResearchState 只增不改** — 不删除现有字段
5. **API 向后兼容** — 现有端点不变，只新增
6. **LangGraph stream_mode="updates"** — 用于 SSE 流式返回
7. **节点超时 15-45s** — 超时走 fallback，不阻塞管道
8. **测试并行化** — 见下方"测试策略"

## 测试策略

### 基本原则

- **可并行的测试必须并行**：独立测试用例（如 5 个题目端到端、4 个 validator 各跑一次）必须分发 subagent 并行执行。
- **不值得并行的直接串行**：单条测试 <10s 且串行总耗时 <60s，直接串行跑，不花 subagent 开销。
- **大规模测试需先评估必要性**：超过 10 条用例时，先评估是否每条都有独立发现价值。前 3 条已覆盖核心路径的，后续降级为 smoke test。
- **并行时主线程不空转**：subagent 跑测试时，主线程必须同时做推进性工作（review 代码、写下一 Phase prompt、检查文档、准备测试数据）。禁止等待。

### 每个 Phase 的测试分发方案

**Phase 1 测试**：
| 测试 | 预计耗时 | 独立? | 并行? | 策略 |
|---|---|---|---|---|
| `test_re2_feasibility.py` (单元) | ~5s | ✅ | 与 verify_batch 并行 | subagent A |
| `test_re2_verify_batch.py` (单元) | ~5s | ✅ | 与 feasibility 并行 | subagent B |
| index.html 手动测试 | ~2min | ✅ | 与上述并行 | 主线程做（需人工） |

> 主线程在 subagent 跑单测时：编写 Phase 2 的 innovation_extractor prompt 草稿。

**Phase 2 测试**：
| 测试 | 预计耗时 | 独立? | 并行? | 策略 |
|---|---|---|---|---|
| `test_re2_innovation.py` | ~5s | ✅ | 3 个并行 | subagent A |
| `test_re2_narrative.py` | ~5s | ✅ | 3 个并行 | subagent B |
| sota_matcher 单测 | ~5s | ✅ | 3 个并行 | subagent C |

> 主线程在 subagent 跑单测时：编写 Phase 3 的 optimization_advisor prompt 草稿。

**Phase 4 测试（最关键的并行场景）**：
| 测试 | 预计耗时 | 独立? | 并行? | 策略 |
|---|---|---|---|---|
| 5 个标准题目 E2E | 各 ~3min | ✅ 互不依赖 | **5 个并行** | subagent ×5 |
| 3 个高风险题目 | 各 ~2min | ✅ | **3 个并行** | subagent ×3 |
| paper_validator (5 题合并) | ~30s | ✅ | 1 个 subagent | subagent |
| repo_validator (5 题合并) | ~30s | ✅ | 1 个 subagent | subagent |
| dataset_validator | ~10s | ✅ | 直接串行 | 主线程 |
| conclusion_validator | ~5s | ✅ | 直接串行 | 主线程 |

> **并行策略**：5 个 E2E 题目 + 3 个高风险题 + 3 个 validator = 最多 8 个 subagent 同时跑。
> **主线程在 subagent 跑测试时**：审查 Phase 1-3 已完成的节点代码、检查文档一致性、准备验收报告框架、review API 端点实现。

**大规模测试判断**：
- 如果 8 个题目 E2E 总串行耗时 ~25min → 值得并行（并行后 ~3-5min）
- 如果每个 E2E 只需验证"不 crash" → 降级为 smoke test，不跑全量断言
- 如果前 3 个题目已覆盖核心路径 → 后 5 个可以只检查 `final_recommendation` 非空

### 测试结果汇总流程

```
主线程分发 N 个 subagent 并行测试
    │
    ├── subagent 1: E2E 题目 1 → pass/fail
    ├── subagent 2: E2E 题目 2 → pass/fail
    ├── subagent 3: validator → pass/fail
    └── ...
    │
    ▼ (全部返回后)
主线程统一汇总:
    - 全 pass → 进入下一 Phase
    - 有 fail → 分析失败模式 → 决定: 全部重跑 or 只重跑失败项
    - 不逐条处理，统一判断
```

---

## 实施顺序（按 Phase）

### Phase 1（1.5 周）— 你现在应该做这个

1. 扩展 `ResearchState`（加字段，不改现有）
2. 实现 `feasibility_assessor` 节点 + prompt
3. **verify 批量化**（24 次 LLM → 3 次）
4. **paper_retriever 去 sleep**
5. **默认 DeepSeek**（改 .env）
6. **SSE 端点** `POST /api/v1/research/stream`
7. **简易 index.html**
8. FastAPI 静态托管
9. 单元测试

### Phase 2（1.5 周）

1. `innovation_extractor` 节点 + prompt
2. `sota_matcher` 节点 + prompt
3. `narrative_builder` 节点 + prompt
4. 条件边接入
5. 单元测试

### Phase 3（1 周）

1. `optimization_advisor` 节点 + prompt
2. `devils_advocate` graph 节点 + prompt
3. 条件边接入
4. 单元测试

### Phase 4（1 周）

1. 6 个新 API 端点
2. 端到端测试
3. 自测框架（4 个 validator）
4. 测试用例（5 标准 + 3 高风险）

### Phase 5（0.5 周）

1. 验收（22 条检查项）

---

## 完成标准

| 必须达到 | 验证方式 |
|---|---|
| 输入"基于YOLOv5的钢材表面缺陷检测"能端到端跑通 | E2E 测试 |
| 搜索阶段 ≤3 min | node_timings 计时 |
| 完整结果 ≤5 min | node_timings 计时 |
| 论文 URL 可访问率 ≥80% | paper_validator |
| Repo 可访问率 ≥80% | repo_validator |
| Dataset 在已知注册表 ≥90% | dataset_validator |
| 分析结论全部绑定真实 candidate_id | conclusion_validator |
| 高风险题目输出退化路线 | E2E 测试 |
| index.html 搜索结果逐条流入 | 手动测试 |
| verify 结果实时标记 ✓/✗/⚠ | 手动测试 |

---

## 一句话

> 读 `docs/design/PaperAgent_Re2_FullChain_Design.md`，按 Phase 1-5 顺序实现，每个节点写完跑自测。测试能并行的分发 subagent 并行跑，主线程不空转——趁 subagent 跑测试时写下一 Phase 的 prompt 草稿或 review 已完成代码。全部通过后提交 SOP AI 审核。只做保毕业，不搞花活。
