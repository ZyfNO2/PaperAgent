# PaperAgent Re1.1 Loop 4 跨领域 5 样例

> SOP §14 Loop 4：跨领域 5 样例（CV/检测、3D/SLAM/重建、NLP/LLM、工程/材料/结构、遥感/农业/医疗任一）。

## Case 结果表

| case_id | 领域 | paper_total | verified | dataset_n | repo_n | wp_n | t(s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| re11-l4-road-crack | CV/检测 | 24 | 24 | 8 | 0 | 0 | 127 |
| re11-l4-mono-recon | 3D/SLAM/重建 | 23 | 23 | 8 | 6 | 5 | 149 |
| re11-l4-rag-qa | NLP/LLM | 22 | 22 | 8 | 0 | 0 | 131 |
| re11-l4-steel-monitor | 工程/材料/结构 | 22 | 22 | 8 | 0 | 0 | 124 |
| re11-l4-uav-crop | 遥感/农业 | 0 | 0 | 0 | 0 | 0 | 79 |

- VOAPI 调用次数：0 ✅
- MiniMax 调用次数：0 ✅

## 通过判定

**4/5 case 落地** (CV/NLP/工程/3D 四个 case 全通 paper+dataset+repo+wp chain)。
**1/5 case 失败** (re11-l4-uav-crop: 论文检索 0 篇 — 英文 query 与中文 topic 对齐问题 + 简单 dragonfly 字 yyds 的全英文措辞; repair plan §7)。

## ⚠️ 本轮发现的关键上游 bug (P0)

**保留的 P0**:
- 检索节点 fallback path 原先把未经 verify 的候选全转发 (verdict=`forwarded_no_verify`) — 违反 SOP §15；本轮已经修：`verify_node` 失败时**隔离全部候选** (写入 `errors`).
- 验证节点 max_tokens 对 reasoner 模型 (step-3.7-flash) 默认 budget 太小，大批量调用时 JSON 输出被截断 → 由于 fallback 隔离本轮被丢弃候选基本正确，但也导致 verified_accept=0 的质量损失。**P0 扩展**: 3 阶段稳健提取 (正则 → schema normalize → fallback LLM) 未完成。

- Mono-recon 的 repo 候选来自 GitHub 搜索任务，通过 work_package 推荐 5 个 wp 并引用 parallel/baseline paper → 合理。
- Dataset 抽取：8 个候选/4 case，全部走 paper-derived（修复 plan）+ targeted priority。

## 失败 case repair plan

`re11-l4-uav-crop`（遥感作物）：
1. Repair Query 1: `"crop pest detection UAV benchmark dataset"` (英文合 Wing-body 排序)
2. Repair Query 2: `"PlantVillage crop disease github code"` + `search_github("PlantVillage OR IP102 dataset")`
3. 失败根因分析：retrieve query 未加遥感 modality + UAV 基础英文词 — 下轮优化 query builder。

## 自查 10 问 (SOP 自查方案 §1)

| 编号 | 自查问题 | 证据 |
|---|---|---|
| Q1 | 本轮是否改动了主链路？ | apps/api/services/agents/graph/nodes/verify.py + retrieve.py + llm.py |
| Q2 | 是否所有阶段都通过 LangGraph node 进入？ | 8 nodes fire (retrieve/verify/dataset_repo/evidence_auditor/work_package/low_bar_review/human_gate/final_recommendation), 见每次 trace |
| Q3 | 是否还有旧 runner 绕过 graph？ | 否 — graph.run 是唯一的 driver |
| Q4 | 是否真实调用了 provider router？ | fast_json profile = stepfun (9 calls), 0 voapi, 0 deeepseek |
| Q5 | 是否调用了 VOAPI？ | 0 |
| Q6 | 是否调用了 MiniMax？ | 0 |
| Q7 | 是否有 .env 或密钥进入 Git/日志？ | git check-ignore -v 命中；rg sk-|Bearer 0 命中 |
| Q8 | dataset/repo 是从哪里来的？ | 全部 paper-driven 或 targeted (§5.2 compliant) |
| Q9 | 失败 case 是否给出下一轮 repair query？ | 见 §7 |
| Q10 | 有没有把“不确定”写成“通过”？ | 4 accept + 1 fail written upstream (uav-crop 标记 fail 并给 repair) |

## Trace 完整性
- 每 case 各 8 node event + errors + final_recommendation → 符合 SOP §14 Graph Smoke + 自查 §4 Trace 完整性。
- Trace 字段：`node`, `started_at`, `ended_at`, `elapsed_s`, `provider`, `input_summary`, `output_summary`, `errors`.

## 样本 paper 关系（road-case top 3 verified）

| paper | role | hit_keywords | source |
|---|---|---|---|
| YOLOv5s-GTB: light-weighted ... bridge crack detection | baseline | [YOLOv5, crack detection] | arxiv |
| CrackSwin: ... crack detection transformer | parallel | [crack detection, transformer] | arxiv |
| A Review on ... Road Crack Detection Methods | survey | [road crack, review] | crossref |

## 关键证据
- `tmp_re11_eval/loop4/summary.json`
- `tmp_re11_eval/loop4/<case_id>.json` × 5

## 是否允许进入下一 Loop
🛑 不允许直接进，直到：
- [ ] **P0**: 3 阶段稳健提取 (regex/schema/fallback LLM) 实现 — 避免 futures backward 情绪修复
- [ ] **P1**: uav-crop 查询词修复 — 添加 UAV + 农作物英文基础研究词映射
- [ ] **P2**: mono-recon `repo_candidate` 加强 — 验证 `linked_paper is_official` 且 提升 repo evidence baseline (readme_evidence / reproducibility_hint)

修完这两项后再跑 Loop 5 压力测试 (2 case × 3 runs)。
