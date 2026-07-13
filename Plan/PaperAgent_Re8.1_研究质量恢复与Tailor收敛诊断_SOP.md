# PaperAgent Re8.1：研究质量恢复与 Tailor 收敛诊断 SOP

> Status: Draft for execution
> Date: 2026-07-14
> Predecessor: Re8.0 Close-the-Loop
> Canonical path: `Plan/PaperAgent_Re8.1_研究质量恢复与Tailor收敛诊断_SOP.md`
> Archive policy: 仅在完成、废弃或被后续 SOP 明确取代后移入 Legacy

---

## 0. 目标与非目标

### 0.1 本阶段目标

Re8.0 已经完成真实种子论文驱动的后端闭环、三层 PASS 标准、Gate 修复路由、证据归因与假阳性消除。Re8.1 不再以“能跑通”为目标，而以以下结果为目标：

1. 证明 2026-07-13 后新增的 Tailor 上游字段补全、Seed Repair 标题检索和 Gate 容错补丁真实进入端到端链路；
2. 定位 `tailored_method.core_method` 为空、Tailor Gate unresolved、novelty reject 与 low-bar blocked 的真实根因；
3. 修复 Tailor 数据输入、Prompt、Parser、Schema、Validator 或 fallback 中的主要故障点；
4. 建立可复用的标题型 Seed Repair 基准集和防误验收机制；
5. 让至少部分真实案例从 `BLOCKED` 恢复到 `CONDITIONAL`、`RISKY` 或 `GO`；
6. 将前端静态 fixture 升级为真实后端链路，并诚实显示失败、修复循环和 Gate 状态。

### 0.2 明确非目标

本阶段不承诺：

- 三个案例全部达到 `GO`；
- 通过放宽 Gate、降低 ablation 数量或伪造字段实现 `quality_pass=true`；
- 在证据不足时强行生成“创新点”；
- 对所有学科完成跨领域泛化；
- 未经用户批准修改 `REFLECTION_GATE_MAX_ROUNDS=2`；
- 未经用户批准将 ablation 最低要求从 4 项下调。

### 0.3 不可违反的原则

- `runtime_pass`、`contract_pass`、`quality_pass` 必须继续独立报告；
- `fused_verdict=BLOCKED` 时，`quality_pass` 必须为 false；
- open gap 不得因“找到了任意论文/仓库”而批量标记为 satisfied 或 partially_satisfied；
- 所有 satisfied gap 必须具有可追溯 `evidence_delta`；
- 字段非空不等于语义有效；
- 规则 fallback 不得覆盖更高质量的 LLM 输出而不留痕；
- 负结果和 unresolved 结果必须保留。

---

# 1. 当前基线与已知问题

## 1.1 冻结基线

执行前记录并冻结：

- repository：`ZyfNO2/PaperAgent`
- branch：默认 `master`
- baseline commit：执行开始时的 HEAD
- previous verified baseline：Re8.0 authoritative artifacts
- recent patches：
  - Tailor 5-field upstream fix；
  - Method Family dataset/reproduction input fix；
  - Seed Repair title search；
  - Tailor Gate `assembly_plan.description` 容错。

必须将以下内容写入 `artifacts/re8_1/baseline_manifest.json`：

```json
{
  "repo": "ZyfNO2/PaperAgent",
  "branch": "master",
  "head_sha": "...",
  "python": "...",
  "node": "...",
  "model_provider": "...",
  "model_name": "...",
  "network_policy": "online",
  "reflection_gate_max_rounds": 2,
  "ablation_min_rows": 4,
  "seed_cases": ["vit_dr", "xlm_r", "yolo_steel"]
}
```

## 1.2 当前已知症状

1. 三个案例此前均 `runtime_pass=true`、`contract_pass=true`、`quality_pass=false`；
2. 三个案例此前均为 `fused_verdict=BLOCKED`；
3. `tailored_method.core_method` 跨案例为空；
4. Tailor Gate 存在 unresolved/cap；
5. novelty extractor 可能出现 schema/output quality 问题；
6. low-bar review 可能因为 work package 质量不足而 blocked；
7. Seed Repair 标题检索已有代码与单测，但尚缺真实端到端验证；
8. WP7 仍是静态 fixture，未接真实后端 API。

## 1.3 本阶段必须回答的根因问题

