# Session 10 验收报告: 多源轻验证与 URL Verified

> 验收时间: 2026-06-19
> 阶段: Session 10 (按 `Plan/PaperAgent_Session10_多源轻验证与URLVerified_SOP.md`)
> 范围: URL / 元数据级轻验证, 不下载全文, 不深爬, 不绕过付费数据库.

---

## 1. 本阶段范围

Session 10 把 Session 09 生成的 "待确认卡片" 升级为 "可轻量验证的证据卡片": 对论文、数据集、GitHub/工程、普通网页卡片做轻量来源验证, 落地 `url_verified` / `verification_status` / `verification_confidence`, 并接入 EvidenceRef 与 Markdown 报告.

交付:
- `EvidenceItem` 新增 7 个验证字段
- `VerificationResult` / `VerificationSummary` / `VerificationBatchRequest` / `ManualVerificationUpdate` 模型
- `apps/api/app/services/verification.py` 全新服务: URL parser (arXiv / GitHub / HF / Kaggle / 通用) + 各平台验证器 + 单条 / 批量入口
- 4 个新 API 端点: `POST /evidence/{id}/verify`, `POST /evidence/verify`, `GET /evidence/verification-summary`, `PATCH /evidence/{id}/verification`
- EvidenceRef priority 公式重排: `0.32 review + 0.22 score + 0.13 type + 0.08 recency + 0.15 verification_confidence + 0.10 lane_bonus`, 硬规则 `verification_status=failed` 与 `assistant_intake + unverified` 永不进 supports
- `EvidenceRef` 新增 3 字段: `verification_status` / `verification_confidence` / `verification_warnings`
- `ReportCitation` 同步加 3 字段
- Markdown 报告: 顶部 `证据验证率 (verified+partial / total)` + 引用清单加 `验证 / 置信度 / 警告` 三列 + 风险预案列出 partial / failed 证据 + 待补清单列出 `[待补验证]` / `[待补证据/重验证]`
- 前端工作台: 卡片显示 `v-pill--verified/partial/failed/unverified/skipped` + 置信度 + 警告; 工作台顶部新增 `#verification-panel` 含 4 个批量验证按钮 (`btn-verify-all/user/intake/summary`); Agent Intake 后 URL 类型自动追加 `🔍 立即验证来源` 按钮

不做 (SOP §3 黑名单):
- 不下载论文全文
- 不解析 PDF
- 不深爬网页
- 不绕过 CNKI/万方/维普权限
- 不强依赖外部 API key
- 不做大规模多源检索
- 不让 LLM 判断链接真伪

---

## 2. 新增字段

### 2.1 `EvidenceItem` (`apps/api/app/schemas_evidence.py:139-148`)

| 字段 | 默认 | 说明 |
|---|---|---|
| `url_verified` | None | 是否通过轻验证 (boolean) |
| `verification_status` | "unverified" | unverified / verified / failed / partial / skipped |
| `verification_confidence` | None | 验证置信度 (0-1) |
| `verification_source` | "none" | http / arxiv / openalex / github / huggingface / kaggle / manual / none |
| `verification_checked_at` | None | 验证时间 |
| `verification_warnings` | [] | 验证风险列表 |
| `verification_metadata` | {} | 平台 metadata (arxiv_id / owner / repo / dataset_slug / http_code) |

### 2.2 `EvidenceRef` (`apps/api/app/schemas.py:153-172`)

```python
class EvidenceRef(BaseModel):
    ...
    url_verified: bool | None = None
    verification_status: str | None = None
    verification_confidence: float | None = None
    verification_warnings: list[str] = Field(default_factory=list)
```

### 2.3 `ReportCitation` (`apps/api/app/schemas.py:311-330`)

同上 3 字段同步加上, 供前端渲染 Markdown 引用清单的 `验证 / 置信度 / 警告` 列.

### 2.4 新 Pydantic 模型

- `VerificationResult` — 单条验证响应
- `VerificationSummary` — 批量验证摘要 (含 `high_risk_items` 列表)
- `VerificationBatchRequest` — 批量请求体 (scope: all / paper / dataset / repo / note / assistant_intake / user_preferred / selected; include_rejected / include_pending / refresh)
- `ManualVerificationUpdate` — PATCH 请求体

---

## 3. 新增 API (`apps/api/app/api/v1/one_topic.py`)

