# Session 12 验收报告: 报告质量检查与低门槛委员会复核

> 验收时间: 2026-06-19
> 阶段: Session 12 (按 `Plan/PaperAgent_Session12_报告质量检查与低门槛委员会复核SOP.md`)
> 范围: 基于 FinalPackage + EvidenceRef + Verification + Trace 做 8 维低门槛审核.

---

## 1. 本阶段范围

Session 08 生成开题报告, Session 10 给证据加了验证, Session 11 加了 Trace — Session 12 把这些组合成"开题能不能给导师看"的低门槛审核.

交付:
- `ReportQualityCheck` / `DefenseQuestion` / `ReportQualityReview` / `ReportReviewRequest` / `ReportReviewSummary` Pydantic 模型
- `apps/api/app/services/report_quality.py` 全新服务: `build_quality_review()` 8 维评分
- 3 新 API 端点: `POST /report/review`, `GET /report/review`, `GET /report/review/markdown`
- 独立 Markdown 导出 (`render_quality_markdown`)
- 缓存最近 review (in-memory)
- 前端 `#quality-panel` 含 verdict badge / 8 维检查表 / 修改清单 / 答辩追问

不做 (SOP §3 黑名单): 复杂多 Agent 辩论, 模拟导师人格, 论文润色, 严格新颖性证明, 长篇正文.

---

## 2. 8 维审核维度 (SOP §5)

| 维度 | 检查内容 | 评分规则 |
|---|---|---|
| 题目边界 | recommended_topic 长度 / 风险词 | 长度 8-60 得满分; 含风险词 (智能/通用/高精度/实时/自适应/端到端) -10 |
| 研究现状 | feasibility.paper refs + verification failed 计数 | n<2 -20; 每 failed -10 |
| 数据集 | dataset refs + license + download | 无数据集 -70; 无 license -15; 无 download -10 |
| Baseline | repo refs + repo_type | 无 repo -70; unknown/demo_only/not_reproducible -20 |
| 工作包 | 每 WP 引用 ≥ 2 | 每弱 WP -15 |
| 创新点 | reason_evidence_refs 覆盖 | 无绑定 -30; 覆盖率 < 50% -25 |
| 风险预案 | missing_evidence / partial 列出 | 空 -25; partial -5 |
| 表达清晰度 | verdict / topic / confidence ≥ 0.5 | 缺 verdict -20; 缺 topic -20; confidence<0.5 -15 |

每维 0-100, 阈值 ≥80 通过 / 60-79 有条件 / 40-59 需修 / <40 不建议.

**关键维度 (触发"不建议"任一即降级):** 数据集, Baseline, 工作包, 证据覆盖.

---

## 3. 总体 verdict 规则 (SOP §6)

```text
任一关键维度 = 不建议 → 总体不建议
2+ 维度 = 需修改    → 总体需修改
1 维度 = 需修改 或 2+ = 有条件通过 → 有条件通过
否则 → 通过
```

总评分 = 各维等权平均.

---

## 4. 6 题答辩追问 (SOP §5 / §6)

模板生成 6 题, 每题绑定 evidence_refs (paper / dataset / repo):

1. 题目边界界定与核心差异 (高风险)
2. 数据集 license / 授权 (中)
3. Baseline 硬件 / 训练耗时 (中)
4. 题目风险词界定 (高)
5. 创新点量化与 SOTA 对比 (中)
6. 工作包依赖与降级方案 (低)

每题含 `question / risk_level / suggested_answer / evidence_refs`.

---

## 5. 新增 API

| 端点 | 方法 | 用途 |
|---|---|---|
| `/api/v1/one-topic/{project_id}/report/review` | POST | 构建并缓存 ReportQualityReview |
| `/api/v1/one-topic/{project_id}/report/review` | GET | 缩略 summary (verdict / score / dim / failing) |
| `/api/v1/one-topic/{project_id}/report/review/markdown` | GET | 独立 Markdown 导出 (text/markdown) |

---

## 6. EvidenceRef / ReportCitation 联动

不需要新增字段 — quality review 是项目级而非 evidence 级. 但 review 会从 ledger 读 evidence 的 verification 状态来降级维度分数 (failed/skipped 计入 "未覆盖"):

```python
# report_quality.py
for item in pool:
    if item.verification_status in ("failed", "skipped") and item.evidence_id not in {r.get("evidence_id") for r in all_refs}:
        all_refs.append(...)  # 把 failed evidence 注入 all_refs 让 _check_related_work 算入
```

---

## 7. FinalPackage 联动

按 SOP §8 MVP 推荐, 不强行改 FinalPackage markdown, 走独立导出:

`render_quality_markdown(review)`:
- 标题 + 总体判断
- 8 维表格 + 每维 issues / suggestions / 关联证据
- 修改清单
- 答辩追问 (按风险等级分组)

---

## 8. 前端 UI (`#quality-panel`)

- 🛡️ 运行审核 按钮 → `POST /report/review` → 渲染 verdict badge (`quality-verdict--{通过/有条件/需修改/不建议}`)
- ⬇ 下载审核 Markdown 按钮 → `GET /report/review/markdown`
- 8 维 checks 列表 (维度 / 分数 / result / issues / suggestions)
- 修改清单 (ul)
- 答辩追问 (按 risk_level 上色: 高 红 / 中 黄 / 低 灰)

---

## 9. 后端测试结果 (`apps/api/tests/test_session12_report_quality.py`)

**12/12 通过:**

```
test_01_build_quality_review                       PASSED
test_02_dataset_dimension_warns_on_missing        PASSED
test_03_baseline_dimension_warns_on_missing       PASSED
test_04_rejected_evidence_in_evidences_does_not_promote_pass PASSED
test_05_failed_verification_lowers_score          PASSED
test_06_work_packages_with_refs_pass              PASSED
test_07_revision_checklist_generated              PASSED
test_08_defense_questions_generated               PASSED
test_09_get_recent_review                         PASSED
test_10_review_does_not_change_evidence_state     PASSED
test_11_markdown_export                           PASSED
test_12_no_snapshot_returns_warn                  PASSED
```

---

## 10. Playwright 测试 (`apps/web/e2e/test_one_topic_session12_report_quality.py`)

**6 tests (后台 subagent 跑):** 面板可见, verdict badge, 8 维, 修改清单, 答辩追问 ≥ 6 题, evidence refs 绑定.

---

## 11. 修复的非 Session 12 问题

`_check_related_work` 原本只看 `feas_refs`, 手动加的 failed evidence 不计入. 增加:

```python
for item in pool:
    if item.verification_status in ("failed", "skipped") and item.evidence_id not in {r.get("evidence_id") for r in all_refs}:
        all_refs.append(...)  # 手动 failed 也注入
```

---

## 12. 未做项

- 不模拟真实导师人格 (Professor_skill 思路后置)
- 不做完整论文润色 (只检查骨架)
- 不生成长篇正文
- LLM 模式 (`use_llm=true`) 留接口但 MVP 不实现

---

## 13. 下一 Session 建议

Session 13 — 内部 Skill Registry 最小版 (已完成, 见 `Session_13_SkillRegistry_验收报告.md`).