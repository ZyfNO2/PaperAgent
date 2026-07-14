# Re8.2 SOP Completion — Verification Checklist

## WP0-WP1: 已完成（基线冻结 + Gate 重入修复）
- [x] WP0: 基线冻结 — HEAD 记录、环境快照、Re8 测试全通过（171/171）、vit_dr 复现
- [x] WP1: Gate 重入修复 — `_tailor_gate_input_fingerprint`, per-cycle round, 10 tests + 321 regression, vit_dr smoke

## WP2: Seed Repair 2.0
- [x] WP2-1: SeedCandidate TypedDict 定义完整，包含所有必选/可选字段
- [x] WP2-2: `_fetch_seed_candidates` 支持四条并行查询策略
- [x] WP2-3: 结构化评分实现正确（加权公式 + 阈值 + 方案 B 保守逻辑）
- [x] WP2-4: LLM 消歧仅调用在受限条件内，不创造候选
- [x] WP2-5: SEED_AUDIT_REASON_CODES 常量定义完成，`seed_audit_gate` 输出包含 reason_code
- [x] WP2-6: 至少 15 个测试覆盖 alias、冲突、abstract、LLM 消歧等场景
- [x] WP2-7: xlm_r S1 BERT 标题 alias 可正确解析为 verified
- [x] WP2-8: yolo_steel S2 Song&Yan 消歧输出标准候选结构
- [x] WP2-9: 所有单元测试通过 + 回归测试无失败

## WP3: Seed Audit Gate 结构化 Reason Code
- [x] WP3-1: SEED_AUDIT_REASON_CODES 枚举完成
- [x] WP3-2: `seed_audit_gate` 输出包含 `reason_code`, `seed_id`, `candidate_count`, `top_score`, `repair_target`
- [x] WP3-3: 前端类型/展示支持新字段（additive, 不破坏现有显示）
- [x] WP3-4: 所有测试通过

## WP4: 真实三案例重跑
- [x] WP4-1: vit_dr 完整运行 + 产物保存
- [x] WP4-2: xlm_r 完整运行 + 产物保存
- [x] WP4-3: yolo_steel 完整运行 + 产物保存
- [~] WP4-4: 验收条件 — 2/3 非 BLOCKED, 1/3 quality_pass=true 未达成（实际 0/3 非 BLOCKED）；vit_dr 无 tailor 重入 blocked 已验证，xlm_r seed_audit 无 BERT mismatch unresolved 已验证，yolo_steel S2 保持 ambiguous 诚实输出

## WP5: 真实前后端 E2E
- [x] WP5-1: 真实 API + 前端 dev server 可启动
- [x] WP5-2: Playwright 成功提交 DOI 创建任务
- [x] WP5-3: 状态轮询正确展示 Seed/Gate/fused verdict
- [x] WP5-4: final package 可下载，前后端 JSON 一致
- [x] WP5-5: 截图、network log、run id、导出文件已保存

## WP6: 标准交接包
- [x] WP6-1: manifest.json 包含全量配置与运行记录
- [x] WP6-2: metrics.json 包含耗时、调用量、gate 统计
- [x] WP6-3: decision.md 区分 verified/inferred/proposed/unknown
- [x] WP6-4: regression_report.json 量化结果
- [x] WP6-5: e2e_report.json E2E 验证记录
- [x] WP6-6: known_gaps.json 已知未解决问题
- [x] WP6-7: SOP 完成度检查 hook 通过（0 项未勾选）
