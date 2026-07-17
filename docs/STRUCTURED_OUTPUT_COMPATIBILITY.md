# Structured Output 兼容性、校验与修复策略

> Status: ACTIVE ENGINEERING POLICY  
> Scope: PaperAgent LLM Provider、结构化输出合同、JSON 解析与修复  
> Last updated: 2026-07-17

## 1. 背景与已知问题

DeepSeek V4 Flash 通过 OpenCode 代理调用时，不支持 OpenAI 风格的：

```json
{
  "response_format": {
    "type": "json_schema"
  }
}
```

OpenAI-compatible 只表示请求和响应大体兼容 Chat Completions 形状，不代表代理、网关和模型完整支持 OpenAI Structured Outputs。

PaperAgent 不得把以下推断作为实现依据：

```text
endpoint 是 /chat/completions
→ 所以支持 response_format
→ 所以支持 json_schema strict mode
```

正确做法是将原生 Structured Outputs 视为可选优化能力，而不是 PaperAgent 结构化结果正确性的唯一保障。

## 2. 总体决策

PaperAgent 的统一结构化输出能力必须由以下部分共同构成：

```text
StructuredOutputContract
+ Provider capability resolution
+ ResponseEnvelope normalization
+ local JSON extraction
+ Pydantic validation
+ semantic validation
+ bounded repair
+ typed failure
```

允许的能力降级顺序：

```text
native json_schema
→ native json_object
→ prompt-only JSON
→ typed structured-output failure
```

对当前 DeepSeek V4 Flash + OpenCode 组合，默认走：

```text
prompt-only JSON
+ 本地解析
+ Pydantic 校验
+ 语义校验
+ 最多一次格式修复
```

请求中不得继续保留不支持的 `response_format` 字段。

## 3. Provider 能力模型

Provider 与模型能力必须细分，不允许只使用模糊的 `supports_structured_output`：

```python
from enum import StrEnum


class StructuredOutputMode(StrEnum):
    JSON_SCHEMA = "json_schema"
    JSON_OBJECT = "json_object"
    PROMPT_ONLY = "prompt_only"
```

```python
class ProviderCapabilities(BaseModel):
    supports_json_schema: bool = False
    supports_json_object: bool = False
    supports_reasoning_field: bool = False
    supports_tool_calling: bool = False
    supports_streaming: bool = False
```

能力来源只能是：

1. 受版本控制的静态 Provider/Model profile；
2. 可重复运行的 capability probe；
3. 已记录的真实 Provider 验收结果。

未知能力一律按 `false` 处理。

建议 Trace 记录：

```text
provider_id
model_id
requested_output_mode
resolved_output_mode
capability_source
fallback_reason
contract_id
repair_stages
```

不得记录 API key、Authorization header 或完整私有 reasoning。

## 4. 请求构造规则

请求体必须按能力条件注入 `response_format`：

```python
def apply_structured_output(
    payload: dict[str, object],
    *,
    capabilities: ProviderCapabilities,
    schema_name: str,
    json_schema: dict[str, object],
) -> StructuredOutputMode:
    if capabilities.supports_json_schema:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": json_schema,
            },
        }
        return StructuredOutputMode.JSON_SCHEMA

    if capabilities.supports_json_object:
        payload["response_format"] = {"type": "json_object"}
        return StructuredOutputMode.JSON_OBJECT

    payload.pop("response_format", None)
    return StructuredOutputMode.PROMPT_ONLY
```

禁止无条件添加：

```python
payload["response_format"] = {
    "type": "json_schema",
    "json_schema": schema,
}
```

## 5. StructuredOutputContract 是主合同

原生 `json_schema` 只能提高模型遵循概率，不能替代 PaperAgent 自己的合同。

每个结构化 LLM 节点必须绑定一个可版本化合同，至少包含：

```text
contract_id
schema_version
task_name
expected_top_level_shape
json_schema
pydantic_model
semantic_validator
repair_strategy
max_repairs
fallback_behavior
```

推荐合同示例：

```python
class StructuredOutputContract(BaseModel):
    contract_id: str
    expected: Literal["dict", "list"]
    json_schema: dict[str, Any]
    semantic_validator: str
    repair_strategy: Literal[
        "same_model_once",
        "formatter_once",
        "fallback_model_once",
        "fail",
    ] = "formatter_once"
    max_repairs: int = 1
    fallback_behavior: Literal[
        "typed_failure",
        "heuristic_marked",
    ] = "typed_failure"
```