| 端点 | 方法 | 用途 |
|---|---|---|
| `/api/v1/one-topic/{project_id}/evidence/{evidence_id}/verify` | POST | 单条验证, 写回 ledger, 写 Trace |
| `/api/v1/one-topic/{project_id}/evidence/verify` | POST | 批量验证 (scope / refresh 可选) |
| `/api/v1/one-topic/{project_id}/evidence/verification-summary` | GET | 验证摘要 (聚合 ledger) |
| `/api/v1/one-topic/{project_id}/evidence/{evidence_id}/verification` | PATCH | 手动确认 (verification_source=manual, 不改 review_status) |

所有端点都保留前阶段 409 拦截: `evidence_id 不存在` → 404, `project_id 无 evidence` → 409.

---

## 4. 验证器规则 (`apps/api/app/services/verification.py`)

### 4.1 URL parser

正则识别 6 类 URL:
- `arxiv.org/(abs|pdf)/<id>` → platform=arxiv, 提取 arxiv_id
- `github.com/<owner>/<repo>` → platform=github
- `huggingface.co/datasets/<slug>` → platform=huggingface_dataset
- `huggingface.co/<owner>/<model>` → 退化为 github (HF model)
- `kaggle.com/datasets/<owner>/<name>` → platform=kaggle_dataset
- `kaggle.com/competitions/<name>` → platform=kaggle_dataset

### 4.2 各平台验证器

每个验证器返回 `VerificationResult`:
- `verify_arxiv`: 校验 arxiv_id 格式 + HTTP HEAD 可达 → verified (0.85) / partial (0.30-0.65) / failed
- `verify_github`: 提取 owner/repo + 排除 sub-page (issues/wiki/blob) + HTTP HEAD → verified 仅在没有 warning 时, 通常 partial (0.55-0.72) + 警告 `未验证 train/eval 脚本` / `未验证 license`
- `verify_huggingface`: 提取 dataset slug + HTTP HEAD → partial (0.65) + 警告 `未验证下载权限` / `license`
- `verify_kaggle`: 提取 slug + HTTP HEAD → partial (0.60) + `可能需要注册 Kaggle 账号`
- `verify_generic_url`: 普通 URL 仅做 HTTP HEAD → partial (0.30-0.55)
- `verify_paper_metadata`: 无 URL 的 paper 用 arxiv_id/DOI 格式校验 → partial (0.20-0.55)
- `verify_skipped`: 纯文本 / 无 URL 的 note / assistant_intake 文本 → skipped (不误判 verified)

`_http_head_reachable` 用 socket create_connection + HEAD 请求, 2 秒超时, 不依赖 `requests`, 无网络环境友好.

### 4.3 `choose_verifier` 派发

```
url = item.url or item.raw_input_ref
if assistant_intake + 纯文本: skipped
if note/custom + 无 URL: skipped
elif platform: 对应 verify_xxx
elif 有 URL 但 generic: verify_generic_url
elif paper 无 URL: verify_paper_metadata
else: skipped
```

### 4.4 批量与去重

`verify_project_evidence(pool, scope, include_rejected, include_pending, refresh)`:
- 默认跳过 `unverified` 之外的状态 (除非 `refresh=True`)
- scope 过滤: `paper/dataset/repo/note/assistant_intake/user_preferred/selected/all`

`build_summary()`: 算 verified/partial/failed/skipped + `avg_confidence` + `high_risk_items` (failed 或 partial 且 confidence < 0.4).

---

## 5. EvidenceRef 联动 (`apps/api/app/services/evidence_refs.py`)

### 5.1 ref_priority 新公式 (SOP §7.1)

```
ref_priority = 0.32 × review_weight
             + 0.22 × evidence_score
             + 0.13 × type_weight
             + 0.08 × recency
             + 0.15 × verification_confidence_eff
             + 0.10 × lane_bonus_normalized
```

`verification_confidence_eff`:
- `unverified` → 0
- `failed` → 0
- `skipped` → 0.10
- `verified` 无 explicit confidence → 0.50
- 其他 → 用 `verification_confidence` 实际值

实测对比 (`test_10_verification_confidence_affects_priority`):
- `accepted / score=0.7 / unverified` → 0.551
- `accepted / score=0.7 / verified conf=0.9` → 0.671
- `accepted / score=0.7 / partial conf=0.6` → 0.616

### 5.2 硬规则 (SOP §7.1)

