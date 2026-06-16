# Faraway 3 项目对 TopicPilot-CN 的应用建议

> 当前 TopicPilot-CN MVP 状态: Phase 01-08 完成 + 21 端点 + 176 pytest + 真 arXiv 检索 + 委员会 3 角色 + apps/web v2 流式 trace
> 本建议: 把 Faraway 3 份精读总结里的设计 / skill / trick, 按"立即可搬 / 1-2 周 / 长期" 3 档排序
> 日期: 2026-06-16

---

## 0. 当前 MVP 与 3 份参考的能力差距总览

| 子能力 | TopicPilot-CN 方案 | GradThesis-CN | ThesisFlow | 当前 MVP |
|---|---|---|---|---|
| TopicSpec 9 字段拆解 | ✓ §5.1 | — | — | △ 有但不强 |
| 4 级检索词 (L0-L3) | ✓ §5.2 | — | — | △ Phase 03 简化 |
| 5 级裁决 GO/NARROW/PIVOT/PARK/STOP | ✓ §6.4 | — | — | ✗ 只有 继续/收缩/转向 |
| 7 维航母风险 (双轴) | ✓ §6.1 | — | — | △ 6 维, 缺双轴 |
| 6 条硬性否决 | ✓ §6.4 | — | — | ✗ 缺 |
| Topic Generalization Graph 6 维 | ✓ §7.2 | — | — | ✗ 缺, 仅有单点 PIVOT |
| 5 种工作包模板 | ✓ §8.4 | — | — | △ 默认 2 包 |
| 11 类委员会质询 | ✓ §10.10 | — | — | △ 3 角色 1 段评语 |
| 19 节 Feasibility Report | ✓ §13 | — | — | △ Markdown 初稿 (10 节) |
| 5 角色盲审模拟 | — | ✓ BlindReviewAgent | — | ✗ 缺 |
| 4 层合规优先级 | — | ✓ §3.3 | — | ✗ 缺 |
| SchoolRulePack 目录 | — | ✓ §3.1 | — | ✗ 缺 |
| 12 类材料一致性 | — | ✓ §2.5 | — | ✗ 缺 |
| PaperCard 十字段 | — | — | ✓ §6.3 | ✗ 仅有 PaperEvidence (5 字段) |
| Baseline 5 维评分 | — | — | ✓ §6.2 | △ BaselineCandidate 5 项 checklist |
| 方法组合 7 问审计 | — | — | ✓ §6.4 | ✗ 缺 |
| RESULT_PENDING 标记 | — | — | ✓ §6.5 | ✗ 缺 |
| 阶段感知路由 | — | — | ✓ §10.4 | ✗ 一次性跑完全流程 |
| Evidence Ledger (evidence_id 全程挂接) | ✓ §13 末节 | △ §2.5 | ✓ §6.7 | ✗ 缺 |
| LangGraph 6 并行子图 + Supervisor | ✓ §11 | ✓ §10 | ✓ §6 | △ 线性 chain, 无子图 |
| DOCX 格式逆向 | — | ✓ §4.1 | — | ✗ 缺 |
| PDF 解析 (Docling/GROBID) | — | △ | ✓ §6.6 | ✗ 缺 |
| 混合检索 (BM25+Embed+Rerank) | — | — | ✓ §6.1 | ✗ 缺 (纯 arXiv HTTP) |

> ✓ 完整 / △ 部分 / ✗ 缺. **当前 MVP 大致实现 30% 的能力**, 缺 5 类核心子系统.

---

## 1. 立即可搬 (< 1 周, 半天-1 天能落地)

### 1.1 [高] 5 级裁决替换当前 2 分类

- **来源**: TopicPilot-CN §6.4 + §3.5
- **当前**: Phase 05 Decision Literal = `Literal["继续","收缩","转向"]` 3 档
- **改**: 加 `PARK` (条件不具备, 未来重启) + `STOP` (核心任务无法验证) 2 档; 给分数门槛 (< 60 PIVOT, 60-75 有条件通过, ≥ 75 GO, 任一硬性条件失败 STOP)
- **涉及文件**: `packages/domain/phase5_models.py` (Decision Literal 扩) + `packages/agents/nodes/phase5_risk.py` (`_decide()` 函数)
- **估时**: 半天
- **pytest 增量**: ~3 条 (每档 1 条)

### 1.2 [高] 6 条硬性否决条件短路逻辑

