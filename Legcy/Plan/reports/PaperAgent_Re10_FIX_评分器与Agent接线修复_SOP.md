# PaperAgent_Re10 FIX：评分器与 Agent 接线修复 SOP

## 0. 本轮判定

Re10 暂不通过，不能进入 Re11。

当前 Re10 的主要问题不是“搜索 Agent 已经证明无效”，而是两类更基础的问题叠加：

1. **Agent 工具接线失败**：Trace 中出现 `missing client openalex_search`、`missing client github_search`，说明搜索动作没有真正调用到可用 adapter。
2. **评分/验收器误判**：`no_new_signal` 被直接映射为 `weak`，导致“没有新增候选、没有真实命中、没有 LLM 反思”的情况仍被报告为通过。

因此 Re10 FIX 的目标不是继续扩功能，而是先建立真实、可失败、可定位的验证链路。

## 1. 必须锁定的原问题

### 1.1 接线问题

涉及文件：

- `G:\PaperAgent\apps\api\scripts\run_balanced40_reflection_re10.py`
- `G:\PaperAgent\apps\api\app\services\agents\search_reflection_loop.py`

现象：

- runner 构造的 retrieval client key 是 `arxiv`、`openalex`、`github` 等。
- loop 内部通过 `TOOL_CLIENT_KEYS` 查找的是 `arxiv_search`、`openalex_search`、`github_search` 等。
- 结果是 `_execute_query()` 找不到函数，Trace 记录 `missing client xxx_search`。

必须修复：

- runner 返回的 `retrieval_clients` 必须包含 loop 实际查找的 key：
  - `arxiv_search`
  - `openalex_search`
  - `crossref_search`
  - `github_search`
  - `huggingface_search`
- 可以同时保留短 key，但长 key 必须存在。
- adapter wrapper 的参数签名必须统一为：

```python
async def adapter(query: str, top_k: int = 3) -> list[dict]:
    ...
```

该模块不应该：

- 靠修改 Trace 文本伪装成功。
- 把 `missing client` 当作 `no_new_signal`。
- 在 adapter 未接通时继续生成“弱通过”报告。

### 1.2 Stop Reason 问题

涉及文件：

- `G:\PaperAgent\apps\api\app\services\agents\search_reflection_loop.py`

现象：

- `_decide_stop()` 中，如果连续两轮 `accepted_n < 2` 就返回 `no_new_signal`。
- 但目前连续两轮失败的原因是工具没有接上，不是搜索空间没有新信号。

必须修复：

- 如果一轮或多轮 action 全部是 `status=error`，且 error 包含 `missing client`，必须返回：
  - `tooling_failure` 或 `blocked_tooling`
- `no_new_signal` 只能在满足以下条件时出现：
  - 至少有一个 adapter 成功执行；
  - 至少有一个 source 返回过明确的 `no_results` 或有效结果；
  - 失败原因不是接线、异常、JSON 解析失败、provider 未配置。

该模块不应该：

- 把工具错误归类为搜索无增量。
- 用 `accepted_n == 0` 自动判断方向不好。
- 在没有成功调用任何检索源时输出毕业选题结论。

### 1.3 评分器问题

涉及文件：

- `G:\PaperAgent\apps\api\scripts\validate_re10_reflection_search.py`

现象：

- `no_new_signal -> weak` 的映射过宽。
- repair gate 实际上永远通过。
- `missing client` 没有成为硬失败。
- `pass+weak` 被 stop reason 粉饰，没有检查真实 evidence。

必须修复：

- 任何 Trace 中出现 `missing client`，本次验证必须失败。
- `adapter_attempt_n > 0` 但 `adapter_success_n == 0`，必须失败。
- `llm_call_count == 0` 时不能自动通过；除非命令显式启用 `--allow-no-llm`，且报告标题必须标注“无 LLM 诊断模式，不作为 Re10 通过依据”。
- `query_repair_total == 0` 不能硬通过；如果测试样例包含坏 query 或占位符 query，必须触发 repair。
- `url_repair_total == 0` 不能硬通过；如果测试样例包含空 URL 或占位符 URL，必须触发 URL repair 或标记 `url_repair_pending`。
- `pass/weak/fail/blocked` 必须由 evidence 状态推导，不允许只由 `stop_reason` 推导。

建议状态映射：

