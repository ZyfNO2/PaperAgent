# PaperAgent Re10 FIX-2：小样例闭环检索修复 SOP

## 0. 本阶段目标

本阶段只做一件事：把 Re10 FIX 暴露出的“能调用工具但没有有效候选”的问题修到闭环产出正确。

当前已经完成：

- `missing client` 问题已修复。
- Validator 已经能真实失败，不再假通过。
- 5 个典型样例已经跑出 Trace。

当前未完成：

- 5 个典型样例全部 `new_candidates_n=0`。
- 5 个典型样例全部 `accepted_candidates_n=0`。
- OpenAlex 429、GitHub 403、中文 query 退化、UNet repo fallback、placeholder leak 仍在破坏结果。

**本阶段不允许进入 Re11。**

只有在“小量测验 -> 自查 -> 修理 -> 再测”的 Loop 全部通过后，才允许进入抽样测试；抽样通过后才允许跑全量。

## 1. 总原则

### 1.1 不改架构，只修链路

本阶段不得重构 PaperAgent 总架构，不新增大型 Agent 框架，不改前端，不改业务目标。

允许改动的范围：

- `G:\PaperAgent\apps\api\scripts\run_balanced40_reflection_re10.py`
- `G:\PaperAgent\apps\api\app\services\agents\search_reflection_loop.py`
- `G:\PaperAgent\apps\api\app\services\agents\search_reflection_helpers.py`
- `G:\PaperAgent\apps\api\app\services\agents\domain_scout_agent.py`
- `G:\PaperAgent\apps\api\app\services\agents\reflection_critic_agent.py`
- `G:\PaperAgent\apps\api\app\services\agents\query_repair_agent.py`
- `G:\PaperAgent\apps\api\scripts\validate_re10_reflection_search.py`
- 必要时可补少量单元测试或导出脚本，但不能绕过 validator。

不允许：

- 新建一套平行检索系统替代现有 loop。
- 为了通过测试大改数据模型。
- 把典型 case 写成硬编码规则。
- 降低 validator 阈值。
- 删除失败样例。
- 把 `no_new_signal` 重新映射成 `weak`。
- 把错误隐藏到报告里不展示。

### 1.2 小量测验优先

本阶段执行顺序固定：

1. 跑 5 个典型样例。
2. 如果失败，阅读 Trace，定位失败点。
3. 修复最小相关代码。
4. 重跑同一批 5 个典型样例。
5. 重复 1-4，直到 5 个典型样例达到最低通过线。
6. 才允许抽样 10 个。
7. 抽样 10 通过后，才允许 Balanced40 全量。
8. Balanced40 达到 95% 通过后，仍必须做一次致命问题自查。

**小量测验通过前，不允许停下。**

## 2. 关键参考源

撞墙时先看这些文件，不要闭门造车。

### 2.1 AutoResearchClaw

根目录：

```text
C:\Users\ZYF\Desktop\Paper\AutoResearchClaw
```

优先参考：

- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\web\search.py`
  - 看 web/search 如何组织外部检索、失败兜底、结果结构。
- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\web\scholar.py`
  - 看学术检索如何处理论文源。
- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\web\crawler.py`
  - 看 URL/网页抓取的容错边界。
- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\pipeline\stage_impls\_literature.py`
  - 看 literature stage 如何把主题转成文献搜索流程。
- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\pipeline\stage_impls\_topic.py`
  - 看 topic stage 如何做领域识别和主题拆解。
- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\agents\code_searcher\query_gen.py`
  - 看 repo/code query 生成，不要再用固定 `U-Net semantic segmentation`。
- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\agents\code_searcher\github_client.py`
  - 看 GitHub rate limit / token / 搜索失败处理。
- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\domains\detector.py`
  - 看领域识别如何做，不要把 NLP/遥感/3D 都打到 CV。
- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\domains\profiles\ml_vision.yaml`
- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\domains\profiles\ml_nlp.yaml`
- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\domains\profiles\robotics_control.yaml`
- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\prompts.default.yaml`
  - 看 prompt 如何拆解任务、工具、证据和候选。

### 2.2 academic-research-skills

根目录：