- Tailor 上游字段是否真的在真实链路中非空？
- 字段内容是否来自目标论文，而非模板或泛化改写？
- LLM 是否生成了 `core_method`，但被 parser、validator 或 fallback 丢弃？
- `generated_by` 是否能真实区分 rule fallback 与 LLM output？
- Tailor Gate 的拒绝来自内容不足、结构错误、证据缺失，还是 cap 路由？
- Seed Repair 是否会把相似标题或不存在论文误标为 verified？
- quality_pass 失败是否由真实科研证据不足导致，而非工程字段缺失？

---

# 2. WP0：版本冻结、单题 Smoke 与诊断采集

## 2.1 目的

先用最接近成功的 `vit_dr` 做低成本 smoke，确认最新补丁是否进入真实链路，避免三个案例全部运行后才发现链路无效。

## 2.2 执行顺序

严格按以下顺序：

1. 冻结 HEAD 与环境；
2. 跑全部 Re8 相关单元测试；
3. 跑 `vit_dr`；
4. 按分支矩阵判定是否继续；
5. `vit_dr` 通过后跑 `xlm_r`；
6. `xlm_r` 通过后跑 `yolo_steel`；
7. 三案例均完成后，才允许将最新补丁标记为 end-to-end verified。

## 2.3 Smoke 升级矩阵

| vit_dr | xlm_r | yolo_steel | 判定 |
|---|---|---|---|
| FAIL | 不运行 | 不运行 | 最新补丁未进入有效链路或引入回归 |
| PASS | FAIL | 不运行 | 存在单案例过拟合或领域依赖 |
| PASS | PASS | FAIL | 跨领域鲁棒性不足 |
| PASS | PASS | PASS | 允许进入 WP1 收敛诊断 |

这里的 PASS 仅表示：

- 无 crash；
- runtime/contract 无回归；
- 诊断数据完整；
- 上游五字段与 Tailor 输出均可观测。

不要求 WP0 即达到 `quality_pass=true`。

## 2.4 必采集诊断字段

每个案例必须保存：

1. 原始 seed 输入；
2. SeedCard 全量结构；
3. `task_definition`；
4. `method_summary`；
5. `dataset_and_metrics`；
6. `reproduction_environment`；
7. `limitations`；
8. Method Family 输入与输出；
9. Tailor prompt 完整文本或哈希与版本；
10. 原始 LLM response；
11. parser 前文本；
12. parser 后结构；
13. schema validator 结果；
14. fallback 触发原因；
15. `generated_by`；
16. gate 输入快照；
17. gate 输出 verdict/rationale；
18. round index；
19. model/provider/temperature；
20. final package 与 evidence ledger。

保存位置：

```text
artifacts/re8_1/wp0/<case>/
  run.json
  trace.jsonl
  tailor_prompt.txt
  tailor_raw.txt
  tailor_parsed.json
  gate_snapshots.json
  final_package.json
```

## 2.5 WP0 验收

- [ ] HEAD 与环境清单已冻结；
- [ ] Re8 测试全部通过；
- [ ] vit_dr 诊断产物完整；
- [ ] 无 runtime/contract 回归；
- [ ] 上游五字段的真实值可见；
- [ ] Tailor raw/parsed/validated/fallback 四层均可见；
- [ ] xlm_r 与 yolo_steel 按升级规则完成；
- [ ] 三案例结果写入 `artifacts/re8_1/wp0/decision.md`。

---

# 3. WP1：Tailor 收敛诊断与针对性修复

## 3.1 诊断优先原则

禁止直接继续“补字段”或“放宽 Gate”。必须先将每个失败归类，再只修复已证实的故障分支。

## 3.2 六类故障分类

### A. `UPSTREAM_EMPTY`

上游字段确实为空或缺失。

检查：

- fulltext 是否下载成功；
- paper_understanding 是否消费 `raw_input.pdf_bytes`；
- SeedCard 字段路径是否一致；
- method_family 是否收到完整输入；
- Tailor adapter 是否真正渲染字段。

### B. `UPSTREAM_SEMANTIC_LOW`

字段非空，但内容是标题扩写、模板话术或错误摘要。

检查：

- 是否能指向全文证据；
- 是否包含数据集、方法机制、限制；
- 是否与目标论文一致；
- 是否存在跨 seed 污染。

### C. `LLM_OMISSION`

Prompt 已包含充分信息，但 LLM 未输出核心方法或结构。

修复方向：

- 调整 Prompt 层级与字段顺序；
- 增加显式输出合同；
- 提供正负例；
- 限制泛化句；
- 减少无关上下文；
- 必要时拆分一次生成任务。

