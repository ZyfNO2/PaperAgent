# Re8.2 工程决策报告

**生成时间**：2026-07-14  
**SOP**：Re8.2 SeedAudit收敛·Gate路由修复与真实E2E  
**最终判定**：**PARTIAL**（工程目标达成，但业务验收指标未完全满足）

---

## 1. 已达成目标（verified）

| 目标 | 证据 | 可信度 |
|---|---|---|
| Gate 重入修复 | `reflection_gates.py` 引入输入 fingerprint 与 per-cycle round 计数；`vit_dr` tailor_gate 不再因相同输入重入 cap | verified |
| Seed Repair 2.0 | `seed_resolver.py` 实现多源并行检索、结构化评分、LLM 受限消歧；`xlm_r S1` BERT 长标题别名可解析 | verified |
| Seed Audit reason code | `re80_schema.py` / `reflection_gates.py` / 前端 `SeededResearch.tsx` 已输出并展示结构化 reason code | verified |
| 真实 WP4 三案例运行 | `artifacts/re8_2/final/{vit_dr,xlm_r,yolo_steel}/` 下 summary/state/trace/gate_cycles/seed_candidates/final_package 完整 | verified |
| 真实 WP5 前后端 E2E | Playwright 测试通过，case_id=`2f7868f8f2ff8`，用时 827s，导出 JSON 与界面一致 | verified |
| 回归测试 | Re8 567 单元测试通过 + 25 个 Seed Repair 测试 + Gate re-entry 10 测试 + 1 E2E 通过 | verified |

---

## 2. 未达成业务验收指标（known gaps）

| 指标 | 目标 | 实际 | 说明 |
|---|---|---|---|
| 非 BLOCKED 比例 | ≥ 2/3 | 0/3 | 三案例 fused_verdict 均为 BLOCKED |
| quality_pass 比例 | ≥ 1/3 | 0/3 | 因 fused_verdict=BLOCKED，quality_pass 强制为 false |

**根因分析**（inferred / proposed）：

1. **vit_dr**：Tailor Gate 达到 cap 后未收敛，最终 review gate 同样 unresolved。`tailor_gate` 仍因 `gap-S2-fulltext` 开放而失败，说明 S2 baseline 全文获取链路尚未完全打通。
2. **xlm_r**：Seed Audit 与 Tailor Gate 均通过，但 `final_review_gate` 在 novelty/weak_reject 压力下达到 cap unresolved。反映最终评审对证据充分性要求高于当前检索能力。
3. **yolo_steel**：S2（Song & Yan 钢铁表面缺陷论文）未能获得稳定 identifier，Seed Audit Gate 达到 cap unresolved。Seed Repair 2.0 对无 DOI/arXiv 的中文/工业论文覆盖仍不足。

---

## 3. 决策矩阵

| 维度 | 结论 | 等级 |
|---|---|---|
| 工程修复完成度 | WP1-WP3 代码实现与测试全部完成 | verified |
| 系统集成度 | 前后端真实 E2E 可跑通 | verified |
| 业务目标（案例通过率） | 0/3 非 BLOCKED，未达 SOP 目标 | not_met |
| 交付可继续性 | 系统可运行、可观测、可交接 | verified |

---

## 4. 最终建议

- **短期**：当前代码状态可作为 Re8.2 工程包交付，理由是 Gate 重入与 Seed Repair 2.0 已按 SOP 实现并通过测试。
- **中期**：需在 Re8.3 或后续阶段继续攻关 `final_review_gate` 收敛与 baseline 全文获取，以提升非 BLOCKED 比例。
- **长期**：yolo_steel S2 类无稳定 identifier 论文需引入更激进的 Repair 策略（如作者+年份+期刊多源交叉、本地 PDF 上传、或人工确认）。

---

## 5. 可信度图例

- **verified**：有直接运行产物或测试覆盖。
- **inferred**：基于运行结果与代码逻辑的合理推断。
- **proposed**：基于观察提出的下一步假设，待验证。
- **unknown**：当前数据不足以判断。
