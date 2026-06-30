# PaperAgent Session 61 SOP：科研检索增强与项目/数据集发现

日期：2026-06-30

状态：正式 SOP。Session 60 本地 RAG 最小闭环已出验收报告，建议通过；但 Ponytail 审计指出一个 P1 根因修复必须在 S61 开工第一步完成。

继承 Rules：

- `Plan/PaperAgent_SOP执行Rules_真实接线与点击验收.md`

参考材料：

- `Plan/reports/Session_60_LocalRAG_MinimalLoop_验收报告.md`
- `Plan/reports/Session_60_Ponytail_Audit_Report.md`
- `Plan/reports/AutoResearchClaw_对标移植_验收报告.md`
- `Plan/reports/AutoResearchClaw_求职向增强_验收报告.md`
- `docs/interview/AutoResearchClaw_对标与小型化移植.md`
- 现有检索模块：
  - `apps/api/app/services/retrieval/query_plan.py`
  - `apps/api/app/services/retrieval/orchestrator.py`
  - `apps/api/app/services/retrieval/ranker.py`
  - `apps/api/app/services/retrieval/adapters/openalex_search.py`
  - `apps/api/app/services/retrieval/adapters/arxiv_search.py`
  - `apps/api/app/services/retrieval/adapters/github_search.py`
  - `apps/api/app/services/retrieval/adapters/huggingface_search.py`

## 0. 最新审核结论与执行前置

### 0.1 Session 60 审核结论

`Session_60_LocalRAG_MinimalLoop_验收报告.md` 建议通过：

- 文献 RAG 库已从前端 `useState` 改为后端 `POST /manual` + `GET /paper-library`。
- 本地索引已接 `POST /index`，并真实生成 `embeddings.jsonl`。
- 本地问答已接 `POST /local-ask`，能返回 answer + evidence quote。
- 刷新后文献仍存在。
- 有后端测试、前端 Playwright、真实点击截图。

但 S60 仍有两个需要后续注意的边界：

- 证据提交区 `EvidenceSubmitPanel` 仍未完整接后端 evidence ledger。
- 中文 query 到英文 corpus 的命中率仍弱，需要后续检索增强解决。

### 0.2 Ponytail 审计必须处理的 P1

`Session_60_Ponytail_Audit_Report.md` 指出一个 S61 开工前必须修的 P1：

```text
retriever.dense_retrieve 需要增加 vocab 参数；
local_rag.py 里复刻 dense 计算的代码应删除，改为复用 retriever.dense_retrieve(vocab=embedding.get_vocab())。
```

这是根因修复，不是优化项。S61 执行者必须先做：

1. 修改 `apps/api/app/services/paper_library/retriever.py`。
2. 删除 `apps/api/app/services/paper_library/local_rag.py` 中复刻 dense retrieve 的代码。
3. 确认 S60 本地 RAG 测试仍通过。

不允许：

- 不允许在 S61 继续复制第三份 dense retrieve。
- 不允许只因为当前测试通过就跳过 P1。
- 不允许在检索增强模块里再写一套相似度检索。

### 0.3 S61 检索增强最低质量门槛

一次检索运行必须产出结构化结果，而不是一句“没找到”：

| 类型 | 最低要求 |
|---|---|
| paper | 至少 3 条候选，或明确 source/query 失败原因 |
| dataset | 至少 1 条候选，或明确 source/query 失败原因 |
| repo | 至少 1 条候选，或明确 source/query 失败原因 |
| source_results | 每个 source 必须记录 `completed / failed / no_result / adapter_missing` |
| gap_report | 必须区分 `no_result / source_failed / query_too_narrow / adapter_missing` |
| candidate action | 每条有效候选必须能导入证据区或文献 RAG 库 |

候选为空可以接受，但必须能解释为什么为空，并给出下一轮补搜 query。

## 1. 当前问题

当前检索过于简陋，尤其对类似：

```text
基于三维成像的损伤智能检测
```

这类题目容易出现：

- 能搜到少量论文，但搜不到合适数据集。
- GitHub 工程候选不足或不相关。
- 数据集/工程没有被拆成独立候选供用户确认。
- 可行性判断直接因“缺数据集/工程”给不建议，但没有继续扩展搜索。
- 前端只给结论，不告诉用户搜索了哪些 query、哪些 source 失败、下一步该怎么补。

S61 的目标是先补强“科研检索发现能力”，不是做完整 AutoResearchClaw。

## 2. 本轮目标

做一个简单但真实的检索增强闭环：

```text
题目
→ 关键词/对象/任务/方法拆解
→ 生成多层检索计划
→ 并发搜索论文/数据集/项目
→ 候选归一化与评分
→ 前端展示候选和缺口
→ 用户可把候选导入证据区或文献 RAG 库
```

