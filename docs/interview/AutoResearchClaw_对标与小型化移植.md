# AutoResearchClaw 对标与小型化移植设计（求职向）

> 日期：2026-06-22
>考文：《全自动科研论文生成：AutoResearchClaw度技术解析》（aiming-lab，8.2k star，23 / 8 相位全自动科研流水线，"Chat an Idea. Get a Paper"）
> 当前项目：TopicPilot-CN（科研证据 Agent作台，5前端 + 8 相位后端，面试导向，已完成 Session 01-43）
> 口径：以**思路对齐**为主，不强制全部实现（用户明确："主要是思路，不一定要实现"），所有移植点必须能贴合求职/企业技能库口径，且不破坏现有 implemented / lightweight / design-only 三档边界。

---

## 0. 为什么要对标 AutoResearchClaw，而不是直接照搬

AutoResearchClaw（下文简称 ARC）解决的是「一个想法 一篇完整学术论文」的全流程自动化，核心是 23 8 相位流水线 + 三重门控 + 四层引用验证 + 多智能体辩论 + MetaClaw 自进化。

TopicPilot-CN 解决的是更前置、也更收敛的问题：「一个题目断能不能开题 给出可追溯的开题报告草稿」，并且**不跑实验、不生成 LaTeX 论文、不声称能产出原创研究**。两者不是同一个产品，而是同一条"科研辅助"价值链上的不同相位。

所以对标的目标是**借工程化思想**，不是再造一个 ARC：

1. 把 TopicPilot-CN **已经落地**的能力，按企业技能库的语言重新讲一遍，让面试官直接对得上号；
2. 把 ARC 里 **3 个真正能加分的点**（见第 3）做**小型化**移植，作为后续可落地的思路；
3. 对 ARC 里 TopicPilot-CN **不适用**的部分（跑实验、LaTeX、ACP 多后端）**诚实划界**，不在面试里把没做的说成做了。

这套口径本身就是一条面试加分项：**知道一个 8.2k star 项目的架构长什么样，清楚自己做了哪一段、没做哪一段、为什么不照搬** —— 这正是需求清单里"6.么处理路由错误/怎么控制成本""7. 什么让 AI 做、什么不让 AI 做"想要的判断力。

---

## 1.架构对标总表

口径三档：

- **已对齐（讲）**：TopicPilot-CN 已经有同构能力或等价设计，只需用企业技能库的话术包装，不补代码。
- **可补强（小型化）**：ARC 有、TopicPilot-CN或弱，且小型化成本可控、讲解价值高 → 第 3详述。
- **不适用（边界）**：与 TopicPilot-CN围不重叠，明确划界，不强行移植。

| ARC 特性 | TopicPilot-CN状 | 口径 | 企业技能库对标 |
|---|---|---|---|
| 23 / 8 相位流水线 | 5前端 + 8 相位后端 | 已对齐 |作流引擎 /态机编排 |
| 三重门控（Stage 5/9/20） | 4 Gate：keyword / candidate / promotion / readiness | 已对齐 | Saga偿事务 /作流 check-point |
|策循环 PROCEED/REFINE/PIVOT | PIVOT 三档路线（S04/S28） | 已对齐 |态机分支 / 回滚 /偿 |
| 多源文献检索（OpenAlex/S2/arXiv） | 多源检索 OpenAlex/arXiv/GitHub/HF（S14） |分对齐 |邦查询 / 数据集成 |
|索熔断降级（circuit breaker） | 有 fallback，无显式熔断器 | 可补强 3.3 | Resilience4j / Sentinel / Hystrix |
| 四层引用验证链 | URL Verified 单层 + 平台元数据（S10） | 可补强 3.2 | Great Expectations / dbt tests / 数据质量门 |
| VerifiedRegistry 反伪造 | EvidenceRef +删除保留 Trace（S07/S42） | 可补强 3.2 | 数据血缘 (Lineage) / 版本化 |
|件感知代码生成 | 不跑实验，N/A | 不适用 |源感知调度（仅类比） |
|箱自愈（NaN/Inf→诊断→修复→重跑，10） | LLM→heuristic fallback（primitive） | 可补强 3.3 | 自愈系统 / 重试退避 /断 |
| OpenCode Beast Mode 多文件委托 | 无 | 不适用 |杂度阈值委托（仅类比） |
| 多智能体辩论 | Supervisor+Retriever/Review/Proposal（S37，design-only） | 设计级对齐 | Multi-Agent 编排（CrewAI/AutoGen/LangGraph） |
| 对等评审 + length guard |员会复核 + RevisionLoop（S30） |分对齐 | Code Review 回环 /量门 |
| MetaClaw 自进化（教训→注入） | 无 | 可补强 3.1（最高优） | Prompt 版本化 / 经验反哺 / DSPy |
| ACP 任意智能体后端 | input-prefer：auto/llm/heuristic |分对齐 |型无关抽象 / LLM Gateway |
| artifacts/ 结构化产物 | FinalPackage Markdown（S08/S32） | 已对齐 | CI/CD 制品 / 可追溯交付 |
|息平台桥接（Discord/飞书/微信） | 无 | 不适用（不在范围） | 通知/IM接（仅类比） |

---

## 2. 已对齐：只讲不补（8 个对齐点）

每条按统一结构：「同名对标点 → 为什么这么设计 → 一句话面试话术 → 企业技能库映射」。这些在面试里**直接可讲**，不需要再写代码。

### 2.1 多阶段流水线 + 三重门控 ↔工作流引擎 / Saga事务补偿

- **对应**：ARC 的 23三重门控；TopicPilot-CN 的 5主工作流 + 4 Gate
- **为什么这么设计**：开题判断不是一次性生成，而是在「范围界定 →索 → 可行性 → 开题建议 → 导出」的每一处决策点保留人工否决权。Gate 不是延迟，是**可补偿事务**——拒绝即回滚到上一个稳定状态，而不是全盘重来。
- **一句话话术**：「我把开题判断做成一个带 Gate 的状态机而不是一次 LLM 生成，本质是 Saga偿事务：每个 Gate 是一个 decision point，reject发回滚到上一步稳定态。」
- **企业技能库**：Airflow/Prefect/Temporal（任务编排）+ Saga式（补偿事务）+ LangGraph checkpoint（状态持久化）

### 2.2 PIVOT决策循环 ↔态机分支 / 事务补偿回滚

- **对应**：ARC Stage 15 的 PROCEED/REFINE/PIVOT；TopicPilot-CN S04/S28 的三档退化路线
- **为什么这么设计**：可行性判断的最坏情况不是"做不了"，而是"硬做却收不了尾"。PIVOT 把"收缩到更稳的版本"做成一等公民，而不是异常分支。
- **一句话话术**：「可行性裁决有三档出口而非二元的能/不能：proceed / refine / pivot。pivot 不是失败，是带版本化的降级路线，避免学生在一个做不动的题目上耗半年。」
- **企业技能库**：状态机（FSM / Col procedural）+偿事务 + A/B线版本化

### 2.3 Candidate → Evidence晋升 +除保留 Trace ↔ 数据血缘 / 版本化

- **对应**：ARC VerifiedRegistry 的"反伪造"；TopicPilot-CN S07 EvidenceRef + S42删除「保留 Trace」
- **为什么这么设计**：检索到的候选不等于可写进报告的证据。晋升要过 URL Verified + 用户确认；refuse/restore 也要留 Trace。**软删除而非物理删除**，因为开题现场可能要解释"为什么不选那条"——删了就讲不清了。
- **一句话话术**：「Candidate 不直接变 Evidence，中间隔一层 promotion gate + URL Verified；即使是 reject 也走软删除并留 Trace，等于数据血缘 + 逻辑删除，报告里每个 cite 都能追溯到来源时刻。」
- **企业技能库**：数据血缘（OpenLineage / Apache Atlas）+ 逻辑删除 / 版本化 + provenance

### 2.4 PromptProtocol + action whitelist +禁止任意 JS ↔ 最小权限 /箱 / Prompt 注入防护

