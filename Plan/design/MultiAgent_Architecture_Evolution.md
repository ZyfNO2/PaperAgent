# PaperAgent 多 Agent架构演进设计（求职向，design-only）

> 日期：2026-06-23
> 性质：设计稿（design-only），不是 SOP / Phase收。
>发：小红书一面反思点 #2 —「方案/架构设计薄弱，需要多 Agent架构设计思维能力」。同时回答连串追问：5 种 Agent架构 / Supervisor颈 / 子 Agent胀到 20-50么办 / Hierarchical +票 +并行化取舍。
> 口径：当前 PaperAgent = 单 Agent + 4 Gate（SAS + Gate），多 Agent `design-only`。本稿给可演进路径与「被面试官追着挑战时怎么答到最优解」的话术树。

---

## 0.状盘点 + 与架构科学的对照

### 0.1 当前定位
PaperAgent = **SAS（Single-Agent System）顺序型 + 4 Gate**：
- 单流程：题目 →关键词拆解 →索计划 →选证据 →据晋升 →行性判断 →题报告 →出前检查。
- Gate：keyword gate / candidate gate / promotion gate / readiness gate。
- 不做 Supervisor，不做多路并行评审。

### 0.2 为什么当前用 SAS没问题（守诚实口径）
对标 Google「Towards a Science of Scaling Agent Systems」经验阈值：
- 单 Agent基线 45% 时，加协调收益递减趋负 → SAS更安全。
- PaperAgent是顺序强、Gate强的选题流程 →顺序推理，**过早拆多 Agent收益有限反而汪路由复杂度**。
- 这正是小红书场反思里该讲的「为什么我现在不用多 Agent」。

### 0.3 什么时候该往多 Agent演进（触发条件，不是为多而多）
- 子流程膨胀（检索/验证/评审变成不同关注点）。
-要多视角并行候选（多模型投票、多源对齐）。
-要层级路由（多行业/多任务分发）。

## 1.5 种架构 × PaperAgent落点（面试一图讲清）

|构 |杂度 | PaperAgent当 |进到位 | 用场景 |
|---|---|---|---|---|
| SAS 单体 | O(T) 顺序，0信 | **implemented** | — |序推理 /工具密集 |
| MAS立并行 | O(n) 并行 +整合 |分隐式（多源并行召回） |显式多 Retriever 并行 + RRF合 |多视角子任务 |
| 中心化 Supervisor | Supervisor颈 | design-only | Retriever/Verifier/Reviewer子 Agent |规划 /分发 |
|中心化 Peer |信开销大容错强 | 不适用在主链 |态检索路由 |态环境 |
|合 Hierarchical |级 + Peer | design-only候选 | Supervisor +层分发 +层投票 |通用推荐 |


## 2.孙问链：子 Agent膨胀到 20-50么办？（小红书店级最优解还原）

面试官追问链（还原）：
1. Supervisor下子 Agent胀到 20-50，Supervisor力怎么办？
2.型层级分类，第一层分错后面全错怎么办？
3.加投票分类准确性，但性能开销大，怎么办？
4. 并行化性能，是不是又回到容错/一致性问题？

### 2.1 最优解综合（不是单点是组合拳）

**第一层：Hierarchical 降扇出。** 把单 Supervisor 50 子 Agent改成多层 Supervisor（每层扇出 ≤ 5-7）。数字原理：广度 b、深度 d，总容量 `b^d`；b=5 d=3 = 125能力，胜如果性大靠单层。这是组织学/数据库 B+树的常规结论，能给面试官「不是拍脑袋」的感觉。

**第二层：分类用多 Agent投票 +信度门。** 同层 N 个轻量分类器投票（majority / Borda），置信度低于 threshold人工/回退路径。降低单点分类错率。

**第三层：并 +异步降低延迟。**票并发执行（同一层并行，跨层串行），用 LangGraph 并行 branch；不要把投票改成串行。

