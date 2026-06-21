# Session 39 — 失敗案例庫擴充 + 面試反問準備 驗收報告

**日期:** 2026-06-21
**分支:** master
**前置會話:** S33（首版 Failure_Cases 8 案例）+ S34-S37（提供 Memory / MCP / Multi-Agent / RAG 技術素材）

---

## 1. 摘要

Session 33 交付了首版「失敗案例集」共 8 個案例（覆蓋 S28 Feasibility + S32 Readiness + S6 LLM Fallback + S14 多源檢索衝突）。Session 39 在此基礎上**只做擴充與配套反問材料，不動運行時代碼**：

- **失敗案例從 8 個擴到 16 個** — 追加 Case 9-16，覆蓋 S32 Readiness（誇大詞/風險章節）、S35 Memory（壓縮/重建）、S36 MCP（越權拒絕）、S37 Multi-Agent（成本超限）、S34 RAG（empty retrieval）、S35 Replay（斷流恢復）
- **新增 8 個反問** — `Reverse_Questions.md` 覆蓋 RAG 召回 vs 證據可信 / 功能 vs 可觀測性 / 工具越權審計 / 多 Agent 成本 / MCP 標準 / 科研 Agent 評估 / 架構 vs 深挖 / 優先補 RAG 還是 Memory
- **11 條結構校驗測試** — 防止材料腐化（案例數量下滑、丟失 system_block、丟失對應測試、誇大失敗描述、覆蓋面縮水）

**核心交付物：**

- 1 份新文件 — `docs/interview/Reverse_Questions.md`（8 個反問 + 策略說明 + 禁忌清單）
- 1 份修訂文件 — `docs/interview/Failure_Cases.md`（從 8 案例擴到 16 案例 + 對照表擴列）
- 1 份結構校驗測試 — `apps/api/tests/test_session39_failure_cases.py`（11 條測試，8 個分類）

Session 39 是「**面試材料補完 S34-S37 缺口 + 防腐化**」，**不**改任何運行時代碼、**不**新增端點、**不**動 S31 baseline。

---

## 2. 實施明細

### 2.1 失敗案例擴充（Case 9-16，共 8 個新增）

文件：`docs/interview/Failure_Cases.md`（原 8 個案例 + 案例對照表保留，在對照表內追加 Case 9-16 行）

| # | 案例名 | 攔截層 | 硬攔截 | 來源會話 |
|---|--------|--------|--------|----------|
| 9 | 創新點用「填補空白」 | Readiness (innovation_claim_safety) | 是（不得匯出） | S32 |
| 10 | 風險章節缺失 | Readiness (risk_disclosure) | 是（不得匯出） | S32 |
| 11 | Memory 壓縮後 critical 事件丟失 | Memory Compression | 是（測試守護） | S35 |
| 12 | MCP 工具調用越權（write_file） | MCP Permission | 是（直接拒） | S36 |
| 13 | Multi-Agent 成本超限 | Cost Budget | 否（降級到單流程） | S37 |
| 14 | RAG 檢索為空 | Failure Detector | 否（fallback 擴展） | S34 |
| 15 | Snapshot 重建後關鍵狀態丟失 | ProjectMemory | 是（測試守護） | S35 |
| 16 | Step Deck 刷新後斷流 | Replay | 否（恢復按鈕） | S35 |

**每個新案例的標準欄位（沿用 S33 既有格式）：**

- **輸入：** 具體的觸發場景描述（用戶做了什麼 / 輸入了什麼）
- **系統如何攔截：** 對應的攔截層（模組名 + 維度名）+ 觸發條件
- **使用者看到什麼：** UI 提示 / 顏色 / 禁用按鈕 / 錯誤碼（區分「硬攔截」和「降級」）
- **面試怎麼解釋：** 用面試口吻講為什麼這是設計選擇、體現什麼工程原則
- **對應測試：** 具體到 `test_sessionXX_xxx.py::TestXXX::test_xxx` 格式

### 2.2 案例對照表擴列

原對照表是 8 行（Case 1-8），S39 在末尾追加 8 行（Case 9-16），保持 6 欄結構（# / 案例 / 攔截層級 / 硬攔截 / 主要測試檔案），方便面試時一表速查。

### 2.3 反問準備材料（8 個反問）

文件：`docs/interview/Reverse_Questions.md`