| 状态 | 条件 |
| --- | --- |
| `pass` | 有真实 adapter 成功调用；有新增候选；论文/数据集/repo 或 baseline 至少覆盖核心需求；无关键工具错误 |
| `weak` | 有真实 adapter 成功调用；候选不足但保留了可信 seeds；问题可进入下一轮 |
| `blocked_tooling` | provider、adapter、client、JSON、网络配置导致链路无法判断 |
| `fail` | 工具正常运行但多源多轮仍不能形成基本候选 |

该模块不应该：

- 把 `no_new_signal` 直接算成 `weak`。
- 用 `8/8 PASS` 掩盖 `0 accepted / 0 new candidate / 0 LLM call`。
- 继续使用缺少 `status` 字段的 CSV 作为最终审计依据。

### 1.4 报告与统计问题

涉及文件：

- `G:\PaperAgent\Plan\PaperAgent_Re10_ReflectionLoop_统计.json`
- `G:\PaperAgent\Plan\PaperAgent_Re10_Balanced40_逐论文审计.csv`
- `G:\PaperAgent\Plan\PaperAgent_Re10_Balanced40_逐论文审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_完工报告.md`

必须修复：

- 统计文件必须在最终 retry 后重新生成，不允许 stale。
- CSV 必须增加以下列：
  - `re10_status`
  - `stop_reason`
  - `adapter_attempt_n`
  - `adapter_success_n`
  - `adapter_error_n`
  - `missing_client_n`
  - `new_candidates_n`
  - `accepted_candidates_n`
  - `query_repair_n`
  - `url_repair_n`
  - `llm_call_n`
  - `evidence_status`
- 完工报告必须单独列出：
  - 工具接线是否通过；
  - Agent 是否真正执行；
  - 评分器是否真实失败过；
  - 当前是否只是诊断通过。

## 2. Re10 FIX 的验证策略

之后验证不再默认全量跑 Balanced40。

本阶段采用“典型样例优先”的诊断策略：

1. 先跑 3 到 5 个典型样例，覆盖主要失败模式。
2. 每个样例必须输出完整 Trace。
3. 典型样例全部通过后，才允许扩展到 10 个抽样。
4. 只有抽样稳定后，才允许进入 Balanced40。

这一阶段的目标是定位问题，不是刷全量通过率。

## 3. 必跑典型样例

### Case A：钢材/裂缝/UNet

输入：

```text
基于Unet的钢材裂缝分割
```

验证重点：

- 不得再次出现 AGN、German survey、MLPerf、MIMIC 等明显错域论文。
- 必须能查到至少一种相关方向：
  - crack segmentation
  - steel surface defect
  - surface defect detection
  - NEU-DET / Severstal / DAGM / SD-saliency 等候选
- 如果没有直接 baseline，必须说明是“需要补 baseline”，而不是生成伪 baseline。

### Case B：三维成像/损伤检测

输入：

```text
基于三维成像的损伤智能检测
```

验证重点：

- 关键词必须拆出 3D / imaging / damage detection / inspection。
- 可以召回 3DGS、COLMAP、PointNet++、3D reconstruction、defect inspection 等相关方向。
- 不允许只把所有题目归入 2D CV 检测路线。

### Case C：多时相遥感/作物早期识别

输入：

```text
基于多时相遥感数据的作物早期识别
```

验证重点：

- 必须覆盖 remote sensing / crop classification / time series / early-season classification。
- 不应输出钢材裂缝、UNet 裂缝分割等串题结果。
- 如果数据集不足，应标注 dataset gap，并给出下一轮检索 query。

### Case D：NLP/大语言模型

输入：

```text
基于大语言模型的医学问答答案可信度评估
```

验证重点：

- 必须走 NLP / LLM / medical QA / factuality / hallucination evaluation 路线。
- 不允许被 `检测`、`评估` 等词误路由到 CV 检测。
- GitHub 与 paper 检索应优先找 benchmark、evaluation framework、medical QA dataset。

### Case E：坏 query / 占位符修复

构造 query：

```text
X dynamic scene dataset
```

验证重点：

- QueryRepair 必须触发。
- 修复前 query 不允许进入 adapter。
- Trace 必须记录 repair 前后 query。

## 4. 修复后的最小通过条件

典型样例阶段必须满足：

