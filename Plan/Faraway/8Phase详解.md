# TopicPilot-CN 8 Phase 详解：作用 + 输入 + 输出 + 测试用例

> 每个 Phase 都是**纯后端流式端点 + 前端一键按钮**；
> 用户填一次表，系统按 Phase 01 → 08 顺序跑，每步锁上游产物。
> 例子数据基于"基于轻量化注意力机制的YOLOv8带钢表面缺陷检测算法研究"。

---

## Phase 01 · 任务建档 + 评级

**作用**：用户填建档表（含专业 / 学位 / 目标档位 / 时间 / 原始题目），系统给出 A/B/C/D 评级，**D 评级会阻断后续 6 个 phase**。

| 项 | 内容 |
|---|---|
| **输入** | `ProjectIntake`: case_id, major, degree_type, goal_level, 3 个时间 (开题/毕业/首结果), advisor_direction, raw_topic, must_keep[], student_resources{...}, weekly_hours |
| **端点** | `POST /api/v1/projects` (新建) + `POST /api/v1/projects/{id}/intake/validate` (评级) |
| **输出** | `Project` row + `intake_rating` ∈ {A, B, C, D} + `outcome` ∈ {OK, NEED_CLARIFICATION, BLOCKED} + `missing_fields[]` |
| **前端 UI** | 表单 + 按钮"创建项目 + 评级" + 4 个关键字段卡片 |

**评级公式**（来自 `compute_intake_rating`）：
```
intake_rating = f(missing_fields, 字段齐备度, 占位检测)
A = 全部补齐, 无缺失
B = 有 P1/P2 缺失 (一般字段)
C = 有 P0 缺失 (必填字段)
D = 占位符 (TBD/TODO) 或 P0≥4 且 P1≥2
```

**测试用例**：
```bash
# 输入
POST /api/v1/projects
{
  "intake": {
    "case_id": "YOLO_DEMO",
    "major": "计算机科学与技术",
    "degree_type": "硕士",
    "goal_level": "保毕业",
    "proposal_deadline": "2026-10-15",
    "thesis_deadline": "2027-06-01",
    "first_result_deadline": "2026-12-31",
    "advisor_direction": "工业质检",
    "school_requirements": [],
    "inherited_resources": [],
    "student_resources": {
      "programming_level": "熟练", "dl_or_algorithm_foundation": "中",
      "paper_reading_ability": "中", "english_reading_ability": "中",
      "compute_resource": "笔记本 3060", "weekly_hours": 25,
      "data_collection_ability": "中", "data_annotation_ability": "中",
      "code_reproduction_ability": "中", "system_dev_ability": "中"
    },
    "raw_topic": "基于轻量化注意力机制的YOLOv8带钢表面缺陷检测算法研究",
    "must_keep": ["YOLOv8", "带钢表面缺陷", "轻量化", "注意力机制"],
    "can_drop": [], "missing_fields": [], "intake_rating": "A"
  }
}

# 期望输出
{
  "id": 1,
  "payload": {
    "case_id": "YOLO_DEMO", "intake_rating": "B",
    "goal_level": "保毕业", "raw_topic": "...",
    "missing_fields": ["school_requirements", "inherited_resources", ...]
  }
}
# outcome=OK (允许进 Phase 02)
# rating=B (P1/P2 缺, 不阻断)
```

**反例**：
```bash
raw_topic: "TBD"  # 占位
# → outcome=BLOCKED, rating=D, 后续 6 phase disabled
```

---

## Phase 02 · 题目拆解 (TopicSpec)

**作用**：把自然语言题目拆成结构化 TopicSpec：研究对象 / 任务 / 模态 / 方法 / 数据 / 评价 + 扫 8 个高风险词（智能/高精度/端到端...）。

| 项 | 内容 |
|---|---|
| **输入** | 已建档 project + prefer ∈ {heuristic, llm, auto} |
| **端点** | `POST /api/v1/projects/{id}/topic/decompose/stream` (SSE 流式) |
| **输出** | `TopicSpec`: normalized_topic, research_object, application_scenario, task_type[], data_modality[], method_family[], expected_outputs[], evaluation_metrics[], engineering_constraints[], risk_terms[{term, weight}], work_package_drafts[] |
| **前端 UI** | 9 拆解字段明细 (折叠) + 评分公式 (A/B/C/D) + 风险词 chips |