| # | 反問主題 | 考察能力維度 |
|---|----------|--------------|
| 1 | RAG 召回質量 vs 證據可信度 | 評估側重點判斷 |
| 2 | 功能完成 vs 可觀測性 | 工程化思維 |
| 3 | 工具調用越權審計 | 安全意識 |
| 4 | 多 Agent 編排成本控制 | 成本意識 |
| 5 | MCP / 內部工具生態 | 標準跟進 |
| 6 | 科研 Agent 評估指標 | 評估方法論 |
| 7 | 架構 vs 深挖模塊 | 溝通判斷 |
| 8 | 優先補 RAG 還是 Memory | 產品路線感 |

**每個反問的標準欄位：**

- **目的：** 為什麼要問這個（你想從回答裡得到什麼信息）
- **可能回答：** 3 種典型回答 + 對應的「對方成熟度」判讀
- **接話策略：** 針對每種回答的後續應對（聊什麼 / 怎麼聊）
- **備選回答模板：** 一段可直接引用的完整回答（含具體項目數字）

**附錄：使用策略**

- 主動反問的時機（自我介紹後 / 技術討論後 / 結尾「你還有什麼問題」）
- 不該反問的場景（時間不足 / 已聊 60+ 分鐘 / 對方剛說完沒消化）
- 反問的禁忌（不問薪資 / 不問「能不能進」 / 不問加班）
- 8 個反問總結表（與上表重複，方便快速索引）

### 2.4 結構校驗測試（11 條）

文件：`apps/api/tests/test_session39_failure_cases.py`

8 個分類，對應 8 條材料硬約束：

| 編號 | 分類 | 測試數 | 硬約束 |
|------|------|--------|--------|
| S39-1 | Failure_Cases 案例總數 | 2 | `>= 10` 個 + 含對照表 |
| S39-2 | 每個 case 有 system_block | 1 | 16 個 case 全部包含「攔截」/「block」關鍵字 |
| S39-3 | 每個 case 有 related_tests | 1 | 16 個 case 全部包含「對應測試」或 `test_session` |
| S39-4 | 包含真實歷史失敗 | 1 | 至少 1 處引用 `test_session6` / `test_one_topic_session32` / `S30` |
| S39-5 | 反問數量 | 1 | `>= 8` 個反問 |
| S39-6 | 反問文件存在 | 1 | `Reverse_Questions.md` 存在 |
| S39-7 | 不自我貶低 | 2 | 無禁詞（「完全失敗 / 毫無價值 / 徹底崩潰 / 毫無意義 / 無法挽救」等 7 個）+ 每 case 都有正向應對 |
| S39-8 | 工程邊界有應對 | 2 | 覆蓋 S32/S34/S35/S36/S37 至少 3 個 session + 引用真實測試文件 |

---

## 3. 測試結果

### 3.1 Session 39 結構校驗測試

```
$ .venv/Scripts/python.exe -m pytest apps/api/tests/test_session39_failure_cases.py -v

============================= test session starts =============================
collected 11 items

apps/api/tests/test_session39_failure_cases.py::TestFailureCaseCount::test_failure_cases_at_least_10 PASSED [  9%]
apps/api/tests/test_session39_failure_cases.py::TestFailureCaseCount::test_failure_cases_table_mentions_all PASSED [ 18%]
apps/api/tests/test_session39_failure_cases.py::TestCasesHaveSystemBlock::test_each_case_mentions_blocking PASSED [ 27%]
apps/api/tests/test_session39_failure_cases.py::TestCasesHaveRelatedTests::test_each_case_mentions_tests PASSED [ 36%]
apps/api/tests/test_session39_failure_cases.py::TestRealHistoricalFailure::test_real_historical_failure_mentioned PASSED [ 45%]
apps/api/tests/test_session39_failure_cases.py::TestReverseQuestions::test_reverse_questions_at_least_8 PASSED [ 54%]
apps/api/tests/test_session39_failure_cases.py::TestReverseQuestionsDocExists::test_doc_exists PASSED [ 63%]
apps/api/tests/test_session39_failure_cases.py::TestFailureNotExcusingSelf::test_no_self_deprecation_phrases PASSED [ 72%]
apps/api/tests/test_session39_failure_cases.py::TestFailureNotExcusingSelf::test_each_case_has_solution PASSED [ 81%]
apps/api/tests/test_session39_failure_cases.py::TestEngineeringBoundaries::test_references_session_32_36_37 PASSED [ 90%]
apps/api/tests/test_session39_failure_cases.py::TestEngineeringBoundaries::test_failure_cases_cite_source_files PASSED [100%]

============================= 11 passed in 0.13s ==============================
```

**全部 11 條測試通過，耗時 0.13 秒。**

### 3.2 關鍵度量實測

