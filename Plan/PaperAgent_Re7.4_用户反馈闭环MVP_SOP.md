# PaperAgent Re7.4：用户反馈闭环 MVP SOP

> 目标：把真实用户对报告、创新点、RAG 答案和引用的判断保存为可审查数据；本期不自动训练模型、不把评论直接塞回 prompt。

## 目录

1. 最小产品流
2. 数据合同
3. API 与 UI
4. 安全边界
5. 验收

## 1. 最小产品流

在最终建议、创新点卡片、RAG 回答下提供五选一：`useful|not_useful|incorrect|unsupported|needs_more_evidence`，
可选 1000 字以内说明与被质疑的 citation。提交后立刻显示“已记录”，可查看该 case 的历史反馈。

反馈先只服务于离线复盘：每周生成按 artifact/失败类型/模型/领域聚合的报告，再人工决定是否进入
gold set、prompt 或规则改动。

## 2. 数据合同

```json
{
  "feedback_id": "uuid",
  "idempotency_key": "uuid",
  "case_id": "case",
  "artifact_type": "final_recommendation|innovation|rag_answer|citation",
  "artifact_id": "stable id or null",
  "verdict": "useful|not_useful|incorrect|unsupported|needs_more_evidence",
  "comment": "optional <=1000 chars",
  "selected_citation_ids": ["cit:..."],
  "client_version": "web",
  "created_at": "ISO-8601"
}
```

MVP 存储采用 `tmp_re13_eval/<case>/feedback.jsonl` append-only；接口层校验 case/artifact/citation 存在，
评论不写入 LLM context。上线多用户前迁移到数据库并增加 owner/user_id。

## 3. API 与 UI

- `POST /api/v1/feedback`：校验、脱敏、幂等写入；
- `GET /api/v1/feedback?case_id=`：按时间返回，不暴露其他 case；
- `GET /api/v1/feedback/summary?from=&to=`：仅管理员/离线任务使用；
- React `FeedbackBar`：最终报告与 RAG 答案复用，失败原因可选，展示“不会自动改变回答”。

## 4. 安全边界

- 评论按不可信输入处理：不进入 prompt、检索索引、HTML 或日志；
- 限长、rate limit、XSS 转义、删除入口、审计 event；
- 未登录 Beta 使用匿名 session hash，不能将其宣传为用户身份隔离；
- 反馈只反映体验，不构成论文事实或模型训练标签。

## 5. 验收

- [ ] 反馈稳定关联 `case_id + artifact_type + artifact_id`；
- [ ] 同 idempotency key 重试只写入一条；
- [ ] 页面刷新后历史可读，删除后不可由 API 再读取；
- [ ] 10 条 unsupported/incorrect 反馈可按模型、领域、节点和失败类型聚合；
- [ ] 恶意评论不出现在 LLM 输入或未转义页面；
- [ ] 一条反馈不会自动改变同 case 的检索、prompt 或最终结论。
