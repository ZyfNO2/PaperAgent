# PaperAgent Re1.1 执行者 AI 自查方案

> 配套文件：`PaperAgent_Re1.1_LangGraph_LangSmith_全链路重构与小样例验证_SOP.md`

## 0. 自查目标

执行者 AI 每完成一个 Loop，都必须先自查，再写完工报告。  
本方案的目的不是让执行者解释“我做了什么”，而是逼它回答：

- 有没有真的接入 LangGraph 主链路？
- 有没有真实调用目标 provider？
- 有没有绕过旧问题，只是在报告里说通过？
- 有没有把错误候选、空证据、无 dataset/repo 的结果包装成可用？
- 有没有泄露密钥？
- 有没有用 VOAPI / MiniMax 逃避低成本测试要求？

没有完成自查，不允许进入下一 Loop。

## 1. 每轮必须先回答的 10 个问题

执行者在每份报告开头必须写：

| 编号 | 自查问题 | 必须给出的证据 |
| --- | --- | --- |
| Q1 | 本轮是否改动了主链路？ | 文件路径 + 函数/类名 |
| Q2 | 是否所有阶段都通过 LangGraph node 进入？ | graph node 列表 |
| Q3 | 是否还有旧 runner 绕过 graph？ | 调用链说明 |
| Q4 | 是否真实调用了 provider router？ | provider profile 统计 |
| Q5 | 是否调用了 VOAPI？ | 调用次数，普通 loop 必须为 0 |
| Q6 | 是否调用了 MiniMax？ | 调用次数，必须为 0 |
| Q7 | 是否有 `.env` 或密钥进入 Git/日志？ | git 检查摘要 + redaction 检查 |
| Q8 | dataset/repo 是从哪里来的？ | paper-derived / targeted repair / broad search |
| Q9 | 失败 case 是否给出下一轮 repair query？ | case_id + repair query |
| Q10 | 有没有把“不确定”写成“通过”？ | weak/fail 样例说明 |

## 2. 禁止通过的情况

只要出现以下任一情况，本轮必须判定为失败：

- 只改了检索函数，没有把阶段接入 LangGraph。
- 新增了一个 `run_all()` 或 `legacy_pipeline_node()`，把所有旧流程塞进一个 node。
- 报告里说接入 StepFun，但代码中没有 StepFun adapter。
- `.env` 真实 key 出现在报告、Trace、截图、测试输出中。
- 普通 loop 调用了 VOAPI。
- MiniMax 被隐式 fallback。
- dataset/repo 候选没有来源说明。
- 所有 dataset/repo 都来自固定白名单或硬编码注入。
- 错误候选被标记为 verified，但没有降级、隔离或解释。
- 失败 case 只写“不建议”，没有 repair search plan。
- 只给总通过率，不给逐 case trace。

## 3. 代码层自查

执行者必须在报告中列出以下检查结果。

### 3.1 LangGraph 接入检查

必须确认存在并使用：

- `apps/api/app/services/agents/graph/state.py`
- `apps/api/app/services/agents/graph/research_graph.py`
- `apps/api/app/services/agents/graph/nodes/`

必须列出 graph node：

```text
topic_intake_node
topic_parser_node
search_planner_node
paper_retriever_node
paper_verifier_node
dataset_repo_extractor_node
targeted_repair_search_node
evidence_auditor_node
baseline_classifier_node
work_package_brainstorm_node
low_bar_review_node
human_gate_node
final_recommendation_node
```

允许 node 内部暂时调用旧函数，但必须满足：

- node 名称清晰。
- trace 写明 `legacy_adapter=true`。
- 输入输出字段符合 `ResearchState`。
- 不能把多个阶段合并成一个黑箱 node。

### 3.2 Provider Router 检查

必须确认：

- `llm_router.py` 存在。
- `fast_json` 默认 DeepSeek。
- `execution` 默认 StepFun。
- `premium_review` 默认 VOAPI。
- `MiniMax` 默认 disabled。

必须检查：

```text
LLM_PROVIDER=deepseek
LLM_FAST_PROVIDER=deepseek
LLM_EXECUTION_PROVIDER=stepfun
LLM_PREMIUM_PROVIDER=voapi
MINIMAX_DISABLED=true
PAPERAGENT_ALLOW_MINIMAX=false
VOAPI_USAGE_POLICY=premium_review_only
```

报告只能写 key 是否存在，不得写真实值。

### 3.3 硬编码检查

必须运行或等价检查：

```powershell
rg -n "generic_repos|STRONG_NOISE_TOKENS|ORB_SLAM3|open_vins|awesome-visual-slam|if .*YOLO|if .*SLAM|if .*检测" apps/api/app apps/api/scripts
```