**评分公式**：
```
decomposition_rating = f(risks_count) ∧ allow_proceed_to_phase03
A = 0-3 风险词, WP≥2 + 章节齐 + 评价指标非空
B = 4-7 风险词
C = 8+ 风险词 (智能/高精度/端到端 等)
D = 阻断 (WP 缺 / 章节缺 / 评价空)
```

**测试用例**：
```bash
# 输入
POST /api/v1/projects/1/topic/decompose/stream
{"prefer": "heuristic"}

# 期望输出
{
  "normalized_topic": "基于轻量化注意力机制的YOLOv8带钢表面缺陷检测算法研究",
  "research_object": "带钢表面",
  "application_scenario": "工业质检",
  "task_type": ["目标检测", "缺陷分类"],
  "data_modality": ["RGB"],
  "method_family": ["YOLOv8", "CBAM", "GhostConv"],
  "expected_outputs": ["mAP", "FPS"],
  "evaluation_metrics": ["mAP@0.5", "Recall"],
  "engineering_constraints": ["GPU 显存 < 8GB"],
  "risk_terms": [{"term": "轻量化", "weight": 0.6}],
  "work_package_drafts": [
    {"wp_id": "WP1", "title": "轻量化 backbone", "research_question": "..."},
    {"wp_id": "WP2", "title": "注意力增强 neck", "research_question": "..."}
  ],
  "decomposition_rating": "A",
  "allow_proceed_to_phase03": true
}
```

---

## Phase 03 · 检索计划 (SearchQueryPlan)

**作用**：7 层 × ~17 个检索词（L0 精确 / L1 中英同义 / L2 去场景 / L3 抽象任务 / L4 基线 / L5 综述 / L6 中文）覆盖研究现状。**为 Phase 04 准备检索词**。

| 项 | 内容 |
|---|---|
| **输入** | TopicSpec (上游) |
| **端点** | `POST /api/v1/projects/{id}/search/plan/stream` (SSE) |
| **输出** | `SearchQueryPlan`: query_layers[L0..L6] (每层 title + purpose + queries[] + target_sources[]), work_package_queries[], maturity_probe{expected_paper_density, ...}, baseline_probe{candidate_baselines, expected_datasets}, maturity_rating, query_total |
| **前端 UI** | 7 层卡片 (每层显示 title + queries + 用途) + maturity_rating 评级 |

**测试用例**：
```bash
# 输入: Phase 02 已完成
POST /api/v1/projects/1/search/plan/stream

# 期望输出
{
  "query_layers": [
    {"layer": "L0", "title": "原始题目精确检索", "purpose": "直接命中题目",
     "queries": ["基于轻量化注意力机制的YOLOv8带钢表面缺陷检测算法研究", "YOLOv8 steel surface defect detection"],
     "target_sources": ["arXiv", "CNKI"]},
    {"layer": "L1", "title": "术语对齐",
     "queries": ["lightweight YOLO", "attention mechanism defect", "CBAM object detection"],
     "target_sources": ["arXiv"]},
    {"layer": "L2", "title": "去场景抽象",
     "queries": ["surface defect detection deep learning", "industrial quality inspection"],
     "target_sources": ["arXiv", "Papers with Code"]},
    {"layer": "L3", "title": "抽象任务", "queries": ["object detection", "anomaly detection"],
     "target_sources": ["arXiv"]},
    {"layer": "L4", "title": "基线", "queries": ["YOLOv8", "YOLOv5", "Faster R-CNN"], ...},
    {"layer": "L5", "title": "综述", "queries": ["deep learning defect detection survey"], ...},
    {"layer": "L6", "title": "中文", "queries": ["带钢表面缺陷检测综述", "注意力机制 工业检测"], ...}
  ],
  "work_package_queries": [...],
  "maturity_probe": {"has_survey": true, "expected_paper_density": "中"},
  "maturity_rating": "B",
  "query_total": 28,
  "allow_proceed_to_phase04": true
}
```

---

## Phase 04 · 证据账本 (EvidenceLedger)

**作用**：基于 Phase 03 检索词调 arXiv 拉真实论文 + 找真实 baseline/dataset，LLM 翻译中文摘要，**这是系统的"核心证据"**。

