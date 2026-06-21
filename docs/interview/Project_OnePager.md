# PaperAgent · 科研證據 Agent 工作台 — 專案一頁總覽

## 專案定位

PaperAgent 是一個面向「畢業論文開題」的科研證據 Agent 工作台，讓學生只輸入一個題目，系統就能自動拆解關鍵詞、多路檢索學術證據、判斷可行性、生成開題報告草稿，並在導出前完成學校模板合規檢查。

## 目標用戶

- **本科與碩士畢業生**：快速判斷題目是否「有論文、有數據、有 baseline」，降低開題風險
- **指導導師**：可檢視證據鏈與可行性分析，輔助方向決策
- **答辯委員會**：可審閱開題報告的完整證據引用，確保每一句話都有可追溯來源

## 核心問題

開題的真正門檻不在「寫作」，而在：

1. **找證據** — 論文、數據集、baseline 工程散布多處，學生不知從何搜起
2. **判斷可行性** — 盲目開題後才發現無數據可用或 baseline 不可復現
3. **生成報告** — 開題報告需符合學校模板格式，且每句話都要有引用背書
4. **模板合規** — 不同學院（工科、計算機視覺、通用）有各自的硬性規範，人工檢查耗時且易漏

## 核心流程（8 Phase）

| Phase | 名稱 | 產出 |
|-------|------|------|
| 01 | 一題輸入與預評估 | `OneTopicRequest` + 評級，D 評級直接 409 |
| 02 | 關鍵詞拆解與意圖理解 | `KeywordBreakdown` + LLM 拆詞 + 風險詞標記 |
| 03 | 七層檢索計畫 | `SearchQueryPlan`：論文/數據集/倉庫/程式碼/baseline/全文/指標 |
| 04 | 證據採集與 Baseline | `EvidenceLedger`：候選→選中 第一階段 |
| 05 | 證據評分與 PIVOT 決策 | 7 維風險評估 + 三條退化路線（保守/平衡/進取） |
| 06 | 工作包定稿與實驗矩陣 | `ProposalDraft` 12 節 + 證據綁定 + 工作量/創新點 |
| 07 | 開題報告生成與委員會審查 | 合規開題報告 + 膨脹詞檢測 + 模擬審查 |
| 08 | 材料導出與 Readiness 檢查 | 學校模板合規 + hard-block 維度 + 匯出許可 |

## 技術架構

- **前端**：純 JavaScript SPA，包含 Step Deck（9 步可視化流程）、Workspace Cards（左右欄證據工作台）、ComponentRegistry（13 張核心卡 + 通用 JSON 降級卡）、Trace Panel（NDJSON/SSE 流式回放）
- **後端**：FastAPI（Python 3.12+），Pydantic v2 全 schemas 驗證，LangGraph 風格但更輕量的啟發式編排（非 LLM 圖）
- **LLM**：Minimax API 用於關鍵詞拆解、檢索查詢生成、可行性 Judgment。每次 LLM 路徑都配備 heuristic fallback，確保服務不因 LLM 失效而中斷
- **RAG**：7 檢索層，非傳統向量資料庫。涵蓋 arXiv 論文、公開數據集、GitHub 倉庫、工程程式碼、baseline 復現、全文、指標。前端以「候選」形式展示，不直接餵給 LLM
- **證據存儲**：SQLite + 狀態 JSON，支援多 project 隔離

## 技術難點

- **證據晉升設計**：候選→選中→URL 驗證→證據→引用，5 級顯式晉升。Selected != Evidence 是不變式，晉升是使用者顯式操作，不自動發生。前後端 Promotion Gate 雙重檢查
- **非向量 RAG**：不用 embedding 向量檢索，而是七層結構化檢索 + 啟發式排序。避免向量 DB 門檻，使論文/數據集/baseline/工程程式碼各層獨立可撤
- **LLM 幻覺抑制**：所有 LLM 產出經過 EvidenceRef 綁定驗證，每條開題章節必須有證據引用才能設定 high confidence。膨脹詞（「首創」「國際領先」等）硬阻斷
- **流式可回放**：RunEvent + TraceStore 實現完整事件溯源。每次分析產生的事件序列可被 NDJSON 消費或 SSE 即時推送，後續可完整回放重播
- **模板合規**：三套學校模板（default / engineering / cv_ai），各自定義 hard-block 維度。ReadinessService 在導出前執行全面檢查，不合規則阻斷匯出

## 測試與評估

- **後端測試**：28 個 pytest 檔案，388+ 個測試案例，涵蓋 API 端點、Pydantic schemas、證據晉升邏輯、LLM 路徑、feasibility 判決、proposal draft 驗證、readiness 檢查
- **前端測試**：32 個 Playwright E2E 測試檔案 + baseline fixtures + Playwright 快照回歸
- **Demo Smoke**：完整鏈條「輸入題目→證據展示→可行性→報告草稿→readiness」可在 2 分鐘內完成，含 uvicorn 真實啟動驗證

## 安全邊界

- **URL 驗證**：每條證據的 URL 必須通過 HTTP 狀態碼 + 回應時間檢查，狀態包括 verified / partial / failed / expired
- **膨脹詞檢測**：13 個中英文膨脹詞硬阻斷（首創、填補空白、state-of-the-art 等）
- **hard-block 維度**：Readiness 報告中的硬性阻斷維度，不滿足則 export_allowed = false
- **Human Gate**：Phase 02/03 分別設有關鍵詞確認閘門和檢索詞確認閘門，使用者必須手動確認後流程才能繼續
- **409 階段阻斷**：前一階段未完成時，後階段 API 直接 409 拒絕

## 演示路徑

```
輸入「基於 YOLO 的鋼材表面缺陷檢測」
  → 關鍵詞拆解：YOLO、缺陷檢測、鋼材表面
  → 三線檢索：論文 / NEU-DET 數據集 / Ultralytics YOLO baseline
  → 可行性判斷：「可做」或「收縮後可做」
  → 開題報告草稿：12 節，每節綁定 EvidenceRef
  → Readiness 導出檢查：模板合規、膨脹詞、hard-block
  → 匯出完整開題報告
```

## 未來擴展

- **RAG 面試級檢索**：串接 Semantic Scholar / Google Scholar API，增加引用量與期刊分級過濾
- **MCP Server**：將證據晉升管線封裝為 MCP（Model Context Protocol）Server，供其他 LLM Agent 直接呼叫
- **多 Agent 協作**：拆為搜尋 Agent、評分 Agent、審查 Agent 各自獨立執行，透過事件匯流排協調
- **多語言開題模板**：支援英文、中日韓等語言模板
