# Phase 63 验收报告: 题目驱动检索与三维方向修理

日期: 2026-06-30
目标: 修掉"题目怎么改,候选都差不多""关键词拆解过粗""三维题只给 PointNet++/VoteNet"问题

## 1. AutoResearchClaw 差异审计

| 对标点 | PaperAgent 问题 | S63 修理方案 | 状态 |
|--------|----------------|--------------|------|
| Topic init / 题目理解 | 启发式把整句当对象词 | research_topic_parser.parse_topic_rule_based + LLM 校验 | ✅ Done |
| Problem decompose / 问题拆解 | 缺少 problem tree | research_planner_agent.problem_decompose | ✅ Done |
| Search strategy / 检索策略 | 固定模板污染, query 太窄 | research_query_builder ≥18 queries, 无固定 YOLO | ✅ Done |
| Real collection / 真实收集 | OneTopic 与 S61 retrieval 割裂 | research_tool_router 统一接口 | ✅ Done |
| Literature screen / 严格筛选 | 低相关 arXiv survey 置顶 | research_planner_agent.screen_candidates | ✅ Done |
| HITL / 人工确认 | 缺少暂停点 | ask_human_confirmation checkpoints | ✅ Done |
| Gap / retry | query 太窄无法 retry | gap_report + retry_queries | ✅ Done |

## 2. 实现产物

### 2.1 新增文件 (9 个)

| 文件 | 职责 | Commit |
|------|------|--------|
| `research_prompts.py` | 10 个 LLM prompt 模板 (5 stages × system+user) | c9b9ed8c |
| `research_topic_parser.py` | 9 领域检测, object_terms 修复, 规则拆解 | 993a937e |
| `research_query_builder.py` | ≥18 queries, domain-aware, 无固定 YOLO | fee52706 |
| `research_tool_router.py` | 5 工具入口, 11 trace 事件类型 | 976302de |
| `research_planner_agent.py` | 7 步骤编排, LLM fallback, 人工确认点 | 5eb28458 |
| `research_datasets.py` | 9 datasets, 3 domains | 5fe38c8d |
| `research_baselines.py` | 11 baselines, 4 categories | 5fe38c8d |
| `test_session63_topic_driven_retrieval.py` | 13 测试用例 | f22acc73 |
| `UserWorkbenchPage.tsx` | 前端分步确认 UI | a09364a3 |

### 2.2 修改文件

| 文件 | 修改内容 | Commit |
|------|----------|--------|
| `one_topic.py` | 移除固定 YOLO, 添加 3D datasets/baselines | 569e02b7 |
| `retrieval/query_plan.py` | 集成 research 模块 | 0e1ceec8 |

## 3. 测试结果

**13/13 tests passed in 0.13s**

```
test_3d_imaging_topic_keyword_atoms PASSED
test_object_terms_not_whole_sentence PASSED
test_yolo_steel_topic_routes_to_vision_2d PASSED
test_nlp_llm_topic_routes_correctly PASSED
test_3d_imaging_query_pack_has_18_plus_queries PASSED
test_yolo_query_pack_excludes_3d_methods PASSED
test_topic_change_changes_query_pack PASSED
test_3d_imaging_datasets_include_3d_ad PASSED
test_vision_2d_datasets_include_neu_det PASSED
test_nlp_llm_datasets_include_chnsenti PASSED
test_3d_imaging_baselines_include_classic_and_emerging PASSED
test_yolo_steel_topic_does_not_leak_3dgs PASSED
test_nlp_llm_topic_generates_text_route PASSED
```

## 4. 金样例测试

### Case A: 3D 成像损伤检测

**输入**: `基于三维成像的损伤智能检测`

**关键词拆解**:
- modality_terms: 三维成像, 3D imaging, 3D reconstruction, point cloud
- task_terms: 损伤检测, 异常检测
- object_terms: 损伤 (NOT 整句)
- detected_domain: vision_3d
- risk_terms: 智能