| 项 | 内容 |
|---|---|
| **输入** | TopicSpec + SearchQueryPlan + prefer |
| **端点** | `POST /api/v1/projects/{id}/evidence/build/stream` (SSE) + `POST /api/v1/projects/{id}/papers` (手动加论文) |
| **输出** | `EvidenceLedger`: papers[PaperEvidence], surveys[], datasets[], baselines[], metrics[], experiment_templates[], thesis_templates[], evidence_rating |
| **前端 UI** | 论文卡片 (title / field badge / 年份 / 关键词 chips / 中文简介 / arXiv 链接) + dataset 卡片 + baseline 卡片 + "添加我自己的论文" 折叠表单 |

**PaperEvidence 字段**：
```
paper_id, title, year, source (arXiv / user-uploaded / LLM-generated-candidate),
url, abstract, authors[],
task[], method[], datasets[], metrics[], baseline_mentions[],
reusable_value, evidence_score, wp_binding[],
summary_zh (LLM 翻译), keywords_zh (5 个), field (研究领域)
```

**测试用例**：
```bash
# 输入
POST /api/v1/projects/1/evidence/build/stream
{"prefer": "heuristic"}

# 期望输出
{
  "evidence_rating": "A",
  "paper_count": 5,
  "arxiv_papers": 3,  # 真 arXiv 命中
  "dataset_count": 3,
  "baseline_count": 3,
  "metric_count": 2,
  "payload": {
    "papers": [
      {
        "paper_id": "2306.14289",
        "title": "Faster Segment Anything: Towards Lightweight SAM for Mobile Applications",
        "year": 2023, "source": "arXiv", "url": "https://arxiv.org/abs/2306.14289v2",
        "abstract": "...",
        "field": "图像分割",
        "summary_zh": "本文针对 Segment Anything Model (SAM) 在移动端部署困难...",
        "keywords_zh": ["轻量化模型", "Segment Anything", "知识蒸馏", "移动端部署", "图像分割"]
      },
      {
        "paper_id": "2311.03725",
        "title": "DeepInspect: An AI-Powered Defect Detection for Manufacturing",
        "field": "工业质检",
        "summary_zh": "本文提出DeepInspect系统...",
        "keywords_zh": ["缺陷检测", "深度学习", "CNN", "GAN", "智能制造"]
      }
    ],
    "datasets": [
      {"dataset_id": "D001", "name": "Surface Defect...", "fit_to_topic": "中", "download": "..."}
    ],
    "baselines": [
      {"baseline_id": "B001", "name": "[arXiv:2302.10473]", "repository_url": "..."}
    ]
  }
}

# 手动加论文
POST /api/v1/projects/1/papers
{
  "title": "YOLOv8-Attention for Steel Defect",
  "authors": "Zhang, San",
  "year": 2024,
  "url": "https://arxiv.org/abs/2401.12345",
  "abstract": "我们提出 YOLOv8-Attention..."
}
# → 201, source="user-uploaded", 立即出现在卡片区
```

**评级公式**（`_rate`）：
```
A = papers≥5, surveys≥1, datasets≥2, baselines≥2, metrics≥1
B = 缺 1 个
C = papers<5 或 datasets<2 或 baselines<2
D = 无 metrics
```

---

## Phase 05 · 风险评分 (RiskEvaluation)

**作用**：6 维评分 + LLM 生成 Pivot 候选 + 决策 (继续/收缩/转向/停止)。

| 项 | 内容 |
|---|---|
| **输入** | TopicSpec + SearchQueryPlan + EvidenceLedger + prefer |
| **端点** | `POST /api/v1/projects/{id}/risk/evaluate/stream` (SSE) |
| **输出** | `RiskEvaluation`: risk_score{overall_score, overall_rating, dimensions[6], max_risk_dimension, min_viable_path}, decision, decision_rationale, pivot_candidates[], must_supplement[] |
| **前端 UI** | 总分 0-100 + 评级 A/B/C/D + 6 维评分信号 (++ / -- 明细) + 决策 + pivot 候选列表 |

**6 维度评分公式**（来自 `评分逻辑.md`）：

| 维度 | 公式 | 满分来源 |
|---|---|---|
| 方向成熟度 | papers×4 + surveys×10 + templates×15 + (齐 +15) | 40+20+25+15=100 |
| 数据可得性 | datasets×25 + inherited_available×20 | 60+40=100 |
| baseline 清晰度 | sum(diff_score=低30/中18/高5/未知12) + 10 | 100 |
| 实验可行性 | metrics×8 + templates×15 + (有指标 +10) | 50+40+10=100 |
| 工作量可拆性 | work_packages×35 + bound_wps×15 | 70+30=100 |
| 毕业时间风险 | 80 - (高复现难度 baseline×15) | 80→0 |