```text
C:\Users\ZYF\Desktop\Paper\academic-research-skills
```

优先参考：

- `C:\Users\ZYF\Desktop\Paper\academic-research-skills\deep-research\SKILL.md`
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills\deep-research\agents\research_architect_agent.md`
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills\deep-research\agents\source_verification_agent.md`
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills\deep-research\agents\bibliography_agent.md`
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills\deep-research\references\openalex_api_protocol.md`
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills\deep-research\references\crossref_api_protocol.md`
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills\deep-research\references\arxiv_api_protocol.md`
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills\deep-research\references\semantic_scholar_api_protocol.md`
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills\deep-research\references\source_quality_hierarchy.md`
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills\deep-research\references\failure_paths.md`
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills\academic-paper\agents\literature_strategist_agent.md`
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills\academic-paper-reviewer\references\review_quality_thinking.md`

### 2.3 PaperAgent 本地参考

- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX_完工报告.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX_典型样例审计.csv`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX_SearchTrace_索引.md`
- `G:\PaperAgent\docs\agent_architecture.md`
- `G:\PaperAgent\docs\interview\AutoResearchClaw_对标与小型化移植.md`
- `G:\PaperAgent\docs\testing\Test_Matrix.md`
- `G:\PaperAgent\docs\PaperAgent_工科学位论文爬取测试集_100篇.md`

## 3. 必修问题清单

### P0-1：Provider 熔断和换源

现象：

- OpenAlex 多次 HTTP 429。
- GitHub HTTP 403。
- Loop 没有切到 Crossref / arXiv / HuggingFace。

必须实现：

- 在单次 run 内维护 provider 状态。
- OpenAlex 连续 2 次 429 后，本 case 内暂停 OpenAlex。
- GitHub 403 后，本 case 内暂停 GitHub，并尝试 HuggingFace 或跳过 repo 源。
- 被暂停的 provider 不应继续产生重复失败 action。
- Trace 必须记录：
  - `provider_circuit_breaker.openalex=rate_limited`
  - `provider_circuit_breaker.github=rate_limited`
  - `fallback_tool=crossref/arxiv/huggingface`

不应该：

- 只靠全局 sleep 解决 429。
- 把 429 当成 `no_results`。
- 让 429/403 继续污染 `no_new_signal`。

建议：

- 参考 AutoResearchClaw 的 `web/search.py`、`web/scholar.py`、`agents/code_searcher/github_client.py`。
- 最小实现可以放在 `search_reflection_loop.py` 的本轮 history/provider_state 中，不要新增大型服务。

### P0-2：删除 UNet 固定 repo fallback

现象：

不同领域都出现：

```text
U-Net semantic segmentation github implementation
```

必须实现：

- repo query 必须来自 `topic_atoms.method/object/task/scenario` 或 DomainScout 产出的 `repo_probe_queries`。
- 如果没有可用 repo query，宁可不搜 repo，也不能使用固定 UNet。
- NLP case 必须生成 LLM/medical QA/factuality/evaluation 相关 repo query。
- 遥感 case 必须生成 remote sensing/crop/time-series 相关 repo query。
- 3D case 必须生成 3D reconstruction/point cloud/inspection 相关 repo query。

不应该：

- 用 `if "检测" in topic` 直接走 CV。
- 用单个固定 query 兜底所有领域。
- 为了让 case 过而硬编码标题到 query。

建议：

- 参考 AutoResearchClaw 的 `agents/code_searcher/query_gen.py`。
- 当前 PaperAgent 可在 `domain_scout_agent.py` 或 `search_reflection_helpers.py` 中收口 query 生成。

### P0-3：Round2/Round3 禁止中文原题拼接

现象：

第二轮 query 出现：

```text
基于Unet的钢材裂缝分割 dataset benchmark
基于三维成像的损伤智能检测 baseline method
```

必须实现：

- 对 GitHub / arXiv / Crossref / OpenAlex，query 必须是英文短语。
- 如果 focus 只有中文，先从 `topic_atoms.query_atoms_en`、`topic_atoms.<axis>.en` 或 LLM repair 中生成英文 query。
- 如果无法生成英文 query，标记 `blocked_query_translation`，不要执行 adapter。

不应该：

- 中文原题 + `dataset benchmark` 直接送 OpenAlex/GitHub。
- 拼接 `narrow` 这类空泛词导致 arXiv 串题。
- 让中文 query 的空结果变成方向失败。

建议：

- 参考 `academic-research-skills\deep-research\references\openalex_api_protocol.md` 和 `crossref_api_protocol.md`。
- 参考 `apps/api/app/services/agents/prompts/parse_topic.py` 已写好的 `query_atoms_en` 规则，把 prompt 结果真正用起来。

### P0-4：相关候选不能被全打成 noise

现象：

TYPICAL-01 搜到 DeepCrack、CrackFormer、steel surface inspection review，但 `good_candidates=0`。

必须实现：

- 新增或修正候选相关性规则：
  - 命中 task + object，应进入 accepted 或 at least weak candidate。
  - 命中 task + scenario，也可进入 accepted。
  - 命中 method + task，但 object 缺失，应进入 `candidate_needs_object_check`，不能直接 noise。
- 对明显跨域才标 noise：
  - AGN / astronomy
  - German survey motivation
  - unrelated medical ICD
  - unrelated RL narrow path

不应该：

- 因为没有 dataset/repo 就把相关 paper 标 noise。
- 因为 title 没完全包含中文对象就剔除。
- 用超严格 all-axis match 阻断早期召回。

直接回答难点：

- `DeepCrack`、`CrackFormer` 对“基于 UNet 的钢材裂缝分割”是相关候选，应进入 paper/parallel candidate。
- `Deep Metallic Surface Defect Detection` 对钢材表面缺陷也相关，应进入 candidate。
- `Review of vision-based steel surface inspection systems` 可以作为 survey/context，不是 core baseline，但不能是 noise。

### P0-5：Placeholder repair 后不能泄漏

现象：

TYPICAL-05 中 `X dynamic scene dataset` 被识别为 `needs_clarification`，但仍出现 `query_placeholder_leaks=3`。

必须实现：

- 如果 query 含裸 `X` 或 `{axis}`，在 adapter 前阻断。
- `repair_query` 返回 `needs_clarification` 后：
  - 不执行 adapter；
  - Trace action 记录为 `blocked_query`;
  - stop_reason 应为 `needs_clarification` 或 `blocked_query`；
  - validator 不应把它计入“执行泄漏”。
- 如果是测试用 placeholder case，允许以 `blocked_query` 通过该专项测试。

不应该：

- 把 placeholder query 写入 `executed_queries`。
- 把 placeholder 阻断误判为 `no_new_signal`。
- 为了过 H4 删除 trace 证据。

## 4. 执行 Loop

执行者必须按以下 Loop 工作，不得跳步。

### Loop A：5 个典型样例

命令示例：

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe apps\api\scripts\run_balanced40_reflection_re10.py `
  --out-dir tmp_re04_eval\re10_fix2_typical_cases `
  --raw-topics "基于Unet的钢材裂缝分割||基于三维成像的损伤智能检测||基于多时相遥感数据的作物早期识别||基于大语言模型的医学问答答案可信度评估||X dynamic scene dataset"

.\.venv\Scripts\python.exe apps\api\scripts\validate_re10_reflection_search.py `
  --re10-dir tmp_re04_eval\re10_fix2_typical_cases `
  --skip-baseline-gates
```