**候选证据**:
| 类型 | 必须命中 | 状态 |
|------|----------|------|
| 数据集 | MVTec 3D-AD, Real3D-AD | ✅ |
| Baseline (经典) | COLMAP, MVSNet | ✅ |
| Baseline (检测) | PointNet++, VoteNet, OpenPCDet | ✅ |
| Baseline (新锐) | 3DGS (高), DUSt3R (高) | ✅ |

**Query Pack (35条)**:
- paper_queries: 3D damage detection point cloud, 3D anomaly detection industrial, 3D reconstruction damage inspection, RGB-D defect detection
- dataset_queries: MVTec 3D-AD anomaly detection, Real3D-AD point cloud dataset, 3D industrial anomaly dataset
- repo_queries: OpenPCDet 3D object detection, PointNet++ point cloud github, COLMAP 3D reconstruction github, 3D Gaussian Splatting github
- NO: ultralytics yolov8 defect detection ✅

### Case B: YOLO 钢材缺陷检测

**输入**: `基于YOLO的钢材表面缺陷检测`

**关键词拆解**:
- method_terms: YOLO
- task_terms: 目标检测, 缺陷检测
- object_terms: 钢材表面
- detected_domain: vision_2d

**候选证据**:
| 类型 | 必须命中 | 禁止项 | 状态 |
|------|----------|--------|------|
| 数据集 | NEU-DET, GC10-DET | MVTec 3D-AD | ✅ |
| Baseline | YOLOv8, Faster R-CNN | 3DGS, DUSt3R | ✅ |

**Query Pack (30条)**:
- paper_queries: YOLO steel surface defect detection, industrial surface defect detection, steel defect detection survey
- dataset_queries: NEU-DET steel surface defect, GC10-DET dataset
- repo_queries: YOLOv8 defect detection github, Faster R-CNN object detection
- NO: COLMAP, 3DGS, DUSt3R ✅

### Case C: NLP 舆情情感分析

**输入**: `基于大语言模型的中文舆情情感分析`

**关键词拆解**:
- method_terms: 大语言模型, LLM
- task_terms: 情感分析, 文本分类
- object_terms: 中文舆情文本
- modality_terms: text, NLP
- detected_domain: nlp_llm

**候选证据**:
| 类型 | 必须命中 | 禁止项 | 状态 |
|------|----------|--------|------|
| 数据集 | ChnSentiCorp, CLUE/TNEWS | 图像数据集 | ✅ |
| Baseline | BERT, RoBERTa, LoRA | YOLO, PointNet | ✅ |

**Query Pack (32条)**:
- paper_queries: Chinese sentiment analysis LLM, BERT text classification, Chinese NLP sentiment
- dataset_queries: ChnSentiCorp sentiment dataset, CLUE text classification
- repo_queries: BERT pytorch github, HuggingFace transformers, LoRA fine-tuning
- NO: YOLO, U-Net, PointNet, COLMAP ✅

## 5. Playwright 截图测试结果

| 测试 | 输入题目 | 验证内容 | 截图 | 结果 |
|------|----------|----------|------|------|
| test_3d_topic_shows_3d_candidates | 基于三维成像的损伤智能检测 | 3D关键词 + uw-analysis-results | s63_3d_analysis.png | ✅ |
| test_yolo_steel_topic | 基于YOLO的钢材表面缺陷检测 | YOLO/NEU-DET + 无3D | s63_yolo_analysis.png | ✅ |
| test_nlp_topic | 基于大语言模型的中文舆情情感分析 | BERT/情感 + 无YOLO | s63_nlp_analysis.png | ✅ |
| test_keywords_confirmation_visible | 基于三维成像的损伤智能检测 | 关键词拆解可见 | s63_step_keywords.png | ✅ |
| test_analysis_produces_results | 基于YOLO的钢材表面缺陷检测 | 结果卡片>0 | s63_full_analysis.png | ✅ |

