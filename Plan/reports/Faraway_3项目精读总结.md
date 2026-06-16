# Faraway 3 项目精读总结

> 阅读日期: 2026-06-16
> 3 份文档: `TopicPilot-CN` (2341 行) + `GradThesis-CN` (841 行) + `ThesisFlow` (955 行), 共 4137 行
> 阅读方式: 并行 3 个 Explore agent 精读 + 提取设计思路 / skill / trick
> 目的: 给 TopicPilot-CN MVP (Phase 01-08 已完成) 提供后续优化参考

---

## 1. TopicPilot-CN (开题选题助手) — 最完整, 是当前 MVP 的源头

### 1.1 项目定位

> "面向中国研究生开题的证据驱动选题可行性评估与论文工作量规划 Agent"

**核心命题**: 不是"帮学生想新颖题目", 而是"判断现有题目是否能在毕业周期内完成"。这是和一般"科研灵感助手"最大的区别——创新性是结果, **毕业可行性才是目标**。

### 1.2 核心架构: 10 个 Agent + 15 字段 LangGraph State

| Agent | 职责 | 当前 MVP 状态 |
|---|---|---|
| Topic Parser | 9 字段拆解 (对象/场景/任务/模态/方法/数据/评价等) | ✓ Phase 02 部分实现 |
| Query Planner | 4 级检索词 (L0 精确/L1 同义/L2 去场景/L3 抽象) | ✓ Phase 03 实现 |
| Literature Scout | 文献调研 (OpenAlex/Semantic Scholar) | △ Phase 04 仅有 arXiv |
| Dataset Scout | 12 项硬指标验证数据集 | ✗ 缺 |
| Baseline Scout | 5 维评分 Baseline | ✗ 缺 |
| Benchmark Scout | 评价指标调研 | △ Phase 04 partial |
| GitHub Scout | 代码仓库 | ✗ 缺 |
| Carrier Risk Judge | 7 维航母风险 + 6 条硬性否决 | △ Phase 05 简化 |
| Pivot Planner | Topic Generalization Graph | △ Phase 05 简化为单点 |
| Work Package Designer | 2-3 个工作包 | ✓ Phase 06 实现 |
| Proposal Planner | 12 节开题报告 | △ Phase 07 简化为 10 节 |
| Opening Committee | 5 角色 11 类质询 | △ Phase 07 简化为 3 角色 |

### 1.3 关键设计思路

#### 1.3.1 TopicSpec 9 字段拆解 (§5.1)

把自然语言题目结构化为 `research_object / scenario / task / modality / method_family / target_problem / data_requirement / expected_output / evaluation_metrics`。**必须**拦截 12 个模糊词 (智能 / 高精度 / 实时 / 全场景 / 多模态 / 自适应 / 端到端 / 通用 / 精确测量 / 大模型 / 数字孪生), 强制给出可验证定义。

#### 1.3.2 4 级检索词扩展 (§5.2)

L0 原始精确题目 → L1 中英同义 → L2 去场景 → L3 抽象到底层任务。**目的**: 区分"真没研究" / "术语过窄" / "场景特定但任务成熟" / "底层任务成熟但场景数据缺失"。

#### 1.3.3 5 级裁决 GO/NARROW/PIVOT/PARK/STOP (§6.4 + §3.5)

反对"强迫所有题目进入 GO"的思路, 5 档:
- **GO** — 证据链完整, 进工作包设计
- **NARROW** — 范围过大, 缩小对象/任务/模态
- **PIVOT** — 资源不足, 转向相邻成熟问题
- **PARK** — 条件不具备, 未来重启
- **STOP** — 核心任务无法验证, 不适合作为学位论文

**分数门槛**: < 60 强制 PIVOT; 60-75 有条件通过; ≥ 75 可进工作包; 任一硬性条件失败不得通过。

#### 1.3.4 航母风险双轴模型 (§6.1)

不用单一"航母分数", 而是**两个主轴**:
- **Maturity** (研究基础成熟度): 论文 + 数据 + Baseline + 指标 + 迁移案例
- **Differentiation** (差异空间): 未解决问题 + 场景差异 + 性能/效率/鲁棒性缺口

