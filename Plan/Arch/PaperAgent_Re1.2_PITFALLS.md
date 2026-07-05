# Re1.2 踩坑笔记 — reasoner 模型 JSON 解析与 prompt 工程

> 与 `AutoResearchClaw` / `academic-research-skills` 参考实现对照, 记录已知陷阱。

---

## 坑 1: reasoner 模型返回 list 而非 dict

**现象**: `call_json()` 返回 `["YOLOv5", "steel surface defect detection", ...]`,
调用方对 list 调用 `.get("verdict")` → AttributeError。

**根因**: `call_json(prompt, expected="any")` 时, Phase A 把任何合法 JSON
(包括 list) 当作 success 返回, 不尝试提取 dict。stepfun step-3.7-flash
经常在 reasoning 里只产生 hit_keyword list 而不产生 wrapper object。

**修复**:
1. verifier caller 必须传 `expected="dict"`, 拒绝 list 进入 Phase C
2. 参考 `AutoResearchClaw` 的 `_safe_json_loads`: 依次尝试 direct parse →
   fenced block → balanced-brace → balanced-bracket, 按类型过滤期望
3. 参考 ARS 的 JSON Schema 校验: 出口处用 `jsonschema` 二次校验

**教训**: reasoner 模型的 thinking 字段可能 "污染" 解析 — 要把 reasoning
字段当作独立输入解析, 且要求最终输出必须是 dict。

---

## 坑 2: system prompt 过长导致 "思考到死"

**现象**: stepfun 3.7-flash 对 > 200 token 的 system prompt 在 thinking 中
消耗全部 token budget, 最终 content 为空。

**根因**: step-3.7-flash 的 thinking budget 有限。超长 system prompt 被模型
当作 "需要思考的内容", thinking 写了推理过程, 没有空间写最终 JSON。

**修复**:
1. system prompt < 100 token; 放最小角色定义 + 输出契约
2. user prompt 放具体输入 + 任务步骤 + 输出 schema
3. thinking 阶段利用来 "思考 step-by-step", 不直接输出 JSON
4. 输出契约放在 user prompt 末尾, 用 `[OUTPUT CONTRACT]` 标签

**参考**: AutoResearchClaw 的 `strip_thinking_tags` + JSON hint 作为 system
message 注入, 避免与 thinking 竞争。

---

## 坑 3: 踩 `response_format: json_object` 边界

**现象**: stepfun 对某些模型设置 `response_format: json_object` 后,
返回 `content=""`, 真正的 JSON 在 `reasoning`。

**修复**: 已在 Re1.2 移除 `response_format: json_object`。对 reasoner 模型
不依赖 response_format flag, 靠 prompt 约束内联 JSON 输出。

---

## 坑 4: fallback formatter 递归陷阱

**现象**: Phase C `_fallback_formatter()` 递归调用 `call_json()`, 如果
原始 prompt 已经很强, 二次调用仍然失败, 且二次失败时 `raw_text` 包含
被截断的 reasoning, 进一步污染 JSON 提取。

**修复**:
1. fallback formatter 加 schema_hint (明确描述目标 schema)
2. 调用方层级限制重试 ≤ 2, 超过则 LLMUnavailable
3. 传入 `raw_text[:2000]` 而非全部, 防止 thinking 文本淹没 context

---

## 坑 5: prompt 里内嵌 title 导致 JSON 转义失败

**现象**: candidate title 含 `"` 或 `\` 等字符, 在 prompt 模板中直接嵌入
`"title":"{candidates_title}"` 产生 malformed JSON 引导, 模型容易仿造
错误格式。

**修复**:
1. prompt 模板不预填 title 字段, 让模型自行复制
2. 或使用 `json.dumps(title)` 转义后嵌入

---

## 坑 6: 跨模型一致性 — DeepSeek vs StepFun vs Opencode 行为差异

| 行为 | DeepSeek flash | StepFun 3.7-flash | Opencode big-pickle |
|---|---|---|---|
| thinking 输出 | content 有 JSON | reasoning 有 JSON, content 空 | content 有 JSON, 偶尔空 |
| JSON 遵循率 | ~95% | ~70% (依赖 fallback) | ~60% |
| 对 prompt 长度敏感度 | 中 | 高 | 低 |
| 单候选 latency | ~4s | ~15-20s + fallback | ~6-12s |

**标准化策略**: 所有 verifier caller 统一传 `expected="dict"`,
使用 short system + long user template pattern, 并在 `call_json` 后做
类型检查。

---

## 坑 7: 验证器 expected="any" 陷阱

**根因**: `call_json()` 默认 `expected="any"`, Phase A 接受任何合法
JSON (list/dict/str/int)。当 reasoner 只产生 list of keywords 时, 整条
路径跳过 Phase B/C, 直接返回 list。调用方按 dict 操作 → crash。

**修复**: verifier/dataset_repo/work_package 等所有 "期望返回 dict 对象"
的 caller 必须显式传 `expected="dict"`。对于 "期望 list" 的 caller
(dataset_extractor 的 `expected="list"`), 也需显式声明。

---

## 参考项目技术对照

| 技术点 | AutoResearchClaw | academic-research-skills | PaperAgent (Re1.2) |
|---|---|---|---|
| 解析鲁棒性 | `_safe_json_loads` 4-strategy 链 | JSON Schema + lint | json_repair 3-phase |
| thinking 处理 | `strip_thinking_tags` 清除 | ground-truth isolation | reasoning 字段提取 |
| JSON 模式 | system message 禁用 + prompt 约束 | Markdown schema | inline JSON 模板 |
| 阶段回退 | 模板回退 (default_*) | Markdown fallback dict | Phase C formatter |
| 模型回退链 | `model_chain = [primary, fallback]` + 429 backoff | provider env 路由 | `FAST_JSON_PRIMARY` |
| CoT 利用 | 不作为最终输出 | 不作为最终输出 | 在 thinking 中引导分析 |
| 429 backoff | 指数退避 + jitter | 待确认 | 1/2/4s 指数退避 |
| 输出 schema | yaml (prompts.default.yaml) | JSON Schema files | inline user template |

> **核心教训**: AutoResearchClaw 是最接近的参考 — 它的 `_safe_json_loads` +
> 模板回退 + 模型 fallback 链是生产级 triage。PaperAgent 应该演进到
> 4-strategy 解析 + default 输出模板 + logging 进行 fallback 观测。