**总评阈值**（按 goal_level 调）：
| goal | A | B | C | D |
|---|---|---|---|---|
| 保毕业 | ≥70 | ≥55 | ≥40 | <40 |
| 稳中求新 | ≥65 | ≥50 | ≥35 | <35 |
| 冲高水平 | ≥60 | ≥45 | ≥30 | <30 |

**测试用例**：
```bash
# 输入: Phase 04 已完成
POST /api/v1/projects/1/risk/evaluate/stream
{"prefer": "heuristic"}

# 期望输出
{
  "overall_score": 72.0,
  "overall_rating": "B",
  "decision": "继续",
  "decision_rationale": "中低风险, 建议继续但并行准备 pivot",
  "max_risk_dimension": "baseline清晰度",
  "min_viable_path": "继续当前方向, 但必须并行准备 1 个 Pivot 候选...",
  "risk_score": {
    "dimensions": [
      {"key": "方向成熟度", "score": 75.0, "evidence_summary": "5 篇论文 + 1 篇综述 + 1 份模板",
       "pluses": ["方向论文多 (5 篇) +20", "有综述 (1 篇) +10"],
       "minuses": []},
      {"key": "baseline清晰度", "score": 46.0,
       "pluses": ["有中复现难度 baseline (2 个) +36", "baseline 候选数足 (2 个) +10"],
       "minuses": []}
    ]
  },
  "pivot_candidates": [
    {"pivot_id": "P01", "pivot_type": "收缩",
     "new_topic": "面向本专业的轻量化检测方法研究",
     "rationale": "原题范围过大, 限定场景缩小...",
     "residual_risk": "中"}
  ],
  "must_supplement": ["至少 1 个低/中复现难度的 baseline 替代高难度候选"]
}
```

---

## Phase 06 · 工作包定稿 (WorkPackagePlan)

**作用**：根据 Phase 05 风险评分，把题目拆成 2-3 个**独立可验证工作包**（每 WP 含研究问题 / 数据 / baseline / 评价 / 论文章节）+ 五章式目录 + 实验矩阵。

| 项 | 内容 |
|---|---|
| **输入** | TopicSpec + RiskEvaluation + EvidenceLedger |
| **端点** | `POST /api/v1/projects/{id}/work_package/plan/stream` (SSE) |
| **输出** | `WorkPackagePlan`: final_topic, final_topic_from_pivot, final_topic_rationale, work_packages[WorkPackageFinal], experiment_matrices[ExperimentMatrix], thesis_outline[ThesisOutlineChapter], max_writing_risk, allow_proceed_to_phase07 |
| **前端 UI** | final_topic + from_pivot 标识 + WP 数量 + 实验矩阵 + 5 章目录 |

**WorkPackageFinal 字段**：
```
wp_id (WP1/WP2/WP3), kind, chapter, title,
research_question, method_approach, data_source,
baseline_or_control, metrics[], deliverables[],
wp_binding, figure_refs[]
```

**测试用例**：
```bash
# 输入: Phase 05 已完成
POST /api/v1/projects/1/work_package/plan/stream

# 期望输出
{
  "final_topic": "基于轻量化注意力机制的YOLOv8带钢表面缺陷检测算法研究",
  "final_topic_from_pivot": false,
  "final_topic_rationale": "题目范围可控, 沿用原方向",
  "work_packages": [
    {"wp_id": "WP1", "kind": "method", "chapter": "ch3",
     "title": "轻量化 backbone 设计 (GhostConv + CBAM)",
     "research_question": "在 YOLOv8 骨干网络中嵌入 GhostConv + CBAM, mAP 损失 <2%, 参数量 -40%",
     "method_approach": "GhostConv 替换标准卷积 + CBAM 通道-空间注意力",
     "data_source": "NEU-DET 公开数据集",
     "baseline_or_control": "YOLOv8n baseline",
     "metrics": ["mAP@0.5", "Params (M)", "FPS"],
     "deliverables": ["模型权重", "训练 log", "消融实验表"]
    },
    {"wp_id": "WP2", "kind": "system", "chapter": "ch4",
     "title": "工业级部署 + 端到端测试",
     ...}
  ],
  "experiment_matrices": [
    {"matrix_id": "M01", "type": "对比",
     "rows": [
       {"variant": "YOLOv8n baseline", "wp_binding": "WP1", "expected_mAP": 65.0},
       {"variant": "YOLOv8n + GhostConv", "wp_binding": "WP1", "expected_mAP": 66.5},
       {"variant": "YOLOv8n + GhostConv + CBAM", "wp_binding": "WP1", "expected_mAP": 68.0}
     ]}
  ],
  "thesis_outline": [
    {"chapter": "ch1", "title": "绪论", "content_summary": "..."},
    {"chapter": "ch2", "title": "相关工作", ...},
    {"chapter": "ch3", "title": "轻量化 backbone 设计", "data_sources": ["NEU-DET"], "figures_needed": ["loss curve", "mAP table"]},
    {"chapter": "ch4", "title": "工业级部署与系统验证", ...},
    {"chapter": "ch5", "title": "总结与展望", ...}
  ],
  "max_writing_risk": "中",
  "allow_proceed_to_phase07": true
}
```