形成四象限: 成熟+差异=安全区 / 成熟+同质=红海 / 不成熟+差异=造航母高风险 / 不成熟+无差异=死区。

#### 1.3.5 7 维风险加权公式 (§6.3)

`CarrierRisk = 0.15×R_lit + 0.20×R_data + 0.15×R_base + 0.10×R_eval + 0.15×R_resource + 0.15×R_scope + 0.10×R_wp`

每维 0/25/50/75/100 (极低/较低/中/高/极高). 判定: 0-29 较低 / 30-49 可控 / 50-69 高 / 70-84 强制 PIVOT / 85-100 STOP.

#### 1.3.6 6 条硬性否决条件 (§6.4) — **优先级高于综合分数**

任一触发立即 STOP, 不进工作包:
1. 无可获得数据且毕业周期内无法完成自采与标注
2. 无可执行评价方法且无法获得任何 Ground Truth
3. 必须依赖无法获得的设备或企业数据
4. 核心 Baseline 无代码且学生不具备从零复现条件
5. 两个以上核心前置假设均未验证
6. 工作包完全串行, 任何一步失败都导致整篇失效

#### 1.3.7 Topic Generalization Graph (§7.2) — **最有技术含量的子系统**

沿 6 维 (对象/场景/任务/模态/方法/数据) 建立可操作的父子图。每条退化路线**必须**满足: 2-5 篇真实相关论文 + 1 个可获得数据集 + 1 个可运行 Baseline + 明确评价指标 + 明确实验对照组 + 与学生资源匹配的算力估算。

#### 1.3.8 工作包评分公式 (§8.5)

`WorkPackageScore = 0.20×EvidenceSupport + 0.15×DataAvailability + 0.15×BaselineReadiness + 0.15×ExperimentalClarity + 0.10×Independence + 0.10×ChapterFit + 0.10×ResourceFit + 0.05×Demonstrability`

**5 条硬性条件**: 无数据不能通过 / 无评价指标不能通过 / 无对照组不能通过 / 仅有文字无实验不能通过 / 两 WP 解决同一问题且实验重复不能同时通过。

#### 1.3.9 5 种工作包组合模板 (§8.4)

模板 1: 数据+方法 / 模板 2: 方法+方法 (仅解决不同问题时) / 模板 3: 方法+系统 / 模板 4: 数据+方法+泛化 / 模板 5: 二维+三维+Agent。

#### 1.3.10 委员会 5 角色 + 11 类质询 (§10.10)

5 角色: 领域专家 / 方法专家 / 工程应用专家 / 数据与实验专家 / 严格型导师。
11 问: 为什么必须做 / 为什么是这个对象 / 数据从哪来 / 没自有数据怎么办 / Baseline 能否复现 / 两 WP 是否真不同 / 创新点怎么验证 / 主模块无效论文是否还能完成 / 何时得到第一张结果表 / 是否超毕业周期 / (隐含) 1 个。

#### 1.3.11 19 节 Topic Feasibility Report (§13)

题目拆解 → 检索策略 → 文献地图 → 数据集地图 → Baseline 地图 → 成熟度 → 差异空间 → 航母风险 → 硬性风险 → 5 级判定 → 三条退化路线 → 推荐题目 → 2-3 工作包 → 问题方法实验矩阵 → 论文目录映射 → 开题报告骨架 → 委员会问题 → 风险与备选 → **证据清单**。

### 1.4 反模式提醒 (8 条)

1. 不用单一航母分数 → 混淆资源不成熟 vs 方向过度拥挤
2. 不让 LLM 凭记忆生成数据集名称 → 必须真实 API 验证
3. 不把论文 Future Work 当 Gap → 必须再次时间范围检索
4. 不做"创新点生成器" → 创新是结果, 毕业才是目标
5. 不让工作包完全串行 → 任一失败不能导致整篇失效
6. 不为用户满意而放水 → Unsafe Pass Rate 是头号指标
7. 不在第一版做完整开题报告 / 抓受限中文数据库 / 全学科通用 / 自动保证创新
8. 不绕过权限批量抓取付费数据库 → 只接受 RIS/BibTeX/EndNote 导入

