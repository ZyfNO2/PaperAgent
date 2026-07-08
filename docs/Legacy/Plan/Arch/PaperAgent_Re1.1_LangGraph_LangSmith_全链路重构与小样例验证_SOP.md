# PaperAgent Re1.1 LangGraph/LangSmith 全链路重构与小样例验证 SOP

> 版本定位：从 Re10/FIX 系列进入 `1.1`。`0.x` 的目标是把检索污染和候选审计跑通；`1.1` 的目标是把整套“输入题目 -> 题目理解 -> 检索计划 -> 多源检索 -> 证据审计 -> baseline/parallel/dataset/repo 归因 -> 工作建议 -> 人工可介入节点”统一迁入 LangGraph 控制平面，并用 LangSmith/本地 Trace 记录每一步。

## 0. 本轮结论

Re1.1 不是只重构检索。

本轮必须完成“全链路 Graph 化骨架”，即所有主流程阶段都要成为 LangGraph node，并共享同一个 `ResearchState`。允许部分 node 在第一轮内部调用旧实现，但必须通过 adapter 明确边界，不能继续让旧脚本自行串流程。

执行顺序上，优先验证检索和证据审计，因为 Re10 FIX-4 的最大遗留问题仍然在这里：

- `paper` 候选已经明显改善，但 `dataset/repo = 0`，说明链路没有把论文中的 dataset/repo 关系继续追出来。
- `VOAPI GPT-5.4-medium` 被当作常规模型使用，导致每 case 150-282s，必须改成最终质检模型。
- `.env` 已写入 DeepSeek / StepFun / VOAPI 策略，但当前代码仍主要读取 `LLM_PROVIDER`，且无 StepFun adapter。
- FIX-4 报告声称有 `test_fix4_loop2.py`，但 `apps/api/tests` 下未找到 `*fix4*` 测试文件，必须补齐可追溯测试。

## 1. 已完成的环境与安全检查

本地 `.env` 已补充以下配置类别，不在报告、日志、Trace、截图中输出真实密钥：

- DeepSeek：作为小规模测试与日常快速 JSON 调用的 primary provider。
- StepFun：作为低成本执行/连通性/压力测试 provider，禁止用于复杂推理结论。
- VOAPI `gpt-5.4-medium`：仅作为最终高质量复核 provider。
- MiniMax：默认禁用，后续不得自动 fallback。
- LangGraph/LangSmith：默认关闭，通过 feature flag 分阶段启用。

Git 泄露检查结果：

- `.env` 与 `.env.local` 命中 `.gitignore`。
- `git ls-files .env .env.local` 未返回已跟踪文件。
- `git status --short .env .env.local .env.example` 未显示 `.env` 被 staged/tracked。

执行者必须保持：

- `.env.example` 只能写 placeholder，不得写真实 key。
- 任意测试日志不得打印 `API_KEY`、`Authorization`、`Bearer`、完整 base64/token。
- 每轮报告必须附 `git check-ignore -v .env .env.local` 与 `git ls-files .env .env.local` 的结果摘要。

## 2. 当前代码审计要点

### 2.1 LLM 接线问题

位置：

- `apps/api/app/services/llm.py`

发现：

- 当前 public API 只支持 `minimax / deepseek / voapi`。
- `chat_json()` 和 `chat_json_array()` 默认仍从 `LLM_PROVIDER` 读取 provider。
- 代码中没有 StepFun provider。
- `profile` / `fallback_profiles` 参数存在，但没有真正形成 provider policy。
- MiniMax 仍是代码默认值，一旦 `.env` 漏配可能回落到 MiniMax。

必须修：

- 新建 `apps/api/app/services/llm_router.py`。
- 将 provider 分为 `fast_json`、`execution`、`premium_review`、`disabled` 四类。
- `LLM_PROVIDER=deepseek` 作为旧入口兼容，不再允许默认 MiniMax。
- `MINIMAX_DISABLED=true` 时，任何隐式 MiniMax 调用必须抛出清晰错误。
- StepFun adapter 独立实现，不确认 API 兼容前，不得强塞进 OpenAI-compatible 函数。

该模块不应该：

- 在异常中打印 key。
- 自动从 DeepSeek fallback 到 VOAPI。
- 把 VOAPI 用在普通 loop。
- 在 provider 失败时静默走 heuristic 并标记为 pass。

### 2.2 FIX-4 迁移问题

FIX-4 可保留：

- 删除具体 repo 黑名单的方向是对的。
- `topic_axis_match` 写入 trace 的方向是对的。
- 小样例 loop + `--parallel 1` 的验收方式是对的。