---

## Phase 07 · 开题报告 + 委员会审查

**作用**：生成 10 节开题报告骨架 + 7 维委员会审查 + 3 角色 LLM 对话（支持/质疑/折中）。

| 项 | 内容 |
|---|---|
| **输入** | TopicSpec + EvidenceLedger + RiskEvaluation + WorkPackagePlan |
| **端点** | `POST /api/v1/projects/{id}/proposal/draft/stream` (SSE) + `POST /api/v1/projects/{id}/committee/review/stream` (SSE) |
| **输出 1** | `ProposalDraft`: final_topic, proposal_sections[10 节], research_status[3+], innovation_points[2+], timeline[], risk_plan[] |
| **输出 2** | `CommitteeReview`: reviews[7 维], questions[6 追问], revision_checklist[], discussion[3 角色 LLM], overall_verdict, proposal_maturity, allow_proceed_to_phase08 |
| **前端 UI** | 10 节 + 7 维 + 3 角色对话气泡 (支持/质疑/折中) |

**10 节**：
```
1. 研究背景与意义
2. 国内外研究现状
3. 研究问题与目标
4. 研究内容与技术路线
5. 拟解决关键问题
6. 预期创新点
7. 实验方案与评价指标
8. 可行性分析
9. 进度计划
10. 风险预案
```

**7 维审查**：
```
题目边界 / 研究现状 / 创新点 / 数据与 baseline / 实验方案 / 工作量 / 风险预案
verdict ∈ {通过, 有条件通过, 需修改, 不通过}
```

**3 角色 LLM 对话**：
- supporter: 关注 WP 可行性 / Baseline 成熟度 / 数据可获得
- skeptic: 关注评价指标 / 创新性 / WP 串行
- pragmatist: 关注工程实现 / 算力 / 毕业周期

**测试用例**：
```bash
# 第一步: 开题报告
POST /api/v1/projects/1/proposal/draft/stream

# 期望输出
{
  "final_topic": "基于轻量化注意力机制的YOLOv8带钢表面缺陷检测算法研究",
  "proposal_sections": [
    {"key": "研究背景与意义", "title": "...", "content": "钢铁工业是...",
     "sources": ["topic_spec.research_object", "evidence_ledger.papers[0]"]},
    {"key": "国内外研究现状", "title": "...", "content": "YOLOv8 作为...",
     "sources": ["evidence_ledger.papers", "evidence_ledger.surveys"]},
    ... (共 10 节)
  ],
  "research_status": [
    {"category": "YOLO 系列", "representative_work": "YOLOv8 (2023)", "gap": "...",
     "relation": "本文改进 backbone"}
  ],
  "innovation_points": [
    {"innovation_id": "I01", "problem": "...", "method": "...",
     "verification": "NEU-DET mAP@0.5 ≥68%", "metrics": ["mAP", "Params"], "risk": "中"}
  ],
  "timeline": [
    {"phase": "WP1", "start": "2026-09", "end": "2026-12", "deliverable": "..."}
  ]
}

# 第二步: 委员会审查
POST /api/v1/projects/1/committee/review/stream

# 期望输出
{
  "reviews": [
    {"dimension": "题目边界", "verdict": "通过", "issues": [], "suggestions": ["..."]},
    {"dimension": "研究现状", "verdict": "有条件通过", "issues": ["综述需补充 2024 最新"],
     "suggestions": ["加入 1 篇 2024 综述"]},
    ... (共 7 维)
  ],
  "questions": [
    {"question": "轻量化会不会影响 mAP?", "suggested_answer": "...",
     "evidence_source": "evidence_ledger.papers[2306.14289]"},
    ... (共 6 问)
  ],
  "revision_checklist": [...],
  "discussion": [
    {"role": "supporter", "stance": "支持",
     "comment": "支持方面: 检索到 5 篇相关论文, 2 个工作包有公开 baseline 和数据集可参考..."},
    {"role": "skeptic", "stance": "质疑",
     "comment": "质疑方面: 创新点需要进一步具体化, 答辩时容易被问..."},
    {"role": "pragmatist", "stance": "折中",
     "comment": "工程方面: 评估 GPU 显存 / 训练时长, 如果只有 1 张 3060..."}
  ],
  "overall_verdict": "通过",
  "proposal_maturity": "B",
  "allow_proceed_to_phase08": true
}
```

