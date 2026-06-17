# OneTopic MVP 验收报告

> 验收时间: 2026-06-17
> 阶段: OneTopic MVP (替代原 8 Phase 大入口)
> 目标: 用户只输入一个选题 → 关键词拆解 → 三线检索 → 可行性判断 → 开题建议 → 低门槛审核

---

## 1. 修改范围

按 `Plan/TopicPilot-CN_OneTopic_MVP_修改SOP.md` 全部重写。**旧 8 Phase 入口已整体移到
`Plan/Legcy/old_code/`，不再维护。**

### 1.1 移到 Legcy

```
Plan/Legcy/old_code/
├── apps/api/        旧 FastAPI (8 阶段 router + 8 SSE 端点)
├── apps/web/        旧前端 (8 step dot + 一页一动作)
├── packages/        旧 domain/agents/clients/llm
├── scripts/         旧 demo_smoke / full_smoke / browser_self_test
└── data/            旧 demo_cases / projects
```

可复用的小参考 (但不直接 copy):
- arXiv 公开 API XML 解析思路 → 重写为 `apps/api/app/services/arxiv.py` (httpx 版)
- LLM 客户端 → 重写为 `apps/api/app/services/llm.py` (直连 MiniMax M3, 更简单)

### 1.2 新版结构

```
apps/api/app/
├── main.py                      # FastAPI 入口
├── schemas.py                   # 8 个 Pydantic 模型 (OneTopic §13)
├── api/v1/one_topic.py          # 2 个端点: analyze + analyze/stream
└── services/
    ├── arxiv.py                 # arXiv 公开 API (无 LLM 依赖)
    ├── llm.py                   # MiniMax M3 (httpx 直连, 缺 key 抛 LLMUnavailable)
    └── one_topic.py             # 核心业务: 拆解/检索/评级/推荐/审核

apps/web/
├── index.html                   # 一题输入 + 5 区结果
├── app.js                       # fetch + ReadableStream
├── styles.css                   # 极简风
├── dev_server.py                # 静态文件服务 (18182)
└── e2e/
    ├── conftest.py
    ├── test_one_topic_happy_path.py
    ├── test_one_topic_no_dataset.py
    ├── test_one_topic_review.py
    └── test_one_topic_trace.py
```

---

## 2. 端到端数据流

```text
用户在 apps/web 输入题目
   ↓
fetch POST /api/v1/one-topic/analyze/stream
   ↓
apps/api/app/api/v1/one_topic.py  (SSE 包装, asyncio queue)
   ↓
apps/api/app/services/one_topic.py::run_one_topic_stream
   ↓ 1. 拆解 (LLM 优先, fallback heuristic)
   2. 题目理解
   3. 三线检索词生成
   4. arXiv 公开检索 (httpx 直调)
   5. 数据集启发式匹配
   6. Baseline 启发式匹配
   7. 可行性四档判断
   8. 开题建议 + 工作包
   9. 低门槛 5 维审核
   ↓
emit(start / step / result / end)  ← SSE 流
   ↓
前端按 trace 推面板 + result 渲 5 区
```

---

## 3. 验收标准 (OneTopic §16 MVP 通过条件)

| # | 条件 | 状态 | 证据 |
|---|------|------|------|
| 1 | 用户只输入一个题目即可启动 | ✓ | `index.html` input-card 只有 1 个必填项 |
| 2 | 系统能拆出方法词、任务词、对象词 | ✓ | `KeywordBreakdown` + 启发式词典 |
| 3 | 系统能展示论文 / 数据集 / 工程三类证据 | ✓ | `EvidenceSummary` + `evidence-section` 3 个 list |
| 4 | 系统能给出可行性四档判断 | ✓ | `FeasibilitySummary.verdict` ∈ {可做 / 收缩后可做 / 暂缓 / 不建议} |
| 5 | 系统能给出推荐题目和工作包 | ✓ | `ProposalRecommendation` (≥ 1 个 WP, 默认 2 个) |
| 6 | 系统能进行低门槛模拟审核 | ✓ | `LightReview` 5 维 + 4 档结论 + 修改清单 |
| 7 | Playwright 覆盖 4 个 spec | ✓ | happy / no-dataset / review / trace 共 10 个 case |

---

## 4. 验收数据 (curl 实测)

### 4.1 YOLO 钢材 (happy path)

```json
{
  "feasibility": {"verdict": "可做", "reason": "论文 + 数据集 + baseline + 指标都齐备..."},
  "evidence_summary": {
    "paper_count": 6, "arxiv_paper_count": 6, "dataset_count": 2,
    "datasets": ["NEU-DET", "GC10-DET"], "baselines": ["YOLOv8", "YOLOv5"]
  },
  "light_review": {"verdict": "通过", "checks": [5 维]}
}
```

### 4.2 XXX 极小众 (no-dataset path)

