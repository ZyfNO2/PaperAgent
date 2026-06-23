# Session 24 验收报告：Query Plan & Candidate Cards

> 日期：2026-06-20
> SOP：Plan/PaperAgent_Session24_检索计划与候选资源卡SOP.md
> 状态：✅ 通过

## 1. 本轮目标

从 keyword_review 确认结果出发，生成 query_plan（三类检索），再生成候选资源卡，
用户可保存、淘汰、标记复核。候选资源只进 Candidate，不直接成为 Evidence。

## 2. 关键产物

### 2.1 新增文件

- `apps/api/app/schemas_candidates.py` — 候选资源 Pydantic 模型
  - `QueryItem` / `QueryPlan`: 检索计划结构
  - `CandidateResource`: 候选资源（kind, title, url, matched_keywords, risk_flags, user_mark）
  - `CandidateList`: 候选列表 + query_plan 关联
  - `CandidateActionRequest`: 用户操作请求
  - `BlockedResponse`: keyword 未确认时返回
  - `candidate_is_not_evidence()`: 验证候选 ≠ 证据

- `apps/api/tests/test_session24_candidate_resources.py` — 20 个 pytest 用例
- `apps/web/e2e/test_one_topic_session24_candidate_cards.py` — 10 个 Playwright 测试

### 2.2 已有文件（S23 已完成，本轮仅使用）

- `apps/web/prompt_protocol.js` — STEP_CONTRACTS、isToolAllowed、validateLLMOutput
- `apps/web/step_deck.js` — startExtendedMockStream、startCandidatesMockStream

## 3. Query Plan 结构

```json
{
  "queries": [
    { "source": "paper", "query": "YOLO 钢材表面缺陷检测", "priority": "high" },
    { "source": "dataset", "query": "NEU steel surface defect dataset", "priority": "medium" },
    { "source": "repo", "query": "ultralytics yolov8", "priority": "low" }
  ]
}
```

每条 query 包含：source（paper/dataset/repo）、query、keywords、priority、reason。

## 4. Candidate Schema

```json
{
  "candidate_id": "cand_001",
  "kind": "paper",
  "title": "Steel Surface Defect Detection Using Improved YOLOv5",
  "url": "https://example.com/paper1",
  "source": "IEEE Access",
  "matched_keywords": ["YOLO", "钢材表面缺陷", "目标检测"],
  "risk_flags": ["url_unverified"],
  "status": "candidate",
  "user_mark": "unreviewed"
}
```

`kind` 枚举: paper | dataset | repo | thesis_template | benchmark
`user_mark` 枚举: unreviewed | saved | rejected | needs_review | selected

## 5. 用户标记动作

| 动作 | 效果 | 写 Evidence |
|------|------|------------|
| save_candidate | user_mark → saved | ❌ 不写 |
| reject_candidate | user_mark → rejected | ❌ 不写 |
| mark_needs_review | user_mark → needs_review | ❌ 不写 |
| promote_to_selected | user_mark → selected | ❌ 不写（≠ Evidence） |

## 6. 候选与 Evidence 的边界

| 属性 | CandidateResource | Evidence |
|------|-------------------|----------|
| status | "candidate" | "evidence" |
| support_level | 无此字段 | 有此字段 |
| verification_status | 无此字段 | 有此字段 |
| promote_to_selected | ✅ | N/A |
| 直接写进报告 | ❌ | ✅ |

`candidate_is_not_evidence()` 函数验证：status == "candidate"。

## 7. Mock Stream 扩展流

```
keyword_review approve
  → step_resumed → step_started(query_plan) → token_delta
    → card_delta(SearchQueryPlanCard: 6 queries)
    → step_pause(query_plan)
  → [用户 approve query_plan]
    → step_resumed → step_started(candidates) → token_delta
      → card_delta(RetrievalCandidateCard: paper)
      → card_delta(RetrievalCandidateCard: dataset)
      → card_delta(RetrievalCandidateCard: repo)
      → step_pause(candidates)
```

## 8. 测试结果

### 8.1 后端测试（20 passed）

```
test_session24_candidate_resources.py — 20 passed

S24-B-1: blocked response schema (2 tests) ✅
S24-B-2: query_plan 结构 (4 tests) ✅
S24-B-3: candidate resource (3 tests) ✅
S24-B-4: candidate != evidence (2 tests) ✅
S24-B-5: status 枚举 (2 tests) ✅
S24-B-6: risk_flags url_unverified (2 tests) ✅
S24-B-7: user mark / action (4 tests) ✅
S24-B-8: S17 baseline 不回退 (1 test) ✅
```

### 8.2 Playwright 测试（10 passed）

```
test_one_topic_session24_candidate_cards.py — 10 passed

S24-PW-1: ✅ 未确认关键词时 query_plan blocked
S24-PW-2: ✅ 确认关键词后显示 paper/dataset/repo query
S24-PW-3: ✅ 生成 3 张候选资源卡
S24-PW-4: ✅ 候选卡显示 URL 和 matched_keywords
S24-PW-5: ✅ save_candidate 按钮存在
S24-PW-6: ✅ reject_candidate 按钮存在
S24-PW-7: ✅ promote_to_selected 不写 Evidence
S24-PW-8: ✅ eventBuffer 记录 3 条候选事件
S24-PW-9: ✅ S21 keyword gate 不回退
S24-PW-10: ✅ 非法 candidate card 降级为 invalid 卡

Total tests collected: 454
```

## 9. S17/S21/S22/S23 不回退确认

- S17 OneTopicRequest schema 正常 ✅
- S21 rail 9 步 + mock 流暂停 + approve 推进 ✅
- S22 ComponentRegistry 6 张核心卡 ✅
- S23 PromptProtocol + isToolAllowed + validateLLMOutput ✅

## 10. 后续建议

Session 25 可基于：
- `startExtendedMockStream()` + `startCandidatesMockStream()` 构建完整 9 步流程
- `CandidateActionRequest` 接入后端 API
- `candidate_is_not_evidence()` 作为 Evidence 写入前的强校验
- 真实联网检索可作为增强层接入（不作为通过条件）