默认应使用 `typed_failure`。只有需求文档明确允许时，才能返回带来源标记的 heuristic fallback。

## 6. Prompt-only JSON 模式

当 Provider 不支持原生 Structured Outputs 时，Prompt 必须清楚描述输出合同，但本地代码仍承担最终校验责任。

推荐格式：

```text
Return exactly one JSON object.
Do not include Markdown fences, explanations, or reasoning.

Required structure:
{
  "status": "ready | blocked",
  "queries": [
    {
      "query": "string",
      "gap_id": "string"
    }
  ],
  "block_reason": "string | null"
}

Constraints:
- queries must contain at most 5 entries
- every query must reference an existing gap_id
- do not invent papers, repositories, datasets, URLs, DOI or results
```

避免把极长、包含大量无关定义的完整 JSON Schema 无条件塞入每次调用。Prompt 应提供足够的字段、枚举和约束，但最终正确性由本地合同保证。

## 7. ResponseEnvelope 归一化

Provider adapter 必须先将厂商响应归一化，再交给结构化输出层。

应兼容的常见字段：

```text
choices[0].message.content
choices[0].message.reasoning_content
choices[0].message.reasoning
```

建议统一为：

```python
class ResponseEnvelope(BaseModel):
    provider_id: str
    model_id: str
    request_id: str = ""
    content: str = ""
    reasoning: str | None = None
    finish_reason: str = ""
    usage: TokenUsage = Field(default_factory=TokenUsage)
    raw_shape: str = "custom"
```

规则：

- 优先使用 `content`；
- `content` 为空或不可解析时，才按明确策略检查 `reasoning_content/reasoning`；
- reasoning 只作为兼容恢复来源，不持久化完整私有思维过程；
- 空 `content` 不得自动视为成功；
- 无法归一化时必须返回 typed Provider failure；
- 不得用空字符串、空字典或空列表掩盖 Provider 失败。

## 8. 本地 JSON 解析链

结构化输出必须经过以下有界解析链：

```text
1. direct json.loads
2. strip markdown fence
3. strip <think> / <reasoning> wrapper
4. inspect normalized reasoning field when allowed
5. balanced JSON scan
6. top-level shape validation
7. Pydantic validation
8. semantic validation
9. at most one formatter repair
10. typed failure
```

### 8.1 Direct parse

优先对 `content.strip()` 执行 `json.loads`。

### 8.2 Fence 与 wrapper 清理

允许移除：

```text
```json ... ```
``` ... ```
<think>...</think>
<reasoning>...</reasoning>
```

清理后仍必须重新执行严格 JSON parse。

### 8.3 Balanced scan

模型可能在 JSON 前后附带解释文本。此时可以从后向前扫描完整、括号平衡的 JSON object/array，使最终答案优先于 Prompt 示例或前置草稿。

Balanced scan 必须正确处理：

- object 与 array；
- 字符串内部的括号字符；
- escaped quotes；
- 顶层 shape 要求；
- 多个候选 JSON 时的确定性选择规则。

不得用简单正则 `\{.*\}` 代替结构化扫描。

## 9. Pydantic 与语义校验

合法 JSON 不等于合法业务结果。

必须依次执行：

```text
JSON syntax validation
→ top-level shape validation
→ Pydantic type validation
→ semantic validation
→ normalized artifact
```

语义校验示例：

- planning query 数量不超过预算；
- query 引用的 `gap_id` 必须存在；
- accepted evidence 才能支撑最终 claim；
- rejected、pending、failed verification 不得进入最终证据；
- method design 的 baseline、module、ablation 必须满足最小合同；
- 输出不得包含未验证的论文、DOI、仓库、数据集或实验结果；
- repair 次数不得超过预算。

不要因为 Pydantic 能进行部分类型转换，就跳过业务语义检查。

## 10. Formatter repair

格式修复最多执行一次。

Formatter Prompt 应：

```text
- 只要求重新格式化
- 带上精简后的合同和 validation error
- 明确禁止增加新事实
- 明确禁止改变语义
- 只输出一个 JSON object/array
```

禁止递归调用：

```text
call_json
→ repair_json
→ fallback_formatter
→ call_json
→ repair_json
→ ...
```