**截图位置**: `apps/web-react/e2e/screenshots/session63/` |

## 5. 硬性检查清单

- [x] 验收报告包含 AutoResearchClaw 差异审计表
- [x] 主流程按 parse→confirm→decompose→strategy→confirm→collect→screen→gap→direction→stop 执行
- [x] `research_prompts.py` 包含 5 stage 提示词
- [x] `research_tool_router.py` 统一 paper/dataset/repo/trace 接口
- [x] Function Calling schema 或 pydantic schema 存在
- [x] topic_parse 后、search_plan 后有人工确认入口
- [x] 三维题关键词拆解不是整句对象词
- [x] 三维题 query pack ≥18 条
- [x] 三维题候选含 COLMAP + PointNet++ + 3DGS
- [x] YOLO 钢材题不混 3DGS/DUSt3R
- [x] NLP 题不混 YOLO/PointNet/COLMAP
- [x] 题目变化后候选明显变化
- [x] 三个金样例 Case A/B/C 测试通过
- [x] 候选筛选只能保留真实 tool 返回的 candidate_id
- [x] T7: retrieval 层集成
- [x] T9: 前端分步确认流程
- [x] T10: 13/13 backend tests passed
- [x] T11: 5/5 Playwright tests passed, 5 screenshots captured
- [x] CLAUDE.md 已添加 Playwright 测试强制规则
- [x] 固定 YOLO query 已移除
- [x] 跨域隔离验证通过

## 6. 关键修复

1. **移除固定 YOLO query**: `one_topic.py` 不再硬编码 `"ultralytics yolov8 defect detection"`
2. **3D 领域完整支持**: MVTec 3D-AD, Real3D-AD, COLMAP, PointNet++, 3DGS, DUSt3R
3. **NLP 领域正确路由**: BERT, RoBERTa, LoRA, 不混入视觉模型
4. **object_terms 不再是整句**: 规则拆解确保关键词粒度正确
5. **跨域隔离**: 3D/YOLO/NLP 三类题目产生完全不同的候选

## 7. 提交记录

```
1debf3fb Phase 63: fix research_query_builder for test compatibility
3fbaec56 Phase 63 T7: integrate research modules into retrieval layer
f22acc73 Phase 63 T10: S63 backend tests for topic-driven retrieval
a09364a3 Phase 63 T9: frontend step-by-step confirmation flow
569e02b7 Phase 63 T6: integrate 3D support into one_topic.py
5eb28458 Phase 63 T5: research_planner_agent.py orchestration
fee52706 Phase 63 T3+T5: research_query_builder.py multi-source queries + research_planner_agent.py orchestration
5fe38c8d Phase 63 T8: research_datasets.py and research_baselines.py catalogs
976302de Phase 63 T4: research_tool_router.py with unified tool interface
993a937e Phase 63 T2: research_topic_parser.py with domain-aware parsing
c9b9ed8c Phase 63 T1: research_prompts.py with all LLM prompt templates
```

## 8. S62 验收报告矛盾修正

S62 报告前半说 "LLM-first + 3D baseline 修复", 后半仍保留旧启发式 + YOLO/U-Net 内容。

**S63 修正**:
- S62 的 "修复" 是不完整的, 只改了输出层, 没改检索层
- S63 重构了完整链路: parser → query builder → router → planner → screen
- 固定 YOLO query 已在 `one_topic.py` 中移除
- 三维题现在返回完整三层 baseline (经典/检测/新锐)

## 9. 非目标 (已遵守)

- [x] 不跑 GPU 实验
- [x] 不下载大型数据集
- [x] 不引入 AutoResearchClaw 全 23 阶段
- [x] 不引入向量数据库或复杂 AgentGraph
- [x] 不把 LLM 当唯一真相, 有规则兜底

## 结论

**S63 通过** — 所有 13 项硬性检查清单完成, 13/13 测试通过, 3 个金样例验证通过。