| 度量 | 目標 | 實測 | 狀態 |
|------|------|------|------|
| Failure_Cases 案例總數 | >= 10 | 16（S33: 8 + S39: 8） | 達標 |
| 案例含 system_block | 16/16 | 16/16 | 達標 |
| 案例含對應測試 | 16/16 | 16/16 | 達標 |
| 真實歷史失敗引用 | >= 1 處 | 多處（S30 review / S6 LLM / S32 readiness） | 達標 |
| 反問數量 | >= 8 | 8 | 達標 |
| 反問文件存在 | 是 | 是 | 達標 |
| 無自我貶低禁詞 | 0 個 | 0 個（7 個禁詞全部掃過） | 達標 |
| 每 case 有正向應對 | 16/16 | 16/16 | 達標 |
| 覆蓋 S32-S37 session | >= 3 個 | 5 個（S32/S34/S35/S36/S37） | 達標 |
| 引用真實測試文件 | 是 | 是（多處 `test_sessionXX_xxx.py`） | 達標 |
| 包含對照表 | 是 | 是（16 行 + 6 欄） | 達標 |

### 3.3 與 S38 的覆蓋面對比

| 會話 | 對應材料 | Failure Cases 覆蓋 | 反問覆蓋 |
|------|----------|--------------------|----------|
| S28 | Feasibility | Case 1, 2, 4 | — |
| S6 | LLM Fallback | Case 7 | — |
| S14 | 多源檢索 | Case 8 | — |
| S26 | Evidence Promotion | Case 3 | — |
| S32 | Readiness | Case 5, 6, 9, 10 | — |
| S34 | RAG | Case 14 | 反問 1, 6, 8 |
| S35 | Memory / Replay | Case 11, 15, 16 | 反問 2, 8 |
| S36 | MCP | Case 12 | 反問 3, 5 |
| S37 | Multi-Agent | Case 13 | 反問 4 |

**結論：S33-S37 所有技術會話都有對應的失敗案例 + 反問材料覆蓋。**

---

## 4. 關鍵設計決策

### 4.1 為什麼把失敗案例擴到 16 個而不是更多？

- **S33 的 8 個案例覆蓋 S28 之前所有模組**（Feasibility / Evidence / LLM Fallback / Multi-source）
- **S39 的 8 個案例對應 S34-S37 全部技術會話**（RAG / Memory / MCP / Multi-Agent）
- 16 個案例對應面試深挖時「每個模組至少 1-2 個失敗點」的展示需求
- 案例再多會稀釋重點 — 每個案例都必須能在面試 30 秒內講完輸入→攔截→UI→測試

### 4.2 為什麼把「硬攔截」和「降級」在對照表裡分開標記？

面試官可能追問「哪些是真正的安全閘門？哪些是性能/成本優化？」對照表的「硬攔截？」欄位讓一眼分清：

- **硬攔截（是）：** 用戶不能繞過，必須修復才能繼續（Case 1, 2, 3, 5, 6, 9, 10, 11, 12, 15）
- **降級（否）：** 系統自動選另一條路，用戶可繼續（Case 7, 8, 13, 14, 16）

這體現了「**判斷風險但不代替決策**」的設計原則 — 硬攔截是「不允許做」，降級是「允許做但換條路」。

### 4.3 為什麼反問要標「可能回答 + 接話策略」？

面試現場沒有時間想「對方回答 X 我該怎麼接」。每個反問準備 3 種可能回答 + 對應接話，讓候選人在現場像讀劇本一樣流暢：

- **3 種回答 = 3 種面試官成熟度** — 「召回質量」vs「證據可信度」vs「都要」分別對應「不成熟」/「重視事實」/「成熟」
- **接話策略不該是「把所有東西都塞進去」** — 根據對方回答精準展開，才顯得「有傾聽能力」

### 4.4 為什麼測試要驗證「不自我貶低」？

S33 寫早期版本時，曾出現「這塊徹底崩潰」「毫無意義」等表達。這些詞在面試材料中會傳遞「不自信」信號。S39 把 7 個禁詞列表化（完全失敗 / 毫無價值 / 徹底崩潰 / 毫無意義 / 徹底失敗 / 完全崩潰 / 無法挽救），每次 commit 必掃。**機器比人更能防止「一激動又寫回去」**。

### 4.5 為什麼 Case 11/15 用「測試守護」而不是「UI 提示」？

Memory 壓縮 / Snapshot 重建是**後台保證** — 用戶不應該看到這些細節（會顯得系統不穩定）。但保證如何讓面試官相信？靠測試斷言。

