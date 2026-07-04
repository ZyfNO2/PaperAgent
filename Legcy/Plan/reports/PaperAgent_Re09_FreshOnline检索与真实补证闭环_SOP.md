# PaperAgent Re09 Fresh Online 检索与真实补证闭环 SOP

## 0. 本轮审查结论

Re08 不应被视为“真实检索增强完成”，只能视为“离线再审计与补证计划完成”。

原因很明确：

- `apps/api/scripts/reclassify_balanced40_re08.py` 文件头写明：读取 `tmp_re04_eval/balanced40/`，也就是 Re05 LLM-online raw dumps，然后重新分类输出 Re08。
- `PaperAgent_Re08_候选核验统计.json` 中 `verification_by_status = {"weak_metadata": 424}`，即 424 个候选全部只是弱元数据，没有任何 `verified` / `metadata_repaired`。
- Re08 完工报告自己承认：`raw dump 没变`、`verification_repaired_n=0`、`repair needs network`、`fresh LLM run` 尚未执行。
- `PaperAgent_Re08_弱项补证明细.md` 中大量查询仍是 plan，例如 `X dynamic scene dataset`、`X ORB-SLAM dynamic scene`，说明补证没有实际执行，且模板占位符未被真实对象词替换。

因此 Re08 的通过范围只能写成：

> Re08 通过“离线诊断层 / 报告层 / repair plan 生成层”，未通过“真实检索闭环层”。

## 1. 为什么上一阶段没有强制重跑

这是 Re08 SOP 的验收边界写得不够硬。

上一阶段 SOP 写了“Balanced40 重新生成 Re08 报告”，但没有写死：

- 必须 fresh online retrieval。
- 不允许读取 Re05 raw dump 作为主输入。
- 不允许仅 `reclassify` 旧结果。
- 不允许 `repair_plan` 生成后不执行。
- 不允许 `verification_status` 全部为 `weak_metadata` 还算通过。
- 不允许 `verified=0` 还声明候选核验完成。

执行者因此选择了最低成本路径：基于旧 dump 做 Re08 re-audit。这个选择在代码上是诚实的，但在产品目标上没有完成“检索增强”。

Re09 必须修正这个验收漏洞。

## 2. Re09 目标

Re09 的目标是把 Re08 的“计划型补证”改成“真实执行型补证”。

本阶段必须做到：

1. 对 Balanced40 至少执行一次 fresh online 检索。
2. 对 Re08 的 3 个 fail 和 13 个 weak 执行真实补证查询。
3. 对候选资源执行在线核验，不能全部停留在 `weak_metadata`。
4. 将补证后的新候选重新进入 bucket、eval、report。
5. 报告必须清楚区分：
   - 旧 dump 再审计结果
   - fresh online 新检索结果
   - repair plan
   - repair execution result

## 3. 非目标

本阶段不做：

- 不做完整知识图谱。
- 不做论文写作。
- 不做工作包生成大改。
- 不做 HumanGate。
- 不做 100 题全量长期评测。
- 不做 UI 迭代。

本阶段只修“检索真实执行、候选核验、补证回填、验收防作弊”。

## 4. 必须修复的代码问题

### 4.1 `reclassify_balanced40_re08.py` 不能继续作为验收主入口

当前问题：

`apps/api/scripts/reclassify_balanced40_re08.py`

是 re-audit runner，不是 fresh retrieval runner。它读取旧目录：

```text
tmp_re04_eval/balanced40/
```

然后输出：

```text
tmp_re04_eval/balanced40_re08/
```

Re09 必须新建 fresh runner：

`apps/api/scripts/run_balanced40_fresh_re09.py`

职责：

- 读取 Balanced40 case 列表。
- 对每个 case 调用真实检索主链路。
- 写入新的 fresh raw 目录。
- 记录每个 adapter / LLM / repair query 的调用次数。

输出目录必须是：

```text
tmp_re04_eval/balanced40_re09_fresh/
```

不得把 `balanced40_re08` 或 `balanced40` 复制改名当作 fresh 结果。

### 4.2 CandidateVerifier 批量核验不能只跑 offline

当前问题：

`apps/api/app/services/agents/candidate_verifier.py`

中 `verify_bucket(...)` 即使传入 `llm_client`，也直接调用：

```python
verify_candidate_offline(...)
```

这导致 Re08 的 424 个候选全部是 rule-layer 结果。

