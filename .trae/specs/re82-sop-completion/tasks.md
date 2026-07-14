# Tasks

## WP2 — Seed Repair 2.0

- [ ] WP2-1: 实现 `SeedCandidate` 统一 TypedDict 模型和工厂函数
  - 在 `re80_schema.py` 或新文件 `seed_candidate.py` 定义
  - 包含 all optional fields: title, authors, year, doi, arxiv_id, canonical_url, abstract, venue, sources, 各类 score, total_score, confidence, conflicts

- [ ] WP2-2: 实现多源并行检索 `_fetch_seed_candidates`
  - 四条查询：完整标题、去副标题标题、作者+核心词、年份+核心词
  - 并行调用 available sources (Crossref, Semantic Scholar, OpenAlex, arXiv)
  - 结果归一化到 SeedCandidate
  - 标题 normalization：Unicode normalize, lowercase, 去标点, 去冒号副标题, acronym alias

- [ ] WP2-3: 实现结构化评分
  - `total = 0.35*title + 0.25*author + 0.15*year + 0.15*abstract + 0.10*identifier`
  - 阈值定义：>=0.85 verified, 0.70-0.85 ambiguous, <0.70 not_found
  - 方案 B 保守逻辑（title>=0.88 AND author>=0.70 OR identifier==1.0）

- [ ] WP2-4: 实现 LLM 受限消歧
  - 仅在 2-5 候选、top1-top2<0.08、至少一项>=0.70 时调用
  - LLM 不能检索/造候选，只能选择或 reject_all
  - low confidence 或 reject_all 不得 verified

- [ ] WP2-5: 新增 SEED_AUDIT_REASON_CODES 常量 + 修改 `seed_audit_gate_node`
  - reason_codes 枚举
  - `_rule_seed_audit_gate` 输出 reason_code
  - `_build_seed_audit_prompt` 要求 LLM 输出 reason_code
  - 保持 verdict 兼容（pass/revise/unresolved）
  - `_normalize_gate_output` 扩展处理 reason_code 等新字段

- [ ] WP2-6: 编写测试（xlm_r S1 + yolo_steel S2 + 至少 15 个通用测试）
  - 包括 alias、年份冲突、作者冲突、abstract 支持、近分 LLM、reject_all、低置信度、双源冲突和不存在论文

- [ ] WP2-7: xlm_r S1 定向验证
  - BERT 长标题和去 `BERT:` 的标题视为 alias
  - 预期 top1 为原 BERT 论文，获得 DOI 或 arXiv 标识

- [ ] WP2-8: yolo_steel S2 定向验证
  - 补齐 title、Song/Yan 作者、year、abstract hint
  - 若仍近分，LLM 消歧；无法高置信则保持 ambiguous

- [ ] WP2-9: Seed Repair 单元测试全部通过 + 回归测试

## WP3 — Seed Audit Gate 结构化 reason code

- [ ] WP3-1: 扩展 `re80_schema.py` 增加 `SEED_AUDIT_REASON_CODES` 枚举
- [ ] WP3-2: 修改 `reflection_gates.py` 中 `seed_audit_gate`
  - `_normalize_gate_output` 扩展接受 reason_code
  - `_rule_seed_audit_gate` 输出 reason_code
  - `seed_audit_gate_node` 输出新增字段
- [ ] WP3-3: 更新前端类型定义展示 seed audit reason codes
- [ ] WP3-4: WP3 测试全部通过 + 回归测试

## WP4 — 真实三案例重跑

- [ ] WP4-1: vit_dr 真实重跑（验证 Gate 重入修复）
  - 保存 artifacts/re8_2/runs/vit_dr/ 下全部产物
- [ ] WP4-2: xlm_r 真实重跑（验证 Gate 重入 + BERT Seed Repair）
  - 保存 artifacts/re8_2/runs/xlm_r/ 下全部产物
- [ ] WP4-3: yolo_steel 真实重跑（验证 Song&Yan 消歧）
  - 保存 artifacts/re8_2/runs/yolo_steel/ 下全部产物
- [ ] WP4-4: 验收检查：2/3 非 BLOCKED, 1/3 quality_pass=true
  - vit_dr 不得因 Tailor 重入 blocked
  - xlm_r seed_audit 不再因 BERT mismatch unresolved
  - yolo_steel S2 必须 verified 或结构化 low-conf 诚实 unresolved

## WP5 — 真实前后端 E2E

- [ ] WP5-1: 启动真实 API 和前端 dev server
- [ ] WP5-2: Playwright 提交稳定 DOI 创建任务
- [ ] WP5-3: 轮询任务状态，验证 Seed/Gate/fused verdict 展示
- [ ] WP5-4: 下载 final package，对比 JSON 一致性
- [ ] WP5-5: 保存截图、network log、后端 run id、导出文件

## WP6 — 标准交接包与最终决策

- [ ] WP6-1: 生成 `artifacts/re8_2/final/manifest.json`
- [ ] WP6-2: 生成 `artifacts/re8_2/final/metrics.json`
- [ ] WP6-3: 生成 `artifacts/re8_2/final/decision.md`（区分 verified/inferred/proposed/unknown）
- [ ] WP6-4: 生成 `artifacts/re8_2/final/regression_report.json`
- [ ] WP6-5: 生成 `artifacts/re8_2/final/e2e_report.json`
- [ ] WP6-6: 生成 `artifacts/re8_2/final/known_gaps.json`
- [ ] WP6-7: 执行 SOP 完成度检查 hook（`python .claude/hooks/sop_completion_check.py`）

# Task Dependencies
- WP2 (2-1..2-9)：独立执行，无前置
- WP3 (3-1..3-4)：可独立执行（修改 seed_audit_gate，与 WP2 不冲突）
- WP4 (4-1..4-4)：依赖 WP2 + WP3 完成（需要 Seed Repair 和 reason code 上线）
- WP5 (5-1..5-5)：依赖 WP4 完成（需要后端代码稳定）
- WP6 (6-1..6-7)：依赖 WP4 + WP5 完成
- WP2-3 依赖 WP2-1, WP2-2
- WP2-4 依赖 WP2-3
- WP2-7/WP2-8 依赖 WP2-4