如果当前 validator 暂时仍需要 `--allow-no-llm` 才能跑，允许诊断时使用，但报告必须标注“诊断模式，不是正式通过”。

### Loop A 自查清单

每轮跑完必须检查：

- `missing_client_n == 0`
- `adapter_error_n / adapter_attempt_n < 0.2`
- `new_candidates_n > 0` 的 case 数量
- `accepted_candidates_n > 0` 的 case 数量
- TYPICAL-01 是否 accepted 至少 1 篇 crack/steel/surface defect 相关论文
- TYPICAL-04 是否不再出现 UNet repo fallback
- TYPICAL-05 是否不再有 `query_placeholder_leaks`
- Trace 中是否仍有中文原题拼接英文后缀
- Trace 中 OpenAlex 429 后是否切换 source

### Loop A 最低通过线

必须全部满足：

- 5/5 `missing_client_n == 0`
- 5/5 不出现固定 `U-Net semantic segmentation github implementation`
- 5/5 不出现中文原题拼接英文后缀进入 adapter
- 至少 4/5 `adapter_success_n > 0`
- 至少 3/5 `new_candidates_n > 0`
- 至少 2/5 `accepted_candidates_n > 0`
- TYPICAL-01 至少 accepted 1 篇相关论文
- TYPICAL-04 走 NLP/LLM/medical QA 路线
- TYPICAL-05 `query_placeholder_leaks == 0`
- Validator 不出现 H2/H4/H9 hard fail