---

## 2. GradThesis-CN (中国研究生学位论文全流程 Agent) — 论文下游

### 2.1 项目定位

> "中国研究生学位论文全流程 Agent", 覆盖 开题 → 中期 → 写作 → 格式检查 → 查重 → 预答辩 → 盲审 → 正式答辩 → 归档

**与 TopicPilot-CN 关系**: 明确上下游串联. TopicPilot-CN 产出开题报告 + 题目 + 工作量分解, GradThesis-CN 在此基础上接手所有后续环节, 衔接点为"开题材料归档" + "跨材料一致性".

### 2.2 核心架构: 5 模块特殊化

#### 2.2.1 SchoolRulePack (学校规则包) — **通用能力 + 学校适配分层**

按 `university_code/年份/` 目录组织, 含 metadata / thesis_structure / docx_styles / latex_template / citation.csl / lifecycle / required_materials / review_rules. 目录结构隐喻: `common/` (通用) + `universities/` (学校) + `degree-types/` (学位).

**反例 vs 正例**:
- 反: `{"university": "USTC"}`
- 正: `{"university": "USTC", "rule_version": "2025-03-31", "effective_from": "2025-03-31"}`

→ 规则不是静态的, 是会迭代的, 必须带版本号.

#### 2.2.2 DegreeLifecycleGraph — 13 状态学位流程

`PROPOSAL_PENDING → ... → ARCHIVED`, 每次状态转移检查前置条件. 本质是 LangGraph 状态图.

#### 2.2.3 ThesisComplianceEngine — 4 层合规优先级

优先级: **学校正式规范 > 学院当年通知 > 国家推荐标准 > 导师表达偏好**.

这层优先级避免了"AI 写完但格式被导师打回"的常见痛点.

#### 2.2.4 BlindReviewAgent — 盲审模拟器 (借鉴价值最高)

风险分 5 级: 致命/高/中/低/格式, 输出结构化 JSON 报告. **LLM 管逻辑创新, 程序管编号引用** — 分工清晰.

#### 2.2.5 DegreeMaterialAgent — 12 类材料一致性

管理 12 类材料的一致性检查: 日期冲突 / 题目不一致 / 姓名学号跨文件一致 / PDF 加密检测 / 缺页检测.

### 2.3 与开题阶段的上下游关系

数据契约: TopicPilot-CN 导出的 `proposal.json` 应包含 GradThesis-CN 后续需要的字段: `university / degree_type / title / research_question / methodology / expected_outcomes / innovation_points / workload_breakdown / advisor / submission_date`.

阶段交接: TopicPilot-CN 结束时生成"开题交付清单", GradThesis-CN 开始时验证清单完整性. 共享 SchoolRulePack 避免重复定义.

### 2.4 可借鉴设计

- **优先级 1**: SchoolRulePack 目录结构 + metadata.yaml 模式 → 引入"学校代码 + 年份"作为项目根命名
- **优先级 2**: 4 层合规优先级 → Phase 07 输出每条建议标 rule_source
- **优先级 3**: 跨材料一致性检查 → 题目/方法/创新点在后续 Phase 不被自动改写
- **优先级 4**: 盲审视角预审 → Phase 07 加"开题盲审模拟"环节
- **优先级 5**: DOCX 格式适配 → Phase 08 子模块, OpenXML 解析

### 2.5 技术深度: 比开题多 4 类

1. **DOCX 格式逆向解析** — OpenXMLSDK 读取 styles.xml / numbering.xml, 生成 SchoolFormatProfile
2. **参考文献版本自动切换** — GB/T 7714 有 1987/2005/2015/2025 四个版本, 按学校 + 提交日期动态选
3. **学校规则带版本号** — 规则不是静态的
4. **跨材料字段一致性** — 论文题目在开题报告/学位申请书/评阅书/答辩决议/最终论文封面必须一致