Re09 必须新增：

```python
async def verify_bucket_online(
    bucket_name: str,
    members: list[dict],
    topic_atoms: dict,
    *,
    llm_client,
    metadata_client,
) -> list[VerificationResult]:
    ...
```

该函数必须：

- 对 `weak_metadata` / `metadata_mismatch` 候选调用在线核验。
- 使用 arXiv / OpenAlex / Crossref / GitHub / Web adapter 获取真实 title / abstract / url / DOI。
- 核验后写回 `raw_candidate` 和 `verified_metadata`。
- 不允许仅让 LLM 根据旧 title 猜。

该模块不应该：

- 只调用 LLM 不调检索 adapter。
- 用固定标题黑名单过滤。
- 因为 Crossref mismatch 直接 fail。
- 全量返回 `weak_metadata` 后仍声明通过。

### 4.3 MetadataRepairLoop 必须执行，不只是产出建议

当前问题：

Re08 的 repair 是“计划”，不是“执行”。例如输出：

```text
concrete pavement crack detection deep learning survey
dynamic scene ORB-SLAM
```

但没有实际调用搜索、没有回填候选、没有改变 raw dump。

Re09 必须新建或补强：

`apps/api/app/services/agents/metadata_repair_executor.py`

接口：

```python
async def execute_repair_plan(
    case_id: str,
    topic: str,
    topic_atoms: dict,
    repair_plan: dict,
    *,
    retrieval_client,
    llm_client,
) -> dict:
    ...
```

输出：

```json
{
  "case_id": "...",
  "planned_queries_n": 9,
  "executed_queries_n": 9,
  "adapter_calls": {
    "arxiv": 2,
    "openalex": 3,
    "github": 2,
    "web": 2
  },
  "new_candidates_n": 17,
  "verified_new_candidates_n": 6,
  "inserted_to_buckets": {
    "core": 2,
    "baseline": 1,
    "parallel": 4,
    "dataset": 2,
    "repo": 1
  },
  "remaining_gaps": []
}
```

### 4.4 GapRepairPlanner 不能输出占位符 `X`

当前问题：

Re08 报告中出现：

```text
X dynamic scene dataset
X ORB-SLAM dynamic scene
X UAV aerial imagery dataset
```

这说明 planner 没有从 `topic_atoms` 中正确取对象词 / 场景词 / 方法词。

Re09 必须：

- 在 `GapRepairPlanner` 输出前做 placeholder check。
- 如果 query 中包含 `{object}`、`{scenario}`、`X` 这类未替换占位符，直接 fail。
- 缺对象词时，先调用 topic parser 修复；仍无法解析则标 `needs_clarification`，不得生成伪查询。

新增测试：

```text
输入：面向动态环境的视觉SLAM研究
禁止输出：X ORB-SLAM dynamic scene
必须输出：dynamic visual SLAM dataset, dynamic scene SLAM benchmark, ORB-SLAM3 dynamic environment
```

### 4.5 Report Validator 必须识别“伪 fresh”

当前问题：

`validate_re08_consistency.py` 只校验报告之间数字一致，但不会判断数据是否真的 fresh。

Re09 必须新增：

`apps/api/scripts/validate_re09_fresh_run.py`

必须校验：

- `run_manifest.json` 存在。
- `run_manifest.data_source == "fresh_online_retrieval"`。
- `run_manifest.source_input_dir` 不得是 `tmp_re04_eval/balanced40`。
- `adapter_call_count.total > 0`。
- `llm_call_count.total > 0`，除非显式声明本轮使用 no-LLM mode。
- `repair_execution.executed_queries_n > 0` for fail / weak cases。
- `verification_by_status` 不得全部为 `weak_metadata`。
- `verified + metadata_repaired + weak_metadata + not_found + metadata_mismatch == total_verifications`。
- 完工报告中必须出现 fresh run manifest 摘要。

如果任何一条不满足，Re09 不允许验收。

## 5. Fresh Run Manifest

每次 fresh online run 必须生成：

`tmp_re04_eval/balanced40_re09_fresh/run_manifest.json`

字段：