- **对应**：ARC 的 safety界；TopicPilot-CN S23 PromptProtocol.isToolAllowed + render_protocol 白名单 + 5 个已知 action + 7 个禁用模式
- **为什么这么设计**：LLM 负责"想"，程序负责"能不能做"。渲染层只认白名单组件，禁止任意 JS；工具调用按 isToolAllowed 收口。**写操作永远先出预览再确认**（S42 WorkspaceCommand）。
- **一句话话术**：「LLM 的输出不直接进 DOM、不直接改状态。渲染层 13 个白名单组件 + 5 个白名单 action + 7 个 forbidden pattern；写操作走 WorkspaceCommand览-确认闭环，是对 OWASP LLM Top 10 里 prompt injection / 过度授权的直接工程回应。」
- **企业技能库**：最小权限原则 +染沙箱（DOMPurify同理念）+ Prompt 注入防护 + 双人确认（2-phase commit价）

### 2.5 FinalPackage 结构化产物 ↔ CI/CD 制品 / 可追溯交付

- **对应**：ARC 的 artifacts/rc-目录；TopicPilot-CN S08 FinalPackage + S32 导出前 readiness check
- **为什么这么设计**：导出不是终点，是一个**可审计的产物**。readiness hard block 保证"证据不足就不让导出"，导出动作本身要可回放、可对照。
- **一句话话术**：「最终交付物不是一份 .md，而是一个带 readiness gate 的产物包：覆盖率、字符数、章数、引用数都进摘要；导出前做 hard block，等于 CI/CD 的质量门 + SBOM可追溯交付理念。」
- **企业技能库**：CI/CD 制品管理（artifacts）+量门（GitHub Checks）+ SBOM（可追溯交付物）

### 2.6 对等评审 + RevisionLoop ↔ Code Review 回环

- **对应**：ARC Stage 18/19 peer review + revision；TopicPilot-CN S30 低门槛委员会复核 + RevisionLoop
- **为什么这么设计**：评审不是语法检查，是"方法-证据一致性"检查：声明的路线有没有被证据支撑？引用和论述是否相关？不符则回环修订。
- **一句话话术**：「我把开题答辩前置成一个 RevisionLoop：委员会复核不是语法检查而是方法论-证据一致性检查，不通过就回环改，本质上和 PR review 回环 +度守卫同构。」
- **企业技能库**：Code Review 回环 +量门 + length guard（修订不无限膨胀）

### 2.7 多智能体（design-only） ↔ Multi-Agent 编排 / Supervisor瓶颈

- **对应**：ARC Stage 8/14 多智能体辩论；TopicPilot-CN S37 Multi-Agent 设计（Supervisor + Retriever/Verifier/Reviewer/Proposal）
- **为什么这么设计**：**现在不拆成多 Agent，但能讲清**什么时候拆、怎么避免 Supervisor 退化成瓶颈、并行怎么收敛、投票怎么补救。这是需求清单"多 Agent 不能为了多而多"的直接回答。
- **一句话话术**：「当前是单流程 Agent + Gate，而不是上来就 Supervisor 多子 Agent——因为 Supervisor 会成为串行瓶颈和错误放大器。我把多 Agent 保留成 design-only 的可扩展架构，能讲清拆分时机、层级路由、并行投票和成本上限，避免把设计稿说成已落地。」
- **企业技能库**：Multi-Agent 编排（CrewAI / AutoGen / LangGraph Supervisor）+级路由 + 并行投票

### 2.8 input-prefer模型无关降级 ↔ 可替换 LLM 后端 /型选型

- **对应**：ARC ACP 任意智能体后端；TopicPilot-CN input-prefer（auto / llm / heuristic）
- **为什么这么设计**：**模型负责建议，程序负责证据规则**。auto在 LLM 不可用时降级到 heuristic，保证服务不挂。这是"模型选型与降级策略"八股的项目级落地。
- **一句话话术**：「LLM是可降级的：auto自动 fallback 到启发式，而非让整个服务挂。这等价于一个最小 LLM Gateway——模型可替换、可降级、可旁路，不是绑死某个 provider。」
- **企业技能库**：模型路由 / LLM Gateway（LiteLLM同理念）+ 降级 fallback + 成本路由

---

## 3. 可小型化补强：3 个真正要补的思路点

> 用户口径："不一定要实现"。这三条以**设计思路**为主，标注实现边界。优先级按"讲解价值 × 小型化成本"排序。

### 3.1 【最高优先】MetaClaw"教训沉淀 → prompt 注入"自进化

**ARC么做**：每次 run 的失败/警告被捕获为 lesson，转 arc-* skill到本地 skills 目录，下一次 run 用 build_overlay() 把 skill 注入所有 LLM prompt，LLM避已知陷阱。对照实验：阶段重试率 -24.8%、Refine环 -40%、阶段完成率 +5.3%、鲁棒性 +18.3%。

**TopicPilot-CN状（gap）**：有 Trace / RunEvent 可回放，但**没有从失败到 prompt 的反哺闭环**。教训停留在"记录下来"，没"下次自动避开"。这正是需求清单里 Agent Memory 的"从经验中学习"缺口。

**小型化移植路（思路）**：

```
Run N 完成/失败 + Trace
  ↓取 (stage, failure_signature, lesson) 三元组
  ↓到本地 lessons.jsonl（不接外部 MetaClaw，不写 skills 目录之外）
  ↓ Run N+1动前 build_prompt_overlay(lessons, current_stage)
  ↓ 把相关 lesson 作为 system设条件注入该 stage 的 prompt
  ↓ LLM示里出现"已知陷阱："小节 →避
```

**为什么这么设计（求职口径）**：

- **不接 RLHF / 不做参数更新**：小数据量 MVP有样本量和算力做 RLHF；用"教训注入"是**可解释、可回放、零额外训练成本**的最贴近方案。
- **教训是结构化的**，不是把整段对话塞回去——只取 (stage, signature, lesson)，避免 context胀，呼应需求清单"上下文压缩后什么必须保留"。
- **可舍弃 / 可回滚**：lesson 是 overlay不是 base prompt 的一部分，错了就删，不污染主干。
- 这条直接回答"Agent忆怎么做 / 上下文恢复 /缩策略"的高频追问——而且比单纯讲 RunEventStore 多了一层"经验反哺"。

**职技术深度**：

-级：**中高级 AI程加分项**。这不是"我用了 LLM"的初级叙事，而是"我让流水线具备经验沉淀能力"的工程叙事——把 in-context learning 显式化成 feedback loop。
-职独特性：很多人会讲 RAG，少有人能讲"**run别的经验反哺到 prompt**"。这条把项目从"调用方"抬到"具备自我改进循环的编排方"。

**企业技能库对标（小型）**：

- DSPy Optimizer（prompt 自动调优）—— 我们不优化参数，只做 prompt overlay，是 DSPy 的"穷人版"
- promptfoo / Langfuse（prompt 版本化与评估）—— lessons.jsonl 就是 prompt 的版本化经验
- RLAIF / RLHF-lite —— 结构是 reward（失败信号）到 policy（prompt）的极简版，但用反哺而非梯度

**实现边界与代价**：design-only，可做最小 demo。最小可测单元：写一个 lesson_extractor(run_events)和 build_prompt_overlay(lessons, stage)，加 2 条 pytest。**零额外 GPU**，每次 run LLM用 +~5-10%（仅工作时多注入一小段）。**不依赖**外部 MetaClaw，不引入 pyproject 外的依赖（符合 CLAUDE.md不引未列依赖）。

**面试话术**："ARC 的 MetaClaw训系统是最打动我的一点，但它是外部集成。我把它的核心思路小型化成 lessons.jsonl + prompt overlay：run败留 lesson，下次注入该 stage 的 prompt 作为已知陷阱小节。不做 RLHF，不做参数更新，只做可解释的经验反哺——对照实验方向上预期降重试率，且整个回路可回放、可回滚。"

**反问防线**：

- "和 Vector Memory 有什么区别？" →训是结构化 (stage, signature, lesson)，不是语义检索；注入是按 stage确匹配，不是相似度，避免无关记忆干扰。
- "怎么避免错误教训污染？" → overlay非 base，可单独删除；教训带来源 run_id，可追溯。

### 3.2 【高】多层引用验证链 + VerifiedRegistry 反伪造

**ARC么做**：四层链 arXiv ID → CrossRef/DataCite DOI → Semantic Scholar题匹配 → LLM 相关性评分，任一层失败即移除引用，产出 verification_report.json。VerifiedRegistry 保证"所有写进论文的数据都来自已验证来源"。