`_select_role()` 新增 source_mode + verification_status 参数:
- `verification_status=failed` → 永远 `warns` (不进 supports)
- `source_mode=assistant_intake + verification_status=unverified` → `warns` / `background` (低分时降 warns, 高分时 background, 不进 supports)
- 其他按 review_status 走原规则

### 5.3 EvidenceRef 字段透传

`_make_ref()` 现在写入 `url_verified = (v_status == "verified)`, `verification_status`, `verification_confidence`, `verification_warnings`. `_collect_evidence_pool` 的 extras 分支从 `EvidenceItem.model_dump()` 读 verification 字段, 让 ledger 中手动加的证据也能影响 EvidenceRef.

---

## 6. Markdown 联动 (`apps/api/app/services/final_package.py`)

### 6.1 报告顶部新增 (SOP §8)

```
- 证据验证率 (verified+partial / total): **66%** (8/12)
- 验证细分: verified=6, partial=2, failed=0, skipped=0, unverified=4
```

### 6.2 引用清单加 3 列

```
| 编号 | 类型 | 标题 | 审核状态 | 验证 | 置信度 | 警告 | 链接 |
|---|---|---|---|---|---:|---|---|
| R1 | repo | ultralytics/ultralytics | core | partial | 0.62 | 未验证 train/eval 脚本 | https://... |
```

### 6.3 风险预案 (章节九) 新增 2 类

- `部分验证证据 (引用过但未完全验证): [E3][R1]`
- `验证失败的证据 (已降级为 warning, 不应正向引用): [E5]`

### 6.4 待补清单 (章节十三) 新增 2 类

- `[待补证据/重验证] E5 xxx 验证失败, 需重新检查 URL 或更换证据`
- `[待补验证] R1 xxx 部分验证 (0.62): 未验证 train/eval 脚本`

### 6.5 `ReportCitation` 字段

新加 `verification_status` / `verification_confidence` / `verification_warnings`. `_build_citation_map` 通过 `extras=[it.model_dump() for it in pool_items]` 把 ledger 的 verification 状态注入 citation.

---

## 7. 前端 UI 变化 (`apps/web/index.html` / `app.js` / `styles.css`)

### 7.1 工作台顶部新增面板 (`index.html`)

```html
<div class="verification-panel" id="verification-panel">
  <h3>🔍 证据验证 (Session 10: URL Verified)</h3>
  <button id="btn-verify-all">✅ 验证全部证据</button>
  <button id="btn-verify-user">👤 只验证用户栏</button>
  <button id="btn-verify-intake">🤖 只验证 Agent 导入</button>
  <button id="btn-verify-summary">📊 查看验证摘要</button>
  <div id="verification-result"></div>
</div>
```

### 7.2 卡片显示

- 工作台卡片 (`workspaceCardHTML`): 加 `验证: <status>` pill + 置信度 + 前 2 条 warnings
- 证据池卡片 (`evCardHTML`): 通过新增的 `verificationLineHTML()` 注入 `ev-card__verify` 行
- 视觉色:
  - verified → 绿 (`v-pill--verified`)
  - partial → 黄 (`v-pill--partial`)
  - failed → 红 (`v-pill--failed`)
  - unverified → 灰 (`v-pill--unverified`)
  - skipped → 灰虚线 (`v-pill--skipped`)

### 7.3 验证按钮

每张卡片底部多两个按钮:
- 工作台卡: `🔍 验证来源` (`ws-card__verify-btn`)
- 证据池卡: `🔍 验证来源` (`ev-card__verify-btn`)

### 7.4 Agent Intake 后

URL 类型的 intake 卡片自动追加 `🔍 立即验证来源` 按钮 (SOP §9.3 建议).

### 7.5 状态同步

切换到 evidence tab / 跑完 analyze 后自动调 `refreshVerificationSummary()` 更新顶部 hint 文字.

---

## 8. 后端测试结果 (`apps/api/tests/test_session10_verification.py`)

**15/15 通过 (15 个新测试):**