最低目标：

- 至少能分别返回 paper / dataset / repo 三类候选。
- 如果某类搜不到，要显示搜索过的 query 和失败原因。
- GitHub 和 HuggingFace 不得只是摆设，必须真实调用或明确降级。
- 对“不建议开题”的判断必须附带“检索缺口”和“下一步补搜建议”。

## 3. 本轮不做什么

不做：

- 不做完整 AutoResearchClaw 23 阶段科研自动化。
- 不自动生成论文。
- 不跑实验。
- 不接 Neo4j / GraphRAG。
- 不做多 RAG 策略 A/B。
- 不做 LLM 自动判真伪。
- 不让 LLM 直接写 supports。
- 不把网络失败伪装成“没有资源”。

## 4. 模块设计与约束

### M0：PonytailRootCauseCleanup

建议文件：

```text
apps/api/app/services/paper_library/retriever.py
apps/api/app/services/paper_library/local_rag.py
```

职责：

- 给 `retriever.dense_retrieve` 增加可选 `vocab` 参数。
- 保持 `vocab=None` 时旧调用兼容。
- `local_rag.ask_local_rag` 改为复用 `retriever.dense_retrieve(..., vocab=embedding.get_vocab())`。
- 删除 `local_rag.py` 中复制的 dense cosine 排序逻辑。

不应该：

- 不应该改变 S60 API response。
- 不应该引入外部 embedding。
- 不应该修改 `embeddings.jsonl` 格式。
- 不应该把 dense 逻辑复制到 retrieval enhancement 新模块。

验收：

- S60 后端测试仍通过。
- `local_rag.py` 中不再出现一整段独立 cosine dense 排序循环。

### M1：ResearchQueryExpander

建议文件：

```text
apps/api/app/services/retrieval/research_query_expander.py
```

职责：

- 从题目中拆出：
  - 方法词：YOLO、Transformer、3D reconstruction、depth imaging 等。
  - 任务词：detection、classification、segmentation、damage detection 等。
  - 对象词：steel、bridge、crack、defect、concrete、3D image 等。
  - 资源词：dataset、benchmark、github、pytorch、baseline 等。
- 生成中英混合 query。
- 为 paper / dataset / repo 分别生成不同 query。

不应该：

- 不应该调用外部搜索。
- 不应该返回候选结果。
- 不应该做可行性判断。
- 不应该用 LLM 生成不可解释 query。

最小输出：

```json
{
  "method_terms": ["3d imaging"],
  "task_terms": ["damage detection"],
  "object_terms": ["crack", "defect", "concrete"],
  "paper_queries": ["3d imaging damage detection", "..."],
  "dataset_queries": ["3d crack detection dataset", "..."],
  "repo_queries": ["3d damage detection github pytorch", "..."]
}
```

### M2：RetrievalSourcePolicy

建议文件：

```text
apps/api/app/services/retrieval/source_policy.py
```

职责：

- 根据 candidate type 选择 source：
  - paper：OpenAlex + arXiv。
  - dataset：HuggingFace，后续可加 Kaggle / PapersWithCode。
  - repo：GitHub。
- 当某个 source 失败时记录 source failure。
- 明确区分：
  - `source_failed`
  - `no_result`
  - `query_too_broad`
  - `adapter_not_available`

不应该：

- 不应该直接吞掉异常。
- 不应该把网络错误当作“无资源”。
- 不应该把未实现 source 显示为已搜索。

### M3：DatasetCandidateEnhancer

建议文件：

```text
apps/api/app/services/retrieval/dataset_enhancer.py
```

职责：

- 对 dataset 候选补充可用性提示：
  - 是否有下载链接。
  - 是否有 license。
  - 是否看起来是 benchmark。
  - 是否与对象/任务匹配。
- 给出 warnings：
  - `license_unknown`
  - `low_relevance`
  - `not_public`
  - `needs_manual_check`

不应该：

- 不应该断言数据集一定可用。
- 不应该伪造 license。
- 不应该仅凭标题就标记 `ready`。

### M4：RepoCandidateEnhancer

建议文件：

```text
apps/api/app/services/retrieval/repo_enhancer.py
```

职责：

- 对 GitHub 候选补充复现提示：
  - stars。
  - updated_at。
  - language。
  - license。
  - README/description。
  - 是否含 pytorch / tensorflow / training / dataset 等关键词。
- 给出 warnings：
  - `stale_repo`
  - `no_license`
  - `low_star`
  - `unclear_training_script`
  - `needs_manual_check`

不应该：

- 不应该只按 stars 排序。
- 不应该把高 star 通用项目当作题目相关工程。
- 不应该未检查描述就标记可复现。

### M5：RetrievalGapReport

建议文件：