**TopicPilot-CN状（gap，已核查）**：verification.py 是**单层**——按平台分发到 verify_arxiv / verify_github / verify_huggingface / verify_kaggle / verify_generic_url，做的是 **URL 可达性 + 元数据格式校验**（HTTP HEAD + arxiv_id/DOI 正则），没有"来源权威性交叉验证"也没有"内容相关性 LLM定"，也没有统一的 verification_report 产物。置信度有（0.0-0.85），但**不是多层链路**。

**小型化移植路（思路）**：把单层扩展成可配置的多层链，**每层都是已有基础设施的小步升级**：

```
Layer 1: 可链接性      ← 已有（URL Verified + HTTP HEAD）
Layer 2: 来源权威性    ←级：arXiv_id / DOI 在 OpenAlex/Semantic Scholar 反查交叉命中
Layer 3: 元数据完整性   ←级：title/authors/year全度 + 格式校验（部分已有）
Layer 4: 内容相关性    ← 新增：LLM定"候选内容 vs告论述"相关性（只判定、不生成、不入 supports）
最终产物：verification_report.json（每条引用的层状验证状态 +信度 + warnings）
```

**为什么这么设计（求职口径）**：

- **引用幻觉是科研/检索类项目的第一痛点**——ARC 把它列为"最核心创新之一"，这不是炫技，是工程刚需。把"单层 URL Verified"升级成"多层验证链"是低成本高讲解价值的一步。
- **每层职责单一**：可链接性管"在不在"，权威性管"真不真"，完整性管"全不全"，相关性管"贴不贴"。面试官追问哪一层失败怎么办，能逐层回答。
- **LLM 只做判定不写 supports**：保留项目不变式（LLM 不直接写 supports），相关性层只产出一个布尔/分数，不进证据池。这条对应需求清单"如何避免幻觉"和"什么是让 AI 做、什么不让 AI 做"。

**职技术深度**：

-级：**中高级数据工程 / AI程交叉点**。把 RAG 的"R（检索）"和"G（生成）"之间补上"V（验证）"，并显式成数据质量门，是检索类项目的高级讲法。
-职独特性：大多数人讲 RAG在"召回 + 相似度"，能把验证显式做成多层链 +量门 + 可追溯产物的人不多。这条把"避免幻觉"从口号变成结构。

**企业技能库对标（小型）**：

- Great Expectations / dbt tests —— 数据校验链 +言式质量门
- 数据血缘（OpenLineage）—— verification_report.json 就是引用级血缘
- tfx Data Validation —— schema 与数据漂移检测（理念对标）

**实现边界与代价**：lightweight，可升级。最小可测单元：把 verify_evidence_item 包成 LayerChain，每层产出一层结果，聚合为 verification_report.json。**零额外 GPU**，Layer 4 LLM 相关性判定每次 +1轻量调用。**不新增外部强依赖**：OpenAlex/Semantic Scholar 已是多源检索的一部分（S14），反查复用即可。

**面试话术**："ARC 的四层引用验证是它最核心的反幻觉手段。我把现在的单层 URL Verified级思路设计成四层链：可链接性 → 来源权威性交叉命中 → 元数据完整性 → 内容相关性 LLM定。每层独立可测，失败即降级或移除，最后产 verification_report.json引用级血缘。LLM 只判定相关性不写 supports，守住证据规则边界。"

**反问防线**：

- "Layer 4 会不会又引入幻觉？" → 只判定相关性、只产布尔/分数、不入 supports；判定本身有置信度阈值，低于阈值降级到 partial。
- "为什么不用向量相似度判相关性？" → 向量相似度管语义近邻，不管"这个 cite 是不是支撑这个论述"；用 LLM语义支撑更贴合引用本义，也更可解释。

### 3.3 【中】检索熔断降级 + 自愈重试（显式化）

**ARC么做**：三层文献检索每层带熔断器，前层失败自动降级到下层；实验失败 NaN/Inf → 诊断 → 修复 → 重跑，最多 10自愈。

**TopicPilot-CN状（gap）**：多源检索有 fallback（OpenAlex 不可用转 arXiv），LLM有 auto→heuristic 降级，但**没有显式的熔断器状态、没有重试退避策略、没有失败诊断环节**——降级是"写死的兜底"，不是"可观测的容错机制"。

**小型化移植路（思路）**：把隐式 fallback级成显式容错三件套，**不引入 Resilience4j/Hystrix 这类重依赖**，自己写一个最简版：

```
CircuitBreaker态：closed → half_open → open（基于连续失败计数）
  ↓ open 时直接降级到下一源，不再打挂掉的源
  ↓ 定时 half_open活
+ Exponential Backoff：重试间隔 0.5s → 1s → 2s（上限 3 次）
+败诊断：每次降级写一条 structured_log（已有 structured_log.py），带 source / reason / latency
+ 自愈重试：LLM 单路径失败 → heuristic 重跑 +记 stale（复用 S42 stale 机制），而非静默吞掉
```

**为什么这么设计（求职口径）**：

- **显式化 >式兜底**：同样是"OpenAlex了转 arXiv"，写成 try/except是初级；写成带状态机、带退避、带可观测日志的 CircuitBreaker 是中高级。后者能回答"为什么这次降级了 / 何时恢复 / 降级了几次"。
- **复用已有基础设施**：structured_log.py 已存在（日志），stale 机制已存在（S42 自愈触发点），多源检索已存在（S14 数据源）。这是"把已有零件拼成容错机制"，不是新建系统。
- 这条把需求清单"工具调用失败 / Function Calling效 /么处理路由错误"从"我有 fallback"升级成"我有可观测的容错链"。

**职技术深度**：

-级：**中级后端 / AI程通用加分项**。容错三件套（熔断 + 降级 + 限流 + 重试退避）是任何调用外部 API 的系统都该有的，是"工程成熟度"信号。
-职独特性：在 AI 项目里讲熔断器比在普通 CRUD 里讲更有说服力，因为 LLM/检索源的不稳定性是真实痛点，不是为讲而讲。

**企业技能库对标（小型）**：

- Resilience4j / Sentinel / Hystrix ——断 + 降级 + 限流三件套（我们不引依赖，自写极简版讲清原理）
- Exponential Backoff + Jitter —— 重试退避
- Health Check / Probe —— half_open活

**实现边界与代价**：lightweight，可显式化。最小可测单元：一个 CircuitBreaker（closed/half_open/open态转换）+ 把多源检索的 try/except成 breaker.call()。**零 GPU**，重试只在失败时发生，**无新依赖**（符合不变式）。最多 2-3重试，不改主干数据流。

**面试话术**："我有多源检索的 fallback，但当前是写死的 try/except。ARC 的熔断降级启发我把它显式化成一个极简 CircuitBreaker：closed→half_open→open态机 +数退避 + 降级诊断日志，复用已有的 structured_log 和 stale 机制做自愈触发。不引 Resilience4j，自己写讲清原理，因为它就是几行状态转换，重依赖反而难维护。"

**反问防线**：

- "阈值怎么定？" →败计数用滑动窗口，open续时间用配置项；MVP 给保守默认值（连续 5失败 open，30s 后 half_open活）。
- "half_open 打到一半流量怎么办？" →简版只放一个探活请求，不放半流量，MVP用且更易测。

---

## 4. 不适用：诚实划界（不在面试里冒充）

按需求清单"不要把设计预留说成已落地"和 Technical_Highlights 的三档口径，以下 ARC 特性**明确不移植**，面试被问到时如实划界：