- **来源**: TopicPilot-CN §6.4
- **当前**: Phase 05 只有评分, 无短路 STOP
- **改**: `_decide()` 之后加 6 条 if-elif:
  1. `len(ledger.datasets) == 0 and goal == "保毕业"` → STOP
  2. `len(ledger.metrics) == 0` → STOP
  3. `len(ledger.baselines) == 0 and goal != "冲高水平"` → STOP
  4. `risk_score.overall_score >= 85` → STOP
  5. `2 of 6 dimension_scores >= 75` → STOP
  6. `工作包完全串行 (wp.depends_on == "all")` → STOP
- **涉及文件**: `packages/agents/nodes/phase5_risk.py` (新函数 `_hard_blockers_check()`)
- **估时**: 半天
- **pytest 增量**: ~6 条 (每条 1 个测试用例)

### 1.3 [中] TopicSpec 9 字段化

- **来源**: TopicPilot-CN §5.1
- **当前**: TopicSpec 已有但字段较散 (含 raw_topic / normalized_topic / task_type / method_family / data_requirement / evaluation_metrics / ambiguous_words / thesis_mapping / work_package_drafts)
- **改**: 标准化 9 字段 (research_object / scenario / task / modality / method_family / target_problem / data_requirement / expected_output / evaluation_metrics), 与方案 §5.1 对齐; 题目拆解 prompt 改按 9 字段输出
- **涉及文件**: `packages/domain/phase2_models.py` (加 4 个 Optional 字段) + `packages/agents/nodes/phase2_decompose.py` (改 prompt 模板)
- **估时**: 1 天
- **向后兼容**: 加 Optional 默认空 list, 旧模型字段保留

### 1.4 [中] 5 种工作包模板 (选默认)

- **来源**: TopicPilot-CN §8.4
- **当前**: Phase 06 默认 WP1+WP2 两包 (模板 1)
- **改**: 加模板选择逻辑, 默认根据 ledger 字段选:
  - 数据集 ≥ 2 + baseline ≥ 2 → 模板 1 (数据+方法)
  - baseline ≥ 3 + 数据集 1 → 模板 2 (方法+方法, 须 check 解决不同问题)
  - 数据集 0 + 2+ baseline → 模板 3 (方法+系统, 需配合 cross_dataset)
  - 数据集 ≥ 3 + cross_dataset ≥ 2 → 模板 4 (3 包)
  - 有 2D + 3D 数据 → 模板 5 (二维+三维+Agent)
- **涉及文件**: `packages/agents/nodes/phase6_work_package.py` (新函数 `_select_template()`)
- **估时**: 1 天
- **pytest 增量**: ~5 条 (每模板 1 条)

### 1.5 [中] RESULT_PENDING 标记

- **来源**: ThesisFlow §6.5
- **当前**: Phase 06 写"预期精度"时没强制标待定
- **改**: `Experiment.expected_metrics` 加 `status: Literal["PENDING", "PILOT", "FINAL"] = "PENDING"`; Phase 06 输出时若 ledger.papers 全是 arxiv 拉来(无 LLM 综述), 强制标 PENDING
- **涉及文件**: `packages/domain/phase6_models.py` + `packages/agents/nodes/phase6_work_package.py`
- **估时**: 半天
- **pytest 增量**: ~2 条

### 1.6 [低] 12 节开题报告骨架对齐

- **来源**: TopicPilot-CN §3.9
- **当前**: Phase 07 用 10 节 PROPOSAL_SECTIONS (缺"风险与备选方案" + "创新点与工作量")
- **改**: 加 2 节, 总 12 节
- **涉及文件**: `packages/domain/phase7_models.py` (PROPOSAL_SECTIONS Literal 扩)
- **估时**: 半天
- **向后兼容**: 旧模板生成的 10 节报告, 提示升级

### 1.7 [低] 11 类委员会质询 prompt

- **来源**: TopicPilot-CN §10.10
- **当前**: Phase 07 committee 3 角色 1 段评语, 没强制覆盖 11 类问题
- **改**: committee 评语 prompt 强制覆盖至少 1 类 (从 11 类里随机选 1 类, 强制问该类问题)
- **涉及文件**: `packages/agents/nodes/phase7_proposal.py` (`_build_committee_discussion_llm` 系统 prompt 加 11 类列表 + 强制问句模板)
- **估时**: 半天
- **pytest 增量**: ~1 条 (断言评语含某类关键词如"数据从哪来")

---

## 2. 1-2 周落地 (需要新模块)

### 2.1 [高] 双轴风险 (Maturity × Differentiation)

