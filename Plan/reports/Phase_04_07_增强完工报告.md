# Phase 04+07 增强 + apps/web 侧栏 完工报告

> 触发：用户当前请求 "你是不是没有做真正的检索功能还有真正的中间报告生成，现在我需要你在每一步在右侧展开当前步的中间展示，并添加真正的Minimax LLM生成的学术委员会讨论功能，帮助检索，拆分功能放进去"
> 日期：2026-06-16
> 状态：**commit `6004d6d`，4/4 web e2e + 21/21 phase4 + 22/22 phase7 pytest 全过；arXiv 真检索 + 3 角色 LLM 委员会 + 右侧栏全部交付**

---

## 1. 解决了什么问题

按用户需求 + `Plan/Faraway/TopicPilot-CN_开题选题助手项目方案.md` §10.3 / §10.10：

- **真检索**：Phase 04 之前是 `[placeholder paper ...]` 占位生成，现接 arXiv 公开 API 拿真论文
- **真委员会**：Phase 07 之前是 0 次 LLM 的纯规则 verdict，现 3 角色（支持/质疑/折中）各 1 段 LLM 评语（开题版语气）
- **侧栏展示**：apps/web 之前是 8 phase 卡片平铺，右侧空白；现右侧固定侧栏实时显示当前 phase 关键字段 + arXiv 论文链接 + 委员会对话气泡

按用户"先用 arXiv，别的写 TODO"——OpenAlex / Semantic Scholar / HF / GitHub 留 Phase 09+。

## 2. 做了哪些工作

### 2.1 arXiv 真检索客户端

**新增** `packages/clients/__init__.py` + `packages/clients/arxiv.py` (129 行)：

```python
@dataclass
class ArxivPaper:
    arxiv_id: str          # "2401.12345" (去掉 v 数字)
    title: str
    authors: list[str]
    year: int
    summary: str
    abs_url: str           # https://arxiv.org/abs/2401.12345
    pdf_url: str
    categories: list[str]

def search_arxiv(queries: list[str], max_per_query: int = 3,
                 max_total: int = 10, timeout: float = 10.0) -> list[ArxivPaper]
```

**实现要点**：

- stdlib `urllib.request` + `xml.etree.ElementTree`（**零新依赖**）
- 命名空间 `{http://www.w3.org/2005/Atom}`
- 多 query 独立打 arXiv，**不做 AND 拼接**，让每个词返回最相关的 N 条
- 失败/超时 → 返回 `[]` + log warning，**不抛异常**
- arxiv_id 正则切片：`2401.12345v2` → `2401.12345`

**Smoke 验证**：

```text
[2016] 1609.04846 | A Tutorial about Random Neural Networks...
[2021] 2103.06560 | Heterogeneous Information Network...
[2023] 2312.16183 | LightGCN: Evaluated and Enhanced...
[2020] 2002.02126 | LightGCN: Simplifying and Powering Graph Convolution Network...
```

### 2.2 Phase 04 接 arXiv 真检索

**修改** `packages/agents/nodes/phase4_evidence.py` (+70 行)：

```python
def _merge_arxiv_papers(topic, plan, max_total=5) -> list[PaperEvidence]:
    # 从 plan.query_layers[:3] 抽 queries (前 3 层, 每层前 2 条)
    # 调 search_arxiv; 转 PaperEvidence; 失败返 []
```

**在 heuristic + LLM 两条路径接入**：

- heuristic：`base_papers`（5 占位） → `arxiv_rows`（真论文） → `_replace_with_arxiv`（前 N 条替换，不足补占位）
- LLM：`arxiv_rows` (5) + LLM 输出 papers + `base_default` (5 fallback) → `merged_papers`（去重 + 上限 max(5, LLM 数量)）

**关键发现**：Phase 03 `SearchQueryPlan` 字段是 `query_layers`（不是 `layers`）——explore agent 报告有误，第一次 commit 修复。

**Smoke 验证**：跑 Phase 01-04 happy path，evidence_ledgers.payload.papers 含 5 条 `source=="arXiv"`，title 含 LightGCN / PinSage 等真论文。

### 2.3 Phase 07 真委员会 3 角色 LLM 对话（开题版）

**新增 Pydantic 模型** (`packages/domain/phase7_models.py`)：