| ARC 特性 | 不移植原因 |问到时怎么讲 |
|---|---|---|
|件感知代码生成（CUDA/MPS/CPU） | TopicPilot-CN 不跑 ML 实验，不生成训练代码 | "我们止步于开题判断和报告草稿，不生成可跑的实验代码，所以硬件感知不适用；但这个理念迁移到后端能力探测——比如 backend reachability查就是同构思路" |
| OpenCode Beast Mode 多文件委托 |杂度阈值委托不在范围 | 不讲；不主张这个能力 |
|箱实验 NaN/Inf 自愈 10 |有实验运行环节 | "我们没有实验运行这一相位，所以 NaN/Inf 自愈不适用；但其诊断-修复-重跑的思路迁移成了 3.3 的 LLM 自愈重试 + stale发" |
| LaTeX 论文生成（NeurIPS/ICLR板） | TopicPilot-CN 产出 Markdown 开题报告，不是投稿论文 | "我们止于开题报告 Markdown 导出，不生成 LaTeX稿稿" |
| ACP 任意智能体后端 | 单后端 MVP，input-prefer 已是模型无关雏形 | "ACP 多后端不在范围，但 input-prefer 的 auto/llm/heuristic 是模型可替换可降级的雏形，方向一致" |
|息平台桥接（Discord/飞书/微信） | 不在产品范围 | 不主张 |

**划界本身是加分项**：需求清单反复强调"面试官会问什么让 AI 做、什么不让"，能讲清"我刻意没做 X，因为范围是 Y"比"我都做了"更可信、更像在真实工程里做过取舍的人。

---

## 5.求职技术深度总览（一页式，按研发岗关心重组）

|职关心 | TopicPilot-CN 已讲 | ARC强思路 | 企业技能库对标 |度档 |
|---|---|---|---|---|
| 流水线编排 | 5 + 4 Gate + PIVOT | 23段叙事包装 | Airflow/Temporal/Saga | 中高 |
|错/稳定性 | LLM→heuristic fallback | 3.3 显式熔断 + 自愈重试 | Resilience4j/Backoff | 中 |
| 数据治理 | EvidenceRef +删除留 Trace | 3.2 多层验证链 + verification_report | Great Expectations/Lineage | 中高 |
| Agent构 | 单 Agent + Gate（design-only 多 Agent） |清 Supervisor瓶颈与拆分时机 | CrewAI/AutoGen/LangGraph | 中 |
| Prompt 工程 | PromptProtocol + WorkspaceCommand览 | 3.1训注入 prompt overlay | DSPy/promptfoo/Langfuse | 中高（独特） |
| 评估/基线 | S17/S31 双基线 + pytest + Playwright | 对照实验叙事（重试率/完成率） | MLflow/Ragas | 中 |
| 安全 | whitelist +止 JS + 最小权限 | — | OWASP LLM Top 10/沙箱 | 中 |
|型/部署 | input-prefer型无关降级 |清 LLM Gateway形 | LiteLLM/LLM Gateway | 中 |
| 可观测/可恢复 | RunEvent/Trace/replay | 3.1训沉淀 + lessons 可回放 | OpenTelemetry/Tracing | 中 |

**最值得讲的 3 条（按求职差异化排序）**：

1. **3.1训注入自进化** —— 最独特，少有人讲，直接抬项目定位。
2. **3.2 多层引用验证链** —— 直接命中"避免幻觉"高频追问，把口号变结构。
3. **2.4 PromptProtocol + WorkspaceCommand览闭环** —— 已落地，命中"什么让 AI 做/不让"必问题，可现场点开 UI示。

---

## 6.复杂度 / 成本 / 能力边界

**不做的重活**（避免为了演示引入长期难维护的重依赖，呼应 Technical_Highlights 亮点 4）：

- 不接 MetaClaw 外部集成，不写外部 skills 目录
- 不引 Resilience4j/Hystrix/Sentinel，自写极简 CircuitBreaker
- 不接真实向量库替代当前的 lightweight索
- 不做 RLHF / 参数更新 / 微调
- 不加 ACP 多智能体后端、不做消息平台桥接、不生成 LaTeX

**可做的轻活**（全本地可跑，0外 GPU）：

- lessons.jsonl + build_prompt_overlay()（3.1）
- LayerChain + verification_report.json（3.2，复用 OpenAlex/S2 反查）
- CircuitBreaker + 退避 + 诊断日志（3.3，复用 structured_log + stale）
-期成本：LLM用 +~10-20%（仅 3.1 注入 + 3.2 layer4定时）；其余零开销
- 新增依赖：**无**（3.2 的 OpenAlex/S2 已在 S14 多源检索中）

---

## 7. 与项目不变式对齐

- **三档口径不破坏**：3.1 design-only（可做最小 demo）；3.2 从 lightweight级；3.3 从 implicit fallback 显式化。不把任何一条标成 implemented，除非真的写过测试。
- **设计不冒充已落地**：本文是"思路设计"，不是验收报告。落地与否以代码 + pytest/Playwright 为准。
- **pytest 总数只增不减**（CLAUDE.md）：若实际实现 3.x，每条至少配 pytest，总数不得下降。
- **LLM 不直接写 supports / 不参与真伪判定**（3.2 Layer4 只判定相关性，不入池）：守住已有证据规则不变式。
- **凭据从 .env 读，不引未列依赖**：3.x 全部不新增 pyproject 外的依赖。

---

## 8.落地建议（可选，思路优先，不强约束）

> 不构成新 Session SOP，只是若要实现时的优先级建议。是否落地、何时落地由用户决定。

| 优先级 |路点 | 最小可测单元 |估工作量 |
|---|---|---|---|
| P0 | 3.1训注入 | lesson_extractor(run_events) + build_prompt_overlay(lessons, stage) + 2 pytest | 半天 |
| P1 | 3.2 多层验证链 | LayerChain包 verify_evidence_item + verification_report.json 产物 + 2 pytest | 半天-1 天 |
| P2 | 3.3 显式熔断 | CircuitBreaker + 多源检索接入 + 诊断日志 + 1 pytest | 半天 |

落地后建议各加一个"对照叙事"（不要求跑全量化实验）：在 acceptance report 里写"3.x用 ARC 的哪个思路、小型化做了哪些取舍、对应哪个企业技能库概念"，把对标这条线收口进面试材料（Technical_Highlights / Deep_Dive_QA）。

---


## 9.补充参考：scientific-agent-skills 与 Skill标准化 / 企业技能库