### D. `PARSER_DROP`

Raw response 有有效字段，但 parser 后丢失。

修复方向：

- JSON repair；
- alias mapping；
- 容忍列表/字符串变体；
- 增加 parser regression tests；
- 保存无法解析片段，不得静默丢弃。

### E. `VALIDATOR_REJECT`

Parsed 结构存在，但 validator 因 schema 或规则过严拒绝。

修复方向：

- 区分结构错误与科研质量不足；
- validator 只负责合同，Gate 负责质量；
- 不允许 validator 用空 fallback 替代有效结构；
- 所有 reject 必须返回 reason code。

### F. `FALLBACK_OVERRIDE`

有效 LLM 输出被规则 fallback 覆盖，或 fallback 生成内容被误当作 LLM 主输出。

修复方向：

- `generated_by` 必须保存来源；
- 增加 `fallback_reason`；
- 保留 `pre_fallback_payload`；
- fallback 不得覆盖质量更高的字段；
- rule 生成内容不得直接满足 quality pass。

## 3.3 `generated_by` 合同

统一值域：

```text
llm
rule
hybrid
repaired_llm
unknown
```

必须同时记录：

```json
{
  "generated_by": "llm",
  "fallback_used": false,
  "fallback_reason": null,
  "parser_repaired": false,
  "validator_status": "pass"
}
```

仅有 `generated_by` 不足以判断根因，必须结合 raw、parsed、validator 与 fallback 记录。

## 3.4 Tailor 输出最低合同

```json
{
  "core_method": "non-empty method mechanism",
  "baseline": {
    "name": "...",
    "provenance": "..."
  },
  "modules": [
    {
      "name": "...",
      "source": "...",
      "input_semantics": "...",
      "output_semantics": "...",
      "integration_point": "...",
      "predicted_effect": "...",
      "failure_mode": "..."
    }
  ],
  "assembly_plan": {
    "description": "...",
    "data_flow": ["..."]
  },
  "ablation_matrix": [
    {"experiment_id": "baseline"},
    {"experiment_id": "module_a"},
    {"experiment_id": "module_b"},
    {"experiment_id": "full"}
  ]
}
```

## 3.5 禁止通过的泛化句

以下内容单独出现时不能满足 `core_method`：

- “加入注意力机制提升特征表达”；
- “采用多尺度融合提高性能”；
- “结合 Transformer 和 CNN”；
- “引入对比学习增强鲁棒性”；
- “使用 RAG 提升结果质量”；
- “通过模块组合获得更好效果”。

必须说明：

- 加在哪里；
- 输入输出是什么；
- 解决哪个机制问题；
- 如何训练；
- 如何验证；
- 哪种结果会否证该设计。

## 3.6 WP1 验收

- [ ] 三案例均获得唯一主故障分类；
- [ ] 每个分类都有诊断证据；
- [ ] 修复只针对已证实分支；
- [ ] 新增 regression tests；
- [ ] 至少 2/3 案例 `core_method` 非空；
- [ ] `assembly_plan` 明确 baseline、模块和连接位置；
- [ ] ablation 至少 4 项；
- [ ] 不得仅靠 `assembly_plan.description` 兜底达到 quality pass；
- [ ] rule fallback 不得冒充 LLM 输出。

---

# 4. WP2：Seed Repair 标题解析基准与误验收防护

## 4.1 测试集规模

建立 20 条 title-only seed 基准：

| 类型 | 数量 |
|---|---:|
| 精确标题、完整元数据 | 6 |
| 精确标题、作者缺失 | 2 |
| 轻微拼写/标点/大小写扰动 | 3 |
| 标题缩写或副标题缺失 | 2 |
| 高相似或同名论文 | 3 |
| 年份或作者冲突 | 2 |
| 明确不存在的论文 | 2 |

至少覆盖 CV、NLP、RAG/IR、系统或数据库等多个领域。

## 4.2 Ground Truth 合同

每条样本保存：

```json
{
  "case_id": "title-001",
  "query_title": "...",
  "query_authors": ["..."],
  "query_year": 2024,
  "ground_truth_title": "...",
  "ground_truth_doi": "...",
  "acceptable_aliases": ["..."],
  "expected_status": "verified",
  "expected_top1_doi": "...",
  "negative_reason": null
}
```

## 4.3 能力补全

Seed Repair 候选评分至少考虑：

