# PaperAgent 有界 Agentic Academic RAG 开发计划

## 1. 产品定位

PaperAgent 是学术研究执行层，负责把用户问题、PaperClaw 提供的论文对象、项目 Memory 和检索能力组织成可审计的研究流程。

PaperAgent 负责：

- 研究问题理解；
- Query 分类、分解与改写；
- 检索通道选择；
- 有界补救检索；
- 证据审查、冲突处理和充分性判断；
- baseline、module、gap 与 compatibility 推理；
- 实验和消融设计；
- 学术输出与人工 Review。

PaperAgent 不重复建设通用文件索引、长期 Memory、Artifact Store、Task Runtime、Tool 权限和底层多 Agent 基础设施；这些由 PaperClaw 提供。

## 2. 目标工作流

```text
Research Request
        |
        v
Intent and Constraint Analysis
        |
        v
Query Classification / Decomposition / Rewrite
        |
        v
Retrieval Plan
  | text | page | figure | table | equation | graph | repository |
        |
        v
PaperClaw Retrieval Service
        |
        v
Evidence Review and Sufficiency Gate
        |
   +----+-------------------------+
   | sufficient                  | insufficient / conflict
   v                             v
Synthesis                bounded corrective retrieval
   |                             |
   +--------------+--------------+
                  v
Baseline / Gap / Module Reasoning
                  |
                  v
Compatibility and Novelty Audit
                  |
                  v
Experiment and Ablation Design
                  |
                  v
Human Review
                  |
                  v
Structured Academic Export
```

## 3. 有界 Agentic RAG

PaperAgent 采用有界 Agentic Retrieval，不允许自由无限循环。

默认最多：

```text
1 次主检索
1 次补救检索
1 次冲突核查
```

每轮必须记录：

- 查询目标；
- Query rewrite；
- 选择的检索通道；
- filter 与预算；
- 返回候选；
- 被接受和拒绝的证据；
- 证据缺口；
- 停止原因。

## 4. Query 类型与路由

## 4.1 论文身份类

示例：

- 找到某篇明确论文；
- 确认 DOI、作者、年份；
- 判断两个文件是否是同一论文。

路由：metadata + exact lexical + identifier index。

## 4.2 方法解释类

示例：

- 这篇论文的方法流程是什么；
- 模型由哪些模块组成；
- 损失函数有哪些部分。

路由：Method section + Equation + Algorithm + Figure + page visual retrieval。

## 4.3 架构图与示意图类

示例：

- 找出整体架构图；
- 比较三篇论文的网络结构；
- 某模块在图中接在哪里。

路由：page / figure visual retrieval + caption + surrounding paragraphs。

不能只依赖离线 Caption；最终推理应回读原始页面或 Figure 区域。

## 4.4 实验数值类

示例：

- 表 3 中哪个方法最好；
- 某数据集上的 F1；
- 消融后下降多少。

路由：Table / Cell + caption + experiment section。

输出必须带：

- 表格编号；
- 页码；
- 行列身份；
- 数值单位；
- 是否为作者结果或引用结果。

## 4.5 跨论文比较类

示例：

- 比较方法、数据集、指标和性能；
- 寻找可复现 baseline；
- 查找模块来源。

路由：多论文结构化检索 + relation graph + visual/object retrieval + reranking。

## 4.6 学术裁缝类

路由：

```text
Task and constraints
-> baseline evidence
-> gap evidence
-> module evidence
-> compatibility evidence
-> experiment evidence
-> GO / REVISE / NO-GO
```

## 5. Evidence Review

每个 EvidenceCandidate 必须经过：

- identity verification；
- task relevance；
- role relevance；
- source type；
- claim support；
- version / locator 完整性；
- license / repository provenance；
- duplication 和污染检查。

分类：

- `accepted`；
- `rejected_identity`；
- `rejected_relevance`；
- `rejected_role`；
- `rejected_support`；
- `conflicted`；
- `unknown`。

每个最终 Claim 必须绑定一个或多个 accepted locator。

## 6. Corrective Retrieval

仅在以下情况启动补救：

- baseline 身份缺失；
- Figure 与正文解释不一致；
- Table 数值缺少行列语义；
- 论文之间证据冲突；
- 关键模块只有二手描述；
- 当前候选无法支持目标 Claim；
- 检索只命中摘要而缺少原文；
- 需要代码仓库验证实现。

补救动作：

- 改写 Query；
- 限定 section / object type；
- 切换文本与视觉通道；
- 扩展候选邻域；
- 沿 Citation / Repository 关系跳转；
- 调用受限 Coding Worker；
- 向用户索要指定论文或材料。

禁止因为证据不足而凭模型常识补齐关键事实。

## 7. 学术方法设计产物

## 7.1 Baseline Card

包含：

- 论文与代码身份；
- 任务与数据集；
- 输入输出；
- 核心结构；
- 训练目标；
- 许可证；
- 复现状态；
- 计算需求；
- 选择理由；
- EvidenceLocator。

## 7.2 Gap Hypothesis

使用可证伪形式：

```text
Under condition C, limitation L occurs because mechanism M;
adding intervention B should change metric Y without violating guardrail G.
```

## 7.3 Module Card

包含：

