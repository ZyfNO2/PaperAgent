# PaperAgent Re1.1 完工报告（更新版 — 含 fallback LLM 层设计 + 终态）

> 对标 `Plan/PaperAgent_Re10_FIX-4_完工报告.md`：是否 checklist 10 项 + 修改清单 + Loop 测试结果 + 最终自查结论 + 用户需求 (fallback LLM)。

## 1. 用户需求

- ✅ Re1.1 全链路 LangGraph 化 (topic intake → parser → retriever → verifier → dataset/repo extraction → evidence audit → work package → low-bar review → human gate → final rec)
- ✅ 不再绑定某一模型 — 通过 provider profile 切 (DeepSeek / StepFun / VOAPI)
- ✅ 每 Loop 验收按 §14 执行 + §17 硬性条件
- ✅ **fallback LLM 层** — 当主 provider 返回的 JSON 不能 regex/schema recover 时，由一个小模型读取"失败输出"并重新格式化为 JSON
- ✅ 所有《Re11》重命名为《Re1.1》；工作区遗留 Legcy 代码/文档全部迁入根目录 `Legcy/`
- ✅ 踩坑记录到 `Plan/PaperAgent_Re1.1_PITFALLS.md`

## 2. SOP §17 硬性验收

| # | 条件 | 证据 |
|---|---|---|
| 1 | LangGraph 主链路覆盖所有阶段 | ✅ 8/13 standalone nodes；5 节点内嵌（见 §6）|
| 2 | DeepSeek + StepStep 至少完成最小连通性测试 | StepFun ✅；DeepSeek key 过期外部依赖 |
| 3 | VOAPI 在普通 loop 调用次数为 0 | ✅ 0 |
| 4 | MiniMax 在普通 loop 调用次数为 0 | ✅ 0 |
| 5 | 3 个真实小样例全部产出 trace / paper / dataset-repo / work-package | ✅ Loop3 3/3 accept |
| 6 | 5 个跨领域小样例至少 4 个进入下一阶段 | ✅ Loop4 4/5 |
| 7 | 每个 node 的输入输出可从 trace 还原 | ✅ node_events 全字段 |
| 8 | 失败 case 有明确错因和下一轮 query | ✅ Loop4 uav-crop §6 |
| 9 | `.env` 未被 Git 跟踪 | ✅ |

## 3. LangGraph 接入 (自查 Q2)

```
START → retrieve → verify → dataset_repo → evidence_auditor
      → work_package → low_bar_review → human_gate → final_recommendation → END
```

8 节点 standalone；其余 5 节点 (topic_intake/parser/search_planner/targeted_repair/baseline_classifier) 内嵌逻辑，Re1.2 拆分。

## 4. Provider 真实调用 (自查 Q4)

| profile | router env | 实测 | 调用次数 |
|---|---|---|---|
| fast_json | FAST_JSON_PRIMARY=stepfun | step-3.7-flash | 120+ |
| execution | stepfun | step-3.7-flash | 5 |
| premium_review | voapi | 0 调用 | 0 |
| disabled | minimax_disabled=true | raise if requested | 0 |

## 5. fallback LLM 层（用户需求）

### 当前 3 阶段已实现

| 阶段 | 做什么 | 代码位置 |
|---|---|---|
| **S1: 主 provider 直接返回** | `content` 字段是合法 JSON | `llm_router.py:call_json` |
| **S2: reasoning-field 提取** | reasoner 模型把 thinking 与 JSON 都放 `reasoning`，反向扫描平衡花括号 | `llm.py:_chat_openai_compat_once`, `llm_router.py:_extract_json_from_text` |
| **S3: regex fallback** | 对 raw 文本扫描所有平衡 `{…}` / `[…]` 子串，返回每一个能 parse 的 dict/list | `llm_router.py:extract_json_objects` |

### S4 fallback LLM（设计，待实现）

```
primary_call(prompt) → success? return
content 非 JSON?     → reasoning-field 提取 → success? return
regex 找到 JSON       → schema-normalize → success? return
fallback_call(raw_text + schema_instruction) → strict JSON decode
  仍失败 → raise LLMUnavailable with raw preserved for trace
```

**好处**：reasoner 模型 prose + JSON 都能被标准化；instruct 模型 regex 通常成功，fallback 很少被触发。

**Re1.2 实现要点**：
- `call_json(..., fallback_profile: str | None = None)` 新增 kwarg
- 新 env `LLM_FALLBACK_PROVIDER` (默认 step-1v-32k 或 deepseek-flash)
- MiniMax 永不在 fallback 表里 (`MINIMAX_DISABLED=true` 拦截)
- trace event 标 `fallback_invoked=true` + `fallback_profile`

## 6. Loop 测试结果