- 标题归一化相似度；
- DOI 是否存在；
- 作者姓氏重合；
- 年份一致性；
- 来源一致性；
- 标题长度与副标题差异；
- Crossref / Semantic Scholar 冲突。

输出必须包含：

```json
{
  "candidate_title": "...",
  "doi": "...",
  "source": "crossref",
  "title_score": 0.93,
  "author_score": 0.5,
  "year_score": 1.0,
  "confidence": 0.88,
  "decision": "verified"
}
```

## 4.4 强制安全规则

- 不存在论文不得标记为 verified；
- 同名论文无作者/年份支持时应返回 ambiguous；
- Crossref 与 Semantic Scholar 冲突时不得静默选择；
- 低置信度候选不得自动晋升 verified；
- 用户提供 DOI 与标题冲突时应记录 conflict，而不是覆盖输入。

## 4.5 指标

- Top-1 accuracy；
- false verification rate；
- ambiguous recall；
- nonexistent rejection rate；
- source disagreement rate；
- confidence calibration。

最低要求：

- 精确标题 Top-1 accuracy ≥ 90%；
- 扰动标题成功率 ≥ 70%；
- nonexistent rejection rate = 100%；
- false verification rate = 0%；
- 同名冲突样本不得无证据 verified。

## 4.6 WP2 验收

- [ ] 20 条测试集落盘；
- [ ] 每条有 ground truth；
- [ ] 候选评分可解释；
- [ ] 冲突保留；
- [ ] false verification rate=0；
- [ ] 失败样本写入 error taxonomy。

---

# 5. WP3：七字段语义质量与研究方法合同

## 5.1 七字段

每个案例检查：

1. `task_definition`
2. `method_summary`
3. `dataset_and_metrics`
4. `reproduction_environment`
5. `limitations`
6. `assembly_plan.description`
7. `core_method`

## 5.2 三层验收

### Structural

- 类型正确；
- 非空；
- schema 合法；
- 无明显截断或列表/字符串错位。

### Traceability

- 能映射到全文、SeedCard 或检索证据；
- 记录 provenance；
- 不允许凭标题自动扩写成事实。

### Semantic

- 与目标论文一致；
- 包含实际机制；
- 包含数据/指标或明确 unknown；
- limitations 至少包含一项可验证限制；
- core_method 可转化为实现步骤与实验假设。

## 5.3 自动与人工审查分离

机器检查负责：

- schema；
- 非空；
- provenance 字段；
- ablation 数量；
- 禁止泛化句；
- 字段一致性。

人工或高质量 LLM 审查负责：

- 是否准确描述论文；
- 是否存在错误归因；
- 是否具备可证伪性；
- 模块是否语义兼容；
- 是否只是换词包装。

## 5.4 方法级验收

至少包含：

- baseline 冻结说明；
- gap 与 falsifiable hypothesis；
- 模块 provenance；
- 输入输出语义；
- integration contract；
- 失败模式；
- ablation matrix；
- stop condition。

## 5.5 WP3 验收

- [ ] 三案例七字段均完成三层检查；
- [ ] 至少 2/3 案例 `core_method` 通过语义检查；
- [ ] 所有模块有 provenance；
- [ ] 至少 4 项 ablation；
- [ ] 至少一个可证伪假设；
- [ ] 泛化句不能单独通过；
- [ ] assembly_plan 与 core_method 不自相矛盾。

---

# 6. WP4：Verdict 一致性、质量恢复与假阳性防回归

## 6.1 分层 verdict

必须独立输出：

- seed_audit verdict；
- tailor_gate verdict；
- novelty verdict；
- low_bar verdict；
- final_review verdict；
- fused_verdict；
- runtime_pass；
- contract_pass；
- quality_pass。

## 6.2 一致性规则

- seed unresolved → `BLOCKED`；
- Tailor 无有效方法规范 → 不得 `GO`；
- novelty reject + Tailor GO → 至多 `RISKY`；
- open critical gap → 不得 `GO`；
- any unresolved gate → `quality_pass=false`；
- `fused_verdict=BLOCKED` → `quality_pass=false`；
- 无 traceable evidence delta → 相关 gap 不得 satisfied；
- rule-only method → 不得直接 quality pass。

## 6.3 阶段目标

Re8.1 不要求三案例全 GO，但要求：