FIX-4 不能直接继承为最终结论：

- `has_single_strong` 可能过宽。一个单轴强命中可以进入候选，但不能直接作为毕业方向通过依据。
- 所有候选仍主要归为 `paper`，没有稳定产出 dataset/repo。
- `dataset/repo` 不应先泛化 GitHub 搜；下一阶段要优先从可信论文的 abstract、fulltext、metadata、official code/data URL 中抽取。
- 报告中的 `test_fix4_loop2.py` 未在 `apps/api/tests` 下发现，必须补测试文件或解释真实位置。

## 3. 参考源要求

执行者必须阅读以下参考后再动主链路，不得只凭想象改：

- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\RESEARCHCLAW_AGENTS.md`
- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\prompts.default.yaml`
- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw`
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills\academic-pipeline`
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills\deep-research`
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills\agents`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-4_完工报告.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-4_静态审计报告.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-4_小样例3审计.md`

参考目的：

- 学习多轮检索如何从 broad search 转向 seed expansion。
- 学习 agent 职责分层，而不是继续把 planner、retriever、verifier、synthesizer 混在一个脚本里。
- 学习 tool call / function calling 的输入输出约束。
- 学习失败回路：错误候选要变成下一轮搜索的反例，而不是被静默丢掉。

## 4. 目标流程

最终主链路必须覆盖：

```mermaid
flowchart LR
  A["Topic Intake"] --> B["Topic Parser"]
  B --> C["Search Planner"]
  C --> D["Paper Retriever"]
  D --> E["Paper Verifier"]
  E --> F["Dataset/Repo Extractor From Papers"]
  F --> G["Targeted Repair Search"]
  G --> H["Evidence Auditor"]
  H --> I["Baseline/Parallel Classifier"]
  I --> J["Work Package Brainstorm"]
  J --> K["Low-Bar Review"]
  K --> L["HumanGate Placeholder"]
  L --> M["Final Recommendation"]
```

Re1.1 必须让以上节点全部进入 LangGraph。  
允许某些 node 先调用旧函数，但必须包在明确 adapter 里，并在 Trace 中标出 `legacy_adapter=true`。

## 5. LangGraph 状态设计

创建：

- `apps/api/app/services/agents/graph/state.py`
- `apps/api/app/services/agents/graph/research_graph.py`
- `apps/api/app/services/agents/graph/nodes/`

`ResearchState` 至少包含：

```python
class ResearchState(TypedDict, total=False):
    case_id: str
    topic: str
    user_constraints: dict[str, Any]
    topic_atoms: dict[str, Any]
    search_plan: dict[str, Any]
    raw_results: dict[str, list[dict[str, Any]]]
    paper_candidates: list[dict[str, Any]]
    verified_papers: list[dict[str, Any]]
    dataset_candidates: list[dict[str, Any]]
    repo_candidates: list[dict[str, Any]]
    baseline_candidates: list[dict[str, Any]]
    parallel_candidates: list[dict[str, Any]]
    evidence_audit: dict[str, Any]
    work_packages: list[dict[str, Any]]
    low_bar_review: dict[str, Any]
    human_gate: dict[str, Any]
    trace_events: list[dict[str, Any]]
    provider_profile: str
    errors: list[dict[str, Any]]
