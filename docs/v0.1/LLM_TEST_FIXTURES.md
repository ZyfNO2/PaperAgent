# PaperAgent v0.1 LLM 模拟输入输出与测试 Fixtures

> Version: `v0.1`  
> Status: `FROZEN TEST CONTRACT`  
> Purpose: 规定 LLM 节点在离线 TDD 中接收的模拟输入和必须返回的固定中间回复。

## 1. Fixture 机制

Fake LLM 不读取 Prompt 内容选择答案，只接受以下 key：

```python
FixtureKey(
    task="planning | evidence_synthesis | method_design | report",
    scenario="...",
    call_index=0,
    fixture_version="v0.1",
)
```

返回值是 fixture 文件中的原始 JSON 字符串，再经过与真实 Provider 相同的：

```text
JSON decode
→ Pydantic validation
→ semantic validation
→ normalized artifact
```

Fixture 路径：

```text
tests/fixtures/llm/v0_1/<task>/<scenario>__call_<index>.json
```

所有 `fixture://` locator 都是明确的合成测试资源，不代表真实论文、数据集或仓库。

---

## 2. Canonical Scenario：`happy_path`

### 2.1 用户模拟输入

```json
{
  "question": "如何评估一个小型检索增强生成系统的引用可靠性？",
  "domain_hint": "information retrieval",
  "required_constraints": [
    "只设计最小可运行实验",
    "不得把未验证来源作为事实",
    "单机环境可执行"
  ],
  "optional_preferences": [
    "优先使用确定性指标"
  ],
  "user_material_refs": []
}
```

固定 RunContext：

```json
{
  "schema_version": "0.1",
  "engine_version": "v0.1",
  "run_id": "run-test-001",
  "thread_id": "thread-test-001",
  "created_at": "2026-01-01T00:00:00Z",
  "model_profile": "fake-structured-v0.1",
  "network_policy": "offline",
  "budgets": {
    "max_llm_calls": 6,
    "max_retrieval_rounds": 2,
    "max_method_repairs": 1,
    "max_queries_per_round": 5,
    "max_evidence_items": 30
  }
}
```

### 2.2 Planning 输入投影

```json
{
  "task": "planning",
  "request": {
    "question": "如何评估一个小型检索增强生成系统的引用可靠性？",
    "domain_hint": "information retrieval",
    "required_constraints": [
      "只设计最小可运行实验",
      "不得把未验证来源作为事实",
      "单机环境可执行"
    ],
    "optional_preferences": [
      "优先使用确定性指标"
    ]
  },
  "budgets": {
    "max_queries_per_round": 5,
    "max_retrieval_rounds": 2
  },
  "available_source_types": [
    "paper",
    "dataset",
    "repository",
    "web",
    "user_material"
  ]
}
```

### 2.3 Planning 固定回复

Fixture key：`planning + happy_path + 0 + v0.1`

```json
{
  "schema_version": "0.1",
  "status": "ready",
  "problem_statement": "设计一个资源受限但可复现的评估流程，用于判断检索增强生成系统的回答是否被其引用证据真实支持。",
  "scope": "只覆盖离线问答评估、证据引用匹配和最小消融，不覆盖大规模在线服务或训练新模型。",
  "research_questions": [
    "回答中的关键主张是否能被引用片段直接支持？",
    "检索模块与生成模块分别对引用错误贡献多少？"
  ],
  "evidence_gaps": [
    {
      "gap_id": "gap-support",
      "description": "需要定义主张与引用证据之间的支持关系及可计算指标。",
      "required": true,
      "minimum_accepted_items": 1
    },
    {
      "gap_id": "gap-ablation",
      "description": "需要确定能区分检索错误和生成错误的最小消融设计。",
      "required": true,
      "minimum_accepted_items": 1
    }
  ],
  "search_queries": [
    {
      "query_id": "query-support-01",
      "gap_id": "gap-support",
      "query": "citation support evaluation claim evidence alignment",
      "source_types": ["paper", "web"]
    },
    {
      "query_id": "query-ablation-01",
      "gap_id": "gap-ablation",
      "query": "retrieval generation error ablation evaluation",
      "source_types": ["paper", "web"]
    }
  ],
  "success_criteria": [
    "每个关键主张都能追溯到 accepted evidence",
    "指标可以在单机离线运行",
    "实验能分别暴露检索失败和生成失败"
  ],
  "risks": [
    "合成测试集可能高估真实领域泛化",
    "自动支持度指标仍需要人工抽检"
  ],
  "clarification_question": null,
  "block_reason": null
}
```