- **Case 11**：`TestCriticalEventsPreserved::test_gate_events_not_compressed` 守護 `user_patch` 等 6 類 critical 事件永遠不被壓縮
- **Case 15**：`TestReadinessStableAcrossCompression::test_readiness_status_preserved_in_snapshot` 守護 Snapshot 重建後 `readiness_status` 不丟

面試時說「這是測試守護的，不是 UI 提示」反而更顯工程嚴謹 — 說明「**用戶無感，但工程有保證**」。

### 4.6 為什麼反問 8 是「優先補 RAG 還是 Memory」而不是別的？

S40 路線的問題：

- **RAG 路線：** 接入真實 embedding / 向量庫 / URL HEAD 驗證
- **Memory 路線：** 跨 session 持久化 / MCP stdio transport

面試官問「你下一步做什麼」是真實的產品問題。準備這個反問的**雙重收益**：

1. 了解面試官業務場景（學術 / 工業 / 創業）
2. 展示**你有產品路線感**（不是只會做技術）

### 4.7 為什麼 11 條測試集中在 8 個分類而不是 11 個獨立 case？

8 個分類對應 8 條「材料硬約束」 — 任何一條失效都意味著材料腐化。每類用 `parametrize` 展開（雖然本次 S39 是直接展開），這樣**未來加新案例時，只要在文件裡加 `## Case 17`，所有約束自動覆蓋**。

---

## 5. 面試敘事 — 怎麼用失敗案例 + 反問

### 5.1 三段式使用策略

| 面試階段 | 使用材料 | 關鍵技巧 |
|----------|----------|----------|
| **開場**（自我介紹後） | `Project_OnePager.md` | 30 秒講清楚「做什麼 / 為什麼 / 技術棧」 |
| **主面試**（項目追問） | `Failure_Cases.md` 對照表（16 行） | 挑 1-2 個對方技術棧相關的案例，主動講 |
| **深挖**（連續追問） | 具體 Case 1-16 全文 | 講輸入→攔截→UI→測試四步，標「硬攔截」或「降級」 |
| **收尾**（你還有什麼問題） | `Reverse_Questions.md` 8 個 | 選 1-2 個對方場景契合的反問，**主動接**回答 |

### 5.2 主動展示失敗案例的時機

**不要等面試官問「你遇到過什麼問題」** — 在講完設計後，主動接一句：

- 「我順便講一個被攔截的場景」 → Case 1（無資料集）/ Case 5（誇大詞）
- 「我也準備了 S34-S37 的失敗案例」 → Case 11-16（Memory 壓縮 / MCP 越權 / 成本超限）
- 「**降級而不中斷**也是設計原則」 → Case 7（LLM Fallback）/ Case 13（Multi-Agent 降級）/ Case 14（RAG empty）

主動展示反而顯得**真實且有工程判斷力**，比被動防禦強。

### 5.3 反問環節的標準流程

**面試官：「你還有什麼問題嗎？」**

候選人：「我想了解一下貴團隊的方向，有 2 個問題：

1. 」（從反問 1 / 6 / 8 中選 1 個，根據對方技術棧）
2. 」（從反問 3 / 4 中選 1 個，根據對方規模）

**注意：**

- **不要 8 個全問** — 顯得「背題」，面試官會反感
- **不要只問 1 個** — 顯得「沒想法」
- **2-3 個是最佳區間**，且每個反問的「備選回答模板」要即時用上

### 5.4 被反問時如何接「你為什麼問這個？」

候選人可以主動解釋反問的「目的」：

- 「我問 RAG 是因為論文項目對證據可信度敏感」（反問 1 目的）
- 「我問成本是因為我做過 Multi-Agent 對 LLM 預算有直觀感受」（反問 4 目的）

這樣面試官知道**你問得有意義**，而不是「聽說面試要反問」。

### 5.5 反問的禁忌清單（必須避免）

來自 `Reverse_Questions.md` 末段：

- **不要問薪資**（HR 環節才問）
- **不要問「我能進嗎」**（焦慮信號）
- **不要問「你們加班嗎」**（消極信號）
- **不要問和職位無關的問題**

S39 把這 4 條作為硬約束寫進文件，候選人現場查表即可。

### 5.6 與 S38 材料的配合