允许命中：

- 历史报告。
- mock fixture。
- 测试用例中作为反例出现的字符串。

不允许命中：

- 主链路过滤器。
- 候选注入逻辑。
- 领域特判通过逻辑。

## 4. Trace 自查

每个 case 必须有 trace 文件：

```text
tmp_re11_eval/<run_id>/traces/<case_id>.json
```

Trace 必须包含：

- `case_id`
- `topic`
- `thread_id`
- `node_events`
- `tool_calls`
- `provider_calls`
- `accepted_candidates`
- `rejected_candidates`
- `quarantined_candidates`
- `repair_queries`
- `dataset_repo_extraction`
- `final_status`

每个 node event 必须包含：

- `node`
- `started_at`
- `ended_at`
- `duration_ms`
- `provider`
- `input_summary`
- `output_summary`
- `errors`

如果 trace 缺任一关键字段，本轮不能通过。

## 5. 结果质量自查

> 本节是 Re1.1 自查重点。执行者不能只证明“流程跑完了”，必须证明生成的论文、repo、dataset 候选是可追溯、可解释、可降级、可修复的。

### 5.1 Paper 候选

每个 verified paper 必须说明：

- 为什么相关。
- 命中了哪些 method/object/task/scenario 词。
- 哪些词没命中。
- 是否有 URL / DOI / arXiv / OpenAlex ID。
- 是否存在 metadata mismatch。

不得只显示：

```text
score 0.10
```

#### 5.1.1 Paper 候选逐条自查表

每个进入 `verified_papers / baseline_candidates / parallel_candidates` 的论文，都必须生成逐条自查记录：

| 字段 | 要求 |
| --- | --- |
| `title` | 必须是真实论文标题，不得是搜索 query、网页标题碎片、表格标题 |
| `url` | DOI / arXiv / OpenAlex / publisher URL 至少一个；没有则标 `url_missing_needs_repair` |
| `year` | 尽量给出；缺失不得直接 fail |
| `source` | openalex / arxiv / crossref / web / paper_reference |
| `role` | baseline / parallel / dataset_paper / survey / background |
| `matched_topic_axes` | method/object/task/scenario 至少说明命中哪些 |
| `unmatched_topic_axes` | 必须说明没命中哪些 |
| `why_relevant` | 1-2 句说明与题目的关系 |
| `why_not_noise` | 说明为什么不是误搜、拼接 metadata、领域漂移 |
| `next_use` | 用于 baseline、平行方案、数据集线索、关键词拓展，还是仅候选 |

不允许进入 verified 的情况：

- title 与 abstract 明显不是同一篇。
- title 是搜索 query 或 prompt 残片。
- 只命中 `deep learning`、`AI`、`survey` 等泛词。
- 与题目对象完全无关，例如钢材裂缝题混入问卷编码论文。
- 没有任何 method/object/task/scenario 解释。

允许保留但必须降级的情况：

- 论文真实，但只提供背景知识。
- 论文真实，但只有方法相近，对象不同。
- 论文真实，但 URL 暂缺。
- 论文真实，但只能作为关键词拓展。

#### 5.1.2 Paper 角色判定

执行者必须区分：

| 角色 | 判定标准 | 进入下一步方式 |
| --- | --- | --- |
| `baseline` | 提供可复现实验起点、主干模型、标准方法或 benchmark | 可生成工作包 |
| `parallel` | 同领域类似题目上的改进方法 | 用于找模块和创新点 |
| `dataset_paper` | 介绍数据集/benchmark | 用于 dataset 抽取 |
| `survey` | 综述、系统性回顾 | 用于扩关键词，不直接当工作包 |
| `background` | 领域背景、材料/结构/医学机理 | 可保留候选，不进入 baseline |
| `noise` | 题目关系不足或 metadata 错配 | 隔离，不得参与建议 |

如果不能确定角色，必须标：

```text
role=needs_human_or_llm_audit
```

不得强行归为 baseline。

### 5.2 Dataset/Repo 候选

每个 dataset/repo 必须标注来源：

| 来源 | 是否允许 | 说明 |
| --- | --- | --- |
| `paper_abstract` | 允许 | 从 verified paper 摘要抽取 |
| `paper_fulltext` | 允许 | 从论文正文或 PDF 抽取 |
| `paper_metadata_url` | 允许 | 从 official URL / project page 抽取 |
| `paper_title_targeted_search` | 允许 | 用论文标题反查 |
| `dataset_name_targeted_search` | 允许 | 用论文提到的数据集名反查 |
| `topic_broad_search` | 允许但降级 | 只能作为补充候选 |
| `hardcoded_whitelist` | 不允许 | 不得直接注入 |