Planning 测试断言：

- `status == ready`；
- 两个 query 均绑定现有 gap；
- query 数量不超过 5；
- 回复不包含任何外部论文、数据集或仓库的存在性声明。

### 2.4 Search/Verification 固定 Evidence 输入

以下不是 LLM 回复，而是提供给后续 LLM 节点的固定 accepted evidence：

```json
{
  "items": [
    {
      "evidence_id": "ev-support-001",
      "source_type": "user_material",
      "title": "Synthetic Claim-Support Evaluation Note",
      "locator": "fixture://evidence/ev-support-001",
      "retrieved_at": "2026-01-01T00:01:00Z",
      "verification_status": "accepted",
      "supports_gap_ids": ["gap-support"],
      "summary": "将回答拆为原子主张，并逐条判断引用片段是否直接支持、部分支持或不支持，可计算 supported claims / total claims。",
      "content_hash": "sha256:test-support-001"
    },
    {
      "evidence_id": "ev-ablation-001",
      "source_type": "user_material",
      "title": "Synthetic Retrieval-Generation Ablation Note",
      "locator": "fixture://evidence/ev-ablation-001",
      "retrieved_at": "2026-01-01T00:01:01Z",
      "verification_status": "accepted",
      "supports_gap_ids": ["gap-ablation"],
      "summary": "使用固定 gold context、正常检索 context 和打乱 context 三个条件，可以区分检索质量与生成忠实度的影响。",
      "content_hash": "sha256:test-ablation-001"
    },
    {
      "evidence_id": "ev-rejected-001",
      "source_type": "web",
      "title": "Synthetic Unverified Marketing Claim",
      "locator": "fixture://evidence/ev-rejected-001",
      "retrieved_at": "2026-01-01T00:01:02Z",
      "verification_status": "rejected",
      "supports_gap_ids": ["gap-support"],
      "summary": "未经验证的营销性结论。",
      "content_hash": "sha256:test-rejected-001"
    }
  ],
  "accepted_ids": ["ev-support-001", "ev-ablation-001"],
  "rejected_ids": ["ev-rejected-001"],
  "pending_ids": [],
  "failed_verification_ids": [],
  "coverage_by_gap": {
    "gap-support": 1,
    "gap-ablation": 1
  },
  "conflicts": []
}
```

Context Builder 必须排除 `ev-rejected-001`。

### 2.5 Evidence Synthesis 输入投影

```json
{
  "task": "evidence_synthesis",
  "plan": {
    "problem_statement": "设计一个资源受限但可复现的评估流程，用于判断检索增强生成系统的回答是否被其引用证据真实支持。",
    "evidence_gap_ids": ["gap-support", "gap-ablation"]
  },
  "accepted_evidence": [
    {
      "evidence_id": "ev-support-001",
      "supports_gap_ids": ["gap-support"],
      "summary": "将回答拆为原子主张，并逐条判断引用片段是否直接支持、部分支持或不支持，可计算 supported claims / total claims。"
    },
    {
      "evidence_id": "ev-ablation-001",
      "supports_gap_ids": ["gap-ablation"],
      "summary": "使用固定 gold context、正常检索 context 和打乱 context 三个条件，可以区分检索质量与生成忠实度的影响。"
    }
  ],
  "coverage_by_gap": {
    "gap-support": 1,
    "gap-ablation": 1
  },
  "conflicts": []
}
```

### 2.6 Evidence Synthesis 固定回复

Fixture key：`evidence_synthesis + happy_path + 0 + v0.1`