```json
{
  "feasibility": {"verdict": "暂缓", "missing_evidence": ["题目研究对象极小众..."]},
  "light_review": {"verdict": "需修改", "checks": [...]}
}
```

### 4.3 PCB / 桥梁 / 皮肤 已知数据集命中

| 题目 | 期望数据集 | 实际命中 |
|---|---|---|
| PCB 缺陷检测 | DeepPCB | ✓ |
| 桥梁裂缝检测 | CODEBRIM | ✓ |
| 皮肤病变分类 | HAM10000 | ✓ |

---

## 5. 测试结果

### 5.1 后端单元 / API 测试

```text
apps/api/tests/test_one_topic_api.py
  test_health .......................................... PASSED
  test_analyze_yolo_steel_happy_path ................... PASSED
  test_analyze_niche_topic_triggers_shrink_or_pause .... PASSED
  test_analyze_pcb_bridge_skin_match_known_datasets .... PASSED
  test_request_validation .............................. PASSED
  test_stream_endpoint_emits_expected_events ........... PASSED
  test_keyword_breakdown_always_has_query_keywords ..... PASSED
                                                7 passed
```

### 5.2 Playwright e2e

```text
apps/web/e2e/test_one_topic_happy_path.py
  test_yolo_steel_happy_path_shows_5_blocks ............ PASSED
  test_intent_zh_visible ................................ PASSED
  test_risk_terms_chips ................................. PASSED

apps/web/e2e/test_one_topic_no_dataset.py
  test_niche_topic_triggers_shrink_or_pause ............ PASSED

apps/web/e2e/test_one_topic_review.py
  test_review_block_has_5_checks ........................ PASSED
  test_review_verdict_is_one_of_4 ...................... PASSED
  test_revision_checklist_visible ...................... PASSED

apps/web/e2e/test_one_topic_trace.py
  test_trace_panel_shows_key_events ..................... PASSED
  test_trace_count_increments ........................... PASSED
  test_clear_trace_button ............................... PASSED
                                                10 passed
```

**总计 17 passed / 0 failed.**

### 5.3 真实 uvicorn smoke

```text
后端 uvicorn 启动: http://127.0.0.1:18181/health → {"status":"ok","phase":"one_topic_mvp"}
前端 dev_server:    http://127.0.0.1:18182/        → 200 OK
POST /analyze (YOLO 钢材): 6 段产物齐, arXiv 真实 6 篇, NEU-DET/GC10-DET 命中
POST /analyze (XXX 小众): feasibility=暂缓, missing_evidence 包含数据集
POST /analyze/stream: SSE 事件流正常 (start / step / result / end)
```

---

## 6. 关键不变式 (对齐 CLAUDE.md)

- ✓ LLM 路径配 heuristic fallback (`llm.LLMUnavailable` 触发, 不让 LLM 挂掉服务)
- ✓ LLM 凭据从 `.env` 读 (`MINIMAX_API_KEY` 等), `.env` 不进 git
- ✓ pytest 总数: 7 (旧 0 + 新 7) + 10 e2e = 17 (旧仓库已删, 不计)
- ✓ 真实 uvicorn smoke 至少跑一次 (5.3 已确认)
- ✓ 不在 Pydantic v2 里用 `T | None = None` 默认参数 (全部用 `Field(default=None)` 或 `Field(default_factory=...)`)
- ✓ 不依赖 lifespan 外 ORM class (本版无 ORM, 无 DB)

---

## 7. 修了哪些 bug (相对旧版)

| bug | 旧版 | 新版 |
|---|---|---|
| 8 阶段入口不自然 | 强制 9 个字段 + 多选下拉 + 4 个 deadline | 1 个文本框, 其它可选 |
| LLM 挂掉全服务挂 | 旧 `chat_json` 失败 → 500 | `LLMUnavailable` 自动 fallback heuristic |
| 复杂 8 表 + 409 拦截 | 8 张表 + 7 个 409 链路 | 0 张表, 纯 in-memory 推数据 |
| Trace 是技术步骤 | "📊 评分", "🤖 调 M3" | "🔍 正在拆出方法词", "📚 正在搜索相关论文 (arXiv 真实检索)" |
| 一次问 9 字段 | 卡片 + 表单 + 字段齐备度公式 | 1 屏 1 输入 |

---

## 8. 后续 (不在本 MVP 范围)

按 SOP §14 第六步, OneTopic MVP 通过后, 再把后续 Phase 改成:
- Phase 05: 收缩 / Pivot 推荐
- Phase 06: 开题报告骨架
- Phase 07: 低门槛模拟审核 (MVP 已有轻量版)
- Phase 08: 导出与归档

但因为新版 OneTopic MVP 本身就是「先判断能不能做」, Phase 05-08 不再是必须的流程。
后续如需对接老毕设工作流, 可在 `OneTopicResponse` 上加 `expand_to_full_pipeline(req)` 函数复用本版的拆解结果。