如果 dataset/repo 没找到，必须写：

- 哪些论文中查过。
- 用了哪些 repair query。
- 为什么暂时没找到。
- 下一轮应该搜什么。

### 5.3 Repo 候选专项自查

每个进入 `repo_candidates` 的 repo 必须生成自查记录：

| 字段 | 要求 |
| --- | --- |
| `repo_name` | owner/repo 格式 |
| `url` | 必须是 GitHub/GitLab/官方代码页 URL |
| `source` | paper_official_link / paper_title_search / method_name_search / broad_search |
| `linked_paper` | 如果来自论文，必须写论文标题 |
| `is_official` | true / false / unknown |
| `relevance_axes` | 命中的 method/object/task/scenario |
| `readme_evidence` | README 或描述中支持相关性的短摘要 |
| `reproducibility_hint` | 有无 requirements、训练脚本、数据说明、模型权重 |
| `risk` | 空仓库、fork、无 license、与论文无关、只是一份列表等 |

Repo 不允许通过的情况：

- 只因为 stars 高就进入候选。
- 只因为 repo 名含 YOLO / SLAM / RAG 就进入候选。
- 非 SLAM 题目混入 ORB-SLAM 类通用 repo 且无对象/任务关系。
- repo 描述和题目无关，但被当作 baseline。
- 没有 URL。

Repo 可以保留但必须降级的情况：

- 非官方实现，但 README 明确复现某篇相关论文。
- 是工具库/框架库，只能作为实现基础，不是论文 baseline。
- 是 awesome/list 类仓库，只能用于扩展检索，不得作为可复现 baseline。

Repo 进入工作包前必须满足：

- 至少关联一篇 verified paper，或 README 明确说明任务/数据集/方法。
- 有可运行线索：安装、训练、推理、demo、notebook 任一即可。
- 标注复现风险。

### 5.4 Dataset 候选专项自查

每个进入 `dataset_candidates` 的 dataset 必须生成自查记录：

| 字段 | 要求 |
| --- | --- |
| `dataset_name` | 数据集真实名称 |
| `url` | 官方页、论文页、Kaggle/HuggingFace/Zenodo/GitHub 等 |
| `source` | paper_mentioned / dataset_paper / benchmark_page / targeted_search |
| `linked_paper` | 如果由论文抽取，写论文标题 |
| `task_fit` | detection / segmentation / classification / QA / forecasting 等 |
| `object_fit` | 钢材、混凝土、遥感作物、医学图像等 |
| `modality` | image / text / point cloud / time-series / multimodal |
| `availability` | public / restricted / unknown |
| `preprocess_need` | ready / needs_convert / needs_annotation_check / unknown |
| `risk` | 数据太小、标注不匹配、访问受限、任务不一致 |

Dataset 不允许通过的情况：

- 由领域白名单硬塞，但没有被当前题目论文或搜索结果提到。
- 只命中“dataset”泛词，没有真实名称。
- 任务不匹配，例如分类数据集被当检测数据集。
- 对象不匹配，例如钢材裂缝题混入无关医学数据。
- URL 和名称不一致。

Dataset 可以保留但必须降级的情况：

- 公开但任务不完全一致，可作为 proxy dataset。
- 论文提到但没有下载地址，需要 repair。
- 名称真实但标注格式未知。

Dataset 进入工作包前必须满足：

- task_fit 与题目任务一致，或明确标为 proxy。
- availability 不是 `unknown`，除非工作包明确写“先做数据可获得性验证”。
- 至少说明一个可评价指标，例如 mAP、IoU、F1、Accuracy、BLEU、ROUGE、MAE。

### 5.5 Paper-Repo-Dataset 关系网自查

Re1.1 不要求完整数据网可视化，但必须生成最小关系表。

每个 case 必须输出：

| paper | role | linked_repo | linked_dataset | relation_confidence | missing_links |
| --- | --- | --- | --- | --- | --- |

关系规则：

- baseline paper 如果有 official repo，优先展示。
- dataset paper 必须尝试链接 dataset。
- parallel paper 必须抽取其 baseline 和改进模块。
- repo 若来自 paper title search，必须反向标回 linked_paper。
- dataset 若来自 paper mention，必须反向标回 linked_paper。

不允许：

- repo/dataset 孤立出现但不说明来源。
- baseline 只是一篇论文标题，没有 repo/dataset/实验指标说明。
- 工作建议引用不存在于关系表中的证据。

### 5.6 候选池分层展示要求

候选不再只有 pass/fail。必须分层：