> 第二个参考库：[K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills)
> 147 个科研 skill、100+ 数据库、遵循开放 [Agent Skills](https://agentskills.io/) 标准、SKILL.md + frontmatter、可在 Cursor/Claude Code/Codex/Gemini 间移植、`gh skill install` 带 provenance 元数据、Autoskill 作流生成 skill。
> 与 ARC 是**不同层**的参考：ARC「流水线怎么编排」，scientific-agent-skills「能力怎么封装成可发现、可移植、有 provenance 的资产」。后者更直接命中用户原始要求里的"贴近求职的企业化技能库"。

### 9.1 为什么这一参考对企业技能库口径更重要

ARC讲的是"一条大流水线"，而企业技能库的真实诉求是"**一堆可复用、可治理、可移植的能力单元**"。scientific-agent-skills 给的就是这套**治理范式**：

- **开放标准**：Agent Skills standard（agentskills.io），SKILL.md 单行 frontmatter（name/description/required_environment_variables），未知字段忽略 → forward-compat
- **可移植**：同一份 skill 在 Cursor / Claude Code / Codex / Gemini / OpenClaw / NemoClaw 都能被发现和使用
- **供应链完整性**：`gh skill install`录 provenance 元数据（来源、版本、commit SHA），pin 到 tag/SHA 可复现安装
- **安全口径**：review-before-install、NemoClaw default-deny outbound networking、skill 能执行代码因此务必审查
- **Autoskill**：从一次工作流自动起草一个 skill（经验→可复用资产）

这套东西的名字就叫"企业技能库"，比 ARC更贴用户原始要求。

### 9.2 与 TopicPilot-CN 的对齐（S13 已是内部版）

已核查事实：

- `apps/api/app/services/skill_registry.py` 加载 `skills/registry.json`，读 `SKILL.md`要，提供 `list_skills` / `get_skill` / `health_check`（SKILL.md path 不存在就进 health problems）
- `apps/api/app/services/verification.py` 通过 `source_to_skill`（arxiv→paper-card、github→github-baseline、huggingface/kaggle→dataset-validation）给验证成功的证据打 `validated_by_skill`

也就是说 TopicPilot-CN S13 已经有了一个**内部 Skill Registry +康检查 + skill签回写**，这就是 scientific-agent-skills 的"内部版"。对标动作是**对齐标准**而不是新建。

**可小型化补强（轻，思路）**：把 S13 SkillRegistry 朝 Agent Skills standard 的三个特征对齐——

| Agent Skills 标准 | TopicPilot-CN状 | 小型化动作 |
|---|---|---|
| SKILL.md frontmatter（name/description/required_environment_variables） | 已读 SKILL.md要，无统一 manifest 字段 | 给内部 skill一个最小 manifest（name/desc/required_env） |
| provenance 元数据（来源/版本/SHA） | 无 | skill来源 + 版本，与 EvidenceRef 同构 |
| 可移植性（metadata 单行 JSON + 未知字段忽略） | 单 host 内部用 | manifest 格式对齐标准，未来可被外部 host 发现 |

**实现边界与代价**：design-only，最小 demo。给 registry.json 加一个 `manifest: {name, description, required_env, version}`，health_check查 manifest整性 + 2 条 pytest。**零 GPU，无新依赖**。

### 9.3 企业技能库对标（直接命中"贴近求职的企业化技能库"）

| scientific-agent-skills念 | 企业技能库对标 | TopicPilot-CN脚 |
|---|---|---|
| Agent Skills open standard | 开放能力标准 /件规范 | S13 SkillRegistry对齐标准 |
| SKILL.md frontmatter | skill manifest（类比 package.json / pyproject.toml） | registry.json + manifest |
| `gh skill install` + provenance | 供应链完整性（SBOM念）| skill 版本/来源可追溯 |
| 可移植性（多 host 发现） | 配置驱动 + 可插拔组件 | 已是需求清单明的面试亮点 |
| Autoskill（工作流生成 skill） | 经验沉淀→可复用资产 | 与下方 3.1 MetaClaw互补 |
| NemoClaw default-deny networking | 能力可声明、可审查、可拒绝 | 2.4 PromptProtocol/action whitelist同构 |

### 9.4 与第 3三个补强点的交叉（这条参考补了什么）

- **vs 3.1 MetaClaw注入**：Autoskill 与 MetaClaw都是"经验→可复用资产"，但粒度不同——Autoskill把一次工作流沉淀成 skill（"怎么做"），MetaClaw把失败沉淀成 prompt overlay（"别踩什么坑"）。TopicPilot-CN小型化选 MetaClaw（更轻、零额外结构），讲法上并列对标 Autoskill，叙事更完整。
- **vs 3.2 多层验证链**：scientific-agent-skills 的 database-lookup skill强调"deterministic, provenance-rich access to 78+ databases"——这正是 3.2 Layer 2"来源权威性交叉命中"想要的可追溯访问理念。provenance-rich retrieval是验证链的反面：先保证检索来源可追溯，再谈验证。
- **vs 2.4 PromptProtocol**：scientific-agent-skills安全口径（review before install、default-deny networking）与 TopicPilot-CNaction whitelist +最小权限同构——都是"能力可声明、可审查、可拒绝"，只是它管的是 skill加载，我们管的是 LLM渲染。讲法上可以合一："我对内对外都用同一套可声明、可审查、可拒绝的边界模型。"

### 9.5 诚实划界

- **不照搬 147 个具体科研 skill**：protein docking、RNA velocity、分子动力学不在 TopicPilot-CN题判断范围。的是**standard + registry + provenance + portability**这套"怎么管 skill"的工程范式，不是 skill 内容。
- **不引 `npx skills add` / `gh skill`**：那是外部分发链路，TopicPilot-CN是单仓内部 registry，自洽即可。
- 这条划界正是需求清单"配置驱动与可插拔组件是面试亮点"的直接落地：**讲清"我借的是治理范式不是 skill 内容"，比"我接了 147 个 skill"更可信。**

### 9.6 一句话面试话术（含两个参考）

"我参考了两个项目：ARC给了 23段流水线的编排叙事，我对应到了 5+4 Gate + PIVOT；scientific-agent-skills给了企业技能库的治理范式——开放 manifest、provenance、可移植、Autoskill沉淀——我对应到了项目已有的 S13 SkillRegistry并对齐标准。两者一纵（流水线）一横（技能库），覆盖了 AI程岗位'编排能力'和'平台能力'两个维度。"

---

## 附：参考文与项目对应速查

- ARC考文：《全自动科研论文生成：AutoResearchClaw度技术解析》（aiming-lab，GitHub: aiming-lab/AutoResearchClaw）
- scientific-agent-skills考文：K-Dense-AI/scientific-agent-skills（147 科研 skill + 100+ 数据库 + Agent Skills 标准，见第 9节）
- 本文件定位：docs/interview/AutoResearchClaw_对标与小型化移植.md
- 关联面试材料：
  - docs/interview/Technical_Highlights.md（三档口径来源）
  - docs/interview/RAG_Design_Explainer.md / Deep_Dive_QA_RAG.md（3.2 关联）
  - docs/interview/Agent_Memory_Explainer.md / Deep_Dive_QA_Memory.md（3.1 关联）
  - docs/interview/MultiAgent_Expansion_Design.md / Deep_Dive_QA_Agent.md（2.7 关联）
  - docs/interview/Known_Limitations_For_Interview.md（第 4划界关联）
  - Plan/PaperAgent_面试导向需求清单.md / Plan/PaperAgent_面试导向长期改进SPEC.md（求职口径来源）
- 已核查的代码事实（用于"现状"陈述）：
  - apps/api/app/services/verification.py：单层平台分发验证器（verify_arxiv/github/huggingface/kaggle/generic_url + paper_metadata + skipped），置信度 0.0-0.85，无多层链路与 verification_report 产物
  - 多源检索（OpenAlex/arXiv/GitHub/HF）：Session 14 已落地
  - Evidence删除保留 Trace + WorkspaceCommand览确认：Session 42
  - PIVOT 三档路线：Session 04 / 28
  - S13 内部 Skill Registry：apps/api/app/services/skill_registry.py 加载 registry.json 读 SKILL.md要，提供 list_skills/get_skill/health_check；验成后由 verification.py 用 source_to_skill打 validated_by_skill签


---

## 10.面试材料交叉引用：对标后哪些点讲得更好

> 本节基于实际读到的 docs/interview/ 下面试材料（Interview_QA_Cards 30 / Resume_Bullets / Agent_Memory_Explainer / RAG_Design_Explainer / Failure_Cases /试需求清单 /SPEC 等）。口径：只列"对标文档给对应补强思路后，在面试中会讲得更好"的点；对标没覆盖到的，诚实标为"对口标无补强（保持现状）"，不冒充。
> 两个参考项目对试材料的增益是**给已有项目点配套企业技能库语言和对照叙事**，不是新增声称的能力。

### 10.1面试文档点 → 对标覆盖 → 加在哪

| 试文档 |到的点 | 对标覆盖位置 | 对标后讲得更好的理由 |
|---|---|---|---|
| Interview_QA_Cards Cat1 RAG Q1 |向量库 /三线检索 /源去重 | §2.3 + §3.2 |有口径只讲"我不依赖向量库"；对标后能追加"且验证是多层链（§3.2），对标 ARC 四层引用验证"，把"为什么不用向量库"从防御性回答升级成"我有结构化反幻觉"叙事 |
| Interview_QA_Cards Cat1 RAG Q2 | LLM rerank / review_status /levance scoring | §3.2 Layer 4 内容相关性 | rerank 已有；对标后能讲"rerank 是召回侧，验证链 Layer4 是内容侧判定（只判定不入 supports）"，区分两个层次，回答更清楚 |
| Interview_QA_Cards Cat1 RAG Q4 | 并行检索 / heuristic fallback / SSE | §3.3 显式熔断 |有口径是"我有 fallback"；对标后能讲"fallback在升级成 CircuitBreaker +数退避（§3.3思路），对标 Resilience4j"，把容错从兜底讲成可观测机制 |
| Interview_QA_Cards Cat3 Memory Q | RunEvent / Trace /回放 | §3.1 MetaClaw注入 |有口径是"有 Trace可回放"；对标后能讲"且有教训沉淀反哺到 prompt（§3.1），对标 MetaClaw/Autoskill"，从"记录"升级成"自我改进闭环" |
| Interview_QA_Cards Cat4 MCP | isToolAllowed /权限面 | §2.4 + §9.2 | scientific-agent-skills（§9）的 default-deny networking / provenance / review-before-install给 MCP权限面提供了企业治理语言——能讲"我和 skill库的安全模型同构：能力可声明、可审查、可拒绝" |
| Interview_QA_Cards Cat6 Safety | action whitelist /禁任意 JS | §2.4 | ARC safety +ientific-agent-skills安全口径给已有 whitelist供了对照叙事（OWASP LLM Top 10 /箱），从"我有白名单"升级成"我按企业安全范式做的边界" |
| Resume_Bullets | 5级证据晋升 / RunEvent溯源 /模板合规 hard-block | §2.3 / §2.5 / §2.6 |历亮点不变；对标后每条都能配一个"企业技能库对标"（Saga偿 / CI-CD制品 / Review回环），让简历话术直接对得上企业 JD关键词 |
| Failure_Cases | 后端离线 /出阻塞 /据不足 | §2.5 readiness + §4划界 | ARC诚实划界（§4：不跑实验/LaTeX）给 Failure_Cases 了"我刻意没做 X因为范围是 Y"的诚实叙事模板，比硬讲"都做了"可信 |
|试需求清单 §7短板 | "MetaClaw忆 / RAG真 Hybrid / MCP暴露 未闭环" | §3.1 / §3.2 / §3.3 + §9 |求清单列的 7条短口中，3条被对标文档直接给了思路方向（教训注入 /验证链 /断），剩余按§4诚实划界。短口有了明确的"补强路or"> |

### 10.2试讲解的"3个最高性价比讲法"（对标后建议新增到 Demo_Script）

按"讲解价值 ×准备成本"排序，建议在 3min / 10min Demo本里追加这 3句对照叙事：

1. **容错 → "我有可观测的容错链，不是写死兜底"**（§3.3 + QA Cat1-Q4）：现有"SSE + fallback"回答之后追加一句"fallback向是 CircuitBreaker机，对标 Resilience4j"。
2. **反幻觉 → "验证是多层链，不是单层 URL"**（§3.2 + QA Cat1-Q1/Q2）：现有"Candidate != Evidence"回答之后追加"验证链对标 ARC 四层引用验证，产 verification_report 引用级血缘"。
3. **自我改进 → "Trace 不只是回放，还反哺 prompt"**（§3.1 + QA Cat3）：现有"RunEvent可回放"之后追加"教训沉淀对标 MetaClaw训系统，但不接外部依赖，做成本地 lessons.jsonl overlay"。

### 10.3 诚实缺口（对标无补强，保持现状回答）

- **多模态数据处理**（QA Cat1-Q3到）：对标文档不覆盖（TopicPilot-CNEvidenceItem已有五类型，但不做多模态解析）；保持现有回答。
- **检索结果缓存 /LRU**（QA Cat1-Q4险补充提到）：对标文档未涉及；保持现有"未做缓存"诚实回答。
- **真实向量库接入**：§4明确划界为不适用；保持"lightweight索为主"的回答。

这些缺口**不因为有对标文档就改口径**，避免把"思路补强"误说成"已落地"——守 Technical_Highlights 三档边界。


---

## 11.求职技术深度分层话术（初级 / 中级 / 高级）

> 本节直接回应用户诉求「这个技术在求职中技术深度如何」。同一条技术点，按面试岗位档位给三种讲法，并标注**诚实天花板**——这个项目（MVP模、当前落地范围）讲到哪一档可信、再往上就是吹。口径守 Technical_Highlights 三档：implemented 能现场点开，lightweight 能讲清取舍，design-only须先声明「这是设计、未落地」。
>
>读方式：面试官问到的深度 = 你能答到的最深档；超过天花板的一律切回 design-only界，不要硬撑。

### 11.1 多阶段流水线 + Gate（§2.1，implemented）

|位 |法 | 诚实天花板 |
|---|---|---|
| 初级 | 「我把开题判断做成 5状态机，每步可确认或重跑，不是一次 LLM 出全报告。」 | 可信，能现场演示。 |
| 中级 | 「每个 Gate 是可补偿事务（Saga）：reject 即回滚到上一步稳定态，而非全盘重来。对标 Airflow/Temporal 的 decision point + LangGraph checkpoint。」 | 可信，有代码 + Trace 回放佐证。 |
| 高级 | 「选状态机而非 LangGraph runtime，是因为 5 + 4 Gate 的规模用不上 StateGraph久化与中断恢复，重 runtime 是负资产；但接口已留好可映射到 StateGraph + interrupt。」 | **天花板=中级**。「已映射到 LangGraph」是吹——design-only，没接 runtime。切回「设计可映射、未接」。 |

**反问防线**：「为什么不用 LangGraph？」→模不需要、状态机更可调试、runtime 侵入大；接口预留映射。

### 11.2 PIVOT策循环（§2.2，implemented）

|位 |法 | 诚实天花板 |
|---|---|---|
| 初级 | 「可行性裁决不是二元能/不能，而是 proceed / refine / pivot 三出口。」 | 可信。 |
| 中级 | 「pivot 不是失败，是带版本化的降级路线（保守/平衡/激进三档），避免在学生做不动的题上耗半年；本质是状态机分支 +偿回滚。」 | 可信。 |
| 高级 | 「PIVOT 的版本化是产物级的：每次 pivot 产出一个工作包快照，可对照、可回退；这和 A/B版本化同构。」 | **天花板=中级**。「产物级快照对照」部分 implemented（FinalPackage 有版本），「A/B并行」没做。切回「单线版本化、非并行 A/B」。 |

### 11.3 Candidate→Evidence删除留 Trace（§2.3，implemented）

|位 |法 | 诚实天花板 |
|---|---|---|
| 初级 | 「检索到的候选要过 URL Verified + 用户确认才能写进报告；reject 也留 Trace，不物理删。」 | 可信。 |
| 中级 | 「等于数据血缘 + 逻辑删除：报告里每个 cite 能追溯到来源时刻；软删除是因为开题现场要能解释『为什么不选那条』。」 | 可信。 |
| 高级 | 「Trace 是 provenance的：谁、何时、从哪个源、置信度多少都进 RunEvent；对标 OpenLineage 的列级血缘。」 | **天花板=中级偏上**。血缘是事件级（RunEvent）而非严格列级 lineage；讲「事件级 provenance」最稳，讲「列级 lineage」偏类比。 |

### 11.4 PromptProtocol + WorkspaceCommand览确认（§2.4，implemented）

|位 |法 | 诚实天花板 |
|---|---|---|
| 初级 | 「LLM出不直接进 DOM、不直接改状态；渲染只认白名单组件，写操作先预览再确认。」 | 可信，现场可点。 |
| 中级 | 「这是对 OWASP LLM Top 10 里 prompt injection / 过度授权的工程回应：13 白名单组件 + 5 白名单 action + 7 forbidden pattern + 2-phase commit预览确认。」 | 可信。 |
| 高级 | 「我和 skill（scientific-agent-skills 的 default-deny networking / review-before-install）用同一套『能力可声明、可审查、可拒绝』边界模型——对内管 LLM染，对外管 skill 加载。」 | **天花板=中级**。「对外管 skill 加载」是 S13 内部 registry 的 health_check，不是 review-before-install。切回「内部 registry 已有 health 黑名单，外部 review-before-install 是对标下一步」。 |

### 11.5 MetaClaw教训注入（§3.1，design-only）★最独特

|位 |法 | 诚实天花板 |
|---|---|---|
| 初级 | 「我想做 run败留 lesson，下次注入 prompt开已知陷阱。」 | **design-only——必须先声明「这是设计、未落地」**。 |
| 中级 | 「对标 ARC 的 MetaClaw：教训结构化成 (stage, failure_signature, lesson)，按 stage确匹配注入而非语义检索，避免无关记忆干扰；零 RLHF/零参数更新，用 overlay非改 base prompt，可回滚。」 | design-only，讲法可信。 |
| 高级 | 「结构是 reward（失败信号）→ policy（prompt）的极简 RLAIF，但用反哺而非梯度；对照实验方向上预期降重试率，而不是声称复现了 ARC 的 -24.8%。」 | **天花板=中级**。「复现了 -24.8%」是吹——没跑量化对照。切回「方向预期、未跑对照实验」。 |

### 11.6 多层引用验证链（§3.2，lightweight → 可补强）

|位 |法 | 诚实天花板 |
|---|---|---|
| 初级 | 「候选证据过 URL Verified（HTTP HEAD + 元数据正则）才进池。」 | 可信（implemented 单层）。 |
| 中级 | 「当前是单层；方向上扩成四层链：可链接性 → 来源权威性交叉命中 → 元数据完整性 → 内容相关性 LLM定，产 verification_report.json 引用级血缘。LLM 只判相关性不入 supports。」 | lightweight→design，讲法可信。 |
| 高级 | 「对标 ARC 四层验证 + Great Expectations/dbt 的数据质量门；每层独立可测、失败即降级或移除。」 | **天花板=中级**。「已实现四层」是吹——只到单层 + 设计。切回「单层已落地、多层是设计稿」。 |

### 11.7 显式熔断 + 自愈重试（§3.3，implicit → 可显式化）

|位 |法 | 诚实天花板 |
|---|---|---|
| 初级 | 「多源检索 OpenAlex了会自动转 arXiv，LLM 不可用会 fallback 到启发式。」 | 可信（implicit fallback 已落地）。 |
| 中级 | 「当前是写死的 try/except；方向上显式化成极简 CircuitBreaker：closed→half_open→open +数退避 + 诊断日志，复用已有的 structured_log 和 stale 机制做自愈触发。不引 Resilience4j，自写讲清原理。」 | design，讲法可信。 |
| 高级 | 「熔断三件套（熔断 + 降级 + 限流 + 重试退避）是任何调外部 API统都该有的工程成熟度信号；AI 项目里讲比 CRUD 里讲更值，因为 LLM/检索源不稳定是真实痛点。」 | **天花板=中级**。「已有熔断器」是吹——只到 fallback。切回「fallback 已有、CircuitBreaker 是设计」。 |

### 11.8 S13 SkillRegistry ↔ Agent Skills 标准（§9.2，implemented → 可对齐标准）

|位 |法 | 诚实天花板 |
|---|---|---|
| 初级 | 「项目有内部 Skill Registry：加载 skills/registry.json、读 SKILL.md、有 health_check、验证后给证据打 validated_by_skill。」 | 可信。 |
| 中级 | 「对标 scientific-agent-skills 的 Agent Skills 开放标准：manifest(name/desc/required_env) + provenance(来源/版本/SHA) + 可移植；S13 已是内部版，对齐动作是给 registry.json 加最小 manifest。」 |法可信（对齐是 design）。 |
| 高级 | 「我借的是治理范式不是 skill 内容——不照搬 147 个具体科研 skill（蛋白对接等不在开题范围），只对齐 manifest + provenance + portability 这套『怎么管 skill』，等价于 SBOM念用于能力资产。」 | **天花板=中级偏上**。「已对齐标准」是吹——只到内部 registry。切回「内部 registry 已落地、开放标准对齐是设计」。 |

---

## 12.面试点增强速查表（对标前 → 对标后 delta）

> 回应用户诉求「写这里有面试文档中提到的哪些面试中会更好一点」。每行 = 一个面试文档里的具体点，给出对标前的话术、对标后的话术、强度档提升、出处坐标。出处指向 docs/interview文件 或 Plan/PaperAgent_面试导向需求清单.md / SPEC.md。

|试点 | 出处 | 对标前话术 | 对标后话术（更强） | 强度档 |
|---|---|---|---|---|
| RAG 为什么不只向量库 | QA_Cards Cat1-Q1 /求清单§4.3 | 「我不依赖向量库，三线检索。」 | 「三线检索 + 多层验证链（§3.2），对标 ARC 四层引用验证，产 verification_report 引用级血缘。」 | 中→中高 |
| 如何避免幻觉 |求清单§4.3「避免幻觉」/求清单§6短板 | 「Candidate != Evidence + URL Verified。」 | 「单层 Verified → 四层链（可链接/权威/完整/相关），LLM 只判不入 supports，对标 ARC + Great Expectations 数据质量门。」 | 中→中高 |
| Agent忆怎么做 | QA_Cards Cat3 /求清单§6板1 | 「RunEvent/Trace 可回放。」 | 「可回放 +训沉淀反哺 prompt（§3.1 lessons.jsonl overlay），对标 MetaClaw/Autoskill，从记录升级成自我改进闭环。」 | 中→中高（独特） |
|具调用失败/路由错误 |求清单§4.3「工具调用」/ QA Cat1-Q4 | 「多源有 fallback。」 | 「fallback → 显式 CircuitBreaker +数退避 + 诊断日志（§3.3），对标 Resilience4j，从兜底升级成可观测容错链。」 | 中级→中级偏上 |
| 什么让 AI 做/不让 |求清单八股7 / QA Cat6 Safety | 「action whitelist +任意 JS。」 | 「+ WorkspaceCommand览-确认（2-phase commit）+ 与 skill default-deny 同构的『可声明/可审查/可拒绝』边界模型（§2.4/§9.2），对标 OWASP LLM Top 10。」 | 中→中高 |
| 多 Agent么设计 |求清单§4.3「多 Agent」/ QA Cat2 | 「当前单 Agent + Gate。」 | 「单 Agent + Gate 是主动选择（避免 Supervisor瓶颈）；design-only 保留可扩展架构，能讲清拆分时机/层级路由/并行投票/成本上限（§2.7），对标 CrewAI/AutoGen/LangGraph。」 | 中级（加边界叙事） |
|型选型与降级 |求清单§4.3「模型选型」 | 「LLM 可降级 heuristic。」 | 「input-prefer 是模型无关 LLM Gateway形（auto/llm/heuristic），对标 LiteLLM，可替换/可降级/可旁路（§2.8）。」 | 中级（加对标） |
| RAG实 Hybrid/Eval 闭环 |求清单§6板1 | 「有 rerank + S17/S31 baseline。」 | 「rerank 是召回侧；+证链 Layer4 是内容侧判定（§3.2），区分两层次；+ 对照实验叙事方向（重试率/完成率，对标 MLflow/Ragas）。」 | 中→中高 |
| MCP / Function Calling露 |求清单§6板4 / QA Cat4 | 「有 isToolAllowed，未暴露 MCP。」 | 「内部已有 SkillRegistry + skill回写（§9.2），对齐 Agent Skills 标准；MCP露可复用 registry 的 manifest+provenance 口径。」 | design加分 |
|败案例/诚实划界 | Failure_Cases /求清单八股7 | 「讲后端离线、导出阻塞。」 | 「+ ARC §4 诚实划界模板：不跑实验/LaTeX/ACP，『刻意没做 X 因为范围是 Y』比硬讲都做了更可信。」 | 加可信度（非强度档） |

### 12.1 一句话总结这条线

「对标后没新增任何声称的能力，而是给已有每个项目点配上企业技能库的语言和对照叙事（Saga / 数据血缘 / Resilience4j / Great Expectations / DSPy / Agent Skills 标准 / OWASP LLM Top 10 / LiteLLM），让面试官直接对得上 JD 关键词，同时守住三档口径不冒充。」

### 12.2 诚实红线（本轮不变）

- §3.1教训注入、§3.2多层链、§3.3显式熔断、§9.2标准对齐——全部 design-only 或 lightweight，**不能在面试里说成 implemented**。
- 量化数字（-24.8% 重试率等）是 ARC 的，**不是本项目的复现**；只能说「方向预期」。
- 企业技能库对标是**讲法对标、非依赖引入**：不引 Resilience4j/Sentinel/DSPy/LiteLLM，自写极简版讲清原理。

---

## 13. 本轮求职向增强摘要（2026-06-22）

本轮在原文 §0-§10上追加 §11/§12，直接回应用户「这个技术在求职中技术深度如何、为什么这么用、贴近求职企业化技能库（小型）、主要是思路不一定要实现、写哪些面试点会更好」：

- **§11职技术深度分层话术**：8 个最值得讲的技术点，各给初级/中级/高级三档讲法 + 诚实天花板（讲到哪一档可信、再往上是吹）+ 反问防线。
- **§12面试点增强速查表**：10 个面试文档里的具体点，给「对标前→对标后」话术 delta + 强度档提升 + 出处坐标。
- **口径不变**：三档（implemented/lightweight/design-only）不破，量化数字是 ARC本项目，企业技能库对标是讲法非依赖。
- **关联回写建议（未越界执行）**：建议把 §11 天花板表和 §12 delta 表反哺进 Technical_Highlights.md（三档口径）与 Demo_Script_3min/10min.md（追加 3对照叙事），但本轮不直接改这些文件；是否回写由后续 Session定。


## 14. 多论文 RAG /知识图谱实现调研（求职思路向，design-only）

> 本节响应用户追加需求："将多论文 RAG /知识图谱实现的调研写进去"。
> 性质同全文：思路为主，不强制实现，不破坏三档口径。最小可测单元列在 §14.7。
> 对标：ARC §3.2 四层引用验证（单篇引用级）的上游 + Microsoft GraphRAG（社区/局部查询） + Agentic RAG（判断后动作）。

### 14.1现状与缺口

当前 RAG 仍是"单论文向"：

- 数据流：`query → candidate paper → evidence → 单篇引用`。
- S14 已有多源检索（OpenAlex / arXiv / GitHub / HuggingFace），但融合形态是"多篇并列候选列表"，没有跨论文的关系建模。
-面试高频追问"这几篇论文之间是什么关系"（cites / extends / contradicts / uses-same-dataset）时，当前只能靠 LLM 口述，没有结构化证据落盘。

缺口对应面试需清单：

- §6短板 1："RAG实 Hybrid Search / Rerank / Eval 还没有形成面试级闭环"。
- §6短板 7 里隐含的 GraphRAG / Agentic RAG方法没绑定到项目结构。

### 14.2 多论文 RAG思路（小型化，核心抽象）

核心抽象：`LinkwiseContext = (focus_paper, related_papers[], relation_type, evidence_refs[])`

- `relation_type`举：`cites` / `extends` / `contradicts` / `uses_same_dataset` / `co_cited_by`。
- 不做全文 NER关系（幻觉风险）。只从 OpenAlex / arXiv 的结构化 metadata（`references` / `authors` / `abstract` / `dataset` 字段）抽取，是数据驱动不是 LLM断。
-索增强：拿到 focus paper 后，expand 一步到 `references + cited_by`（这俩 API 已在 S14已接入），形成 1-hop邻域，作为 `LinkwiseContext.related_papers`。
-合策略：不是把多篇拼进一个 context window，而是按 `relation_type` 分组喂给不同 Gate：
  - `contradicts` 组 →给"可行性风险"判断（PIVOT发条件之一）。
  - `extends` 组 →给"技术路线延续性"判断。
  - `uses_same_dataset` 组 →给"可复现性"判断。
- 对标 ARC：ARC §3.2 四层验证是单篇引用级；多论文 RAG 是引用图级，恰好是 §3.2 的自然上游（先有关系图，再对每条边做四层验证）。

### 14.3知识图谱思路（PaperKG，design-only）

Entity 类型：`Paper / Method / Dataset / Author / Venue / Task`

Relation 类型：`cites / proposes_method / evaluates_on_dataset / extends_method / contradicts_claim / authored_by / published_in`

存储（小型化关键决策）：

- 不引 Neo4j / 不引图数据库。
-在 `data/paperkg.json`（节点表 +表），按 `paper_id`引邻域。
- 对标 S13 `SkillRegistry` 的 "json + 加载器 + health_check"式——PaperKG同一套制品形态，保持认知一致性。

查询：

- 给 `focus paper`，返回 1-hop 子图（节点 +）。
- 给 `method`，返回所有使用该方法的 paper表。
- 不做图查询语言，只做内存 `dict`找。

社区发现（可选，design-only 中的 design-only）：

-简 label-propagation（约 15 行）做 method类，用于"同一方法的不同论文系"。
- 对标 GraphRAG 的 community summarization路，但**不做 LLM区摘要**（避免成本 +觉），只做拓扑聚类。

### 14.4 小型化取舍（诚实划界）

不做：

-实向量库嵌入式图存储（Qdrant / Chroma 仍不进 MVP链路）。
- Neo4j / 全图 GNN / 图神经网络节点分类。
- LLM 自动抽三元组（关系必须来自 metadata，不是 LLM断，守住"LLM 不直接写 evidence"不变式）。

做：

- metadata动的关系抽取（`references` / `cited_by` 是结构化字段）。
- JSON落盘 + 内存查找。
- LinkwiseContext 按 `relation_type` 分组喂 Gate。

口径：当前 `design-only`。若落地最小单元（§14.7）可升 `lightweight`，但必须在 acceptance report 里写明"用了 ARC个思路 + 小型化取舍 + 对应哪个企业技能库概念"，且不标 `implemented` 除非真写测试通过。

### 14.5 对标 GraphRAG / Agentic RAG（企业技能库口径）

- **GraphRAG（Microsoft）**：实体抽取 +区摘要 + 全局/局部查询。我们小型化：只做局部（1-hop 子图），不做全局 LLM要。
- **Agentic RAG**：检索-判断-再检索的循环。我们已有 PIVOT策循环（§2.2）+索熔断（§3.3），天然贴合 Agentic RAG 的"判断后动作"模式，不另起炉灶。
- 对标话术（可直接进 Demo_Script）：

> 多论文 RAG 不是把多篇拼进一个 context，而是按引用关系分组喂给不同 Gate；PaperKG 不是图数据库，是 JSON落盘的内存子图查询，对应 GraphRAG 的局部查询模式。关系抽取来自 metadata，不用 LLM断，守住 evidence则不变式。

### 14.6面试讲法增强（回写建议，本轮不直接改）

- `Deep_Dive_QA_RAG.md`：建议加一条 Q"如果面试官问多篇论文关系怎么建模"，A 引用 §14.2-§14.3。
- `Technical_Highlights.md`：PaperKG 可作为 design-only 新增亮点候选（留给后续 Session 评估，不在本轮直接加，避免超出当前 SOP围）。
- `RAG_Design_Explainer.md`：建议补一节"从单论文 RAG 到多论文 RAG"，引用 §14.2 的 LinkwiseContext象。

以上均为回写建议，本轮不直接改这三份文件；是否回写由后续 Session 定（同 §13 口径）。

### 14.7 最小可测单元（不强约束，用户定）

| 优先级 |径点 | 最小单元 | 估工作量 |
|---|---|---|---|
| P3 | PaperKG 加载器 | `load_paperkg()` + `PaperNode` dataclass + 1 pytest | 半天 |
| P3 | 1-hop询 | `get_neighbors(paper_id, relation_type)` + 1 pytest | 半天 |
| P3 | LinkwiseContext 分组 | `build_linkwise_context(focus_paper)` 按 relation_type 分组 + 1 pytest | 半天 |

落地后应在 acceptance report 写对照叙事（GraphRAG部查询 / Agentic RAG断后动作 / metadata动不 LLM断），并回写进 `Deep_Dive_QA_RAG.md` 与 `RAG_Design_Explainer.md`。

### 14.8 与 CLAUDE.md 不变式对齐

- 设计不冒充已落地：§14 全部 design-only，落地与否以代码 + pytest 为准。
- LLM 不直接写 evidence / 不参与真伪判定：关系抽取来自 metadata 结构化字段，不来自 LLM断；LLM 只在"判断后动作"环节给出建议，不写 evidence。
- pytest 总数只增不减：本轮不新增/删除代码，无 pytest 义务变动。
- 数据从 .env 读不引未列依赖：本轮无新依赖、无新代码。
- LLM径配 heuristic fallback：未涉及，不变式保持。

### 13.1追加：§14 多论文 RAG /知识图谱实现调研

应用户追加需求，本轮在 §11/§12基础上再补 §14「多论文 RAG /知识图谱实现调研」，design-only，核心：

- `LinkwiseContext`把多篇论文按 `relation_type`（cites/extends/contradicts/uses_same_dataset）分组喂给不同 Gate，而不是拼进一个 context window。
- `PaperKG` JSON盘 + 内存子图查询，对标 GraphRAG查询模式，不引 Neo4j、不用 LLM断关系（守 evidence则不变式）。
- 与 §3.2层引用验证链构成上下游：先有关系图（§14），再对每条边做四层验证（§3.2）。

口径同 §13：design-only，本轮不落地代码；最小可测单元见 §14.7，落地需另起 acceptance report写对照叙事。