```text
apps/api/app/services/retrieval/gap_report.py
```

职责：

- 汇总 paper / dataset / repo 三类候选数量和质量。
- 输出缺口：
  - 缺公开数据集。
  - 缺可复现工程。
  - 论文有但 baseline 不清。
  - source 查询失败。
- 生成下一步补搜建议。

不应该：

- 不应该直接替代可行性判断。
- 不应该给“建议/不建议开题”的最终结论。
- 不应该把 `source_failed` 当成 `no_result`。

### M6：RetrievalRetryPlanner

建议文件：

```text
apps/api/app/services/retrieval/retry_planner.py
```

职责：

- 根据 `gap_report` 生成第二轮补搜 query。
- 当 dataset 为空时，放宽对象词和数据集词。
- 当 repo 为空时，加入 `implementation / pytorch / github / baseline / code / train`。
- 当 paper 有但 dataset/repo 没有时，从 paper title / abstract 中抽 dataset/repo 线索。
- 最多执行 1 轮 retry，避免成本失控。

补搜示例：

```text
damage detection
→ crack detection dataset
→ concrete defect detection benchmark
→ structural health monitoring dataset
→ 3D reconstruction crack detection github pytorch
```

不应该：

- 不应该无限递归搜索。
- 不应该自动判定题目不可行。
- 不应该把补搜失败伪装成没有资源。
- 不应该在普通用户界面展示 raw debug spam。

### M7：CandidateActionBridge

建议文件：

```text
apps/api/app/services/retrieval/candidate_actions.py
apps/web-react/src/features/evidence/RetrievalCandidatePanel.tsx
```

职责：

- 把 retrieval candidate 导入证据区或文献 RAG 库。
- paper 候选：可导入 evidence ledger，也可进入 paper library。
- dataset 候选：导入 evidence dataset lane。
- repo 候选：导入 evidence repo lane。
- 导入结果必须显示真实后端返回的 evidence_id 或 paper_id。

不应该：

- 不应该只在前端列表中标记“已加入”。
- 不应该在后端失败时显示成功。
- 不应该把 dataset/repo 候选导入 paper library。
- 不应该让用户无法撤销或标记不相关。

最低动作：

- `加入证据`
- `加入文献库`，仅 paper 可用
- `标记不相关`
- `补搜类似`

## 5. 现有模块改造点

### 5.1 `query_plan.py`

增强点：

- 加入三维/成像/损伤/裂缝/桥梁/混凝土/结构健康监测等对象词映射。
- 将中文题目转成更可搜索的英文组合：
  - `three-dimensional imaging`
  - `3D reconstruction`
  - `structural damage detection`
  - `crack detection dataset`
  - `concrete defect detection`
  - `bridge damage detection`
- dataset query 不应只拼 `dataset`，还要拼：
  - `benchmark`
  - `public dataset`
  - `challenge`
  - `Kaggle`
  - `HuggingFace`
- repo query 不应只拼 `GitHub`，还要拼：
  - `pytorch`
  - `implementation`
  - `baseline`
  - `train`
  - `code`

禁止：

- 不要删掉旧 L0-L5 结构。
- 不要只为截图中的一个题目硬编码。
- 不要只返回中文 query。

### 5.2 `orchestrator.py`

增强点：

- 保留 source_results 的失败类型。
- 对 paper/dataset/repo 分别统计候选数量。
- 将 gap_report 放入 RetrievalRun 或新增 summary endpoint。

禁止：

- 不要吞掉 adapter 错误。
- 不要把 `manual_fallback` 当作真实检索成功。

### 5.3 `ranker.py`

增强点：

- dataset score 加入：
  - title/object match。
  - task match。
  - license/access。
  - source reliability。
  - public/download hint。
- repo score 加入：
  - task/method/object match。
  - stars。
  - recency。
  - language/framework。
  - reproducibility hints。

禁止：

- 不要只按 stars。
- 不要只按 source。

## 6. API 与前端接线

如果已有 retrieval API，优先扩展，不另起一套。

目标端点：

```text
POST /api/v1/projects/{project_id}/retrieval/search
GET  /api/v1/projects/{project_id}/retrieval/summary
POST /api/v1/projects/{project_id}/retrieval/import
```

前端普通用户界面要求：

- `让 AI 查证据` 必须触发真实 retrieval/search。
- 显示三类结果：
  - 论文候选。
  - 数据集候选。
  - GitHub 工程候选。
- 每类至少显示：
  - 标题。
  - 来源。
  - 相关性/质量提示。
  - warning。
  - `加入证据` 或 `加入文献库`。
- 如果没有 dataset/repo，显示：
  - 搜索过哪些 query。
  - 哪些 source 成功/失败。
  - 下一步建议，而不是只说“没有”。