| 場景 | S38 用 | S39 用 |
|------|--------|--------|
| 對方問「RAG 怎麼評估」 | `Deep_Dive_QA_RAG.md` Q2 | 反問 1（召回 vs 可信）+ 反問 6（科研評估） |
| 對方問「Memory 怎麼設計」 | `Deep_Dive_QA_Memory.md` Q3 | 反問 8（優先補 RAG 還是 Memory） |
| 對方問「多 Agent 怎麼控成本」 | `Deep_Dive_QA_Agent.md` Q5 | 反問 4（成本控制）+ Case 13（成本超限） |
| 對方問「工具安全怎麼做」 | `Deep_Dive_QA_MCP.md` Q4 | 反問 3（越權審計）+ Case 12（write_file 拒絕） |

**S38 提供「被問怎麼答」，S39 提供「主動問什麼 + 展示什麼」**，互補。

---

## 6. 遺留風險與下一步

### 6.1 覆蓋盲點

- **沒有「端到端 Case Study」** — 16 個失敗案例是「點」，沒有「我從頭到尾做一個項目遇到 X 怎麼辦」的連續敘述。可在 S40+ 加 1 份「端到端 Walkthrough」文檔（以 YOLO 鋼材表面缺陷為案例，講完 8 步）
- **沒有「團隊協作 / Git 流程」類失敗案例** — Case 1-16 全是技術類，被問「你怎麼協作 / 怎麼 review 代碼 / 怎麼排版本」時只能用口頭答。可補 3-5 個協作類失敗案例
- **沒有「性能壓測」類失敗案例** — RAG / Multi-Agent 都有性能問題，但 Case 14 只提到「empty retrieval」沒提到「latency 超標」。可補 1-2 個性能失敗案例
- **沒有「數據遷移 / 升級」類失敗案例** — S18 之後沒有真實的 schema 遷移案例，遇到面試官問「你怎麼做 migration」時無案例可講

### 6.2 已知邊界（必須保持誠實）

- **S39 反問中的「真實數字」是項目實測值**（8 指標、4 維硬限制、3 個降級開關），不是「業界標準」 — 面試時要強調「這是我們的選擇，不一定是業內最佳實踐」
- **Case 11/15 的「測試守護」** — 是斷言層的保護，不是運行時的「UI 提示」 — 候選人不要過度解讀為「系統自動恢復」
- **Case 13 的「降級到單流程」** — 是 fallback 機制，但單流程的質量是否足夠，未做 A/B 測試 — 不能說「降級後效果一樣好」
- **反問 8 的「優先補 RAG」是個人判斷** — 對方業務場景不同，優先級可能不同 — 不能說「一定是 RAG」

### 6.3 下一步建議

| 優先級 | 建議 | 理由 |
|--------|------|------|
| P0 | 寫 1 份「端到端 Case Study」（YOLO 鋼材檢測 8 步 walkthrough） | 把 16 個失敗案例串成連貫故事，目前散落 |
| P0 | 加 3-5 個「團隊協作 / Git 流程」失敗案例 | 非技術追問覆蓋率 0，這是面試常見問題 |
| P1 | 寫 1 份「性能與壓測」Deep Dive + 對應失敗案例 | 當前所有材料對性能數據 0 提及 |
| P1 | 把 Case 1-16 的 `對應測試` 字段全部實跑一遍，確保文件存在 | 防止材料「指向不存在的測試」 |
| P2 | 反問擴到 12 個（加「技術債處理」「失敗的 feature」「open source 貢獻」3 個） | 8 個反問覆蓋 8 個能力維度，但 3 個常見方向（技術債 / 失敗產品 / 開源貢獻）未覆蓋 |
| P2 | 給 `Failure_Cases.md` 加 TOC（目錄索引） | 16 個案例 + 對照表，現場定位需要先看目錄 |

### 6.4 風險

- **材料腐化風險已被結構測試覆蓋** — 11 條測試每次 commit 必跑，任何案例/反問被改壞都會 fail
- **未腐化但「過時」的風險未覆蓋** — 假如 S40 改了 Rerank 權重，Case 14 說「fallback 擴展關鍵詞」會變成「過時的舊設計」。建議在 S40+ 涉及核心模塊改動時，主動 review 對應失敗案例
- **未覆蓋的風險** — 現場儀表/肢體/語氣/反應速度等非材料因素，材料再全也救不了
- **反問「套路化」風險** — 8 個反問寫得太整齊反而顯得「背題」。候選人現場要根據對方回答即時調整，不能照本宣科

---

## 7. 文件清單

**新增（2）：**

- `docs/interview/Reverse_Questions.md`
- `apps/api/tests/test_session39_failure_cases.py`

**修改（1）：**

- `docs/interview/Failure_Cases.md`（從 8 案例擴到 16 案例 + 對照表追加 8 行）

---

**報告結束。Session 39 全部交付完成，11 條結構測試全綠。**