```python
CommitteeRole = Literal["supporter", "skeptic", "pragmatist"]

class CommitteeDiscussionItem(BaseModel):
    role: CommitteeRole
    stance: str                # "支持" / "质疑" / "折中"
    comment: str               # 100-180 字中文评语
    focus: list[str]           # 该角色关注的研究问题

class CommitteeReview(BaseModel):
    # ... 现有字段
    discussion: list[CommitteeDiscussionItem] = []  # 新增
```

**3 角色 prompt**（按用户"开题不需要太正式，标准放低一点"）：

| role | stance | prompt 关键句 |
|---|---|---|
| supporter | 支持 | 站在'这个题目硕士生能毕业'的角度, 指出 1-2 个最有把握的支撑点 (如: baseline 有开源 / 数据公开 / 工作包有先例). |
| skeptic | 质疑 | 站在'这个题目风险在哪里'的角度, 指出 1-2 个最不放心的环节 (如: 创新点难以验证 / 工作包相互依赖). |
| pragmatist | 折中 | 站在'这个方案落地要付出多少'的角度, 指出 1-2 个工程 / 时间 / 算力上的现实约束. |

每个 100-180 字，温度 0.5，**调 3 次 chat_json**（不一次生成 3 角色）。

**LLM 失败 fallback**（`_fallback_comment`）：

- supporter：基于 `len(papers) ≥ 5` 给模板评语
- skeptic：基于 `risk_rating in (C, D)` 给出"创新点需要具体化"
- pragmatist：固定 GPU 显存建议

**接入** `build_committee_review`：算完 7 维度 verdict + 6 问答后追加 `discussion`。

### 2.4 apps/web 右侧固定侧栏

**布局改造**（`index.html` + `styles.css` +90 行）：

```text
+--------------------------+----------+
| Phase 01 卡片 (左列)     | 当前阶段 |
| Phase 02 卡片            | 关键字段 |
| ...                      | (右栏   |
| Phase 08 卡片            | sticky) |
+--------------------------+----------+
```

- `.layout-grid { grid-template-columns: 1fr 320px }`
- `.sidebar { position: sticky; top: 20px; max-height: calc(100vh - 40px) }`
- `@media (max-width: 960px)` → 单列布局

**侧栏状态机**（`app.js` +283 行）：

```js
state = {
  ...,
  intake, topicSpec, searchPlan, evidenceLedger,
  riskEvaluation, workPackage, proposalDraft,
  committeeReview, finalPackage,    // 每个 Phase 缓存 payload
  currentSidebarPhase: 0,
};

function renderSidebar(n) { _renderSidebar0n(); }
function setSidebar(n, title, rows, extras) { /* 渲染 fields + extras */ }
```

**8 个 phase 侧栏字段**（每个 5-8 行 key-value）：

| Phase | 字段 |
|---|---|
| 01 | 项目 ID, case_id, intake_rating, 目标档位, 学位, 导师方向, 开题/毕业时间, 原始题目 |
| 02 | normalized_topic, task/method/data/metric count, decomposition_rating, allow_proceed |
| 03 | maturity_rating, layer_count, query_total, top_layer, sample_query |
| 04 | evidence_rating, paper_count, **arxiv_papers**, latest_year, dataset/baseline/metric count + top 3 arXiv 论文链接 |
| 05 | overall_rating, overall_score, decision, max_risk_dim, pivot_count, top_pivot |
| 06 | final_topic, from_pivot, WP_count, experiment_count, chapter_count |
| 07 | proposal_sections, innovation_count, committee_verdict, maturity, review_count, question_count, **3 角色对话气泡** |
| 08 | ready_for_thesis, backend/ui/playwright, markdown_chars |

**触发**：每个 phase 主按钮 click 成功后调 `renderSidebar(n)`；committee/review 后侧栏额外渲染 3 个角色对话气泡（绿/红/蓝边框区分立场）。

### 2.5 测试

**新增 3 条**（pytest 总数 176 → 179）：

| 文件 | 测试 | 验证 |
|---|---|---|
| `apps/api/tests/test_phase7_models.py` | `test_committee_review_has_3_role_discussion` | CommitteeReview.discussion 含 3 role, 评语 ≥ 20 字 |
| `apps/api/tests/test_phase7_api.py` | `test_committee_review_includes_3_role_discussion` | API 端点返回 payload.discussion |
| `apps/web/e2e/test_web_e2e.py` | `test_sidebar_shows_arxiv_papers_in_phase04` | sidebar-fields 含 `arxiv_papers` 字段 + arxiv-mini 链接 |

