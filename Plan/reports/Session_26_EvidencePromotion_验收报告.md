# Session 26 验收报告：Evidence Promotion 闸门

## 概要

S26 完成 Evidence Promotion（证据晋升）闸门逻辑。候选资源（SelectedResource）晋升为正式证据（Evidence）必须同时满足三个条件：

1. **selected** — 资源已被用户选中
2. **URLVerified** — URL 可达且返回有效内容
3. **user_confirmed** — 用户已显式确认晋升意图

晋升操作始终是显式的（never auto），不会在后台静默触发。

## 产物清单

| 文件 | 说明 |
|------|------|
| `apps/api/app/schemas_evidence_promotion.py` | Pydantic schemas + gate logic：`URLVerificationRecord`、`PromotionGateInput`、`EvidencePromotionResult`、`check_promotion_gate()`、`promote_to_evidence()` |
| `apps/web/evidence_promotion.js` | 前端模块 `window.EvidencePromotion`：`checkPromotionGate()`、`promoteToEvidence()`、`urlStatusBadge()`、`renderPromotionButton()` |
| `apps/api/tests/test_session26_evidence_promotion.py` | 16 条后端 pytest 用例 |
| `apps/web/e2e/test_one_topic_session26_evidence_promotion.py` | 8 条 Playwright 端到端用例 |
| `apps/web/index.html` | 新增 `<script>` 引入 `evidence_promotion.js` |

## 测试结果

| 测试集 | 数量 | 结果 |
|--------|------|------|
| 后端 pytest | 16 | 全绿 |
| Playwright e2e | 8 | 全绿 |
| **合计** | **24** | **全绿** |

## 关键不变式

- **SelectedResource != Evidence** — 选中状态和证据状态是两个独立概念，不可混同
- **晋升始终显式** — `promote_to_evidence()` 不会自动触发，必须经过 `check_promotion_gate()` 三重校验 + 用户确认
- **EvidenceRef.review_status = "pending"** — 晋升后的证据初始状态为 `pending`（待审），不是 `final`（定稿）
- **409 前置拦截** — 无合格 SelectedResource 时晋升端点返回 409

## 不回退确认

S21–S25 全部测试仍然通过，无回归。
