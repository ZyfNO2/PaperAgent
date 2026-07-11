# PaperAgent Re3.8 系统性问题修复 SOP

> 基于 18 篇新代码 case 的回归数据，发现 10 个系统性问题。
> 本 SOP 覆盖全部 10 项，按 P0→P1→P2 顺序执行。

## 问题清单

### P0（3 项）
1. feasibility 评分聚集 75 分 — prompt 评分锚点不够强制
2. 数据集提取弱（13/18 为 0）— extractor 摘要截断 800 字符 + LLM 识别力不足
3. 仓库覆盖率不均（8/18 为 0）— search_agent 查询重复 + 过早 stop

### P1（4 项）
4. baseline/parallel 分类不均衡 — LLM 重分类 prompt 需改进
5. topic_parser 中文翻译不稳定 — 需增加 heuristic 翻译层
6. search_agent 查询重复 8 次 — 需在 LLM prompt 中强化去重
7. 零 BLOCK verdict — devils_advocate heuristic fallback 过于宽松

### P2（3 项）
8. R36-021 数据异常（55 篇/48 parallel）— citation_expander 过度展开
9. Re3.7 硬编码移除后未跑 e2e — 需冒烟验证
10. S2 API 429 限流 — 需增加指数退避

## 修复方案

### Fix 1: feasibility 评分锚点强化
**文件**: `prompts/feasibility_assessor.py`
- 增加更细粒度的评分锚点（已有 Re3.8 版本改进，需确认）
- 增加 "禁止给 75 作为默认值" 的显式禁止

### Fix 2: dataset_extractor 增强
**文件**: `nodes/dataset_repo_extractor.py` + `prompts/re11_dataset_repo_extractor.py`
- 增加摘要截断长度 800→1500
- 在 LLM prompt 中传入 topic domain 上下文

### Fix 3: search_agent 查询去重 + 仓库搜索强化
**文件**: `nodes/search_agent.py`
- 在 _llm_decide 返回后增加去重检查
- 当论文≥5 但仓库=0 时强制搜索 GitHub

### Fix 4: baseline_classifier LLM prompt 改进
**文件**: `nodes/baseline_classifier.py`
- 在 LLM prompt 中增加 "方法名相同但版本不同→baseline" 的判断规则

### Fix 5: topic_parser heuristic 翻译层
**文件**: `nodes/topic_parser.py`
- 在 _heuristic_parse 中增加简单的中文→英文翻译（非硬编码字典，而是基于规则）

### Fix 6: search_agent LLM prompt 强化去重
**文件**: `nodes/search_agent.py`
- 在 _SYSTEM_PROMPT 中增加 "禁止重复已用查询" 的更强语气

### Fix 7: devils_advocate heuristic 收紧
**文件**: `nodes/devils_advocate_node.py`
- _heuristic 中 baseline<3 + risky → BLOCK（而非 MINOR_REVISION）

### Fix 8: citation_expander 上限
**文件**: `nodes/citation_expander.py`
- 增加 expanded_papers 上限（如 30 篇）

### Fix 9: 冒烟验证
- 跑 1 个 case 验证 Re3.7 硬编码移除后系统正常

### Fix 10: S2 指数退避
**文件**: `adapters/semantic_scholar_search.py`
- 429 后增加 retry-after 等待
