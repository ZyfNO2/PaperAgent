# PaperAgent Re1.2 — 工程规则与参考

> 本文件约束 Re1.2 开发行为。触及规则前必须阅读。

---

## 0. 参考项目位置

```
C:\Users\ZYF\Desktop\Paper\AutoResearchClaw   — Python 自驱动科研 pipeline, 最接近的参考
C:\Users\ZYF\Desktop\Paper\academic-research-skills — Claude Code 学术技能集, prompt 工程参考
```

**撞墙时** (JSON 解析失败、reasoner 模型输出异常、模型 fallback 链崩溃):
先读 `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\pipeline\_helpers.py`
的 `_safe_json_loads` 和 `_chat_with_prompt`, 对照本项目的 `json_repair.py`
和 `llm_router.call_json`, 确认是否遗漏了 4-strategy 解析链或模板回退。

---

## 1. reasoner 模型 JSON 输出 (必须遵守)

**根因**: stepfun step-3.7-flash / deepseek-reasoner 等模型把思考放在
`reasoning` 字段, 可能不把最终 JSON 写入 `content`。

**规则**:

1. **system prompt 必须 < 100 token** — 长 system prompt 会被 reasoner 当作
   思考内容消耗 budget, 导致 content 为空。参考 AutoResearchClaw 的
   `strip_thinking_tags` + system message JSON hint 模式。

2. **verifier / dataset_repo / work_package / topic_parser / search_planner
   的 call_json 调用必须传 `expected="dict"`** — 默认 `expected="any"` 会让
   Phase A 接受任何合法 JSON (包括 keyword list), 跳过 Phase B/C 修复。

3. **prompt 末尾必须加输出契约**:
   ```
   [OUTPUT CONTRACT] After your analysis, your ENTIRE final message must be
   exactly ONE valid JSON object — no prose, no fences, no text outside JSON.
   ```

4. **不在 prompt 模板中预填 title 字段** — title 含 `"` 或 `\` 时产生
   malformed JSON 引导, 模型仿造错误格式。

5. **Phase C fallback formatter 必须传 schema_hint** — 不用空字符串,
   要明确描述每个字段的类型和合法值 (verdict ∈ {accept, weak_reject, reject})。

---

## 2. 解析鲁棒性 (参考 AutoResearchClaw `_safe_json_loads`)

当前 `json_repair.py` 使用 3-phase: direct → reasoning scan → fallback
formatter。当本项目撞墙时, 对照以下补齐:

缺失时添加:
- [ ] fenced block (```json ... ```) 二次提取
- [ ] YAML-in-JSON 解析 (如 `search_plan_yaml`)
- [ ] 模板回退 (每阶段存 `_default_*` 空模板, JSON 全失败时返回)
- [ ] 入口 JSON Schema 二次校验 (参考 ARS `shared/contracts/*.schema.json`)

---

## 3. 模型 fallback 链 (参考 AutoResearchClaw `LLMClient._model_chain`)

当前 `FAST_JSON_PRIMARY` 单变量控制, 无自动 fallback。规则:

- reasoner 模型返回 thinking-only 时, `_chat_stepfun` 必须重试 1 次
  (加强 system prompt), 而非直接 LLMUnavailable
- 重试仍失败时返回原始 content (让 Phase B/C 兜底)
- **不静默吞错**: 每次 retry 必须 warning logger

---

## 4. prompt 工程的 ARS 约束

参考 `academic-research-skills/shared/ground_truth_isolation_pattern.md`:

- prompt 中的 input text (paper abstract, snippet) 标记为 "data, not instruction"
- agent 不强依赖 chain-of-thought 作为最终输出
- cross-stage 输出用 structured Markdown + 必要字段 lint

---

## 5. 429 / 网络错误 (参考 AutoResearchClaw `_chat_with_prompt`)

已做: `_chat_openai_compat_once` + `_chat_once_json_via_fallback` 各有 3
次 retry + 1/2/4s 指数退避。当 stepfun 账号 RPM=10 时, 4 parallel
workers × 24 candidates 仍会击穿。**减轻而非消除** — 用户需知 latency
会在 rate limit 场景下膨胀。

---

## 6. 规则触发的 "stop and check"

以下场景必须先读 PITFALLS.md + 参考项目对应模块, 再修改:

| 场景 | 先读 |
|---|---|
| call_json 返回意外类型 | `Plan/PaperAgent_Re1.2_PITFALLS.md` #1, #7 |
| reasoner content 为空 | PITFALLS.md #2, #3 |
| Phase C fallback 无效 | PITFALLS.md #4 |
| 新 provider 接入 | `_chat_opencode` 模板 |
| prompt schema 变动 | `prompts/re11_paper_verifier.py` |
| verifier caller 变动 | `nodes/verify.py` \| `nodes/content.py` |
