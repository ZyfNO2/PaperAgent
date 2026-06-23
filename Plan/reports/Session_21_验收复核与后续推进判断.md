# Session 21 验收复核与后续推进判断

> 日期：2026-06-20  
> 复核对象：`Plan/reports/Session_21_StepDeck_验收报告.md`  
> 结论：Session 21 可以通过验收，但只能视为“前端交互骨架 + mock stream + 安全渲染协议”的通过，不等同于真实流式后端、真实检索、真实 Trace 持久化已经完成。

---

## 1. 验收结论

```text
验收结论：通过
通过等级：有条件通过
可进入后续：Session 22 / Session 23 / Session 24 SOP 编写
不建议直接执行到：Session 25 / Session 26
```

通过理由：

```text
1. Step Deck 页面已经落地；
2. 单页高密度报告被拆成分步卡片；
3. mock stream 能流式推进到 keyword_review；
4. keyword_review 后能暂停；
5. 用户可删除关键词、确认并推进到 query_plan；
6. paperagent-card / pa-card 安全解析器已落地；
7. 非法组件、script、onclick 均有 Playwright 覆盖；
8. 经典页面入口未回退；
9. Playwright 13/13 通过；
10. 本轮没有修改后端证据规则，S17 baseline 风险较低。
```

---

## 2. 验收边界

本轮通过的是：

```text
前端 Step Deck；
前端状态机；
前端 mock stream；
前端安全 render protocol；
keyword_review 最小 Gate；
Playwright 交互测试。
```

本轮没有通过，也不应被误认为已经完成的是：

```text
真实 SSE / NDJSON 后端端点；
后端 render_events 服务；
后端 RunEvent 持久化；
Trace 持久化集成；
真实 LLM 流式输出；
真实检索计划；
候选论文 / 数据集 / 工程检索；
开题报告推荐；
双栏证据工作台。
```

---

## 3. 发现的问题

### 3.1 报告可读性问题

复核时发现部分报告和代码注释在终端输出中出现中文编码显示异常。若文件本身在编辑器中显示正常，可暂不处理；若编辑器中也乱码，需要单独安排一次文档编码清理。

不建议在 Session 22-24 中顺手大规模改编码，因为会制造大量无关 diff。

### 3.2 StepDeck 当前仍是 mock

`apps/web/step_deck.js` 当前的流式推进来自前端 mock 序列，不是后端真实事件。

影响：

```text
S22 可以继续做组件注册表；
S23 必须定义真实 prompt / event schema；
S24 可以设计候选卡，但执行时要注意不要假装真实检索已经闭环。
```

### 3.3 Trace 仍是内存态

当前 Trace 主要存在于 `runState.eventBuffer` 和页面 drawer，刷新即丢。

影响：

```text
S22 不必解决；
S23 需要明确事件字段；
S24 若引入候选资源标记，必须写入已有 Trace 或新建最小持久化桥接。
```

---

## 4. 是否需要修改 Session 21

当前不需要回改 Session 21 的 SOP 或实现。

建议仅保留一条后续要求：

```text
Session 22 开始后，组件注册表必须替换 step_deck.js 内部散落的专属渲染分支，避免后续卡片越来越多后失控。
```

---

## 5. 后续能否一次性多写几个

可以一次性写：

```text
Session 22：Renderer Component Registry 最小卡片库
Session 23：流式 Prompt 协议与工具调用边界
Session 24：检索计划与候选资源卡
```

原因：

```text
S22 直接收束 S21 的技术债；
S23 为真实 LLM / SSE / card_delta 提供协议；
S24 才开始把关键词 Gate 的结果变成论文、数据集、工程候选；
三者是线性链条，能一起设计，但执行时仍应分 Session 验收。
```

暂不建议一次性写细：

```text
Session 25：双栏证据工作台 MVP
Session 26：开题报告推荐与低门槛复核
```

原因：

```text
S25 依赖候选资源卡的数据结构；
S26 依赖用户已选择的核心资料；
如果 S24 的 Candidate schema 变化，S25/S26 细节会返工。
```

---

## 6. 推荐推进方式

```text
现在：写 S22-S24 SOP；
执行：先做 S22；
S22 验收后：执行 S23；
S23 验收后：执行 S24；
S24 验收后：再细化 S25-S26。
```

执行纪律：

```text
每个 Session 都要独立验收；
每个 Session 都要保留 Playwright；
任何涉及 EvidenceRef / Verification / Trace 的变更都要写后端测试；
不允许把候选资源直接提升为强证据。
```