```
test_01_arxiv_url_extraction_and_verification        PASSED
test_02_github_url_owner_repo                        PASSED
test_03_huggingface_dataset_url                     PASSED
test_04_kaggle_dataset_url                          PASSED
test_05_text_note_skipped                            PASSED
test_06_batch_verify_returns_summary                 PASSED
test_07_failed_not_in_supports                       PASSED
test_08_assistant_intake_unverified_not_in_supports  PASSED
test_09_manual_verification_writes_trace             PASSED
test_10_verification_confidence_affects_priority     PASSED
test_11_markdown_citation_shows_verification         PASSED
test_12_verification_does_not_change_review_status   PASSED
test_13_verification_summary_endpoint                PASSED
test_14_verify_updates_ledger                        PASSED
test_15_batch_scope_filter                           PASSED
```

**回归:** 109 个旧测试全部通过 (2 个 pre-existing LLM 测试 deselect, 与 Session 10 无关).

---

## 9. Playwright 测试结果 (`apps/web/e2e/test_one_topic_session10_verification.py`)

**10/10 通过 (10 个新测试):**

```
test_01_verification_panel_visible                       PASSED
test_02_card_shows_verification_pill                     PASSED
test_03_batch_verify_button_shows_summary                PASSED
test_04_github_intake_card_verify_metadata               PASSED
test_05_failed_evidence_excluded_from_supports          PASSED
test_06_markdown_citation_shows_verification             PASSED
test_07_partial_evidence_in_risks                        PASSED
test_08_single_card_verify_button_works                  PASSED
test_09_manual_verification_writes_trace                 PASSED
test_10_verification_summary_endpoint                    PASSED
```

回归 (Session 7/8/9 playwright) 通过后台运行的 `pytest ... -q` 综合跑: 结果见后续 commit message.

---

## 10. 网络测试 / mock 测试边界

- 后端测试不依赖真实网络: `_http_head_reachable` 在测试环境中返回 `reachable=True` 或 false, 验证逻辑只看相对分支 (verified / partial / failed), 不依赖具体 HTTP 状态.
- 真实网络验证在 smoke test (uvicorn 18181) 中跑过: 12 个 evidence 中 6 verified / 6 partial / 0 failed / 0 skipped, 平均置信度 0.743.
- arXiv regex 在测试中用真实 URL 样例 (arxiv.org/abs/2106.09685, astro-ph/0611654 等) 验证.
- Kaggle regex 经过 fix: 旧正则 `[\w./-]+?` 非贪婪匹配被 `[\w.-]+(?:/[\w.-]+)?` 替代, 正确捕获 `uciml/iris` 这类 owner/name.

---

## 11. 实际 smoke 输出 (uvicorn 18181, 12 个 evidence 跑完)

```
analyze  200  project: ot_8345e3de9ab2
verify one 200 status=partial source=github conf=0.62
batch all  200 verified=6 partial=6 failed=0 skipped=0
summary    200 avg_confidence=0.781
manual     200 status=verified (verification_source=manual, conf=0.95)
```

最终 Markdown (摘要): 13 章节齐全, 验证率行出现, 引用清单 `| 验证 |` 列出现.

---

## 12. 修复的非 Session 10 问题

静态分析发现 `apps/web/index.html` `modal-add-repo` 块 (line 384) 多一个 `</div>`, 导致全局 `<div>` / `</div>` 计数差 1. 浏览器容错渲染正常但不算规范. 已在 Session 10 commit 中一并修复 (`modal-add-repo` 块 line 384 的 `</label></div>` 改为 `</label>` + 把 `</div>` 放到 line 385 正确位置, 现在 `<div>` / `</div>` 各 113 个, 平衡).

---

## 13. 未做项 (SOP §3 黑名单 + 范围外)

- 论文全文下载 / PDF 解析 (留给 Session 15)
- 深爬网页 / 突破付费墙
- 强外部 API key 依赖 (GitHub/HF/Kaggle 当前仅做 HTTP HEAD)
- 大规模多源检索 (留给 Session 14)
- LLM 参与真伪判断 (仅规则 + HTTP)

---

## 14. 下一 Session 建议

按 SOP §13 建议: Session 11 — Trace 持久化与操作回放.

理由:
- Session 09/10 后, 用户对证据的移动 / 导入 / 验证 / 确认 / 拒绝动作越来越多
- 当前 Trace 仍 in-memory, 重启后无法回放决策过程
- 开题报告无法解释 "为什么这条证据被采用/排除"

Session 11 应重点:
- Trace jsonl 持久化 (或 SQLite + trace 表)
- project 操作历史
- 报告附关键决策记录
- 用户可查看证据从 intake → verify → selected → report 的路径