```json
{
  "schema_version": "0.1",
  "gap_assessments": [
    {
      "gap_id": "gap-support",
      "status": "supported",
      "evidence_ids": ["ev-support-001"],
      "summary": "可以用原子主张级支持率作为最小引用可靠性指标。",
      "limitations": [
        "支持关系标签仍需人工标注或抽检"
      ]
    },
    {
      "gap_id": "gap-ablation",
      "status": "supported",
      "evidence_ids": ["ev-ablation-001"],
      "summary": "三种 context 条件足以构成最小检索—生成消融。",
      "limitations": [
        "该消融不能覆盖所有真实检索分布变化"
      ]
    }
  ],
  "verified_findings": [
    {
      "claim_id": "claim-support-rate",
      "text": "原子主张级支持率可以作为最小引用可靠性指标。",
      "evidence_ids": ["ev-support-001"]
    },
    {
      "claim_id": "claim-context-ablation",
      "text": "固定 gold、正常检索和打乱 context 可用于区分两类错误来源。",
      "evidence_ids": ["ev-ablation-001"]
    }
  ],
  "conflicts": [],
  "feasibility": "feasible",
  "limitations": [
    "当前证据为合成测试材料，仅证明流程合同可执行，不证明真实研究结论"
  ]
}
```

测试断言：

- 只引用两个 accepted IDs；
- 不出现 `ev-rejected-001`；
- 明确说明 synthetic fixture 的限制。

### 2.7 Method Design 输入投影

```json
{
  "task": "method_design",
  "problem_statement": "设计一个资源受限但可复现的引用可靠性评估流程。",
  "verified_findings": [
    {
      "claim_id": "claim-support-rate",
      "evidence_ids": ["ev-support-001"]
    },
    {
      "claim_id": "claim-context-ablation",
      "evidence_ids": ["ev-ablation-001"]
    }
  ],
  "constraints": [
    "只设计最小可运行实验",
    "单机环境可执行"
  ],
  "repair_reason": null
}
```

### 2.8 Method Design 固定回复

Fixture key：`method_design + happy_path + 0 + v0.1`

```json
{
  "schema_version": "0.1",
  "status": "proposed",
  "baseline": {
    "name": "single-condition RAG evaluation",
    "description": "只在正常检索 context 下测量回答正确率和引用支持率。"
  },
  "modules": [
    {
      "module_id": "module-claim-split",
      "name": "claim segmentation",
      "purpose": "将回答拆分为可独立核验的原子主张。"
    },
    {
      "module_id": "module-support-label",
      "name": "citation support labeling",
      "purpose": "为每个主张标记 supported、partial 或 unsupported。"
    },
    {
      "module_id": "module-context-ablation",
      "name": "context condition ablation",
      "purpose": "比较 gold、retrieved 和 shuffled context。"
    }
  ],
  "integration_contracts": [
    {
      "from_module": "module-claim-split",
      "to_module": "module-support-label",
      "input": "atomic claims with citation references",
      "output": "claim-level support labels"
    }
  ],
  "problem_method_insight": "引用可靠性需要同时测量证据是否被检索到，以及生成内容是否忠实使用该证据。",
  "falsifiable_hypothesis": "若主要错误来自检索，则 gold context 条件下的主张支持率应比正常检索条件至少高 0.15；若差值低于 0.15，则该假设不成立。",
  "minimum_key_experiment": {
    "name": "three-context evaluation",
    "conditions": ["gold_context", "retrieved_context", "shuffled_context"],
    "metrics": ["claim_support_rate", "answer_accuracy"],
    "baseline": "retrieved_context",
    "success_threshold": "gold_context claim_support_rate - retrieved_context claim_support_rate >= 0.15"
  },
  "ablations": [
    {
      "name": "remove claim segmentation",
      "change": "直接对整段回答判断支持度",
      "expected_observation": "错误定位粒度下降"
    },
    {
      "name": "remove shuffled context",
      "change": "只比较 gold 与 retrieved context",
      "expected_observation": "对生成器无证据时行为的诊断能力下降"
    }
  ],
  "risks": [
    "人工支持度标签存在主观差异",
    "样本量过小时 0.15 阈值不稳定"
  ],
  "stop_conditions": [
    "无法获得至少 30 个带引用回答样本",
    "标注者对支持关系的一致性低于预设阈值"
  ],
  "evidence_ids": ["ev-support-001", "ev-ablation-001"]
}
```