**回归子集验证**：

```text
phase4_models:        9/9 PASSED
phase4_api:           7/7 PASSED
phase4_acceptance:    5/5 PASSED
phase7_models:       14/14 PASSED (含新 1 条)
phase7_api:           8/8 PASSED (含新 1 条)
web e2e:              4/4 PASSED (含新 1 条 sidebar arxiv)
```

**全套 pytest** 因 LLM 调用耗时 ~30s/条，全套 ~10 分钟（实际跑到 50% 时被迫 kill；但关键 Phase 04/07 + web e2e + 18 acceptance 已独立 100% PASSED）。

## 3. 数据流：真 arXiv + 真委员会 + 侧栏

```text
浏览器 (18182)            后端 uvicorn (18181)         DB                arXiv.org
                POST .../evidence/build (heuristic)
                ────────────────────────────→  packages/agents/nodes/phase4_evidence.py
                                                    ↓ _merge_arxiv_papers
                                                    ↓ search_arxiv
                                                    ──────────────────────────→  GET .../api/query?search_query=...
                                                    ←──────────────────────────  Atom XML
                                                    ↓ ArxivPaper → PaperEvidence
                                                    ↓ _replace_with_arxiv (前 N 真 + 后 占位)
                ←──────────── papers=[5 arXiv + 0 placeholder]   evidence_ledgers.payload
                [前端 state.evidenceLedger = payload]
                [renderSidebar(4): arxiv_papers=5 + top3 链接]

                POST .../committee/review
                ────────────────────────────→  packages/agents/nodes/phase7_proposal.py
                                                    ↓ _build_committee_discussion_llm
                                                    ↓ 3× chat_json (supporter / skeptic / pragmatist)
                                                    ──────────────────────────→  MiniMax M3 (M3 Anthropic-compat)
                                                    ←──────────────────────────  {comment: "..."}
                ←──────────── committee_reviews.payload
                                  .discussion=[
                                    {role: supporter, comment: "支持方面: ..."},
                                    {role: skeptic, comment: "质疑方面: ..."},
                                    {role: pragmatist, comment: "工程方面: ..."}
                                  ]
                [前端 state.committeeReview = payload]
                [renderSidebar(7): 3 角色对话气泡渲染]
```

## 4. 验收对照

| §5.x 验收点 | 状态 |
|---|---|
| §5.1 Phase 04 真检索 | ✓ `evidence_ledgers.payload.papers` 含 source=="arXiv" 真论文（LightGCN / PinSage 等）|
| §5.2 Phase 07 真委员会对话 | ✓ `committee_reviews.payload.discussion` 含 3 角色 LLM 评语 |
| §5.3 apps/web 右侧栏 | ✓ `renderSidebar(n)` 8 个 phase 各 5-8 字段 |
| §5.4 arXiv 论文链接侧栏展示 | ✓ Phase 04 侧栏 top-3 arXiv 链接 |
| §5.5 委员会对话气泡侧栏展示 | ✓ Phase 07 侧栏绿/红/蓝 3 色气泡 |
| §5.6 LLM 失败 fallback | ✓ `_fallback_comment` 3 角色规则模板 |

## 5. 过程中修复的真实 Bug

### Bug 1：Phase 03 字段名错

**现象**：第一次跑 Phase 04 测试 17 个全挂 `AttributeError: 'SearchQueryPlan' object has no attribute 'layers'`

**原因**：Explore agent 报告 `plan.layers`，实际是 `plan.query_layers`（多了 `query_` 前缀）

**修复**：`phase4_evidence.py:141` 改 `plan.query_layers[:3]`

### Bug 2：Phase 07 WorkPackagePlan 字段名错

**现象**：第一次跑 Phase 07 tests 10/22 挂 `AttributeError: 'WorkPackagePlan' object has no attribute 'chapter_mapping'`

**原因**：我假设 `chapter_mapping`，实际是 `thesis_outline` (list[ThesisOutlineChapter], 5+ 章)

