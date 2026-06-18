# Session 09 验收报告: 双栏证据工作台与 Agent Card Intake 入口

> 验收时间: 2026-06-18
> 阶段: Session 9 (按 `Plan/PaperAgent_Session09_双栏证据工作台与Agent卡片导入SOP.md`)
> Commit: `573a2284` (后续 amended 含 e2e 修复)

---

## 1. 本阶段范围

按 SOP §2, Session 09 把 Session 07 复核过的 EvidenceRef 落进"用户 vs 系统"双栏工作区, 并加 Agent Card Intake 最小入口.

交付:
- EvidenceItem 7 个新字段 (workspace_lane / workspace_order / paired_with / raw_input_type / raw_input_ref / extraction_confidence / extraction_warnings)
- 双栏工作台 (paper / dataset / repo 三类) + lane 切换 + 核心 / 拒绝栏
- Agent Card Intake: URL / 文字 → pending EvidenceCard (GitHub / arXiv / HF / Kaggle 自动识别)
- workspace_lane 进入 EvidenceRef ref_priority (selected +0.15, user_preferred +0.10, rejected -1.00)
- Markdown 报告 / EvidenceRef 联动: rejected lane 永不进 supports; user_preferred / selected 优先

不做 (SOP §3 黑名单):
- 拖拽排序
- 图片识别 / OCR
- PDF 解析
- 网页深爬
- 真实 GitHub API 强依赖
- Skill Marketplace
- 报告结构重写

---

## 2. 新增字段 (`apps/api/app/schemas_evidence.py`)

```python
WorkspaceLane = Literal["user_preferred", "system_found", "selected", "rejected"]
RawInputType = Literal["url", "text", "github", "dataset_page", "paper_page", "image", "pdf"]
```

EvidenceItem 扩展:

| 字段 | 默认 | 说明 |
|---|---|---|
| workspace_lane | "system_found" | 工作台栏位 (manual 默认 user_preferred, auto_search 默认 system_found, core → selected, rejected → rejected) |
| workspace_order | None | 用户排序 (后续用) |
| paired_with | [] | 论文-论文配对 (后续用) |
| raw_input_type | None | Agent Card Intake 输入类型 |
| raw_input_ref | None | 原始 URL / 文本 |
| extraction_confidence | None | Agent 抽取置信度 (0-1) |
| extraction_warnings | [] | 抽取风险 (e.g. "未实际验证 train/eval 脚本") |

`_derive_workspace_lane(review_status, current_lane)` helper:
- `core` → `selected`
- `rejected` → `rejected`
- 其余保留

`update_review()` 联动: 改 review_status 时自动同步 workspace_lane.

---

## 3. 新增 API

| 方法 | 路径 | 用途 | SOP |
|---|---|---|---|
| GET | `/{project_id}/workspace/board` | 三类双栏 (paper/dataset/repo) | §4.3 |
| PATCH | `/{project_id}/workspace/item` | 移动 / 标核心 / 拒绝 evidence (同步 review_status + 写 Trace) | §4.3 |
| POST | `/{project_id}/cards/intake` | Agent 卡片生成 (URL / 文字) | §4.4 |

Pydantic 模型 (新增 5 个):
- `EvidenceWorkspaceBoard`
- `WorkspaceBoardResponse`
- `WorkspaceItemPatch`
- `WorkspaceItemPatchResponse`
- `CardIntakeRequest` / `CardIntakeResponse` (在 one_topic.py 内)

后端服务:
- `apps/api/app/services/workspace.py` (~120 行)
- `apps/api/app/services/card_intake.py` (~170 行)

---

## 4. 双栏 UI 变化

### 4.1 工作台 (`#workspace-board`)

新增 tabs: paper / dataset / repo, 默认显示 paper. 每个 panel 内左右两栏:

```
📚 论文工作台
┌─────────────────────────┬──────────────────────────┐
│ 用户希望使用 (left)     │ 系统检索候选 (right)      │
│ ─────────────────────── │ ──────────────────────── │
│ [论文卡片 + 4 按钮]     │ [论文卡片 + 4 按钮]       │
└─────────────────────────┴──────────────────────────┘
```