不满足就继续修，不允许停。

### Loop B：抽样 10

Loop A 通过后，从：

```text
G:\PaperAgent\docs\PaperAgent_工科学位论文爬取测试集_100篇.md
```

抽样 10 个题目，必须覆盖：

- 2D/CV/工业检测
- 3D/成像/重建/测量
- 遥感/时序
- NLP/LLM
- 传统工科非强 AI 题目

通过线：

- 10 个中至少 8 个 `new_candidates_n > 0`
- 10 个中至少 7 个 `accepted_candidates_n > 0`
- 0 个 `missing_client`
- 0 个明显串题
- 0 个固定 UNet fallback
- provider error rate < 20%

不满足就回到 Loop A 或针对失败 case 建立 Loop B-Repair，不允许直接跑全量。

### Loop C：Balanced40 全量

Loop B 通过后，才允许跑 Balanced40。

通过线：

- `pass + weak >= 95%`
- `missing_client_n == 0`
- 固定 UNet fallback 出现次数 = 0
- 中文原题拼接英文后缀进入 adapter 次数 = 0
- placeholder leak 次数 = 0
- provider error rate < 20%
- 每个 fail/blocked case 必须有明确 failure_mode，不允许空白。

达到 95% 以后还不能马上停，必须做 Loop D。

### Loop D：95% 后致命问题自查

全量 95% 通过后，必须抽查：

- 所有 `pass` 中随机 5 个 Trace。
- 所有 `weak` 中随机 5 个 Trace，如果不足 5 个则全看。
- 所有 `fail/blocked` 全看。
- TYPICAL-01 到 TYPICAL-05 再跑一遍，确认没有回归。

致命问题定义：

- pass case 实际候选全部错域。
- pass case 没有真实 adapter 调用。
- pass case 是旧 seed 伪装新结果。
- pass case 仍有 provider 全失败。
- pass case 仍有 placeholder 或中文 query 泄漏。
- pass case 的 accepted candidate 为空。

发现任一致命问题：

- 全量 95% 作废。
- 回到 Loop A 或 Loop B 修理。
- 不允许停。

## 5. 什么时候可以停

只有以下条件全部满足，执行者才能停：

- Loop A 通过。
- Loop B 通过。
- Loop C Balanced40 `pass+weak >= 95%`。
- Loop D 致命问题自查通过。
- 已生成完工报告，并写明每个 Loop 的命令、结果、失败修复记录。
- 报告能从 CSV/JSON/Trace 复算。

## 6. 什么时候允许停下求助

只有撞到以下墙，才允许停下并向用户汇报：

1. 外部 API 全部不可用：
   - OpenAlex 长时间 429；
   - Crossref/arXiv/HuggingFace/GitHub 同时不可用；
   - 已记录 provider status 和重试日志。
2. 缺少必要凭据：
   - GitHub 403 且没有 `GITHUB_TOKEN`；
   - 需要用户提供 token 或允许禁用 GitHub source。
3. LLM 服务不可用：
   - parse_topic / DomainScout / ReflectionCritic 连续失败；
   - 已有 fallback，但 fallback 无法满足典型样例。
4. 参考工程中没有对应实现，且当前架构需要用户确认是否引入新依赖。
5. 修复会触及架构边界：
   - 需要新增长期 provider registry；
   - 需要新增大型 Agent 编排；
   - 需要改数据模型或前端协议。