```

规则：

- node 只能读写自己负责的字段。
- node 输出必须是 dict patch，不得原地修改全局对象后返回空。
- 每个 node 必须写 `trace_events`，至少包含 `node`、`started_at`、`ended_at`、`input_summary`、`output_summary`、`provider`、`tool_calls`、`errors`。
- `case_id` 必须作为 LangGraph `thread_id`，以便恢复。

## 6. LangGraph 编排要求

使用当前 LangGraph Python 文档中的模式：

- `StateGraph(ResearchState)`
- `START` / `END`
- `graph.compile(checkpointer=...)`
- 本轮本地先用 `InMemorySaver` 或 `MemorySaver`。
- 后续再升级 SQLite/Postgres checkpointer。

Human-in-the-loop 预留：

- 使用 `langgraph.types.interrupt` 设计 `human_gate_node`。
- Re1.1 默认不开启人工等待，`HUMAN_GATE_ENABLED=false` 时直接 pass-through。
- 节点要保留 schema：用户可确认/删除候选/指定 baseline/补充约束。

该模块不应该：

- 在 Re1.1 直接重做 UI。
- 把 HumanGate 写成永远阻塞。
- 把所有旧脚本塞进一个 `run_all_node`。
- 无 Trace 地调用 LLM 或外部工具。

## 7. LLM Provider Router

创建：

- `apps/api/app/services/llm_router.py`
- `apps/api/tests/test_llm_router_re11.py`

Provider Profile：

| Profile | 默认 provider | 用途 | 禁止 |
| --- | --- | --- | --- |
| `fast_json` | DeepSeek | topic parse、planner、verifier JSON | 禁止长推理 |
| `execution` | StepFun | 连通性、低成本小压测、简单执行 | 禁止最终判断 |
| `premium_review` | VOAPI GPT-5.4-medium | 最终抽样复核 | 禁止 loop 默认调用 |
| `disabled` | none | MiniMax 等停用供应商 | 禁止隐式 fallback |

StepFun 接入要求：

- 新建 `_chat_stepfun()`，不要复用 OpenAI-compatible adapter，除非实际连通测试证明接口兼容。
- 支持最小 JSON 输出测试。
- 请求体和响应体要有 redaction。
- 若 StepFun 不支持 JSON mode，则在 router 层标记 `json_mode=false`，由调用方做严格 JSON 解析与重试。

DeepSeek 接入要求：

- 仅用 flash/快速模型跑小样例与日常测试。
- 不得自动 fallback 到 reasoner/pro，除非用户显式打开。
- 模型名必须集中在 env / provider config，不得散落硬编码。

VOAPI 接入要求：

- 仅在 `profile="premium_review"` 且 `ALLOW_PREMIUM_REVIEW=true` 时可用。
- 报告中必须统计 VOAPI 调用次数。
- 小样例 loop 和压力测试中 VOAPI 调用次数必须为 0。

## 8. Prompt 与 Tool Call 规范

所有 LLM prompt 必须集中放入：

- `apps/api/app/services/agents/prompts/re11_topic_parser.py`
- `apps/api/app/services/agents/prompts/re11_search_planner.py`
- `apps/api/app/services/agents/prompts/re11_paper_verifier.py`
- `apps/api/app/services/agents/prompts/re11_dataset_repo_extractor.py`
- `apps/api/app/services/agents/prompts/re11_work_package.py`

### 8.1 Search Planner Prompt 要求

必须要求 LLM 输出：

- `topic_atoms`: method/object/task/scenario/domain/dataset_terms/baseline_terms/avoid_terms
- `search_rounds`: broad / focused / seed_expansion / repair
- `tool_calls`: 每个 tool call 必须有 `tool_name`、`query`、`why_call`、`expected_evidence_type`、`stop_condition`
- `negative_feedback`: 上一轮错因和本轮避免策略

Tool call 规范：

| Tool | When to call | Why call | How call |
| --- | --- | --- | --- |
| `search_openalex` | 需要学术论文、综述、领域关键词 | 找可信论文种子 | query 包含 method/object/task，避免只搜 generic method |
| `search_arxiv` | 计算机/AI/工程新论文 | 找近年方法和 baseline | query 使用英文领域词 + task |
| `search_crossref` | arXiv 不足或工程/材料/医学论文 | 补 DOI 与期刊论文 | query 不带 `[Fallback]` 等控制词 |
| `search_github` | 已有论文标题、方法名、dataset 名 | 找 official implementation | 优先 `"<paper title>" github`，禁止先用泛词搜 repo |
| `web_search` | 数据集/repo 缺口，或论文 metadata 不足 | 补网页证据 | 必须记录来源和候选类型 |

### 8.2 Dataset/Repo Extractor Prompt 要求

必须从已验证论文中抽：

- dataset name
- benchmark name
- official code URL
- project page URL
- supplementary material URL
- paper mentioned repo
- paper used baseline

如果论文没有给出 dataset/repo，输出 `not_found_in_paper`，不得编造。

## 9. Dataset/Repo 策略调整

Re1.1 开始，dataset/repo 不再优先从泛化搜索获得。

优先级：

1. 从 verified paper 的 metadata / abstract / URL / DOI page / project page 中抽取。
2. 用论文标题反查 official repo。
3. 用论文中出现的 dataset 名称反查 dataset page。
4. 最后才允许 topic-level broad search。

该模块不应该：

- 用固定白名单直接注入 dataset。
- 因为题目是 YOLO 就塞 COCO/VOC。
- 因为题目是 SLAM 就塞 ORB-SLAM3。
- 因为没有 URL 就 fail；应进入 URL repair。
- 把空 URL 当作证据错误；只要论文真实，可标记 `url_missing_needs_repair`。

## 10. 证据审计与分类

创建：

- `apps/api/app/services/agents/graph/nodes/evidence_auditor.py`
- `apps/api/app/services/agents/graph/nodes/baseline_classifier.py`

分类规则：

- `baseline`: 论文或 repo 明确提供可复现基础方法/主干/benchmark 起点。
- `parallel`: 同领域、同任务或相近对象上做改进的论文，可学习模块组合。
- `dataset`: 数据集本体、benchmark、数据说明论文。
- `repo`: official implementation、可运行工程、复现实验工程。
- `survey`: 综述，不作为 baseline，但可用于扩展关键词。

显示层不再显示抽象分数。改显示：

- 命中关键词
- 相关关键词
- 无关关键词
- 来源类型
- 与题目的关系
- 是否需要 URL repair
- 是否需要人工确认

## 11. 工作建议生成

创建：

- `apps/api/app/services/agents/graph/nodes/work_package_brainstorm.py`

必须基于已分类证据生成，不得硬编码：

- 不能永远输出“复现 baseline + 加注意力机制”。
- 工作包必须引用来源论文/parallel 论文/数据集/repo。
- 每个工作包要说明：研究问题、baseline、改进模块来源、数据来源、实验指标、风险、预计工作量。

如果证据不足：

- 输出“缺什么证据”，而不是编造工作包。
- 给出下一轮 repair search 的 tool calls。

## 12. API 与 UI 兼容

Re1.1 不要求重做前端，但后端 API 必须能返回 Graph 状态。

新增或改造 endpoint：

- `POST /api/v1/research/analyze`
- `GET /api/v1/research/{case_id}/state`
- `GET /api/v1/research/{case_id}/trace`
- `POST /api/v1/research/{case_id}/resume`

要求：

- 旧接口可以保留，但必须通过 Graph service。
- 前端仍可只展示简单结果。
- 开发者模式可展示 trace events。
- 普通模式只展示低密度状态：正在搜什么、搜到多少、需要确认什么。

## 13. LangSmith Trace

`.env` 默认：

- `LANGSMITH_TRACING=false`

执行者如果配置 LangSmith key，可以打开：

- `LANGSMITH_TRACING=true`
- `LANGSMITH_API_KEY=<placeholder only in docs>`
- `LANGSMITH_PROJECT=paperagent-re11`

无 LangSmith 时必须写本地 trace：

- `tmp_re11_eval/<run_id>/traces/<case_id>.json`

Trace 必须能回答：

- 每轮搜了哪些 query。
- 调用了哪些 tool。
- 哪些候选被接收/降级/隔离。
- 哪些错误候选影响了下一轮 query。
- 哪个 provider 被调用，耗时多少。
- 是否调用了 VOAPI。

## 14. 小样例 Loop 设计

禁止一上来跑 Balanced40。

### Loop 0：静态安全

必须通过：

- `.env` ignored 且未 tracked。
- `rg -n "sk-|Bearer |Authorization|DEEPSEEK_API_KEY=.*[A-Za-z0-9]" Plan apps` 不得命中真实 key。
- `apps/api/tests` 下存在 Re1.1 测试文件。
- 无 `generic_repos = {...}`、无候选标题黑名单、无 `if "YOLO" in topic` 直接注入候选。

### Loop 1：Provider 连通性

只跑 2 个最小请求：

- DeepSeek `fast_json`: 返回 `{"ok": true, "provider": "deepseek"}`。
- StepFun `execution`: 返回 `{"ok": true, "provider": "stepfun"}` 或明确记录接口不兼容原因。

禁止：

- 打印 key。
- 调 VOAPI。
- 调 MiniMax。

### Loop 2：Graph Smoke

使用 mock retrieval 跑 1 个 case。

通过条件：

- 所有主节点都进入 LangGraph。
- 每个 node 都写 trace。
- `case_id` 成为 `thread_id`。
- `human_gate_node` 在关闭状态下 pass-through。
- 输出包含 paper/dataset/repo/work_package 字段，即使为空也要有状态说明。

### Loop 3：真实小样例 3 个

题目：

1. `基于YOLOv5的钢铁表面缺陷检测研究`
2. `基于深度学习的视觉SLAM语义地图的研究`
3. `基于大语言模型的医学问答可信度评估方法研究`

通过条件：

- 每个 case 至少 3 篇相关 paper。
- 每个 case 的候选都显示命中关键词/无关关键词。
- 错误候选不得进入最终 `verified_papers`。
- 每个 case 必须尝试从 verified papers 抽 dataset/repo，并记录 `found` 或 `not_found_in_paper`。
- VOAPI 调用次数为 0。
- MiniMax 调用次数为 0。
- 平均每 case 低于 120s；超过则必须给出 provider/tool 耗时拆解。

### Loop 4：真实小样例 5 个

从 `PaperAgent_工科学位论文爬取测试集_100篇.md` 中抽 5 个跨领域题目。

必须覆盖：

- CV/检测
- 3D/SLAM/重建
- NLP/LLM
- 传统工程/材料/结构
- 遥感/农业/医疗任选一个

通过条件：

- 4/5 case 能产出可进入下一阶段的 paper evidence。
- 3/5 case 能从论文或论文反查中找到 dataset/repo 线索。
- 任何失败 case 都必须给出 repair query，而不是只写“不建议”。

### Loop 5：小压力测试

只用 DeepSeek/StepFun。

要求：

- 3 case 连续跑 3 次。
- 检查缓存、耗时、provider fallback、trace 完整性。
- 不做全量。

## 15. 禁止事项

- 禁止把 Re1.1 做成只重构检索函数。
- 禁止绕过 LangGraph 直接跑旧 runner 后写报告。
- 禁止全量 Balanced40 先行。
- 禁止候选标题硬编码黑名单。
- 禁止领域白名单硬塞 dataset/repo。
- 禁止无 Trace 的 LLM 调用。
- 禁止普通测试调用 VOAPI。
- 禁止 MiniMax 隐式 fallback。
- 禁止把空 URL 直接判 fail。
- 禁止报告只给总 pass，不给失败样例 trace。
- 禁止把评分作为主要展示；必须展示关键词命中和证据关系。

## 16. 交付物

代码：

- `apps/api/app/services/llm_router.py`
- `apps/api/app/services/agents/graph/state.py`
- `apps/api/app/services/agents/graph/research_graph.py`
- `apps/api/app/services/agents/graph/nodes/*.py`
- `apps/api/app/services/agents/prompts/re11_*.py`
- `apps/api/tests/test_llm_router_re11.py`
- `apps/api/tests/test_re11_research_graph_smoke.py`
- `apps/api/tests/test_re11_no_secret_leak.py`
- `apps/api/tests/test_re11_dataset_repo_from_papers.py`

报告：

- `Plan/PaperAgent_Re1.1_环境与密钥安全检查.md`
- `Plan/PaperAgent_Re1.1_FIX-4迁移审计.md`
- `Plan/PaperAgent_Re1.1_Loop0_静态审计.md`
- `Plan/PaperAgent_Re1.1_Loop1_Provider连通性.md`
- `Plan/PaperAgent_Re1.1_Loop2_GraphSmoke.md`
- `Plan/PaperAgent_Re1.1_Loop3_真实小样例3.md`
- `Plan/PaperAgent_Re1.1_Loop4_跨领域小样例5.md`
- `Plan/PaperAgent_Re1.1_完工报告.md`

## 17. 最终验收条件

只有同时满足以下条件，Re1.1 才能通过：

- LangGraph 主链路覆盖所有阶段，不是单点检索重构。
- DeepSeek 和 StepFun 至少完成最小连通性测试，真实 key 不出现在日志。
- VOAPI 在普通 loop 中调用次数为 0。
- MiniMax 在普通 loop 中调用次数为 0。
- 3 个真实小样例全部产出 trace、paper evidence、dataset/repo 抽取尝试、work package 或 repair plan。
- 5 个跨领域小样例至少 4 个能进入下一阶段。
- 每个 node 的输入输出可从 trace 还原。
- 失败 case 有明确错因和下一轮 query，不允许静默 heuristic 接管。
- `.env` 未被 Git 跟踪。

## 18. 撞墙停止条件

执行者只有在以下情况才允许停止并上报：

- DeepSeek 或 StepFun 官方接口连续 3 次最小连通性失败，且返回不是代码错误，而是认证/额度/服务端不可用。
- LangGraph 依赖无法安装或版本冲突，且提供完整错误日志。
- 参考目录不可读，导致无法完成对照设计。
- 同一个 3-case loop 连续 3 轮仍有结构性失败，并已附 trace、候选、query、provider 耗时、失败节点。

不允许因为以下原因停止：

- 单个 case 结果不好。
- dataset/repo 一轮没找到。
- 旧脚本更方便。
- VOAPI 更稳。
- UI 还没接上。

## 19. 文档同步

本次属于架构、状态管理、LLM provider、Trace、API 行为的大调整。执行完成后必须询问是否同步更新 `/docs`，建议更新大纲：

- `docs/architecture/langgraph_research_flow.md`
- `docs/operations/provider_policy.md`
- `docs/operations/trace_and_langsmith.md`
- `docs/testing/re11_small_loop_validation.md`

