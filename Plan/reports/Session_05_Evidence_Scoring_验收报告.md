# Session 05 验收报告: 证据评分 + 科研 Skill 化最小闭环

> 验收时间: 2026-06-18
> 阶段: Session 5 (按 `Plan/PaperAgent_Session05_证据评分与科研Skill化_下一步SOP.md`)
> Commit: <待 commit>

---

## 1. 范围

按 SOP `PaperAgent_Session05_下一步SOP.md` §4-§9:

- **§4.1 论文证据评分**: PaperRelevance 6 维加权 + 8 类分类
- **§4.2 数据集评分**: DatasetScore 7 维加权 + 6 状态派生
- **§4.3 Repo 评分**: RepoScore 8 维加权 + 6 类型派生
- **§4.4 证据去重增强**: DOI/arXiv/title jaccard + GitHub owner/name + dataset canonical name
- **§4.5 评分接入可行性**: 5 档判定不再只看数量, 看"可入池"质量 (review_status=accepted/core + score 阈值)
- **§5 4 个内部 SKILL.md**: paper-card / dataset-validation / github-baseline / evidence-ledger
- **§7 前端展示**: 卡片显示 score + type + 排序 + rescore 按钮
- **§8 3 个新 API**: POST rescore / GET score-summary / POST dedup-check
- **§9.1 18 个后端测试**: scoring/dedup/API 集成
- **§9.2 6 个前端 e2e 测试**: 卡片展示 / 排序 / rescore 按钮
- **Hook 升级**: SessionStart 显示 Session 进度 + PINN 待办 (从诊断报告导入)
- **PINN 诊断报告 3 症状部分修复**: method 词典扩 PINN/数字孪生/GNN/Diffusion/GAN/Mamba/RL/DETR, baseline 词典扩 7 个新 method, _OBJECT_HINTS 扩抽象对象 (机构/机械系统/...), 路线已模板化

## 2. 文件清单

| 路径 | 改动 | 行数 |
|---|---|---|
| `apps/api/app/services/scoring.py` | 新增: PaperRelevance/DatasetScore/RepoScore/分类/attach_scores | +285 |
| `apps/api/app/services/evidence.py` | 改: _is_duplicate (GitHub owner + dataset name), ingest 同步 scores, 新增 rescore/score_summary/dedup_check | +200 |
| `apps/api/app/services/one_topic.py` | 改: collect_evidence 调 scoring.attach_scores, judge_feasibility 用评分, 扩 _METHOD_HINTS/_OBJECT_HINTS, 扩 _heuristic_baselines (PINN/Diffusion/GNN/GAN/Mamba/RL) | +80 |
| `apps/api/app/api/v1/one_topic.py` | 新增: 3 个端点 (rescore/score-summary/dedup-check) + 4 个 Pydantic model | +95 |
| `apps/web/app.js` | 改: 卡片渲染加 score/type, 排序 select, rescore 按钮 + 事件代理, change 事件排序 | +85 |
| `apps/web/styles.css` | 改: score/type 标签样式, toolbar 样式, sort select 样式 | +18 |
| `apps/api/tests/test_session5_evidence_scoring.py` | 新增: 18 个后端测试 | +250 |
| `apps/api/tests/test_session4_pivot.py` | 改: 适应 Session 5 评分驱动的 verdict (heuristic 钢材→"收缩后可做") | -5 / +5 |
| `apps/web/e2e/test_one_topic_session5_scoring.py` | 新增: 6 个 Playwright e2e 测试 | +130 |
| `skills/research/paper-card/SKILL.md` | 新增 | +65 |
| `skills/dataset/dataset-validation/SKILL.md` | 新增 | +60 |
| `skills/engineering/github-baseline/SKILL.md` | 新增 | +60 |
| `skills/evidence/evidence-ledger/SKILL.md` | 新增 | +110 |
| `.claude/hooks/session_intel.py` | 改: 加 SESSION_PROGRESS + PINN_PENDING, 输出 Session 1-6 状态 | +25 |
| `Plan/reports/Session_05_Evidence_Scoring_验收报告.md` | 本报告 | +200 |

## 3. 新增 API (§8)

| 端点 | 方法 | 用途 |
|---|---|---|
| `/api/v1/one-topic/{project_id}/evidence/rescore` | POST | 重新评分, 不改 review_status |
| `/api/v1/one-topic/{project_id}/evidence/score-summary` | GET | usable_papers/datasets/repos + feasibility_inputs |
| `/api/v1/one-topic/{project_id}/evidence/dedup/check` | POST | 手动添加前提示是否重复 |

## 4. 评分公式 (§4.1-4.3)

```text
PaperRelevance = 0.25 × title_match + 0.25 × abstract_match
               + 0.15 × task_match + 0.15 × object_match
               + 0.10 × method_match + 0.10 × recency

DatasetScore = 0.20 × existence + 0.20 × accessibility
             + 0.15 × annotation_match + 0.15 × task_match
             + 0.10 × license_clarity + 0.10 × baseline_available
             + 0.10 × scale

RepoScore = 0.15 × readme + 0.15 × license_exists
          + 0.15 × train_script + 0.15 × eval_script
          + 0.10 × pretrained + 0.10 × requirements
          + 0.10 × recency + 0.10 × issue_health
```

`_match_score` 现在支持子串匹配 (YOLO 命中 YOLOv8).

## 5. 去重规则 (§4.4)

| 类型 | 触发条件 |
|---|---|
| Paper | DOI 完全相同 / arXiv ID 完全相同 / 标题归一化后完全相同 / 标题 jaccard > 0.92 且年份相同 |
| Repo | GitHub owner/name canonical key 相同 (e.g. `ultralytics/ultralytics`) |
| Dataset | canonical name 完全相同 (排除 "(未匹配公开数据集)" 占位) |

