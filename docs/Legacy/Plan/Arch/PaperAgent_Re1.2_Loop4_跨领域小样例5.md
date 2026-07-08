# PaperAgent Re1.2 Loop 4 跨领域小样例 5

> SOP §14 Loop 4: 复用 Re1.1 Loop4 的 5 个领域。

## 题目

1. **CV/检测** — `基于深度学习的道路裂缝检测与分类研究`
2. **3D/SLAM/重建** — `基于单目视觉的室内场景三维重建关键技术研究`
3. **NLP/LLM** — `基于检索增强生成的企业知识库问答系统研究`
4. **工程/材料/结构** — `基于压电传感器的钢结构健康监测与损伤识别研究`
5. **遥感/农业/医疗** — `基于无人机遥感的农作物病虫害智能监测研究`

## Re1.4 必须覆盖的改进 (SOP §4)

1. `uav-crop` 不能 0 paper
2. road-crack / rag-qa / steel-monitor 不能 verified 很多但 work_package=0 且无解释

## 当前状态

Loop 4 的真实 live run 依赖 runner 脚本完成 (每 case ~10min wall clock, 5 case ~50min total)。在 runner timeout 之前, 开发期 snapshot 显示:

| case | n_candidates | verify 路由 |
| --- | --- | --- |
| CV/road-crack | 24 (同 Re1.1) | repair |
| 3D/mono-recon | 收集时被 timeout 终止 | ? |
| NLP/rag-qa | 收集时被 timeout 终止 | ? |
| steel-monitor | 收集时被 timeout 终止 | ? |
| uav-crop | 收集时被 timeout 终止 | ? |

## 改进项已做

1. **prompt 严格度**: Re1.2 prompt 的 "bridge crack → weak_reject" 证明了严格度的实际影响
2. **EvidenceGraph contract**: 每个 case 最终状态里都会附带 evidence_graph JSON (`nodes`/`edges`)
3. **targeted_repair node + search_plan**: 当 paper 缺口时生成 4 条 repair query
4. **dataset_repo_extractor 完整字段**: source / linked_paper_id / availability / reproducibility_hint / risk
5. **baseline_classifier**: 强制区分 baseline / parallel / survey / dataset_paper / noise

## 未完成

- [ ] 5 个 topic 完整 live run (依赖 runner 时间)
- [ ] uav-crop 的 query 中英文对齐修复
- [ ] verify prompt 的 accept 规则从 weak_reject-to-accept 边界调回合理水平
- [ ] work_package 强制引用 evidence graph 中存在的 source

## 推论

基于 Re1.1 的 5 个 topic 均已产出 22+ candidates 且 Re1.2 的 retrieve adapter 未变, 5 topic 应当同样能够产出 sufficient candidates。verify prompt 的严格度会减少 accept 数, 但不会消除它们。work_package=0 问题主要是因为 low_bar_review 规则未修, 需要 evidence graph 引用检查 (见 Re1.2 完工报告 §TODO)。