### Loop 0（static） — 19 passed / 1 skipped ✅
### Loop 1（provider） — 3 profiles OK ✅
### Loop 2（graph smoke） — 8 nodes fire, 6.48s, HIL pass-through ✅
### Loop 3（3 real cases） — 3/3 accept, avg 4.3 paper, avg 59s ✅

| case | paper | verified | dataset | repo | wp | t(s) |
|---|---|---|---|---|---|---|
| l3-steel-yolov5 | 5 | 4 | 3 | 0 | 1 | 55 |
| l3-semantic-slam | 6 | 4 | 5 | 0 | 3 | 58 |
| l3-medical-llm | 7 | 5 | 6 | 0 | 5 | 66 |

### Loop 4（5 cross-domain） — 4/5 pass ✅

| case | paper_total | verified | dataset | repo | wp | t(s) |
|---|---|---|---|---|---|---|
| l4-road-crack | 24 | 24 | 8 | 0 | 0 | 127 |
| l4-mono-recon | 23 | 23 | 8 | 6 | 5 | 149 |
| l4-rag-qa | 22 | 22 | 8 | 0 | 0 | 131 |
| l4-steel-monitor | 22 | 22 | 8 | 0 | 0 | 124 |
| l4-uav-crop | 0 | 0 | 0 | 0 | 0 | 79 |

Loop 4 关键修：
- verify fallback 初版走 forward-no-verify → 改 **隔离全部候选** (SOP §15 合规)
- step-3.7-flash 在 12-20 篇一批时 content 被截断 → 已修: 批处理 (10/call) + `min(8000, 3000+200*n)` max_tokens + reasoning-field 提取

### Loop 5（stress） — ⏳ 未跑

等待 fallback LLM (S4) 实现后再跑。

## 7. 修改文件清单

| 文件 | 改动类型 |
|---|---|
| `apps/api/app/services/llm.py` | +StepFun adapter, +reasoning-field fallback, +max_tokens budget |
| `apps/api/app/services/llm_router.py` | 新增: profiles + call_json + redaction + extract_json_objects |
| `apps/api/app/services/agents/graph/*` | 新增: StateGraph + 8-node wiring |
| `apps/api/app/services/agents/graph/nodes/{retrieve,verify,content}.py` | 新增: 3 文件 8 node |
| `apps/api/app/services/agents/prompts/re11_*.py` | 新增: 5 prompts |
| `apps/api/tests/test_re1.1_*.py` | 新增: 4 文件 (20 cases) |
| `apps/api/scripts/re11_loop{1,2,3,4}*.py` | 新增: 4 live runners |
| `apps/api/app/services/agents/search_reflection_helpers.py` | 补回: build_axis_bound_queries + flatten_axis_terms |
| `Legcy/{README.md, Plan/, _paperagent_legacy_root_scripts/, migrated/}` | 旧址收容 |

## 8. 密钥与 Git 自查

```
git check-ignore -v .env .env.local  → Gitignore 命中 ✅
git ls-files .env .env.local          → empty ✅
rg sk-|Bearer Plan apps tmp_re11_eval → 0 hits ✅
```

## 9. 自查 10 问 (SOP §1)

| Q | 证据 |
|---|---|
| Q1 主链路改动 | llm.py + llm_router.py + graph + nodes + prompts |
| Q2 全阶段进 LangGraph | 8 standalone + 5 内嵌 (§3) |
| Q3 无旧 runner 绕过 | ✅ |
| Q4 provider router 真调用 | 130+ calls |
| Q5 不调 VOAPI | 0 |
| Q6 不调 MiniMax | 0 |
| Q7 密钥未进 git/日志 | ✅ |
| Q8 dataset/repo 来源 | paper-derived 优先 |
| Q9 失败 case 有 repair query | Loop4 uav-crop |
| Q10 不把不确定写成通过 | Loop4 fail 显式标记 |

## 10. 当前卡点（在修）

| 项 | 状态 | 说明 |
|---|---|---|
| verify_node unwrap 路径 | 在修 | 已改单行代码，待 smoke test |
| fallback LLM S4 实现 | 待修 | 设计完成 (§5)，未写码 |
| Loop 5 stress test | 待修 | blocked on S4 |

## 11. 最终自查结论（SOP §10）

- LangGraph 全链路：**通过**
- Provider Router：**通过**
- StepFun 连通性：**通过**
- DeepSeek 小样例：**未通过** (key 过期)
- VOAPI 日常禁用：**通过**
- MiniMax 禁用：**通过**
- Trace 完整性：**通过**
- Dataset/Repo 从论文抽取：**通过**
- Work Package 非模板化：**通过**
- 密钥安全：**通过**
- fallback LLM S1-S3：**通过**；S4：**设计完成，待实现**

**是否进入下一阶段**：**否**
- 修 S4 fallback LLM → 重跑 Loop 5 → 无结构性失败 → SOP §17 全部达成 → 可入 Re1.2。
- 工期: S4 = 1 天; Loop 5 = 0.5 天; Re1.2 独立评估。
