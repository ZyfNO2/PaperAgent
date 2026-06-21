# 面试反问准备（Session 39）

> 面试不是单向输出。**反问环节**是展示你思考深度的关键时机。
> 本文准备 8 个反问，覆盖：技术选择 / 团队实践 / 评估标准 / 项目方向。

---

## 反问 1：贵团队更关注 RAG 的召回质量还是证据可信度？

**目的：** 了解团队对 RAG 评估的侧重点。

**可能回答：**
- 「召回质量」→ 团队关注覆盖率，可能没重视事实性
- 「证据可信度」→ 团队重视 URL 验证 / 来源权威
- 「都要」→ 团队成熟，期待更深入讨论

**接话策略：**
- 如果选召回 → 我会聊 nDCG@10 / Recall@K / Coverage
- 如果选可信 → 我会聊 URL verified / URL 失效 fallback
- 如果都要 → 抛出 8 指标 + 5 检测器的设计

**备选回答模板：**

> 「我猜两个都关注，但我注意到业界常见误区是只看 Recall@K。如果让我优化 PaperAgent 的 RAG，我会优先优化 `nDCG@10` + `MRR` + `Coverage`，因为用户体验是看前 10 名的质量。证据可信度靠 `URLVerified` 状态 + Gate 校验保证。」

---

## 反问 2：Agent 项目里你们更看重功能完成还是可观测性？

**目的：** 了解团队对工程化的态度。

**可能回答：**
- 「功能完成」→ 团队偏 PoC
- 「可观测性」→ 团队成熟，关心运维
- 「功能完成 + 后期补可观测性」→ 团队务实

**接话策略：**
- 如果选可观测 → 聊 Trace 设计 / 4 层 Memory / 失败检测器
- 如果选功能 → 聊 8 个 Step Deck 完整闭循环

**备选回答模板：**

> 「我会选可观测性。Agent 项目最怕『模型抽了』難調試。PaperAgent 的 Trace 設計（mcp_tool_call、user_patch、gate、evidence_promotion、readiness_check、llm_call）讓任何 step 都能回放審計，這比『先跑通』更有長期價值。」

---

## 反问 3：工具调用越权你们通常怎么做审计？

**目的：** 了解团队对权限边界和安全的实践。

**可能回答：**
- 「框架自帶」（如 LangSmith） → 我會聊第三方
- 「自己寫 log」 → 我會聊 PaperAgent 的 Trace + Gate
- 「沒做」 → 機會，說服他們需要

**接话策略：**
- 主动說明 PaperAgent 3 層權限（白名單 + 黑名單 + Gate）
- 強調「所有調用（包括 forbidden）都寫 Trace」

**备选回答模板：**

> 「PaperAgent 用 3 層：白名單（必須在 manifest）、黑名單（write_file 等高風險永拒）、Gate 前置（keyword gate / FinalPackage 狀態）。**所有調用包括 forbidden 都寫 Trace**，這樣安全審計可追溯『誰嘗試調 write_file』。」

---

## 反问 4：多 Agent 编排中你们怎么控制成本？

**目的：** 了解團隊對 LLM 成本的關注。

**可能回答：**
- 「不控制，燒得起」→ 不成熟
- 「max tokens 限制」 → 基本
- 「agent 數量 + 並行 + 路由」 → 成熟

**接话策略：**
- 抛出 4 維硬限制（agent_count / llm_calls / parallel / rounds）
- 說明 2 個降級開關（fallback_to_single_agent / early_stop_on_gate_blocked）

**备选回答模板：**

> 「PaperAgent 設計了 4 維硬限制（max_agent_count=8、max_llm_calls=20、max_parallel_tasks=3、max_rounds=5）和 2 個降級開關。超限立即停止 + 回退單流程。**寧可降級不可失控**是核心原則。」

---

## 反问 5：你们现在有没有 MCP 或内部工具生态？

**目的：** 了解團隊是否接受 MCP 標準。

**可能回答：**
- 「有 / 在評估」 → 聊 PaperAgent MCP server
- 「沒有，Function Calling 夠用」 → 不強推，聊補充
- 「不知道 MCP」 → 簡要解釋

**接话策略：**
- 強調 PaperAgent MCP 的 3 個優勢：白名單 / 黑名單 / Gate
- 不誇大 MCP 對 Function Calling 的取代關係