```json
{
  "run_id": "re09_fresh_20260703_xxxxxx",
  "data_source": "fresh_online_retrieval",
  "created_at": "2026-07-03Txx:xx:xx+08:00",
  "case_set": "Balanced40",
  "n_cases": 40,
  "source_input_file": "...",
  "source_input_hash": "...",
  "llm_provider": "...",
  "llm_model": "...",
  "adapter_call_count": {
    "arxiv": 0,
    "openalex": 0,
    "crossref": 0,
    "github": 0,
    "web": 0,
    "huggingface": 0
  },
  "repair_execution": {
    "planned_queries_n": 0,
    "executed_queries_n": 0,
    "new_candidates_n": 0,
    "verified_new_candidates_n": 0
  },
  "fresh_run_gate": "pass | fail",
  "notes": []
}
```

该文件是 Re09 的第一验收证据。没有它，其他报告全部无效。

## 6. Re09 主流程

### Step 1：构建 Fresh Case Set

输入：

- Balanced40 case 列表。
- Re08 fail / weak 列表。
- Re08 repair_plan。

输出：

```text
tmp_re04_eval/balanced40_re09_fresh/cases.jsonl
```

每行至少包含：

```json
{
  "case_id": "...",
  "topic": "...",
  "priority": "fail | weak | pass_sample",
  "re08_status": "...",
  "re08_gaps": [],
  "repair_plan": {}
}
```

### Step 2：Fresh Retrieval

对每个 case 调用真实检索主链路。

建议调用顺序参考 AutoResearchClaw 的 stage 思路：

1. topic parse
2. search strategy
3. source collection
4. metadata verification
5. synthesis
6. citation / reference expansion

PaperAgent 中对应简化为：

1. `parse_topic`
2. `plan_tools`
3. `multi_round_fetch`
4. `candidate_dedup`
5. `candidate_verify_online`
6. `gap_repair_execute`
7. `resource_eval`

### Step 3：Fail / Weak 定向补证

对 Re08 的 3 fail + 13 weak，必须执行 repair plan。

要求：

- 每个 fail 至少执行 6 条查询。
- 每个 weak 至少执行 3 条查询。
- 每个查询必须记录 adapter、query、返回数量、插入 bucket 数量。
- 如果查询失败，必须记录失败原因，而不是静默跳过。

### Step 4：候选在线核验

所有新候选必须进入 `verify_bucket_online`。

验收要求：

- `verified + metadata_repaired` 必须大于 0。
- baseline bucket 中不得出现 `not_found`。
- `metadata_mismatch` 候选必须保留修复记录或 quarantine 记录。

### Step 5：重新计算资源状态

用 fresh raw + repaired candidates 重新跑：

- `compute_resource_status`
- summary aggregation
- per-case report
- candidate-level CSV

不得直接复用 Re08 的 status。

### Step 6：报告生成

产出：

- `Plan/PaperAgent_Re09_完工报告.md`
- `Plan/PaperAgent_Re09_Balanced40_逐论文审计.md`
- `Plan/PaperAgent_Re09_Balanced40_逐论文审计.csv`
- `Plan/PaperAgent_Re09_Balanced40_候选论文.csv`
- `Plan/PaperAgent_Re09_FreshRunManifest.json`
- `Plan/PaperAgent_Re09_真实补证执行明细.md`

## 7. 必测样本

### 7.1 Fail 样本必须 fresh repair

1. `ENG-THESIS-043` 无人机动态目标检测  
   必须真实搜索 UAV / aerial imagery / dynamic object detection / dataset / repo。

2. `ENG-THESIS-048` 动态视觉 SLAM  
   必须真实搜索 ORB-SLAM3 / dynamic SLAM / visual odometry / TUM / KITTI / EuRoC / dynamic scene benchmark。

3. `ENG-THESIS-075` 混凝土路面裂缝检测  
   必须真实搜索 concrete pavement crack detection / crack dataset / road crack dataset / benchmark / github。

### 7.2 Weak 样本抽样

至少抽 5 个 Re08 weak 样本执行真实补证。

必须包含：

- 一个 2D 缺陷检测题目。
- 一个 3D / SLAM / 点云题目。
- 一个攻击防御或鲁棒性题目。
- 一个非视觉或跨模态题目。
- 一个数据集缺口题目。

### 7.3 Pass 样本回归

至少抽 5 个 Re08 pass 样本，验证 Re09 不会把正常候选大面积降级。

## 8. 验收标准

Re09 通过必须同时满足：

### 8.1 Fresh Run Gate

