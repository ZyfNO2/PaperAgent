# PaperAgent Session 26 SOP：Candidate 到 Evidence 晋升与 URLVerified 桥接

> 日期：2026-06-21  
> 前置：Session 25 已有 SelectedResource 双栏工作台。  
> 本轮目标：建立“候选/选中资料”进入 EvidenceRef 之前的轻验证与晋升流程。

---

## 1. 目标

```text
只有 selected + URLVerified + 人工确认的资源，才能尝试晋升为 EvidenceRef。
```

本轮不是让所有候选变证据，而是建立闸门。

---

## 2. 晋升条件

必须同时满足：

```text
1. candidate.user_mark == selected；
2. selected_resource 存在；
3. url_verified.status in verified | partial；
4. 用户点击 promote_to_evidence；
5. candidate_is_not_evidence() 已通过；
6. EvidenceRef schema 校验通过。
```

禁止：

```text
未验证 URL 晋升；
未选中 Candidate 晋升；
LLM 自动晋升；
UI action 直接写 supports；
URLVerified 失败仍强行晋升。
```

---

## 3. 新增模型

```text
EvidencePromotionRequest
  selected_id
  candidate_id
  promotion_reason
  claim_hint
  user_confirmed

EvidencePromotionResult
  status: blocked | eligible | promoted
  evidence_ref?
  blockers[]
```

建议文件：

```text
apps/api/app/services/evidence_promotion.py
apps/api/app/schemas_evidence_promotion.py
apps/api/tests/test_session26_evidence_promotion.py
apps/web/evidence_promotion.js
apps/web/e2e/test_one_topic_session26_evidence_promotion.py
```

---

## 4. URLVerified 桥接

桥接字段：

```text
candidate.url
candidate.risk_flags
selected.verification_status
url_verified.status
url_verified.checked_at
url_verified.failure_reason
```

UI 展示：

```text
未验证：灰色；
验证通过：绿色；
部分可用：黄色；
失败：红色；
```

---

## 5. EvidenceRef 输出

晋升成功后生成：

```text
evidence_id
source_type
source_url
title
claim
verification_status
candidate_id
selected_id
created_from: candidate_promotion
```

仍然不直接生成：

```text
supports
final claim
report paragraph
```

---

## 6. 测试

后端：

```text
1. 未 selected -> blocked；
2. URL 未验证 -> blocked；
3. URL failed -> blocked；
4. verified + selected + user_confirmed -> promoted；
5. partial -> eligible 但带 warning；
6. promoted EvidenceRef 反向引用 candidate_id；
7. EvidenceRef 不含 report final claim；
8. candidate_is_not_evidence 仍通过。
```

Playwright：

```text
S26-PW-1：候选未选中时晋升按钮 disabled；
S26-PW-2：选中但 URL 未验证时显示 blocked；
S26-PW-3：URLVerified 后按钮可用；
S26-PW-4：晋升后 EvidenceRefCard 出现；
S26-PW-5：EvidenceRef 可追溯到 Candidate；
S26-PW-6：晋升不生成 supports；
S26-PW-7：失败 URL 显示原因；
S26-PW-8：S25 双栏不回退。
```

---

## 7. 验收标准

```text
1. Candidate -> Evidence 有明确闸门；
2. URLVerified 状态参与晋升；
3. 用户必须确认；
4. EvidenceRef 可追溯 Candidate；
5. 不直接生成 supports；
6. 后端测试通过；
7. Playwright 通过；
8. S17/S21-S25 不回退。
```

---

## 8. 完工报告

```text
Plan/reports/Session_26_EvidencePromotion_URLVerified_验收报告.md
```