- `missing_client_n == 0`
- `adapter_attempt_n > 0`
- `adapter_error_n / adapter_attempt_n < 0.05`
- 至少 3 个典型样例中有 2 个出现 `new_candidates_n > 0`
- 至少 3 个典型样例中有 2 个出现 `accepted_candidates_n > 0`
- Case E 必须出现 `query_repair_n > 0`
- 如果候选 URL 为空但论文真实，不能直接 fail，必须标记：
  - `url_repair_pending`
  - 或 `url_repaired`
- `no_new_signal` 只能作为“搜索空间暂时无增量”，不能作为工具失败的别名。

不满足以上任一条件，Re10 FIX 不通过。

## 5. 执行顺序

### Step 1：修正 retrieval client key

修改：

- `G:\PaperAgent\apps\api\scripts\run_balanced40_reflection_re10.py`

要求：

- `_build_retrieval_clients()` 返回长 key。
- 添加一个本地断言：

```python
required = {"arxiv_search", "openalex_search", "crossref_search", "github_search", "huggingface_search"}
missing = required - set(retrieval_clients)
if missing:
    raise RuntimeError(f"retrieval client missing: {sorted(missing)}")
```

### Step 2：修正 stop reason

修改：

- `G:\PaperAgent\apps\api\app\services\agents\search_reflection_loop.py`

要求：

- 增加 round-level `tool_error_n`、`missing_client_n`、`successful_action_n`。
- `_decide_stop()` 先判断工具故障，再判断 `no_new_signal`。
- `blocked_tooling` 必须写入 trace 和 summary。

### Step 3：修正 validator

修改：

- `G:\PaperAgent\apps\api\scripts\validate_re10_reflection_search.py`

要求：

- 删除“repair gate 永远 true”的逻辑。
- 添加 hard fail：
  - `missing_client_n > 0`
  - `adapter_success_n == 0`
  - `status` 列缺失
  - `trace_path` 缺失
  - final stats 与 manifest 不一致
- `pass+weak` 不能只看 stop reason。

### Step 4：补齐审计输出

修改或新增：

- Re10 CSV/MD 导出脚本。

要求：

- 每个 case 的状态必须能从 CSV 独立判断。
- CSV 不允许只有 `case_id/title/stop_reason/rounds/seed_n` 这类弱字段。
- 报告中的数字必须能从 CSV 或 JSON 复算。

### Step 5：跑典型样例

先不要跑全量 Balanced40。

输出目录建议：

```text
G:\PaperAgent\tmp_re04_eval\re10_fix_typical_cases
```

必须保留：

- 每个 case 的 trace JSON。
- 一个样例汇总 CSV。
- 一个 validator 输出 Markdown。

### Step 6：只在典型样例通过后抽样扩展

抽样规则：

- 从 `PaperAgent_工科学位论文爬取测试集_100篇.md` 中抽 10 个。
- 必须覆盖：
  - CV/工业检测
  - 3D/重建/测量
  - 遥感/时序
  - NLP/LLM
  - 传统工科非 AI 强关键词题目

不再要求本轮直接跑 Balanced40。

## 6. Re10 FIX 交付物

必须生成：

- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX_完工报告.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX_典型样例审计.csv`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX_典型样例审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX_SearchTrace_索引.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX_Validator输出.md`

可选生成：

- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX_抽样10审计.csv`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX_抽样10审计.md`

本轮不要求生成 Balanced40 报告。

## 7. Re10 FIX 最终验收口径

通过条件：

- 典型样例全部完成。
- 无 `missing client`。
- validator 至少能在构造坏样例时真实失败。
- Case A-D 不出现明显串题。
- Case E 触发 query repair。
- 报告不能再出现“0 new candidate / 0 accepted / 0 LLM call / 0 adapter success 但 8/8 PASS”。

不通过条件：

- 仍然把 `no_new_signal` 当作 `weak` 兜底。
- 仍然全量跑 Balanced40，但无法解释典型样例。
- Trace 里仍然有 adapter missing client。
- 完工报告中的通过率无法从 CSV/JSON 复算。

## 8. 文档同步提醒

本次涉及 Agent 状态、检索链路、评分器、Trace schema 和验收口径。按项目协作规则，Re10 FIX 完成后应询问是否同步更新 `/docs` 中对应的 Agent 检索与评估规范。