---

## 3. ThesisFlow (科研全周期工作流) — 科研中游

### 3.1 项目定位

> "证据驱动的科研工作台" — 把经验型 SOP 编排为可暂停 / 可回放 / 有人类审核 / 带引用证据的 LangGraph 流程

**核心不是"自动写论文", 而是科研项目管理**. 与 TopicPilot-CN 是**平行且下游**: 把开题作为输入起点, 把 GradThesis-CN 缺乏的"证据追溯 + 方法谱系 + 多 Agent 审查"补齐.

### 3.2 核心架构: 4 层分工

- **固定 Workflow** — 上传解析 / 导出文档 / 阶段切换 (确定性)
- **Agent** — 判断科研阶段 / 哪篇做 Baseline / 生成草稿 (不确定性)
- **Tool** — 文献检索 / PDF 解析 / 指标计算 (执行)
- **Human Gate** — 是否接受候选创新点 / 最终定稿 (高风险)

**LangGraph 6 个并行子图**: 文献研究 / Baseline 分析 / 方法组合 / 实验规划 / 章节写作 / 质量审查, 由 Supervisor 统一调度.

### 3.3 关键设计思路

#### 3.3.1 PaperCard 十字段 schema (§6.3) — **借鉴价值最高**

把每篇论文拆为 10 字段: `task / problem / baseline / modules / datasets / metrics / key_results / limitations / reusable_parts / evidence_spans`, 并维护"论文 → Baseline → 模块 → 问题 → 数据集 → 指标"**方法谱系图** (不是单纯向量库).

#### 3.3.2 Baseline 5 维评分 (§6.2) — 借鉴价值高

`BaselineScore = 0.25×代码可用性 + 0.20×数据兼容性 + 0.20×复现成本 + 0.15×发布时间 + 0.10×社区活跃度 + 0.10×可扩展模块数`.

输出表格含 5 列: 代码状态 / 数据适配 / 算力成本 / 可修改位置 / 风险.

#### 3.3.3 方法组合 7 问审计 (§6.4) — 借鉴价值中-高

每个 A+B+C 创新组合必须回答 7 问:
1. A 的什么问题
2. B 能否解决
3. 输入输出是否兼容
4. 是否重复 (已有组合?)
5. 怎么设计消融
6. 降级方案
7. 是否已有人做过

输出 `novelty_risk` 和 `implementation_cost`. 防止"看起来新但实际无法验证"的伪创新.

#### 3.3.4 RESULT_PENDING 标记 (§6.5)

"没有日志不生成结果 / 没有指标文件不生成数字 / 未完成统一标 RESULT_PENDING". 堵住"凭空写预期指标"漏洞.

#### 3.3.5 阶段感知路由 (§10.4)

根据项目当前状态 (刚选题 / 有代码无实验 / 有实验无论文 / 有初稿) 自动激活不同 Agent. 用户多周回访时走"验证→补充"路径而不是"重新生成".

#### 3.3.6 证据账本 (§6.7)

所有输出段落绑定 `evidence_id` (paper_xxx_chunk_xx). 把"AI 生成的文字"变成"可追溯到原文片段的文字".

### 3.4 技术细节: 跟开题不同的实现

- **PDF 解析**: Docling / GROBID 比 PyPDF 强, 能提取章节 / 参考文献 / 表格元数据
- **混合检索**: BM25 + Embedding + Reranker 三段式, 召回率比纯向量高 20-30%
- **文献元数据源**: OpenAlex / Semantic Scholar / Crossref 三选一做 API 补全
- **证据账本**: 所有输出绑定 evidence_id, 是 TopicPilot-CN 完全缺失的能力

### 3.5 可借鉴模块

1. **PaperCard schema** → 替换 Phase 02 文献输出格式
2. **Baseline 5 维评分** → 嵌入 Phase 04, 输出可比较候选表
3. **方法组合 7 问审计** → 嵌入 Phase 05 创新点生成
4. **证据账本最小版** → Phase 06 每段开题文字绑定 evidence_id
5. **阶段感知路由** → Phase 07-08 增加"用户中途回访"识别
6. **RESULT_PENDING 标记** → Phase 05-06 写"预期指标"时若没 pilot 数据, 必须打 pending