- **来源**: TopicPilot-CN §6.1
- **当前**: RiskScore 单 overall_score, 6 个 dimension_score
- **改**: RiskScore 加 2 个子分 (maturity_score / differentiation_score) + 四象限定位 (SAFE / RED_OCEAN / CARRIER / DEAD_ZONE); 四象限图前端可视化
- **涉及文件**: `packages/domain/phase5_models.py` (RiskScore 扩) + `packages/agents/nodes/phase5_risk.py` (新 `_score_maturity()` / `_score_differentiation()` 函数) + `apps/web/app.js` (双轴图)
- **估时**: 3 天
- **新增 pytest**: ~6 条 (双轴评分 + 4 象限判定)
- **价值**: 让"为什么这个题目造航母"可解释, 不仅是 0-100 分数

### 2.2 [高] Topic Generalization Graph (6 维泛化)

- **来源**: TopicPilot-CN §7.2 (最有技术含量的子系统)
- **当前**: PIVOT 候选是单点 (`PivotCandidate.to_topic: str`)
- **改**: PIVOT 候选升级为 6 维算子:
  - 对象算子 (ObjectGeneralization): 特殊桥型 → 桥梁 → 混凝土结构 → 工业表面
  - 任务算子: 三维测量 → 三维定位 → 二维分割 → 二维检测
  - 模态算子: RGB+Depth+PointCloud → RGB-D → 双目 → 单目 RGB
  - 方法算子: 端到端新模型 → 成熟模型适配 → 轻量模块改进
  - 数据算子: 自建完整3D标注 → 公开2D数据 + 少量自采
  - 结论算子: 精确测量 → 估计量测 → 定性定位 → 可视化验证

  生成 3 条路线: 保守 (A) / 平衡 (B) / 激进 (C), 每条带 evidence_papers/datasets/baselines/metrics/tradeoff
- **涉及文件**: `packages/domain/phase5_models.py` (新 PIVOT_OPERATORS Literal + PivotRoute 嵌套模型) + `packages/agents/nodes/phase5_risk.py` (`_generate_pivots` 重写) + 新文件 `packages/agents/nodes/phase5_generalization.py`
- **估时**: 5 天
- **新增 pytest**: ~10 条
- **价值**: 把"风险"变成"具体怎么改"的可操作建议, 不再是"建议转向"的口水话

### 2.3 [中] PaperCard 十字段 schema

- **来源**: ThesisFlow §6.3
- **当前**: PaperEvidence 仅 13 字段 (paper_id / title / year / source / url / abstract / task / method / datasets / metrics / baseline_mentions / reusable_value / evidence_score / wp_binding)
- **改**: 加可选 7 字段向后兼容 (problem / modules / key_results / limitations / reusable_parts / evidence_spans / baseline); LLM 填 paper 走"十字段"prompt
- **涉及文件**: `packages/domain/phase4_models.py` (PaperEvidence 扩 7 Optional 字段) + `packages/agents/nodes/phase4_evidence.py` (LLM prompt 加十字段)
- **估时**: 3 天
- **新增 pytest**: ~3 条
- **价值**: 让"研究现状"章节从"流水账"变"问题驱动的对比表"

### 2.4 [中] Baseline 5 维评分

- **来源**: ThesisFlow §6.2
- **当前**: BaselineCandidate 有 5 个布尔字段 (has_readme / has_env_file / has_training_script / has_eval_script / has_pretrained_weight) + reproduce_difficulty
- **改**: 加 5 维评分 (代码可用性 / 数据兼容 / 复现成本 / 发布时间 / 可扩展模块数), 公式 `BaselineScore = 0.25×code + 0.20×data + 0.20×reproduce + 0.15×time + 0.10×community + 0.10×extensibility`
- **涉及文件**: `packages/domain/phase4_models.py` (BaselineScore 嵌套模型) + `packages/agents/nodes/phase4_evidence.py` (LLM 评估 5 维)
- **估时**: 2 天
- **新增 pytest**: ~4 条

### 2.5 [中] Evidence Ledger 强制挂接

- **来源**: TopicPilot-CN §13 末节 (19 节报告含"证据清单") + ThesisFlow §6.7 (evidence_id 全程绑定)
- **当前**: Phase 05/06/07 输出无 evidence_id 字段, 用户无法追溯结论来源
- **改**: 3 层挂接:
  - L1: Phase 05 risk_score 评分每维加 `evidence_refs: list[EvidenceRef]` (paper_xxx_chunk_xx)
  - L2: Phase 06 work_package.proposed_change 加 `evidence_refs`
  - L3: Phase 07 committee reviews[i].suggestions 加 `evidence_refs`