**备选回答模板：**

> 「PaperAgent 實現了 4 個最小 MCP tool（search_topic_evidence / get_candidate_resources / get_project_trace / check_export_readiness）。高風險操作（promote / generate_proposal / delete / write_file）**不暴露**。MCP 不是取代 Function Calling，而是把『安全邊界、審計、權限 Gate 做進協議層』。」

---

## 反问 6：科研 / 文檔類 Agent 的評估指標通常怎麼定？

**目的：** 了解團隊的評估體系成熟度。

**可能回答：**
- 「人工評估」→ 沒標準
- 「BLEU / ROUGE」 → 偏 NLP
- 「業務指標」→ 比較實用

**接话策略：**
- 聊 PaperAgent 的多維評估：8 指標 + 5 failure detector
- 強調「業務指標 + 技術指標」結合

**备选回答模板：**

> 「科研 Agent 比較難用 BLEU 評估。PaperAgent 用 8 維技術指標（nDCG@10、MRR、Recall、Coverage、Diversity、Latency、Cost、Stability）+ 5 個業務 Failure Detector（empty_retrieval / low_recall / hallucinated_url / duplicate / off_topic）。技術指標 + 業務指標結合。」

---

## 反问 7：面試官更希望我展示系統架構還是某個模塊深挖？

**目的：** 收尾時確認重點。

**可能回答：**
- 「架構」→ 走 OnePager + Architecture Diagram
- 「深挖」→ 選你最熟的模塊
- 「你覺得呢？」→ 主動選擇

**接话策略：**
- 如果有時間：架構 1 分鐘 + 1 個深挖模塊 3 分鐘
- 沒時間：架構 30 秒 + 1 個關鍵 Demo 場景

**备选回答模板：**

> 「我先講 1 分鐘架構（輸入題目 → 拆關鍵詞 → 三線檢索 → 可行性 → 證據晋升 → 報告導出），然後選 RAG 或 Memory 模塊深挖。RAG 看『怎么防 LLM 編造 URL』，Memory 看『4 層分層 + critical 事件不壓縮』，您想聽哪個？」

---

## 反问 8：如果繼續做這個項目，你們建議優先補 RAG 還是 Memory？

**目的：** 顯示你有產品路線感。

**可能回答：**
- 「RAG」→ 證據可信是當前瓶頸
- 「Memory」→ 跨 session 體驗重要
- 「看你們業務」→ 不表態

**接话策略：**
- 展示你的優先級判斷 + 理由
- 不要無腦說「都重要」

**备选回答模板：**

> 「我會選 RAG。因為 RAG 是『證據來源』，錯了後面全錯；Memory 是『體驗優化』，暫時可用 in-memory 湊合。具體優先級：(1) 真实 embedding 接入 (2) 向量庫 (3) URL HEAD 验证 (4) Memory 持久化 (5) MCP stdio transport。1-3 是 RAG，4-5 是 Memory。」

---

## 反問使用策略

### 主動反問的時機
- 面試官說「你還有什麼問題嗎」 → 必問
- 自我介紹結束後 → 選 1 個
- 技術討論結束後 → 選 1 個

### 不該反問的場景
- 面試官明確趕時間
- 已經聊了 60 分鐘+
- 對方剛說完技術細節你沒消化

### 反問的禁忌
- 不要問薪資（HR 環節才問）
- 不要問「我能進嗎」（焦慮信號）
- 不要問「你們加班嗎」（消極信號）
- 不要問和職位無關的問題

---

## 8 個反問總結表

| # | 反問 | 考察你的能力 |
|---|---|---|
| 1 | RAG 召回 vs 證據可信 | 評估側重點判斷 |
| 2 | 功能完成 vs 可觀測性 | 工程化思維 |
| 3 | 工具越權審計 | 安全意識 |
| 4 | 多 Agent 成本控制 | 成本意識 |
| 5 | MCP / 內部工具生態 | 標準跟進 |
| 6 | 科研 Agent 評估 | 評估方法論 |
| 7 | 架構 vs 深挖 | 溝通判斷 |
| 8 | 優先補 RAG 還是 Memory | 產品路線感 |

---

> **面試重點：反問不是禮貌，是展示思考深度的機會。**
> **8 個反問覆蓋 8 個能力維度，準備好對應的接話策略。**