### 2.9 Report 输入投影

```json
{
  "task": "report",
  "quality": {
    "verdict": "pass",
    "reason_codes": []
  },
  "accepted_evidence_ids": [
    "ev-support-001",
    "ev-ablation-001"
  ],
  "method_status": "proposed"
}
```

### 2.10 Report 固定回复

Fixture key：`report + happy_path + 0 + v0.1`

```json
{
  "schema_version": "0.1",
  "status": "completed",
  "executive_summary": "建议以主张级引用支持率为核心指标，并通过 gold、正常检索和打乱 context 三条件实验区分检索错误与生成错误。",
  "verified_findings": [
    {
      "text": "主张级支持率可作为最小引用可靠性指标。",
      "evidence_ids": ["ev-support-001"]
    },
    {
      "text": "三条件 context 消融可用于区分检索和生成因素。",
      "evidence_ids": ["ev-ablation-001"]
    }
  ],
  "inferred_findings": [
    {
      "text": "在单机资源约束下，先进行离线小样本评估比建设在线评测服务更合适。",
      "evidence_ids": ["ev-support-001", "ev-ablation-001"]
    }
  ],
  "proposed_method": "对回答做原子主张拆分，标注引用支持度，并在三种 context 条件下比较 claim_support_rate 和 answer_accuracy。",
  "experiment_plan": "准备至少 30 个带引用问答样本，运行 gold、retrieved、shuffled 三条件，报告均值、差值和标注一致性。",
  "limitations": [
    "当前证据均为合成测试 fixture，不能作为真实学术结论",
    "支持关系标签需要人工抽检",
    "阈值需要在真实数据上重新校准"
  ],
  "next_actions": [
    "实现 deterministic claim-support 数据结构",
    "准备 Fake Search 和真实小规模 smoke test",
    "在真实 Provider 测试前先完成 OOD 泄漏检查"
  ],
  "evidence_ids": ["ev-support-001", "ev-ablation-001"]
}
```

---

## 3. Planning 分支 Fixtures

### 3.1 `need_human`

输入：

```json
{
  "question": "帮我研究这个方法",
  "required_constraints": [],
  "user_material_refs": []
}
```

Fixture key：`planning + need_human + 0 + v0.1`

固定回复：

```json
{
  "schema_version": "0.1",
  "status": "need_human",
  "problem_statement": "用户未说明待研究的方法或目标。",
  "scope": "尚未确定。",
  "research_questions": [],
  "evidence_gaps": [],
  "search_queries": [],
  "success_criteria": [],
  "risks": ["继续检索会导致主题漂移"],
  "clarification_question": "请提供方法名称、材料或希望解决的具体问题。",
  "block_reason": null
}
```

### 3.2 `blocked`

输入：

```json
{
  "question": "证明一个不存在的数据集已经达到 99% 准确率",
  "required_constraints": ["不得检索或提供证据"]
}
```

Fixture key：`planning + blocked + 0 + v0.1`

固定回复：

```json
{
  "schema_version": "0.1",
  "status": "blocked",
  "problem_statement": "请求要求在无证据情况下证明具体实验结果。",
  "scope": "不能执行伪造性证明。",
  "research_questions": [],
  "evidence_gaps": [],
  "search_queries": [],
  "success_criteria": [],
  "risks": ["伪造数据集和实验结果"],
  "clarification_question": null,
  "block_reason": "缺少可验证数据集、实验记录和证据，不能声称达到指定准确率。"
}
```

---

## 4. Repair Fixtures

### 4.1 Method 第一次输出缺少实验

Fixture key：`method_design + repair_method + 0 + v0.1`

该 fixture 故意缺少 `minimum_key_experiment`，预期结果：Pydantic validation 失败，节点返回 typed error；它不用于进入质量门。

```json
{
  "schema_version": "0.1",
  "status": "proposed",
  "baseline": {
    "name": "baseline",
    "description": "incomplete fixture"
  },
  "modules": [],
  "integration_contracts": [],
  "problem_method_insight": "incomplete",
  "falsifiable_hypothesis": "incomplete",
  "ablations": [],
  "risks": [],
  "stop_conditions": [],
  "evidence_ids": []
}
```