1. 三案例均不得因“字段不可观测”而 BLOCKED；
2. 至少 2/3 案例达到 `CONDITIONAL`、`RISKY` 或 `GO`；
3. 至少 1/3 案例达到 `quality_pass=true`；
4. 所有 satisfied gap 均有证据归因；
5. 所有 Gate 冲突均有 reason code。

## 6.4 回归测试

至少新增：

- BLOCKED 不得 quality true；
- unresolved 不得 quality true；
- rule fallback 不得 quality true；
- gap 无 evidence delta 不得 satisfied；
- core_method 空且 assembly_plan 非空时可继续诊断，但不得自动 quality pass；
- valid LLM output 不得被 fallback 覆盖；
- parser repair 后必须标记 `repaired_llm`。

## 6.5 WP4 验收

- [ ] 所有 verdict 可追踪；
- [ ] 无假阳性；
- [ ] 至少 2/3 非 BLOCKED；
- [ ] 至少 1/3 quality true；
- [ ] satisfied gap 全部可追溯；
- [ ] 冲突有 reason code。

---

# 7. WP5：真实 API 与前端诚实呈现

## 7.1 输入能力

真实前端支持：

- DOI；
- URL；
- title；
- PDF。

## 7.2 模式

- Full Agent；
- Lite Chain；
- Offline Replay；
- Online/Offline 网络策略。

## 7.3 必须展示

- seed resolution 状态；
- fulltext 状态；
- evidence gaps；
- Tailor method；
- Gate verdict 与 rationale；
- repair round；
- fused verdict；
- runtime/contract/quality；
- final package 导出；
- error reason code。

## 7.4 五类错误必须诚实显示

1. seed ambiguous/not found；
2. fulltext unavailable；
3. Tailor parse/schema failure；
4. Gate unresolved/capped；
5. backend/network/model failure。

禁止：

- 将 BLOCKED 显示为 success；
- 隐藏 fallback；
- 隐藏 repair cap；
- 空 package 仍允许“成功导出”；
- 以静态 fixture 冒充真实 API。

## 7.5 WP5 验收

- [ ] 前端调用真实 API；
- [ ] 四种输入均可提交；
- [ ] Gate 循环可见；
- [ ] 五类错误可见；
- [ ] 结果与后端 JSON 一致；
- [ ] 可导出真实 final package；
- [ ] 无 fixture 冒充生产结果。

---

# 8. 风险预案

| 风险 | 早期信号 | 预防/处理 |
|---|---|---|
| 补丁未进入真实链路 | 五字段仍全部为空 | WP0 保存节点级输入输出，先查字段路径 |
| Prompt 调优制造假阳性 | 内容变长但仍泛化 | 使用语义检查与禁止泛化句 |
| Parser 静默丢字段 | raw 有、parsed 无 | 保存 pre/post parser 与 reason code |
| Validator 越权 | schema pass 但质量 reject 混杂 | 合同检查与质量 Gate 分离 |
| Fallback 覆盖 LLM | generated_by=rule 且 raw 有效 | 保存 pre_fallback_payload，禁止覆盖 |
| 标题检索误验收 | 相似标题被 verified | false verification rate 必须为 0 |
| 同名论文误匹配 | 无作者年份也 verified | 返回 ambiguous，要求冲突证据 |
| Gate 为求通过被放宽 | rounds 或 ablation 被修改 | 需用户批准，写入 baseline manifest |
| 三案例运行成本过高 | 单题已显示链路失败 | vit_dr smoke 失败即停止升级 |
| 前端掩盖后端失败 | UI success、后端 BLOCKED | 端到端状态一致性测试 |

---

# 9. 验收、NO-GO 与交接

## 9.1 Re8.1 PASS 条件

以下条件必须全部满足：

### 工程层

- [ ] 最新补丁在三案例中完成真实重跑；
- [ ] runtime/contract 无回归；
- [ ] 诊断数据完整；
- [ ] regression tests 全部通过；
- [ ] 前端真实 API 可用。

### Tailor 层

- [ ] 三案例主故障均已分类；
- [ ] 至少 2/3 `core_method` 非空且语义有效；
- [ ] baseline/modules/integration/ablation 完整；
- [ ] rule fallback 不冒充 LLM。

### Seed Repair 层

- [ ] 20 条基准完成；
- [ ] false verification rate=0；
- [ ] nonexistent rejection rate=100%；
- [ ] 同名冲突不误验收。

### 科研质量层