- **涉及文件**: 新建 `packages/domain/evidence_ref.py` (EvidenceRef Pydantic) + 3 phase models + 3 phase nodes
- **估时**: 4 天
- **新增 pytest**: ~6 条 (每层 2 条)
- **价值**: 让"AI 为什么这么建议"可追溯, 是反 AI 幻觉的物理保障

### 2.6 [中] 4 层合规优先级 (学校 / 学院 / 国家 / 导师)

- **来源**: GradThesis-CN §3.3
- **当前**: Phase 07 输出无 rule_source, 用户无法知道建议优先级
- **改**: 新建 `packages/domain/school_rule.py`:
  ```python
  class ComplianceLevel(Literal["SCHOOL", "DEPARTMENT", "NATIONAL", "ADVISOR"]):
    pass
  class SchoolRule(BaseModel):
      level: ComplianceLevel
      rule_id: str
      description: str
      source_url: str | None
  ```
  Phase 07 committee reviews[i].suggestions 加 `rule_source: ComplianceLevel` 字段; default 模板 (中科大 2025) 装进 `data/school_rules/ustc_2025.yaml`
- **涉及文件**: 新建 `packages/domain/school_rule.py` + `data/school_rules/ustc_2025.yaml` + `packages/agents/nodes/phase7_proposal.py` (prompt 加 rule_source)
- **估时**: 4 天
- **新增 pytest**: ~4 条 (加载 YAML / 4 层优先级)
- **价值**: 让"AI 建议"和"学校要求"明确分开, 避免被导师打回

---

## 3. 长期 (Phase 09+, 需独立 Phase 工作)

### 3.1 LangGraph 状态图重构

- **来源**: TopicPilot-CN §11 (15 字段 State) + ThesisFlow §6.6 (6 并行子图)
- **当前**: 线性 chain (Phase 01 → 02 → 03 → ... → 08), 8 阶段无回退
- **改**:
  - State 加 7 字段 (pivot_state / evidence_ledger / committee_reviews / blocked_at / retry_count)
  - 拆 4 子图: intake / search_evidence / risk_pivot / proposal_committee
  - 加 `human_select_pivot` 暂停点 (PIVOT 后必须用户选)
  - 加 `revise_proposal` 反馈环 (committee 不通过时回 Phase 07)
- **估时**: 1-2 周
- **风险**: 破坏现有 176 pytest, 需大量回归

### 3.2 SchoolRulePack 目录结构

- **来源**: GradThesis-CN §3.1
- **改**: `data/school_rules/{university_code}/{year}/` 目录, 含 metadata / thesis_structure / docx_styles / latex_template / citation.csl / lifecycle.yaml / required_materials.yaml / review_rules.yaml
- **估时**: 3-5 天
- **依赖**: 先做 2.6 4 层合规优先级

### 3.3 DOCX 格式逆向 (OpenXMLSDK)

- **来源**: GradThesis-CN §4.1
- **改**: Phase 08 导出时读学校 docx_styles.xml, 自动套字号/行距/页眉页脚
- **估时**: 1 周
- **依赖**: py-docx / openxml 库

### 3.4 PDF 解析 (Docling / GROBID)

- **来源**: ThesisFlow §6.6
- **改**: Phase 04 接收用户上传 PDF, 提取章节 / 参考文献 / 表格元数据 → 自动填 PaperCard
- **估时**: 1 周
- **依赖**: docling / grobid-client 库

### 3.5 混合检索 (BM25 + Embedding + Reranker)

- **来源**: ThesisFlow §6.1
- **当前**: Phase 04 仅 arxiv HTTP 检索, 缺语义召回
- **改**: 加 BM25 (rank_bm25) + Embedding (BGE-M3) + Reranker (bge-reranker) 三段式
- **估时**: 1-2 周
- **依赖**: sentence-transformers / rank_bm25

### 3.6 历史开题题目标注数据集

- **来源**: TopicPilot-CN §17
- **改**: 收集 50-100 个历史开题题目标注 (顺利 / 大幅改题 / 因数据不足失败 / 因题目过大延期 / 因工作量不足 / 导师评定合适过大过小)
- **估时**: 持续 2-4 周 (需人工)
- **价值**: 评估 Unsafe Pass Rate, 是核心 KPI

### 3.7 阶段感知路由

- **来源**: ThesisFlow §10.4
- **改**: ProjectState.current_stage 持久化, 用户多周回访时识别阶段, 走"验证→补充"路径
- **估时**: 1 周

### 3.8 Unsafe Pass Rate 评估指标