- 来源论文与代码；
- 原始用途；
- 当前拟议用途；
- 输入输出语义；
- shape / scale / normalization；
- mask / ordering；
- gradient / trainability；
- loss；
- 计算成本；
- 许可证；
- 假设和失败模式。

## 7.4 Compatibility Matrix

至少检查：

- semantic compatibility；
- tensor / interface compatibility；
- normalization；
- temporal / spatial order；
- gradient flow；
- objective compatibility；
- data availability；
- compute budget；
- license；
- evaluation fairness。

## 7.5 Experiment Matrix

必须包含：

- frozen baseline；
- strong comparison；
- full method；
- single-module ablation；
- leave-one-out；
- interaction ablation；
- parameter sensitivity；
- resource / latency / memory；
- failure case；
- seeds 和 uncertainty；
- stop condition。

## 8. 多模态证据生成策略

PaperAgent 回答图、表、公式问题时使用：

```text
retrieved original page or region
+ structured object
+ caption
+ surrounding paragraphs
+ neighboring references
```

禁止只依据：

- OCR 文本；
- 自动生成 Caption；
- 缩略图；
- 单个向量分数。

VLM 生成的解释标记为 `inferred`，原始图注、正文和表格值标记为 `verified`。

## 9. Graph-assisted Retrieval

关系图主要用于：

- baseline 演进路线；
- 方法引用来源；
- Dataset 与 Metric 传播；
- 模块与代码仓库关联；
- 跨论文多跳查询。

Graph 只用于候选发现和关系约束，最终 Claim 仍必须落到原始 PaperClaw EvidenceLocator。

## 10. 轻量 Coding Worker

PaperAgent 仅在论文方法理解和验证需要时调用 PaperClaw Coding Worker：

- 读取论文关联仓库；
- 定位模型、损失、数据加载与训练入口；
- 对照论文与代码；
- 提取配置、超参数和命令；
- 生成最小实验 Patch；
- shape / forward / gradient / tiny-batch 检查；
- baseline parity 检查；
- 输出 verified / pending / blocked。

不承担：

- 通用 IDE；
- 大型应用开发；
- 长期多分支维护；
- 自动部署；
- 未授权主分支修改。

## 11. PaperClaw 集成协议

PaperAgent 输入：

```text
ProjectContext
MemorySnapshot
PaperRecord summaries
RetrievalService handle
ArtifactService handle
CodingWorker handle
```

PaperAgent 输出：

```text
RetrievalPlan
EvidenceLedger
ClaimEvidenceMap
BaselineCard
GapHypothesis
ModuleCard[]
CompatibilityMatrix
ExperimentMatrix
ReviewDecision
MethodDraft
ResearchReport
```

所有输出必须使用 PaperClaw Artifact Revision 保存。

## 12. 开发阶段

## P0-A：Query Planner

- intent classification；
- query decomposition；
- multilingual rewrite；
- exact identity preservation；
- object/channel routing；
- bounded retrieval budget。

## P0-B：Evidence Ledger

- accepted / rejected / conflicted；
- claim-support binding；
- locator validation；
- cross-paper conflict handling；
- insufficient evidence route。

## P0-C：Multimodal Answering

- Figure 问答；
- Table 问答；
- Equation 问答；
- 架构图比较；
- 原页面证据回读。

## P0-D：Academic Tailoring Closure

- baseline selection；
- module attribution；
- compatibility；
- novelty；
- experiment matrix；
- GO / REVISE / NO-GO；
- human approval before academic prose finalization。

## P1-A：Relation Graph Reasoning

- Citation path；
- Method lineage；
- Dataset / Metric relationships；
- Paper / Repository linkage。

## P1-B：Quality Evaluation

- Query rewrite before / after；
- channel routing accuracy；
- Recall / MRR / nDCG；
- page and object recall；
- citation grounding；
- Table Cell extraction；
- baseline selection accuracy；
- compatibility review agreement；
- cost and latency。

## P2：Controlled Coding Validation

- repository analysis；
- minimal patch；
- intermediate verification；
- explicit Handoff。

## 13. 非目标

当前不优先：

- PixelRAG / PixSearch 式端到端像素级自主检索训练；
- 无上限 Agentic RAG；
- 自由多 Agent 搜索；
- 用 GraphRAG 代替原始证据；
- 依赖公开论文 API 才能完成核心任务；
- 把合成评测当作科学质量证明。

## 14. 推荐实施顺序

```text
1. Freeze PaperClaw <-> PaperAgent contracts
2. Query classification and channel routing
3. EvidenceLedger and locator validation
4. Figure / Table / Equation multimodal answering
5. Corrective retrieval and conflict handling
6. Baseline / Module / Compatibility / Experiment artifacts
7. Human review and export
8. Relation graph assistance
9. Real-paper benchmark and expert adjudication
10. Narrow Coding Worker validation
```

## 15. 第一阶段 GO 条件

- 同一接口能够处理文字、架构图、表格和公式问题；
- Query Planner 能选择正确检索通道；
- 最终 Claim 可以回到原始页面或对象区域；
- 证据不足时明确拒绝或请求材料；
- 可以完成一次多论文 baseline 与模块分析；
- 可以产出 Compatibility Matrix 与 Experiment Matrix；
- 合成、离线真实论文和人工专家评测分别报告；
- 不再依赖普通文本向量 RAG 作为唯一检索路径。
