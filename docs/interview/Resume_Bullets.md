# PaperAgent · 簡歷亮點（中文）

---

- 獨立設計並實現了一個基於 FastAPI + JavaScript SPA 的畢業論文開題證據 Agent 工作台，支援 8 階段流式任務處理與 Step Deck 可視化流程，使用者僅需輸入一個題目即可完成關鍵詞拆解、多路檢索、可行性判斷與開題報告生成。

- 設計了一套 5 級證據晉升機制（候選 → 選中 → URL 驗證 → 證據 → 引用），前後端雙重 Promotion Gate 確保「Selected != Evidence」為不變式，每條開題報告章節皆有可追溯的引用來源。

- 實現了基於 Minimax API 的 LLM 編排層，涵蓋關鍵詞拆解、檢索查詢生成、可行性判決三大路徑；每條 LLM 路徑均配備 heuristic fallback，確保 LLM 超時或降級時服務不中斷，95% 以上常見輸入無需 LLM 即可完成可行性判斷。

- 設計了非向量 7 層檢索架構（論文 / 資料集 / 倉庫 / 程式碼 / Baseline / 全文 / 指標），替代傳統 vector DB 方案，使每層檢索結果獨立可撤，降低部署門檻並保留結構化調試能力。

- 建立了 388+ 後端 pytest 測試與 32 個 Playwright E2E 測試檔案的完整測試基礎設施，涵蓋 API schemas 驗證、證據晉升邏輯、LLM 路徑降級、學校模板合規、可行性評分等核心場景，並支援 uvicorn 真實啟動 smoke 驗證。

- 設計了 RunEvent + TraceStore 事件溯源系統，將每次分析的全部事件（含 LLM 呼叫、檢索結果、使用者閘門確認）持久化為可回放的事件流，支援 NDJSON 消費與 SSE 即時推送，實現完整審計軌跡。

- 實現了三套學校模板（default / engineering / cv_ai）的 Readiness 導出檢查系統，包含 hard-block 維度阻斷、膨脹詞檢測（13 個中英文詞彙）、URL 驗證（HTTP 狀態碼 + 回應時間）等多層安全邊界，不滿足條件則阻斷匯出。

- 設計了含 LLM + heuristic 雙路徑的可行性評分引擎，基於 7 維風險評估（EvidenceSupport / DataAvailability / BaselineReadiness / ExperimentalClarity / ScopeControl / ResourceFit / NoveltyDifferentiation）與 6 條硬性否決規則，產出 GO / CONDITIONAL / PIVOT / PARK / STOP 五檔裁決。

- 實現了開題報告草稿（ProposalDraft）的 12 節結構化生成，每節綁定 EvidenceRef 與 confidence 等級，並包含工作量分解（至少 5 項）、創新點標註（至少 2 項）、膨脹詞硬阻斷，確保報告可直接用於答辯提交。

- 實現了 Human-in-the-Loop 閘門機制：Phase 02 關鍵詞確認閘門與 Phase 03 檢索詞確認閘門，使用者必須手動確認後流程才能繼續，前後階段未完成時 API 以 409 拒絕，避免不完整資料進入後續環節。