- **来源**: TopicPilot-CN §17.2
- **改**: 标注数据集 + 自动评估脚本 + CI 指标
- **估时**: 依赖 3.6

### 3.9 SchoolRulePack 模板库 (10 学校 × 4 年 = 40 套)

- **来源**: GradThesis-CN §3.1
- **改**: 用户可下载 / 提交学校规则包, MVP 内置 5 套 (中科大 / 清华 / 北大 / 浙大 / 上交)
- **估时**: 持续, 每周 1 套

### 3.10 跨材料一致性检查

- **来源**: GradThesis-CN §2.5
- **改**: 12 类材料 (开题 / 中期 / 论文 / 摘要 / 答辩 PPT / 评阅书 / 决议 / 学位申请表 / 归档 PDF / 致谢 / 原创声明 / 授权书) 题目 + 作者 + 导师 + 时间字段自动比对
- **估时**: 1 周 (接 GradThesis-CN)

---

## 4. 建议执行路线

### 4.1 1 周冲刺 (W1)

按"立即可搬" 7 条 + pytest 增量 ~22 条 全部落地:

| 序号 | 工作 | 估时 |
|---|---|---|
| 1.1 | 5 级裁决 + 分数门槛 | 0.5 天 |
| 1.2 | 6 条硬性否决 | 0.5 天 |
| 1.3 | TopicSpec 9 字段化 | 1 天 |
| 1.4 | 5 种工作包模板 | 1 天 |
| 1.5 | RESULT_PENDING | 0.5 天 |
| 1.6 | 12 节报告骨架 | 0.5 天 |
| 1.7 | 11 类质询 prompt | 0.5 天 |
| 验证 | pytest 全过 + Playwright e2e | 0.5 天 |
| **合计** | | **5 天** |

### 4.2 2 周冲刺 (W2-W3)

按"1-2 周落地" 6 条选 3 条 (按价值):

| 序号 | 工作 | 价值 | 估时 |
|---|---|---|---|
| 2.1 | 双轴风险 | 高 | 3 天 |
| 2.2 | Topic Generalization Graph | 高 | 5 天 |
| 2.5 | Evidence Ledger 强制挂接 | 中-高 | 4 天 |

### 4.3 1 个月 (W4-W5)

2.3 PaperCard + 2.4 Baseline 5 维 + 2.6 4 层合规.

### 4.4 2 个月 (W6-W9)

3.1 LangGraph 重构 + 3.2 SchoolRulePack 目录 + 3.3 DOCX + 3.4 PDF 解析.

### 4.5 3 个月+ (W10+)

3.5 混合检索 + 3.6 标注数据集 + 3.7 阶段路由 + 3.8 评估指标 + 3.9 模板库 + 3.10 跨材料一致性.

---

## 5. 不建议做的事

| 反模式 | 原因 |
|---|---|
| 第一版接 OpenAlex/Semantic Scholar/Crossref/HF/GitHub 5 源 | 当前 arXiv 已足够, 加 5 源易分散, 应先做 2.5 证据挂接 |
| 一次到位做 LangGraph 6 并行子图 | 现有 8 阶段线性已过 176 pytest, 重构风险 > 收益 |
| 自动生成几万字开题报告正文 | 方案 §14.1 明确暂不支持, 应坚持"骨架+委员会质询" |
| 抓取知网/万方/维普/学校仓储 | 法律风险, 方案 §1.4 红线 |
| 跨学科通用 | 方案 §14.1 只支持计算机/AI/工科视觉 |
| 一次实现 19 节 Feasibility Report | 当前 10 节够用, 加 9 节成本高, 可留 Phase 09+ |
| Unsafe Pass Rate 评估 | 依赖 3.6 标注数据集, 3 周前无意义 |
| 自动保证创新性 / 自动保证通过开题 | 方案 §1.4 红线 |

---

## 6. 一句话总结

**当前 TopicPilot-CN MVP 实现 30% 的设计意图, 优先搬 5 件大事能让产品从"开题报告生成器"升级为"毕业风险控制系统"**: (1) 5 级裁决 + 6 硬性否决 (来自 TopicPilot-CN 自身方案); (2) Topic Generalization Graph 6 维泛化 (来自 TopicPilot-CN §7); (3) Evidence Ledger 强制挂接 evidence_id (3 项目共识); (4) SchoolRulePack 4 层合规 (来自 GradThesis-CN); (5) PaperCard 十字段 (来自 ThesisFlow). 1 周内能搬 7 个"立即可搬"小改, 1 个月能搬 6 个"1-2 周"中等改, 3 个月能完整对齐 3 份方案.