- `run_manifest.data_source == "fresh_online_retrieval"`。
- `adapter_call_count.total > 0`。
- `repair_execution.executed_queries_n > 0`。
- `source_input_dir` 不得是 Re05 / Re08 raw dump 目录。
- 完工报告必须写明“本轮 fresh online run 的真实调用统计”。

### 8.2 Candidate Verification Gate

- `verification_total > 0`。
- 不允许 `verification_by_status == {"weak_metadata": total}`。
- `verified + metadata_repaired > 0`。
- baseline bucket 不允许 `not_found`。
- `metadata_mismatch` 必须有 repair 或 quarantine 明细。

### 8.3 Repair Execution Gate

- 3 个 Re08 fail 必须都有真实执行记录。
- 每个 fail 的 executed query 数量 >= 6。
- 每个 fail 必须至少新增 1 个候选，除非所有工具都失败且报告列出失败证据。
- `repair_plan` 不能代替 `repair_execution`。

### 8.4 Query Quality Gate

- 查询中不得出现 `{object}`、`{scenario}`、`X` 这类未替换占位符。
- 查询必须包含对象词 / 任务词 / 方法词中的至少两类。
- 数据集查询必须包含 dataset / benchmark / 数据集 / challenge / corpus 等资源词。
- repo 查询必须包含 github / implementation / code / repo 等资源词。

### 8.5 Report Honesty Gate

完工报告必须明确分成：

- Fresh retrieval result
- Repair execution result
- Verification result
- Remaining gaps
- Re08 -> Re09 status delta

如果只是 re-audit，必须标为 fail，不允许写 PASS。

## 9. 推荐实现顺序

1. 新建 `run_balanced40_fresh_re09.py`。
2. 新增 `run_manifest` 写入。
3. 修复 `verify_bucket`，新增 `verify_bucket_online`。
4. 新增 `metadata_repair_executor.py`。
5. 修复 `GapRepairPlanner` 的占位符泄露。
6. 新增 `validate_re09_fresh_run.py`。
7. 对 3 fail 跑 fresh repair smoke。
8. 对 Balanced40 跑 fresh online。
9. 生成 Re09 报告。
10. 用 validator 阻断伪 fresh 报告。

## 10. 对执行者的硬性规则

执行者不得：

- 把 Re05 / Re08 dump 复制为 Re09 fresh。
- 只跑 `reclassify_*` 就提交。
- 只生成 repair plan 不执行查询。
- 把 `verified=0` 写成候选核验通过。
- 把全量 `weak_metadata` 写成 SOP PASS。
- 用本地硬编码标题黑名单处理噪声。
- 用单一关键词把所有题目导向 CV 检测。
- 静默吞掉 adapter / LLM 错误。

执行者必须：

- 在完工报告开头给出 fresh manifest 摘要。
- 在报告中列出真实 adapter call count。
- 在报告中列出 3 fail 的 query execution trace。
- 在报告中列出新增候选数、核验通过数、仍缺口数。
- 明确说明是否还需要下一轮。

## 11. 参考工程要求

执行前必须阅读并参考：

- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw`
  - 重点：search strategy、source collection、citation verify、reference expansion、run manifest / stage artifacts。
  - Re09 借鉴点：阶段性产物必须真实落盘，citation verify 是最后硬门，不是报告文字。

- `C:\Users\ZYF\Desktop\Paper\academic-research-skills`
  - 重点：literature strategist、source screening、citation compliance、trust provenance。
  - Re09 借鉴点：必须区分 source acquired / AI verified / human read，不允许把“自洽检查”说成“真实核验”。

## 12. 最终交付物

必须交付：

- `G:\PaperAgent\Plan\PaperAgent_Re09_完工报告.md`
- `G:\PaperAgent\Plan\PaperAgent_Re09_Balanced40_逐论文审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re09_Balanced40_逐论文审计.csv`
- `G:\PaperAgent\Plan\PaperAgent_Re09_Balanced40_候选论文.csv`
- `G:\PaperAgent\Plan\PaperAgent_Re09_FreshRunManifest.json`
- `G:\PaperAgent\Plan\PaperAgent_Re09_真实补证执行明细.md`

如果无法完成 fresh online run，必须提交：

- `G:\PaperAgent\Plan\PaperAgent_Re09_Blocker_Report.md`

并明确写出：

- 缺哪个 API key。
- 哪个 adapter 失败。
- 哪些 case 没跑。
- 为什么不能验收。