| 层级 | 含义 | UI/报告动作 |
| --- | --- | --- |
| `verified_primary` | 高相关、可直接用于下一步 | 放前面 |
| `verified_secondary` | 相关但角色较弱 | 放候选 |
| `needs_repair` | 真实但缺 URL/repo/dataset/细节 | 生成 repair query |
| `needs_audit` | 可能相关但需 LLM/人工再审 | 不进入工作包 |
| `quarantined_noise` | 错误/错配/漂移 | 隔离展示，不参与建议 |

每个 case 至少要展示：

- 前 5 个最可信 paper。
- 前 3 个可用 dataset 或 dataset 缺口。
- 前 3 个可用 repo 或 repo 缺口。
- 被隔离的典型噪声 1-3 个及隔离理由。

### 5.7 Work Package

每个工作包必须引用至少一个证据源：

- baseline paper/repo
- parallel paper
- dataset
- metric

如果缺 baseline，不允许输出“复现 baseline + 加注意力机制”这种模板话。  
必须输出“当前缺 baseline，建议先执行哪些 search query”。

## 6. 小样例自查

### Loop 2 Graph Smoke

必须确认：

- Graph 能从 START 到 END。
- HumanGate 关闭时 pass-through。
- 每个 node 都有 trace。
- 旧实现 adapter 明确标注。

### Loop 3 真实 3 样例

三个题目：

1. `基于YOLOv5的钢铁表面缺陷检测研究`
2. `基于深度学习的视觉SLAM语义地图的研究`
3. `基于大语言模型的医学问答可信度评估方法研究`

每个题目必须逐项自查：

- 相关 paper 数量。
- 错误候选数量。
- dataset/repo 抽取是否执行。
- 是否进入 repair search。
- 是否调用 VOAPI。
- 是否调用 MiniMax。
- 总耗时。

### Loop 4 跨领域 5 样例

必须至少覆盖：

- CV/检测
- 3D/SLAM/重建
- NLP/LLM
- 工程/材料/结构
- 遥感/农业/医疗

报告必须列出失败 case，不允许只写通过率。

## 7. 密钥与 Git 自查

每轮报告必须包含以下摘要：

```text
git check-ignore -v .env .env.local
git ls-files .env .env.local
git status --short .env .env.local .env.example
```

还必须做日志泄露检查：

```powershell
rg -n "sk-|Bearer |Authorization|DEEPSEEK_API_KEY=.*[A-Za-z0-9]|STEPFUN_API_KEY=.*[A-Za-z0-9]|VOAPI_API_KEY=.*[A-Za-z0-9]" Plan apps tmp_re11_eval
```

如果命中真实 key：

- 立即停止。
- 删除或重写泄露文件。
- 报告泄露位置。
- 不得继续执行测试。

## 8. 报告模板

每轮报告必须使用以下结构：

```markdown
# PaperAgent Re1.1 Loop X 报告

## 1. 本轮目标

## 2. 改动文件

## 3. Graph 接入情况

## 4. Provider 调用统计

| provider | profile | calls | avg_ms | purpose |
| --- | --- | --- | --- | --- |

## 5. Trace 完整性

## 6. Case 结果

| case_id | topic | paper_n | dataset_n | repo_n | repair_query_n | status |
| --- | --- | --- | --- | --- | --- | --- |

## 7. 失败与弱项

## 8. 自查 10 问

## 9. 密钥与 Git 检查

## 10. 是否允许进入下一 Loop
```

## 9. 进入下一 Loop 的硬性条件

执行者必须明确写：

```text
结论：允许 / 不允许进入下一 Loop
原因：
- ...
```

允许进入下一 Loop 的条件：

- 当前 Loop 的硬性测试全部通过。
- 无密钥泄露。
- 无 VOAPI 普通调用。
- 无 MiniMax 隐式调用。
- trace 完整。
- 失败 case 有 repair plan。
- 没有新增硬编码候选注入。

不满足任一条件，就必须继续本 Loop 修复。

## 10. 最终自查结论格式

完工报告最后必须写：

```markdown
## 最终自查结论

- LangGraph 全链路：通过 / 未通过
- Provider Router：通过 / 未通过
- DeepSeek 小样例：通过 / 未通过
- StepFun 连通性：通过 / 未通过
- VOAPI 日常禁用：通过 / 未通过
- MiniMax 禁用：通过 / 未通过
- Trace 完整性：通过 / 未通过
- Dataset/Repo 从论文抽取：通过 / 未通过
- Work Package 非模板化：通过 / 未通过
- 密钥安全：通过 / 未通过

是否进入下一阶段：是 / 否
```