Formatter 必须直接调用底层普通 completion，然后只运行本地 parse/validate，不得再次进入 formatter。

硬限制：

```text
max_format_repairs = 1
max_provider_attempts <= 3
```

Provider retry 和 format repair 必须分别计数。

## 11. Typed failure

禁止：

```python
except Exception:
    return {}
```

禁止：

```python
except Exception:
    return []
```

建议错误类型：

```python
class StructuredOutputError(RuntimeError):
    provider_id: str
    model_id: str
    contract_id: str
    requested_mode: StructuredOutputMode
    resolved_mode: StructuredOutputMode
    repair_stages: list[str]
    validation_error: str
```

错误信息必须经过脱敏，不能包含：

- API key；
- Authorization header；
- 完整请求 body 中的敏感用户数据；
- 完整私有 reasoning；
- 超出必要范围的 Provider 原始响应。

Graph 必须区分：

```text
provider_unavailable
provider_rejected_request
invalid_provider_response
structured_output_parse_failed
structured_output_schema_failed
structured_output_semantic_failed
repair_budget_exhausted
```

## 12. 推荐调用路径

```text
PaperAgent Node
→ resolve StructuredOutputContract
→ resolve Provider/Model capabilities
→ build request
→ call OpenCode + DeepSeek V4 Flash
→ ordinary chat/completions without unsupported response_format
→ normalize ResponseEnvelope
→ local JSON extraction
→ Pydantic validation
→ semantic validation
→ optional one-shot formatter
→ validated artifact or typed failure
```

## 13. 测试要求

至少覆盖：

| 场景 | 预期 |
|---|---|
| OpenCode 不支持 json_schema | 请求体不存在 `response_format` |
| 支持 json_schema 的 Provider | 正确发送 native schema |
| 仅支持 json_object | 自动降级到 `json_object` |
| 两者都不支持 | 自动降级到 prompt-only |
| content 是合法 JSON | 直接通过 |
| JSON 在 reasoning_content | 按策略恢复 |
| Markdown fenced JSON | 可以恢复 |
| JSON 前后有解释文本 | balanced scan 获取确定性候选 |
| 顶层要求 dict，模型返回 list | 校验失败 |
| JSON 合法但字段类型错误 | Pydantic 拒绝 |
| JSON 合法但语义错误 | semantic validator 拒绝 |
| 首次格式错误 | formatter 最多执行一次 |
| formatter 后仍错误 | typed failure |
| Provider 网络错误 | 走 Provider retry，不走 formatter |
| 业务 schema 错误 | 走 format repair，不盲目网络重试 |
| capability 未知 | fail-closed |
| Fake/Mock 测试 | 明确标记为离线验证 |
| 真实 OpenCode + DeepSeek smoke | 单独标记、单独报告 |

必须验证 formatter 不会递归，repair 次数和 Provider attempt 次数不会相互污染。

## 14. 禁止事项

- 禁止无条件发送 `response_format=json_schema`；
- 禁止因为接口是 OpenAI-compatible 就推断完整兼容；
- 禁止把 Prompt-only JSON 描述为 schema guarantee；
- 禁止把 malformed output 静默转为空对象；
- 禁止无界 repair、fallback 或 provider retry；
- 禁止 formatter 递归调用结构化输出入口；
- 禁止业务节点直接读取厂商原始响应；
- 禁止持久化完整私有 reasoning；
- 禁止把 Fake/Mock 结果描述为真实端到端验证；
- 禁止把未验证内容补造为论文、数据、代码或实验事实。

## 15. 与 PaperClaw 的职责差异

PaperClaw 的 Provider baseline 是：

```text
普通 completion
+ Provider reliability
+ response normalization
```

PaperAgent 在此基础上承担更严格的研究工作流合同：

```text
StructuredOutputContract
+ Pydantic validation
+ semantic validation
+ bounded repair
+ evidence safety
```

不要把 PaperAgent 的业务 schema 和研究语义塞回 PaperClaw 的底层网络 adapter。

## 16. 当前结论

对于 DeepSeek V4 Flash + OpenCode：

```text
不发送 response_format=json_schema
```

采用：

```text
prompt-only JSON
→ ResponseEnvelope
→ local JSON extraction
→ Pydantic validation
→ semantic validation
→ at most one formatter repair
→ typed failure
```

原生 `json_schema` 只有在 capability profile 或真实 probe 明确证明支持后才能启用。