- 如果 retry 执行过，显示：
  - 第一轮为什么不足。
  - 第二轮补搜用了哪些 query。
  - 第二轮有没有新增候选。

开发者窗口显示：

- query plan。
- source_results。
- raw candidate count。
- gap report。
- retry plan。
- candidate import response。

普通用户界面不显示：

- RAG Eval 指标。
- Playwright。
- Session 标签。
- raw request/response。
- AutoResearchClaw 大段术语。

## 7. 测试要求

### 7.1 后端测试

新增：

```text
apps/api/tests/test_session61_retrieval_enhancement.py
```

最低测试：

0. S60 P1 修复后，本地 RAG 测试仍通过。
1. `基于三维成像的损伤智能检测` 能生成 paper/dataset/repo 三类 query。
2. query 中包含至少一个英文三维/损伤相关 query。
3. dataset query 包含 dataset/benchmark/public 之一。
4. repo query 包含 github/pytorch/implementation/baseline 之一。
5. source failure 与 no_result 能区分。
6. dataset enhancer 能输出 `needs_manual_check`。
7. repo enhancer 能识别 stale/no_license/low_star。
8. gap report 不把 source_failed 当作 no_result。
9. retry planner 在 dataset 为空时能生成第二轮 dataset query。
10. candidate action 导入 paper 时返回真实 paper_id 或 evidence_id。

### 7.2 前端 Playwright

新增：

```text
apps/web-react/e2e/test_session61_retrieval_enhancement.py
```

最低测试：

1. 输入题目并开始分析。
2. 点击 `让 AI 查证据`。
3. 页面出现检索中状态。
4. 页面出现 paper/dataset/repo 三类区域。
5. 至少显示 source_results 或缺口说明。
6. dataset/repo 没结果时显示 query 和原因。
7. 开发者窗口能查看 query plan。
8. 候选可导入证据区或文献 RAG 库。
9. 候选导入后页面显示真实后端 id。
10. 补搜后页面显示 retry query 与新增结果或缺口说明。

## 8. 真实点击验收

执行者必须用真实浏览器测试这个题目：

```text
基于三维成像的损伤智能检测
```

点击链路：

1. 打开 `http://127.0.0.1:18183`。
2. 输入题目。
3. 点击 `开始分析`。
4. 点击 `让 AI 查证据`。
5. 查看三类候选。
6. 打开开发者窗口查看 query plan。
7. 选择一个候选加入证据区或文献 RAG 库。

必须保存：

```text
Plan/reports/session61-retrieval-flow.json
Plan/reports/session61-retrieval-flow.png
apps/web-react/e2e/screenshots/session61/s61_retrieval_candidates.png
apps/web-react/e2e/screenshots/session61/s61_gap_report.png
apps/web-react/e2e/screenshots/session61/s61_query_plan_dev.png
```

截图分析必须回答：

- 用户是否能看到系统搜了哪些资源？
- 用户是否能区分论文、数据集、工程？
- 数据集/工程为空时，原因是否清楚？
- 是否还能继续补搜，而不是直接终止？
- 是否存在假成功或固定 mock？

## 9. 验收报告

完成后输出：

```text
Plan/reports/Session_61_RetrievalEnhancement_ProjectDatasetDiscovery_验收报告.md
```

报告必须包含：

- S60 已验收结论，以及 Ponytail P1 是否修复。
- 新增模块清单。
- AutoResearchClaw / 科研 Skill 参考如何小型化落地。
- query plan 增强前后对比。
- 对截图题目的真实检索结果。
- dataset/repo 是否有候选；如果没有，失败原因。
- retry planner 是否触发；触发后新增了什么 query。
- 候选导入是否真实写入后端，返回了什么 id。
- 自动测试结果。
- 真实点击截图分析。

## 10. 通过标准

可以通过：

- S60 Ponytail P1 已修复，且 S60 本地 RAG 测试仍通过。
- 检索能生成 paper/dataset/repo 三类 query。
- GitHub 和 HuggingFace 不是摆设，有真实调用或明确失败原因。
- 前端能展示候选或缺口报告。
- 用户能把候选导入证据区或文献库。
- 导入后能看到真实后端 id。
- dataset/repo 为空时能展示 gap_report 和 retry query。
- 对“三维成像损伤智能检测”这类题目，不再只给一句“不建议”，而能展示补搜过程和缺口。
- 有自动测试和真实点击截图。

不通过：

- 跳过 S60 Ponytail P1 根因修复。
- 只改前端文案，没有后端 query/retrieval 变化。
- 只搜论文，不搜数据集/项目。
- 数据集/项目搜不到但不展示原因。
- 网络失败被当成无资源。
- 候选不能导入任何工作区。
- 导入只是前端 useState 假动作。
- 没有截图和真实点击分析。