按钮 (每张卡): `加入左侧` / `标核心` / `移到系统` / `拒绝`.

折叠区 `<details>` 内: 核心栏 (selected) + 拒绝栏 (rejected) 列表.

### 4.2 Agent 卡片导入 (`#card-intake-panel`)

```
🤖 Agent 卡片导入
[URL ▼] [content input] [hint input] [lane ▼] [生成卡片]
↓ 展开
[type pill] [conf pill] [warnings]
[title] [evidence_id · 状态 · 栏位]
[确认 (标 core)] [拒绝]
```

识别规则:
- `github.com/{owner}/{repo}` → repo
- `huggingface.co/.../...` → repo (model)
- `arxiv.org/abs/{id}` → paper
- `huggingface.co/datasets/...` → dataset
- `kaggle.com/datasets|competitions/...` → dataset
- hint 含 "论文/paper/文献/research" → paper
- hint 含 "数据集/dataset/数据" → dataset
- hint 含 "代码/工程/repo/baseline/实现/github" → repo
- 纯文本 → note

### 4.3 CSS (`apps/web/styles.css`)

新增 `.card-intake / .workspace-board / .ws-tab / .ws-lane / .ws-card` 样式 (左侧绿边框 / 右侧蓝边框).

---

## 5. Agent Card Intake 规则 (§4.4)

### 5.1 置信度

| input_type | confidence | warnings 关系 |
|---|---|---|
| url (无 warnings) | 0.80 | warnings 为空时高 |
| url (有 warnings) | 0.55 | warnings 非空时降 |
| text | 0.40 | 纯文本识别, 默认较低 |

### 5.2 warnings 生成

- paper (无 arXiv): "未识别为 arXiv URL" / "缺少 DOI"
- dataset (无 HF/Kaggle): "未识别为 HF/Kaggle 数据集 URL" / "缺少 license 信息"
- repo (无 GitHub): "未识别为 GitHub URL" / "未实际验证 train/eval 脚本"
- 纯文本: "纯文本未识别具体类型, 默认 note"

### 5.3 卡片写入

所有 assistant_intake 卡片默认:
- `review_status = "pending"`
- `source_mode = "assistant_intake"`
- `workspace_lane = target_lane` (默认 user_preferred)
- 写入 evidence pool, 立即可被 EvidenceRef 看到 (但因 pending, 不会进 supports)

用户确认 (在导入面板点 [确认]) → PATCH `/workspace/item` → lane=selected, status=core → 可进 supports.

---

## 6. EvidenceRef / Markdown 联动 (§6)

### 6.1 _ref_priority 公式更新

```
旧: 0.40 review + 0.30 score + 0.15 type + 0.10 recency + 0.05 url_verified
新: 旧公式 + lane_bonus
```

LANE_BONUS:
- `selected` = +0.15
- `user_preferred` = +0.10
- `system_found` = +0.00
- `rejected` = -1.00

### 6.2 _select_role 增加 lane 参数

```python
def _select_role(review_status, score, evidence_type, lane="system_found"):
    if lane == "rejected" or review_status == "rejected":
        return "alternative"  # 反例/排除
    ...
```

所有 build_*_refs 调用更新为传 lane. rejected lane 永不进 supports.

### 6.3 Markdown 报告

`final_package.py` 复用 evidence_refs 的过滤; 重建时新规则自动生效. rejected 不进 citation_list, user_preferred / selected 优先.

---

## 7. 后端测试结果

新增 `apps/api/tests/test_session9_workspace_board.py` (12 tests, 全部通过):

```
test_01_board_groups_by_type                       PASSED
test_02_manual_default_user_preferred              PASSED
test_03_auto_default_system_found                  PASSED
test_04_patch_moves_evidence                       PASSED
test_05_mark_core_sets_review_status               PASSED
test_06_rejected_lane_excluded_from_supports       PASSED
test_07_user_preferred_priority_higher             PASSED
test_08_intake_github_to_repo                      PASSED
test_09_intake_arxiv_to_paper                      PASSED
test_10_intake_hf_kaggle_to_dataset                PASSED
test_11_assistant_intake_default_pending           PASSED
test_12_intake_pending_excluded_from_markdown      PASSED

12 passed in 0.39s
```