**第四层（关键，面试官会再追）：度 vs容错一致性的取舍。**
- 并行投票引入「快慢差」→用 Barrier或 longest-prefix排序合。
-子 Agent挂 →显式熔断（接 AutoResearchClaw §3.3）+ negative cache +降级 heuristic（项目已有不变式）。
- 不用强一致 →可以接受最终一致概预估，因为 Agent是「给建议人留门」，不是金融交易（对标 Saga最终一致 vs强一致 ja）。

### 2.2 量纲分析（给面试官量化感）
- Supervisor中心化 `复杂度 = O(n × k × r)`（子 Agent n、端数 k、主管轮数 r），n大线性涨。
- Hierarchical `深度 = log_b(n)`，主席度降，但总 joint升（变得可接受）。
-投票并发 `wall-clock = max(同层)批并行 →串行`，胜 n串行。

### 2.3 企业级对标
- **Saga**补偿事务 → Agent败的补偿回滚
- **LangGraph** checkpoint + time travel → Agent可回放到某步重跑（PaperAgent Trace已天然支持）
- **CrewAI / AutoGen**角色协作 →多 Agent权限与任务分发
- **Resilience4j** →显式熔断
- **Airflow / Temporal**务编排 →多 Agent顺序/并行 seat

## 3.架构选型决策树（面试现场出最优解）

```
任务状？（动态检索/网络导航） →去中心化 Peer（不住单点）序长链推理（一步错步步错） → SAS + Gate（在重）规划/分发有明显分层 → Hierarchical + 既有 Skills）发视角并行 → MAS +加权投票/置信度门能对？ →合型
```

这个决策树回答了小红书问 #6「多 Agent时么设计」：从「是否一定要用多 Agent法（而是去中心化或 SAS）。这正是博主反思里点出的「评估好的架构资料」落到讲法。

## 4. Agent「分层路由」最小可测单元（design-only）

|段 |产出 |最小单元 |
|---|---|---|
|段 A | AgentRouter决策树（SAS/Supervisor/Peer个） + 1 pytest | 0.5 天 |
|段 B |薄 Supervisor（1+3子 Agent：Retriever/Verifier/Reviewer）+ 1 pytest | 1 天 |
|段 C | Hierarchical层 +并行投票（confidence门） + 2 pytest | 1.5-2 天 |
|段 D | LangGraph映射（不执行） + checkpoint可回放对照 | 1 天 |

落地后写对照叙事：CrewAI Supervisor + LangGraph checkpoint + Resilience4j熔断，小型化取舍为「自写以讲清原理代替重依赖」。

## 5.试讲法树

-（用）：「PaperAgent是 SAS + 4 Gate，因为顺序选题推理一步错步步错，过早拆多 Agent反而加汪」。
- 中（加分）：「Service膨胀时演 Hierarchical，扇出 b=5、深度 log_b(n)，对标 Sreeraj组织的扁以降汪」。
- 深（最优解）：「胀是组合拳：层级降扇出 +同层投票 +并行 +显式熔断 + Saga最终一致；不用强一致 Agent给建议人留门」。

## 6.与 CLAUDE.md 不变式对齐

- 设计不冒充已落地：全文 design-only。
- LLM 不直接写 evidence：多 Agent是对话/计划编排，不写 supports。
- 不引未列依赖：LangGraph/CrewAI/AutoGen只为 design-only对标，未入 pyproject.toml。
- LLM径配 heuristic fallback：分级分析/投票都有 heuristic fallback。

## 7.与既有文档交叉引用

- `docs/interview/MultiAgent_Expansion_Design.md` / `Deep_Dive_QA_Agent.md` / `Architecture_Diagram.md`
- `docs/interview/AutoResearchClaw_对标与小型化移植.md` §2.2（PIVOT）/ §2.7（多 Agent design-only）/ §3.1（MetaClaw与多 Agent关联）/ §3.3（熔断）