---

## Phase 08 · 最终材料 + Markdown 导出

**作用**：把所有 phase 产物拼成完整开题报告 Markdown 初稿，3 维 MVP 验收 (backend / ui / playwright)。

| 项 | 内容 |
|---|---|
| **输入** | ProposalDraft + WorkPackagePlan + CommitteeReview + RiskEvaluation + EvidenceLedger |
| **端点** | `POST /api/v1/projects/{id}/final_package/build/stream` (SSE) + `GET /api/v1/projects/{id}/final_package/markdown` (下载) |
| **输出** | `FinalPackage`: ready_for_thesis (bool), backend_verification (PASS/FAIL), ui_verification, playwright_verification, proposal_markdown (10 节 + 创新点 + 答辩问答 + 风险预案 + 9 个未来工作) |
| **前端 UI** | ready_for_thesis 状态徽章 + 3 维验收 badge + Markdown 字符数 + "导出 Markdown 到本地" 按钮 |

**Markdown 初稿结构**：
```
# 开题报告: {final_topic}
## 一、研究背景与意义
## 二、国内外研究现状
... (10 节)
## 创新点
## 答辩问答 (7 问)
## 风险预案
## 未来工作 (9 条)
```

**测试用例**：
```bash
# 第一步: 拼装
POST /api/v1/projects/1/final_package/build/stream

# 期望输出
{
  "ready_for_thesis": true,
  "backend_verification": "PASS",
  "ui_verification": "BLOCKED",   # 或 PASS
  "playwright_verification": "BLOCKED",
  "proposal_markdown_chars": 10000-20000,
  "proposal_markdown": "# 开题报告: ..."
}

# 第二步: 下载
GET /api/v1/projects/1/final_package/markdown
# → 200 text/markdown
# → Content-Disposition: attachment; filename=proposal_1.md
```

---

## 端到端流程图

```
[用户填表] 
   ↓ POST /projects
[Phase 01] Project + intake_rating=B ─── rating=D ─── [BLOCKED]
   ↓ OK
[Phase 02] TopicSpec + decomposition_rating=A ─── allow_proceed_to_phase03=true
   ↓
[Phase 03] SearchQueryPlan (7 层 × ~17 query) + maturity_rating
   ↓
[Phase 04] EvidenceLedger (5 papers + 3 datasets + 3 baselines) + evidence_rating
   ↓ user 可加 paper
[Phase 05] RiskEvaluation (6 维 + 决策 + pivot) + overall_rating
   ↓
[Phase 06] WorkPackagePlan (2-3 WP + 5 章 + 实验矩阵)
   ↓
[Phase 07a] ProposalDraft (10 节)
[Phase 07b] CommitteeReview (7 维 + 3 角色对话)
   ↓
[Phase 08] FinalPackage + Markdown 下载
```

每步**阻塞规则**：
- Phase 01 阻断: rating=D
- Phase 02 阻断: WP 缺 / 章节缺 / 评价空
- Phase 03 阻断: 无
- Phase 04 阻断: 无 (papers<5 时 evidence_rating=C 但允许)
- Phase 05 阻断: rating=D
- Phase 06 阻断: work_package 缺
- Phase 07a 阻断: 无
- Phase 07b 阻断: verdict=不通过 / maturity=D
- Phase 08 阻断: 无 (read_for_thesis=false 时只警告)

---

## 与下游对接

- **Phase 08 输出 Markdown** → 用户拿去 word 排版 → 提交开题
- **论文卡片**（Phase 04）→ 论文阅读阶段
- **工作包**（Phase 06）→ 实验阶段，每 WP 对应论文 1 章
- **委员会追问**（Phase 07）→ 答辩 PPT 准备
- **风险预案 + 未来工作**（Phase 08）→ 中期检查 + 答辩材料
