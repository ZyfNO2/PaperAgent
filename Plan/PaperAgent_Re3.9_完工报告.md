# PaperAgent Re3.9 完工报告

> **版本**: Re3.9 — Fallback 标注 + Dataset 跨节点补全 + PubMed 适配器
> **日期**: 2026-07-08
> **承接**: Re3.8 收尾清理 + 50 篇回归

---

## 1. 执行概览

| Phase | 内容 | 状态 |
|---|---|---|
| 0 | topic_parser 强制英文输出 | ✅ 完成 |
| 1 | Fallback 标注 | ✅ 完成 |
| 2 | Dataset 跨节点补全 | ✅ 完成 |
| 3 | 产物溯源分析 | ✅ 完成（95 case） |
| 4 | PubMed 适配器 + 领域门控 | ✅ 完成 |
| 5 | 禁用 S2/OpenAlex 链路验证 | 🔄 后台运行中 |

---

## 2. Phase 0: topic_parser 强制英文输出

- **文件**: `prompts/re11_topic_parser.py`
- **修改**: SYSTEM 添加 "ALL keywords MUST be in English" + translate 指令 + 示例
- **USER_TEMPLATE**: method/object/task 添加 "ALL IN ENGLISH (translate Chinese)"
- **验证**: assertion 脚本通过

## 3. Phase 1: Fallback 标注

### Fix 1.1: known_dataset_names → known_dataset_names_fallback
- 添加 FALLBACK ONLY 注释块（说明是安全网，非主路径）
- rules.md §1 合规：flat string-match，非 domain→dataset 映射

### Fix 1.2: source 标签统一

| 来源 | 旧标签 | 新标签 |
|---|---|---|
| LLM 提取 | `paper_abstract` | `llm:dataset_repo_extractor` |
| Heuristic (innovation_plan) | `innovation_plan_heuristic` | `heuristic_fallback:innovation_plan` |
| Heuristic (paper_title) | `paper_title_heuristic` | `heuristic_fallback:paper_title` |
| 跨节点补全 | (不存在) | `cross_node:innovation_extractor` |

### Fix 1.3: trace used_fallback 标志
- `output_summary` 新增 `used_fallback` + `llm_success_rate` 字段

### Fix 1.4: 前端 fallback 警告
- 时间线详情面板显示橙色 ⚠ 警告

## 4. Phase 2: Dataset 跨节点补全

- **文件**: `graph/nodes/innovation_extractor.py`
- **新增**: `_cross_node_dataset_scan()` — 扫描 innovation_points + stitching_plan 文本
- **关键设计**: 返回 `existing_ds + new_ds`（state.py 中 dataset_candidates 无 operator.add）
- **测试**: 输入 "NEU-DET and KITTI" → 正确找到 2 个数据集

## 5. Phase 3: 产物溯源分析

- **脚本**: `scripts/re39_provenance_analysis.py`
- **分析**: 95 个 eval case
- **发现**:
  - 3 个 case 触发 heuristic fallback
  - 所有 dataset source 为 `paper_title_heuristic`（pre-Re3.9 旧 case）
  - 0 个 cross_node dataset（需用 Re3.9 代码重跑才能生效）
- **报告**: `tmp_re39_eval/provenance_report.json`

## 6. Phase 4: PubMed 适配器 + 领域门控

- **新文件**: `apps/api/app/services/retrieval/adapters/pubmed_search.py`
- **注册**: REGISTRY + SearchSource Literal 添加 "pubmed"
- **领域门控**: `_get_domain_tools(domain)` — 仅 medical/biomedical/health/clinical 返回 {"pubmed"}
- **环境变量**: `PAPERAGENT_DISABLE_S2` / `PAPERAGENT_DISABLE_OPENALEX`
- **验证**: domain gating 测试通过

## 7. Phase 5: 禁用链路验证

### 状态: 🔄 后台运行中

2 个 case 运行中（S2 + OpenAlex 禁用）：
- R39-MED: 基于YOLOV5的肺结节检测算法研究（医学，应使用 PubMed）
- R39-066: 面向自动驾驶中多模态融合感知算法的攻击和防御（非医学，不应使用 PubMed）

### 已知限制
- citation_expander 的 S2 API 调用不受 env var 控制（直接调用，非通过 _run_tool）
- 需在 citation_expander 中也添加 env var 检查（Re4.0）

---

## 8. SOP 验收条件对照

| # | 条件 | 结果 |
|---|---|---|
| 1 | topic_parser 含 ALL+ENGLISH+translate | ✅ |
| 2 | known_dataset_names_fallback 标注 | ✅ |
| 3 | heuristic 产物 source 含 heuristic_fallback | ✅ |
| 4 | LLM 产物 source 含 llm: | ✅ |
| 5 | trace output_summary 含 used_fallback | ✅ |
| 6 | innovation_extractor 返回 dataset_candidates | ✅ |
| 7 | cross_node source = "cross_node:innovation_extractor" | ✅ |
| 8 | 验证 case dataset_candidates > 0 | ⏳ 需重跑验证 |
| 9 | PubMed 适配器返回 ≥3 结果 | ⏳ 需网络验证 |
| 10 | PubMed 注册到 REGISTRY | ✅ |
| 11 | _get_domain_tools 医学→pubmed | ✅ |
| 12 | 非医学 search_steps 无 pubmed | ⏳ 需验证 |
| 13 | 禁用链路 2 case 完成 | 🔄 运行中 |
| 14 | 禁用链路无 RecursionError | ⏳ |
| 15 | 禁用链路 verified_papers ≥ 3 | ⏳ |
| 16 | 禁用链路 search_steps 无 S2/OpenAlex | ⏳ |
| 21 | Batch20 溯源报告生成 | ✅ (95 case) |
| 22 | 前端时间线显示 fallback 警告 | ✅ |
