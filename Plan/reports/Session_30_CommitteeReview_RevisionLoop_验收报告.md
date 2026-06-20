# Session 30: 委员会复核与修订环 — 验收报告

## 概要

| 项目 | 内容 |
|------|------|
| Session | 30 |
| SOP | `Plan/PaperAgent_Session30_*.md` |
| 目标 | 委员会复核与修订环（§5: 5视角复核 → 修订 action → 再次复核） |
| 状态 | ✅ 全部通过 |

## 交付物

### 后端
- `apps/api/app/schemas_review.py` — ReviewRound / ReviewIssue / RevisionAction / ReviewHistory / ReviewRequest 等 Pydantic schema；Severity / ReviewVerdict / ReviewPerspective / RevisionActionType 枚举；can_verdict_pass() 判定函数
- `apps/api/app/services/review.py` — 5 视角复核函数（advisor/method/experiment/writing/risk）；run_review() 组合检查 → ReviewRound；get_review_history() / clear_review_history() 历史管理
- `apps/api/app/api/v1/one_topic.py` — POST /review（提交复核）、GET /review/{topic_title}/history（查看历史）

### 前端
- `apps/web/committee_review.js` — 委员会复核 UI 模块；5 视角分组、severity 排序、revision action 渲染、复核历史展示；window.CommitteeReview 公开 API

## 测试结果

### 后端 pytest（8 条）
| # | 测试 | 结果 |
|---|------|------|
| 1 | 缺数据集 → fatal/high issue | ✅ |
| 2 | 无 baseline → fatal/high issue | ✅ |
| 3 | 无证据段落 → medium/high issue | ✅ |
| 4 | fatal 未处理不得 pass | ✅ |
| 5 | accept_fix 生成 revision action | ✅ |
| 6 | rerun_review 保留历史轮次 | ✅ |
| 7 | revise_topic 触发回到 keyword_review | ✅ |
| 8 | ReviewRound 可序列化 | ✅ |

### Playwright E2E（9 条）
| # | 测试 | 结果 |
|---|------|------|
| PW-1a | CommitteeReview 模块已加载 | ✅ |
| PW-1b | review 卡片渲染 | ✅ |
| PW-2 | 5 类视角分组可见 | ✅ |
| PW-3 | severity badge 可见 | ✅ |
| PW-4 | accept_fix 按钮存在 | ✅ |
| PW-5 | fatal verdict 不能通过 | ✅ |
| PW-6 | 多次 review 轮次递增 | ✅ |
| PW-7 | revise_topic action 类型存在 | ✅ |
| PW-8 | S29 ProposalDraft 模块仍可用 | ✅ |

### 全量回归
- 367 passed, 1 skipped, 0 failed（含 S30 新增 8 条）

## 修复的 Bug / 偏离

1. **Playwright URL 错误**：fetch('/api/v1/one-topic/review') 使用相对 URL 命中了前端 18182 返回 HTML → 改为绝对 URL http://127.0.0.1:18181
2. **Playwright fixture 冲突**：自定义 navigate/topic_id fixture 覆盖了 conftest 的 page fixture → 删除自定义 fixture，使用 conftest 默认行为
3. **Uvicorn 未重启**：添加新 endpoint 后旧进程未加载新代码 → 重启 uvicorn 后正常

## 数据流

```
用户 → POST /review (sections + feasibility)
    → run_review()
        → _check_advisor()   → advisor issues
        → _check_method()    → method issues
        → _check_experiment()→ experiment issues
        → _check_writing()   → writing issues
        → _check_risk()      → risk issues
        → 合并 issues → 排序 by severity
        → 生成 required_actions + optional_actions
        → 判定 verdict (fatal 阻塞 pass)
    → ReviewRound (JSON 响应)

用户 → accept_fix / revise_topic / rerun_review
    → 对应 revision action 执行
    → 再次 POST /review (轮次 +1)
```

## 审计计数

- 测试总数：367（session 前 359，session 后 367，净增 +8）
- commit：待补充