---

## 4. 三项目共性 / 互补性

### 4.1 共同设计原则

| 原则 | TopicPilot-CN | GradThesis-CN | ThesisFlow |
|---|---|---|---|
| 证据驱动 | 19 节报告含证据清单 | 12 类材料一致性 | evidence_id 全程绑定 |
| 风险控制 | 7 维航母 + 6 硬性否决 | 4 层合规优先级 | RESULT_PENDING |
| 阶段化 | 5 级裁决 (GO/STOP) | 13 状态生命周期 | 6 子图 Supervisor |
| 人在环 | human_select_pivot | 4 层优先级(导师优先) | Human Gate |
| 失败降级 | 工作包不串行 | DOCX 格式回退 | 阶段感知路由 |

### 4.2 互补空白

- TopicPilot-CN 缺 **证据账本** → ThesisFlow 有
- TopicPilot-CN 缺 **学校规则包** → GradThesis-CN 有
- TopicPilot-CN 缺 **PDF 解析** → ThesisFlow 有
- GradThesis-CN 缺 **方法谱系图** → ThesisFlow 有
- ThesisFlow 缺 **题目前置可行性评估** → TopicPilot-CN 有
- 3 项目都缺 **混合检索 (BM25+Embed+Reranker)** → 共同补

### 4.3 三项目串联图 (完整生命周期)

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  TopicPilot-CN   │    │    ThesisFlow    │    │  GradThesis-CN   │
│  (开题)          │ ─→ │  (科研管理)      │ ─→ │  (论文写作+答辩) │
│                  │    │                  │    │                  │
│ Phase 01-08      │    │ 论文调研          │    │ 中期检查          │
│ 21 端点 + 176 测试│    │ Baseline 评分    │    │ 论文撰写          │
│ 8 Phase UI       │    │ 方法组合          │    │ 格式检查          │
│ 5 角色委员会      │    │ 实验规划          │    │ 查重              │
│ 19 节 Feasibility │    │ 章节写作          │    │ 预答辩/盲审        │
│ 报告              │    │ 多 Agent 审查      │    │ 正式答辩          │
│                  │    │                  │    │ 归档              │
└──────────────────┘    └──────────────────┘    └──────────────────┘
       │                        │                        │
       │ SchoolRulePack ────────┴────────────────────────┤
       │ Evidence Ledger ───────┴────────────────────────┤
       │ 阶段路由规则 ──────────┴────────────────────────┘
```

**统一规范** (3 项目共享):
1. **SchoolRulePack** — `university_code/year/{metadata,thesis_structure,docx_styles,latex_template,citation.csl,lifecycle,required_materials,review_rules}.yaml`
2. **Evidence Ledger 格式** — `evidence_id = paper_xxx_chunk_xx | dataset_xxx | baseline_xxx`
3. **阶段状态 Schema** — `ProjectState { current_stage, checkpoint, evidence_refs, risk_flags }`
4. **人在环节点** — TopicPilot-CN 的 PIVOT 选定 / ThesisFlow 的创新点确认 / GradThesis-CN 的最终定稿

---

## 5. 一句话总结

3 份文档合计 4137 行, 构成本科 / 硕士 / 博士论文全生命周期的方法论参考. TopicPilot-CN 当前 MVP 实现了 8 phase 闭环 (176 pytest), 但**缺 5 件大事**: (1) 5 级裁决 + 6 硬性否决 (TopicPilot-CN 自身方案); (2) Topic Generalization Graph (TopicPilot-CN §7); (3) PaperCard 十字段 (ThesisFlow §6.3); (4) Evidence Ledger 强制挂接 (3 项目共识); (5) SchoolRulePack 4 层合规 (GradThesis-CN §3.3). 优先搬这 5 件, MVP 能从"开题报告生成器"升级为"毕业风险控制系统".