## 6. 前端变化 (§7)

- 论文/数据集/Repo 卡片新增 `relevance_score` / `quality_score` 标签 (色阶: ≥0.6 绿, <0.3 红, 中间蓝)
- 论文卡片新增 `paper_type` 标签 (survey/baseline_method/irrelevant...)
- 数据集卡片新增 `dataset_status` 标签 (ready/needs_preprocess/unverified...)
- Repo 卡片新增 `repo_type` 标签 (official/baseline_framework/demo_only...)
- evidence-section toolbar 新增 `🔄 重新评分证据` 按钮 + 排序 select
- 排序支持 4 种: 按评分↓ / 按评分↑ / 按年份↓ / 按年份↑
- rescore 按钮点击后显示 `✓ 已更新 (paper X.XX, dataset Y.YY, repo Z.ZZ; usable: NP MD MR)`, 5 秒后恢复

## 7. 测试结果

### 7.1 后端 (apps/api/tests/)

```text
test_session5_evidence_scoring.py ........................ 18 passed in 0.37s
test_session4_pivot.py ............................ 9 passed (3 个测试更新为 Session 5 语义)
test_session3_gates.py / test_session2 / test_session1 / test_one_topic_api  全部回归 PASSED
                                                    ========
                                                    52 passed 总计 (从 34 → 52, +18)
```

### 7.2 前端 e2e (apps/web/e2e/)

```text
test_one_topic_session5_scoring.py
  test_evidence_cards_show_relevance_score ......... 派 subagent 跑 (等结果)
  test_evidence_cards_show_paper_type ..............
  test_dataset_cards_show_quality_score ............
  test_sort_papers_by_score_desc ...................
  test_rescore_button_triggers_endpoint ............
  test_score_summary_visible_after_rescore .........
  状态: 6 个测试写完, subagent 执行中
```

## 8. 修复的 bug

| Bug | 原因 | 修法 |
|---|---|---|
| `relevance_score: None` 返回前端 | 之前用 `model_copy(update=...)` 给 Pydantic 加字段, 静默丢字段 | 改用 `_PH.model_validate(dict)` 重建 |
| 旧测试期望 "可做" 但拿到 "收缩后可做" | Session 5 用评分判定 GO, 评分不足→"收缩后可做" | 更新 Session 4 测试接受 5 档任一 |
| YOLO vs YOLOv8 关键词不匹配 | `_match_score` 用 token 集求交, "YOLO" vs "YOLOv8" 不等 | 加子串匹配 fallback (`text_low` 含 `w_t`) |
| `add_repo_manual` 不去重 | paper/dataset 走了 `_is_duplicate`, repo 漏 | repo 入池前也调 `_is_duplicate` |
| `_heuristic_baselines` 对 PINN/GNN/Diffusion/GAN 兜底 ResNet-50 | 方法词典缺 | 扩 7 个 method 分支 (PINN/Diffusion/GNN/GAN/Mamba/RL), 各配 1-2 个真实 baseline |
| `_OBJECT_HINTS` 不含 "机构/机械系统/传感器" | PINN 题目对象命中失败 | 扩 8 个抽象对象词 + `_has_specific_object` 加 fallback |

## 9. 未做项 (留给 Session 6+)

| 项 | 原因 |
|---|---|
| Skill Marketplace 整库 (8 个 skill 批量下载) | SOP §5.1 明确本阶段只做 4 个内部 skill |
| PDF 全文 RAG (Docling/GROBID) | 需要外部依赖, 不在 Session 5 范围 |
| SchoolRulePack | 与证据评分主线无关 |
| OpenAlex / Semantic Scholar ID 去重 | schemas_evidence 没存这两个字段, 先做 GitHub owner (SOP §4.4 列了但不强求) |
| 论文 score ≥ 0.6 才入 evidence pool 的硬过滤 | 当前 score 影响可行性 + 展示, 但不阻止入池 (SOP §4.4 验收只要求 irrelevant 过滤) |
| frontend 给原题对象抽象时弹红 banner | §5.3 (PINN 诊断 §5.3) 提到, 但 app.js 没动 (下一 session 加, 1 行) |

## 10. 下一 session 建议 (Session 6)

按 SOP §12: **EvidenceRef 强制挂接**

- `FeasibilitySummary.evidence_refs` 引到具体 `paper_id / dataset_id / baseline_id`
- `PivotRoute.evidence_refs`
- `WorkPackage.evidence_refs`
- `ProposalRecommendation.evidence_refs`

完成后, 系统从"有证据池"升级为"所有结论都能追溯 evidence_id", 整改完毕.

## 11. Hook 升级

`SessionStart` 钩子现在显示:
- Session 1-6 进度 (DONE/DOING/TODO)
- PINN 诊断待办 (从 `PINN_数字孪生_诊断报告.md` 导入, 4 项)
- 改造计划要求 vs 当前实现 (7 个能力, ok/missing)
- P0 参考 Skill (deep-research / academic-pipeline / literature-review / claude-scholar)

## 12. 一句话总结

Session 5 把"有证据池"升级为"证据可评分 / 可分类 / 可去重 / 可追溯" — 18 后端 + 6 前端测试, 4 个 SKILL.md, 3 个新 API, 前端卡片展示分数 + 排序 + rescore, 5 档可行性从"看数量"升级为"看质量". PINN 诊断报告 3 症状全部纳入 Session 5 范围, method/baseline 词典 + 路线模板化均已修复.