不允许因为以下原因停：

- 5 个典型样例还没过。
- 只修了一个 case。
- Validator 还失败。
- 报告还没复算。
- “看起来差不多了”。

## 7. 必交付物

必须生成：

- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-2_完工报告.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-2_典型样例审计.csv`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-2_典型样例审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-2_SearchTrace_索引.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-2_Validator输出.md`

如果进入抽样 10：

- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-2_抽样10审计.csv`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-2_抽样10审计.md`

如果进入 Balanced40：

- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-2_Balanced40_逐论文审计.csv`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-2_Balanced40_逐论文审计.md`
- `G:\PaperAgent\Plan\PaperAgent_Re10_FIX-2_Balanced40_致命问题自查.md`

## 8. 报告必须包含的字段

每个 case 必须列出：

- `case_id`
- `title`
- `domain_route`
- `stop_reason`
- `evidence_status`
- `adapter_attempt_n`
- `adapter_success_n`
- `adapter_error_n`
- `provider_error_summary`
- `provider_circuit_breaker`
- `new_candidates_n`
- `accepted_candidates_n`
- `accepted_titles`
- `rejected_noise_titles`
- `query_placeholder_leaks`
- `chinese_query_leaks`
- `fixed_unet_fallback_seen`
- `primary_failure_mode`
- `trace_path`

报告不允许只写 pass/fail 总数。

## 9. 给执行者的直接提示

### 9.1 OpenAlex 429 怎么修

不要用“全局 sleep 很久”解决。

最小可行做法：

- case 内记录 provider 状态。
- OpenAlex 429 两次后，当前 case 不再调用 OpenAlex。
- 对同一 query 转成 Crossref/arXiv。
- Trace 记录 fallback。

### 9.2 GitHub 403 怎么修

最小可行做法：

- adapter 读取 `GITHUB_TOKEN`。
- 没有 token 且 403 时，当前 case 停用 GitHub。
- Repo 证据缺失不应让论文检索失败，只标 `repo_gap`。

### 9.3 TYPICAL-01 应该怎样才算正确

正确产出至少应包含以下类型之一：

- crack segmentation paper
- steel surface defect detection paper
- surface inspection survey
- U-Net / segmentation baseline or parallel paper

DeepCrack、CrackFormer、Deep Metallic Surface Defect Detection 都不应被标成 noise。

### 9.4 TYPICAL-04 应该怎样才算正确

它是 NLP/LLM/medical QA/factuality evaluation，不是 CV。

query 应类似：

- `medical question answering factuality evaluation`
- `large language model medical QA hallucination`
- `LLM answer faithfulness benchmark`
- `medical QA evaluation benchmark`

不得出现 UNet / semantic segmentation。

### 9.5 TYPICAL-05 应该怎样才算正确

它是坏 query 测试。

正确行为不是搜到论文，而是：

- 识别 `X` placeholder；
- 不进入 adapter；
- stop_reason 为 `needs_clarification` 或 `blocked_query`；
- validator H4 通过。

## 10. 禁止事项总表

- 禁止改低 validator 阈值。
- 禁止删除典型样例。
- 禁止绕过 Trace。
- 禁止只写报告不跑命令。
- 禁止全量测试代替小量测验。
- 禁止把外部 API 错误算成方向失败。
- 禁止把 `no_results` 和 `error` 混为一谈。
- 禁止固定 UNet fallback。
- 禁止中文原题拼接英文后缀进入 OpenAlex/GitHub/arXiv/Crossref。
- 禁止把相关论文因为没有 repo/dataset 直接标 noise。
- 禁止硬编码 case title 到结果。
- 禁止把 placeholder repair 的失败当作正常搜索失败。
- 禁止在 95% 后不做致命问题自查就停。

## 11. 文档同步提醒

本阶段如果修复了 provider 熔断、Trace schema、候选过滤规则或 validator 口径，完成后需要询问是否同步更新：

- `G:\PaperAgent\docs\agent_architecture.md`
- `G:\PaperAgent\docs\testing\Test_Matrix.md`
- `G:\PaperAgent\docs\project\Known_Limitations.md`