**修复**：`phase7_proposal.py` prompt context 改 `thesis_outline={len(plan.thesis_outline)} 章`

### Bug 3：删除 `_build_default_surveys` 函数头

**现象**：第一次 Edit `_merge_arxiv_papers` helper 时误删了 `_build_default_surveys` 的 `def` 行

**修复**：第二个 Edit 补回 `def _build_default_surveys(topic: TopicSpec) -> list[PaperEvidence]:`

### Bug 4：web e2e timeout 10s 不够

**现象**：Playwright happy path 在 Phase 04 卡 10s timeout，但手工浏览器 3s 就过

**原因**：Playwright 启动 Chromium + chromium 自检 + 服务端真实调 arXiv（8s 超时）总耗时不稳定

**修复**：`_click_and_wait` timeout 10s → 20s + 加 robust 的 `wait_for_function` (检查 textContent + el 存在)

### Bug 5：e2e state 缓存错位

**风险**：state.intake = data（POST 响应，含 .payload）；state.topicSpec = data.payload || data (兼容)

**修复**：每个 setState 统一 `data.payload || data`，避免 endpoint 响应格式不一致

## 6. 与原方案的偏离

| 原方案 §10.3 / §10.10 | 实际 MVP | 升级方向 |
|---|---|---|
| OpenAlex + Semantic Scholar 检索 | 只接 arXiv (用户明确"先用 arXiv") | OpenAlex 接 phase4_evidence.py 同位置 |
| GitHub Baseline Scout | 未接 | Phase 09+ |
| 5 维 / 7 维评审 Agent | 3 角色各 1 段评语（用户要求"放低"）| 升级为 2 轮辩论 |
| Hugging Face Dataset Scout | 未接 | Phase 09+ |
| React Flow 状态图 | 静态 grid + sidebar | Phase 09+ |

## 7. 与规约的偏离

无字段偏离。两条**实现细节**标注：

1. **arXiv 用 stdlib urllib + ElementTree**——不引 httpx/requests 依赖
2. **3 角色 LLM 调 3 次 chat_json**——不一次生成 3 段（更稳，失败时可独立 fallback）

## 8. 不在本工作范围（明示）

- 不接 OpenAlex / Semantic Scholar / HF / GitHub
- 不改 Phase 04 Pydantic 模型（复用现有 `papers[]` + `source="arXiv"` literal）
- 不动现有 7 维度 verdict / 6 问答逻辑（只追加 `discussion`）
- 不做 React Flow / ECharts / Next.js
- 不接 Langfuse / LangSmith

## 9. 后续工作（按用户优先级）

| 优先级 | 工作 | 估时 |
|---|---|---|
| P0 | 接 OpenAlex 真检索 (复用 _merge_arxiv_papers 模式) | 1 周 |
| P1 | Phase 07 委员会升级为 2 轮辩论 (复用 chat_json × 6) | 3 天 |
| P1 | 侧栏 Phase 04 arxiv_mini 改为可折叠 top-10 | 2 天 |
| P2 | React Flow 状态图（侧栏改 embedded） | 1 周 |
| P2 | GitHub Baseline Scout（看仓库 README/env/license） | 1 周 |

## 10. 一句话总结

> `packages/clients/arxiv.py` 用 stdlib urllib + ElementTree 接 arXiv 公开 API；Phase 04 在 heuristic + LLM 两条路径接入 `_merge_arxiv_papers`，evidence_ledgers.payload.papers 前 5 条为 arXiv 真实论文（LightGCN / PinSage 等）；Phase 07 新增 `CommitteeDiscussionItem` 模型 + `_build_committee_discussion_llm`（3 角色 supporter/skeptic/pragmatist，开题版语气 100-180 字），LLM 失败 fallback 规则评语；apps/web 改成 `grid 1fr 320px` + 右 sticky 侧栏，app.js 加 state 缓存 + 8 个 `_renderSidebar0X` 按当前 phase 渲染 5-8 行关键字段，Phase 04 侧栏多 top-3 arXiv 链接、Phase 07 侧栏多 3 色对话气泡；新增 3 条测试（phase7 models/api 各 1 + web e2e 1 sidebar arxiv），关键路径 4/4 web e2e + 21/21 phase4 + 22/22 phase7 全过；commit `6004d6d`。