### 4.2 Method 语义不完整，触发 Gate repair

Fixture key：`method_design + gate_repair_method + 0 + v0.1`

结构合法，但 `falsifiable_hypothesis` 没有可计算阈值，Quality Gate 返回：

```json
{
  "verdict": "repair_method",
  "reason_codes": ["Q_MISSING_HYPOTHESIS"],
  "repair_target": "method",
  "missing_gap_ids": [],
  "invalid_evidence_ids": [],
  "human_question": null
}
```

第二次固定回复：`method_design + gate_repair_method + 1 + v0.1`，使用 happy_path Method 回复并将 hypothesis 保持含 `0.15` 阈值。

---

## 5. Invalid Response Fixtures

路径：`tests/fixtures/llm/v0_1/invalid/`

### `malformed_json.txt`

```text
{"schema_version":"0.1","status":"ready",
```

预期：`LLM_RESPONSE_JSON_INVALID`，禁止 fallback。

### `unknown_field.json`

```json
{
  "schema_version": "0.1",
  "status": "ready",
  "unexpected_answer": "legacy test answer"
}
```

预期：Pydantic `extra_forbidden`。

### `unknown_evidence_id.json`

```json
{
  "schema_version": "0.1",
  "gap_assessments": [],
  "verified_findings": [
    {
      "claim_id": "claim-invalid",
      "text": "unsupported",
      "evidence_ids": ["ev-does-not-exist"]
    }
  ],
  "conflicts": [],
  "feasibility": "unknown",
  "limitations": []
}
```

预期：`SEMANTIC_UNKNOWN_EVIDENCE_ID`。

### `provider_timeout`

Fake LLM 不返回 payload，而是抛出：

```python
ProviderTimeoutError(
    provider="fake_llm",
    task="planning",
    retryable=True,
)
```

预期：按 Provider policy 有界重试；超过上限后写 `llm.failed` Trace。

---

## 6. Blocked Report Fixture

Fixture key：`report + blocked + 0 + v0.1`

```json
{
  "schema_version": "0.1",
  "status": "blocked",
  "executive_summary": "当前请求无法形成有证据支持的研究建议。",
  "verified_findings": [],
  "inferred_findings": [],
  "proposed_method": null,
  "experiment_plan": null,
  "limitations": [
    "缺少可验证输入或必要证据",
    "系统未生成或猜测不存在的实验结果"
  ],
  "next_actions": [
    "补充具体研究对象和可验证材料"
  ],
  "evidence_ids": []
}
```

---

## 7. OOD 输入 Fixtures

每个 OOD case 只规定输入和禁止泄漏断言，不规定唯一自然语言答案：

| Scenario | Input summary | Required outcome |
|---|---|---|
| ood_cv | 小样本工业缺陷检测评估 | 正常规划，不出现其他领域固定 baseline |
| ood_nlp | 方言文本分类数据不足 | 正常规划或 need_human |
| ood_recsys | 冷启动推荐离线评估 | 正常规划 |
| ood_timeseries | 传感器异常检测 | 正常规划 |
| ood_database | 数据库索引策略评估 | 正常规划，不强行论文方法化 |
| ood_software | API 迁移回归测试 | 正常规划，不生成学术实验结果 |
| ood_underspecified | “帮我研究一下” | need_human |
| ood_impossible | 无数据证明固定成绩 | blocked |

OOD 测试断言：

- 结果通过 schema；
- 路由合理；
- 不出现 legacy 禁止实体；
- 不引用未提供 Evidence ID；
- 图有界终止。

## 8. Fixture 修改规则

- 修改固定回复必须解释是合同变化还是 Bug 修复；
- 不能为了让生产代码通过而降低断言；
- 合同变化需要同步更新 `schema_version` 或 `fixture_version`；
- happy_path 固定回复必须保持合成资源标记；
- 不允许把真实 API 输出原样提交为 fixture，必须先脱敏、最小化和稳定化。