- [ ] 至少 2/3 案例非 BLOCKED；
- [ ] 至少 1/3 `quality_pass=true`；
- [ ] satisfied gap 全部可追溯；
- [ ] 无假阳性；
- [ ] 至少一个方法具有可证伪假设和公平 ablation。

## 9.2 NO-GO 条件

### A. External dependency NO-GO

适用：

- API 长期不可用；
- 权限或付费资源缺失；
- 目标论文无合法全文来源。

要求：失败日志、重试记录、替代来源尝试。

### B. Architectural NO-GO

适用：

- 根因需要破坏 Re8.1 明确冻结的核心接口；
- 无兼容层修复路径；
- 需要单独架构 SOP。

要求：受影响模块、不可兼容原因、下一 SOP 最小设计。

### C. Evidence NO-GO

适用：

- 无法获得支持科研结论的证据；
- baseline、数据、指标或机制证据缺失；
- 公平对照下收益消失。

要求：保留负结果，不得降级为泛化“创新”。

### D. Resource NO-GO

适用：

- 计算、标注或外部服务成本超出批准预算。

要求：成本估算、最低替代方案、用户确认。

以下情况不得归为“超出 SOP 范围”：

- Prompt 不稳定；
- parser 丢字段；
- schema 不兼容；
- fallback 覆盖；
- 单案例失败；
- 测试不足；
- 修复引入回归；
- 缺少诊断日志。

这些均属于 Re8.1 直接职责。

## 9.3 硬停条件

出现以下任一情况立即停止扩展执行并记录：

1. runtime 或 contract 相比 Re8.0 回归；
2. `quality_pass=true` 与 `BLOCKED/unresolved` 同时出现；
3. open gap 被无归因批量升级；
4. false verification 出现；
5. 有效 LLM 输出被 fallback 静默覆盖；
6. 为求通过修改 `REFLECTION_GATE_MAX_ROUNDS=2`；
7. 为求通过将 ablation 降至 4 以下；
8. 伪造、补写或推测未运行实验结果。

第 6、7 项仅可在向用户报告并获得明确批准后调整。

## 9.4 自主修复边界

允许自主修复：

- 字段路径；
- parser；
- schema alias；
- validator 合同；
- Prompt 结构；
- logging/trace；
- 回归测试；
- 前端状态映射。

必须报告用户后再修改：

- Gate 标准；
- 最大 repair rounds；
- ablation 最低数量；
- quality_pass 定义；
- evidence attribution 规则；
- 研究结论与 novelty 标准。

## 9.5 交接包

最终必须生成：

```text
artifacts/re8_1/final/
  baseline_manifest.json
  vit_dr.json
  xlm_r.json
  yolo_steel.json
  seed_repair_benchmark.json
  seed_repair_metrics.json
  tailor_diagnosis_matrix.json
  verdict_consistency_report.json
  frontend_e2e_report.json
  decision.md
  checklist.md
```

`decision.md` 必须包含：

1. HEAD commit；
2. delivered scope；
3. root causes；
4. fixes；
5. three-case comparison before/after；
6. seed benchmark metrics；
7. remaining risks；
8. PASS / REVISE / NO-GO；
9. 下一 SOP 建议。

---

# 10. 建议执行顺序

```text
WP0 版本冻结与 vit_dr smoke
  ↓
WP1 Tailor 根因诊断与最小修复
  ↓
重新跑 vit_dr
  ↓
通过后跑 xlm_r / yolo_steel
  ↓
WP2 Seed Repair 20 条基准
  ↓
WP3 七字段与方法语义验收
  ↓
WP4 Verdict 一致性与质量恢复
  ↓
WP5 真实 API 与前端 E2E
  ↓
Final decision + handoff
```

禁止在 WP1 根因未确认前直接并行大规模 Prompt 调优、前端美化或跨领域扩展。

---

# 11. 最终判定标准

- `GO`：Re8.1 PASS 条件全部满足；
- `REVISE`：工程链路可修复，但 Tailor 或 Seed Repair 指标仍未达标；
- `NO-GO`：出现 §9.2 合法 NO-GO，且已有证据证明当前范围内不可修复；
- `BLOCKED`：外部依赖、权限或资源尚未解除，不能将其伪装为技术完成。

本 SOP 的核心成功标准不是“让模型说出更像论文的话”，而是：

> 让 PaperAgent 能区分真实方法、字段占位、规则兜底与证据不足，并在真实种子论文上稳定地产生可追溯、可实现、可证伪的研究方案。