回归: `apps/api/tests/` 共 **97 passed** (85 Session 8 + 12 Session 9), 101s.

---

## 8. Playwright 测试结果

新增 `apps/web/e2e/test_one_topic_session9_workspace_board.py` (8 tests, 全部通过):

```
test_01_workspace_board_visible                PASSED
test_02_three_type_panels_exist                PASSED
test_03_add_to_left_button                     PASSED  (修: wait_for_selector)
test_04_mark_core_button                       PASSED  (修: state="attached" 因 selected 在 <details> 内默认折叠)
test_05_reject_excluded_from_citations         PASSED
test_06_card_intake_panel_visible              PASSED
test_07_github_url_creates_repo_card           PASSED
test_08_intake_card_shows_confidence_warnings  PASSED

8 passed in 316.54s (5:16)
```

测试覆盖 (SOP §7.2):
1. 页面显示双栏证据工作台 ✓
2. paper / dataset / repo 三类分区存在 ✓
3. 系统候选卡片可以加入左侧 (right → user_preferred) ✓
4. 卡片可以标为核心 (right → selected / core) ✓
5. 拒绝卡片后 Markdown 不再正向引用 (rejected 不进 citation_list) ✓
6. Agent 卡片导入面板存在 ✓
7. 输入 GitHub URL 后生成 repo 卡片 (识别为 repo, confidence 0.55) ✓
8. 生成的卡片显示 pending / extraction_confidence / warning ✓

修复要点 (amend 进 commit `573a2284`):
- `api_client` fixture 由 `TestClient(app)` 改为 urllib HTTP 走 18181, 跟浏览器共享 ev_store.
- test_03/04 由固定 `wait_for_timeout(2000)` 改为 `wait_for_selector` 等待 DOM 真正出现该 eid.
- test_04 用 `state="attached"` (selected lane 在 `<details>` 内, 默认折叠, Playwright 看不到 visible).

---

## 9. 真实 uvicorn smoke

启动 uvicorn 18182, 跑 YOLO 钢材 + manual 添加 + intake:

- POST /workspace/board → 200, papers right=6, datasets right=2, repos right=2
- POST /workspace/item {eid, lane: "user_preferred", status: "accepted"} → 200, trace_event 写入
- POST /cards/intake (https://github.com/ultralytics/ultralytics) → 200, card_type=repo, confidence=0.55, warning=["未实际验证 train/eval 脚本"]
- POST /final-package/build → rejected eid 不在 citation_list; user_preferred 排在 system_found 前

3 个新 endpoint 全部 200, 字段联动正确.

---

## 10. 未做项

按 SOP §3 黑名单:
- 拖拽排序 (按钮移动替代)
- 图片识别 / OCR
- PDF 解析
- 网页深爬 (URL 规则 + hint 关键词)
- 真实 GitHub API (用 URL 规则生成 pending)
- Skill Marketplace
- 报告结构重写

预留 (后续 Session):
- `workspace_order` 字段已就位, 排序逻辑未做
- `paired_with` 字段已就位, 配对逻辑未做
- `image` / `pdf` input_type 已注册, 实际识别未做

---

## 11. 下一 Session 建议

按 SOP §10: **Session 10 — 多源检索与 URL 验证增强**

重点:
- OpenAlex / Semantic Scholar / GitHub URL 轻验证 (用 HEAD 请求 + JSON metadata)
- dataset URL 验证 (HF / Kaggle API key 可选)
- `url_verified` / `extraction_confidence` 接入 EvidenceRef (类似 ref_priority 加项)
- assistant_intake 卡片可自动 populate (title / author / year) 而非仅占位

仍围绕"证据工作台", 不跳到完整论文写作.

---

## 12. 一句话总结

Session 09 把证据工作台从单栏列表升级为"用户 vs 系统"双栏, 引入 workspace_lane 字段 (selected / user_preferred / system_found / rejected) 联动 ref_priority; Agent Card Intake 从 GitHub/arXiv/HF/Kaggle URL 生成 pending EvidenceCard, 用户确认后才进 supports. Markdown 导出不受影响, 已拒绝 / pending 证据自动排除.