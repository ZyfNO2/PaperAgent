# 失敗案例集（Failure Cases）

> 至少 6 個真實可演示的邊緣案例，覆蓋系統各層攔截邏輯。  
> 每個案例包含：輸入 -> 系統攔截 -> 使用者看到的 UI -> 面試解釋 -> 對應測試。

---

## Case 1：無公開資料集

**輸入：**  
使用者輸入「基於多模態大模型的通用工業缺陷智能診斷」，目標檔位「衝高水平」。

**系統如何攔截：**  
可行性模組的 `DataAvailability` 維度檢查 `has_dataset = False`，觸發硬性否決規則 `no_dataset`。`assess_feasibility()` 回傳 verdict 為 `PIVOT` 或 `STOP`，不得為 `GO`。7 維評分中 DataAvailability 低於 20 分。

**使用者看到什麼：**  
- 可行性區塊顯示紅色 `verdict：暫緩 / 可轉向`。  
- DataAvailability 維度顯示 `分數：15/100`，`level：fatal`。  
- `missing_evidence` 列出「工業缺陷統一基準」。  
- 下方出現 3 條 PIVOT 路線（保守 / 平衡 / 進取）。

**面試怎麼解釋：**  
「系統在可行性階段做了兩層檢查。第一層是硬性否決——無公開資料集直接禁止 GO。第二層是引導——不是簡單拒絕，而是給出三條收斂路線讓使用者選擇。這體現了系統『判斷風險但不代替決策』的設計原則。」

**對應測試：**  
- `test_session28_feasibility.py::TestNoDataset::test_no_dataset_blocks_go`  
- `test_session28_feasibility.py::TestNoDataset::test_no_dataset_no_metrics_no_baseline_is_stop`  
- `test_session31_full_chain_baseline.py::TestCaseBVerdict::test_case_b_must_pivot_park_or_stop`

---

## Case 2：無 Baseline（有資料集但無開源程式碼）

**輸入：**  
使用者輸入一個冷門題目，有公開資料集（如某醫學影像資料集），但相似研究方向無開源程式碼。

**系統如何攔截：**  
`BaselineReadiness` 維度檢查 `has_baseline = False`，觸發 `no_baseline` 硬性否決。可行性 `verdict` 為 `CONDITIONAL` 或 `PIVOT`。`missing_evidence` 中包含「可復現 Baseline 程式碼」。

**使用者看到什麼：**  
- 可行性 verdict 顯示「有條件通過」或「可轉向」。  
- `BaselineReadiness` 分數低於 30，`level = high`。  
- `missing_evidence` 提示：需從零實作 Baseline。  
- PIVOT 路線建議轉向資料更多或有現成 Baseline 的相近方向。

**面試怎麼解釋：**  
「有資料集不代表可做。如果論文方法無法復現——沒有開源程式碼、沒有預訓練權重——碩士生要在半年內從零實作 Baseline 風險極高。系統把 Baseline 可用性作為獨立維度評估，對應真實開題中最常見的『有想法但做不到』問題。」

**對應測試：**  
- `test_session28_feasibility.py::TestDatasetNoBaseline::test_dataset_no_baseline_not_go`  
- `test_session28_feasibility.py::TestDatasetNoBaseline::test_dataset_no_baseline_has_pivot_routes`

---

## Case 3：URL 未驗證 / 404

**輸入：**  
使用者匯入一條論文候選資源，但該論文的 arXiv 連結已失效或輸入錯誤。使用者嘗試將該資源晉升為 Evidence。

**系統如何攔截：**  
Evidence Promotion Gate 檢查 `url_verification_status`。若為 `unchecked` 或 `failed`，`check_promotion_gate()` 回傳 `status = blocked`，blockers 列表中包含 `"url not verified"` 或 `"url verification failed"`。

**使用者看到什麼：**  
- 在證據工作台中，該資源的 `verification_status` 保持為 `unverified`（未驗證）或變為 `failed`。  
- 點擊「確認選定」後彈出提示：「此資源 URL 尚未通過驗證，無法晉升為證據」。  
- 該資源在報告的 `citation_list` 中不會出現。  
- 報告頂部顯示警告：「部分參考資源未驗證」。

**面試怎麼解釋：**  
「URL 驗證是 Candidate 到 Evidence 之間的必經 Gate。系統會實際嘗試存取 URL：arXiv 檢查 arxiv_id 是否存在，GitHub 檢查 owner/repo 是否可存取，一般 URL 檢查 HTTP 狀態碼。驗證失敗的資源不會被報告引用——這是為了確保開題報告中的每一條引用都是可追溯、可存取的。」

**對應測試：**  
- `test_session26_evidence_promotion.py::TestURLUncheckedBlocked::test_unchecked_url_blocked`  
- `test_session26_evidence_promotion.py::TestURLFailedBlocked::test_failed_url_blocked`  
- `test_session10_verification.py::test_01_arxiv_url_extraction_and_verification`

---

## Case 4：有論文但無可復現程式碼（Evidence Discrepancy）

**輸入：**  
使用者找到 8 篇相關論文，但其中 7 篇未開源程式碼，僅 1 篇有 GitHub 倉庫且訓練腳本不完整。

**系統如何攔截：**  
`EvidenceSupport` 維度分數被 `repo_count` 拉低——論文多但可復現的 Baseline 少，`BaselineReadiness` 維度觸發硬性否決。可行性不允許 GO。

**使用者看到什麼：**  
- 可行性區塊顯示 `EvidenceSupport：60/100`（有論文），但 `BaselineReadiness：15/100`（無程式碼）。  
- `verdict` 為 `CONDITIONAL`，條件是「需找到至少一個完整 Baseline 或自行實作」。  
- `missing_evidence` 列出「具備完整訓練腳本的 GitHub 倉庫」。  
- 委員會複核的實驗視角會產出 `high` 級別 issue：「缺乏可復現 Baseline，實驗比對不可靠。」

**面試怎麼解釋：**  
「我們叫它 Evidence Discrepancy——有文獻但沒程式碼。在學術開題中這是最常見的誤判：使用者覺得論文多就可做，但實際上每篇論文的方法都需要自行復現。系統把論文數量和 Baseline 可用性分開評估，暴露這個 discrepancy。」

**對應測試：**  
- `test_session28_feasibility.py::TestFatalDimension::test_fatal_dimension_forces_non_go`  
- `test_session31_full_chain_baseline.py::TestCaseARepo::test_case_a_has_repo`（Case A 檢查至少有 1 個 repo）

---

## Case 5：創新點誇大（Inflated Words）

**輸入：**  
開題報告的創新點章節包含「本研究首次提出了一種全新框架，國際領先，填補了該領域的空白」。

**系統如何攔截：**  
Readiness 模組的 `innovation_claim_safety` 維度使用 `_INFLATED_WORDS` 列表（含「首次」、「國際領先」、「填補空白」、「革命性」、「顛覆性」等 9 個詞）掃描創新點內容。命中後該維度狀態為 `fail`。

**使用者看到什麼：**  
- Readiness 面板：`innovation_claim_safety` 顯示紅色 `fail`。  
- 訊息：「創新點含誇大用詞：首次、國際領先、填補空白」。  
- `required_fix`：「移除誇大用詞：首次、國際領先、填補空白」。  
- `export_allowed = false`，導出按鈕灰色不可點。  
- `hard_blocks` 列表包含 `innovation_claim_safety`。

**面試怎麼解釋：**  
「Readiness 的 innovation_claim_safety 維度是一道安全閘門。在學術開題中，『首次』、『填補空白』這類詞會讓審查委員非常敏感——它們幾乎不可能在碩士階段成立。系統不是禁止使用者寫創新點，而是提醒使用者用詞要精準、有依據。這個檢查是 export 的必要條件之一，屬於 hard block。」

**對應測試：**  
- `test_session32_readiness.py::TestInflatedInnovation::test_hype_word_fails`  
- `test_session32_readiness.py::TestFullReportPass::test_full_report_all_pass`（對比無誇大詞時 pass）

---

## Case 6：匯出前合規失敗（缺技術路線）

**輸入：**  
開題報告缺少技術路線章節（`technical_approach` 為空或不存）。

**系統如何攔截：**  
- `section_completeness` 維度檢查發現缺少 `technical_approach`，狀態為 `fail`。  
- `school_template_fit` 維度檢查（所有模板都需要 `technical_approach`）也同時觸發 `fail`。  
- 因為 `section_completeness` 和 `school_template_fit` 都在 `_HARD_BLOCK_DIMENSIONS` 集合中，導出被硬攔截。

**使用者看到什麼：**  
- Readiness 面板：`section_completeness`（紅）和 `school_template_fit`（紅）兩項 fail。  
- `section_completeness` 訊息：「缺少 1 個必要章節：technical_approach」；`required_fix`：「補充章節：technical_approach」。  
- `school_template_fit` 訊息：「模板 'default' 要求的章節缺失：technical_approach」。  
- `export_allowed = false`，導出按鈕完全 disabled。  
- 頁面可能顯示一個黃色提示條：「匯出前需修復以下問題…」。

**面試怎麼解釋：**  
「這是兩層攔截的疊加效果。section_completeness 檢查所有 12 個章節是否存在——這是通用檢查。school_template_fit 檢查特定模板要求的章節——這是針對學校格式的檢查。當同一缺失觸發兩個維度時，使用者得到更明確的指引：不僅知道少了什麼，還知道這不符合哪個模板。」

**對應測試：**  
- `test_session32_readiness.py::TestMissingTechnicalApproach::test_missing_technical_approach_fails`  
- `test_session32_readiness.py::TestEngineeringTemplate::test_engineering_requires_technical_approach`  
- `test_session32_readiness.py::TestDefaultTemplateLightweight::test_default_allows_light_sections_but_not_empty_evidence`

---

## Case 7（附加）：LLM 呼叫失敗 → Heuristic Fallback

**輸入：**  
使用者使用 LLM 路徑（prefer=llm），但 Minimax API 不可用（金鑰過期、網路超時、服務下線）。

**系統如何攔截：**  
LLM 服務層捕獲異常（`requests.exceptions.RequestException`），回傳 `None`。上層 `keyword_search_assistant` 檢查到結果為 `None`，自動使用 heuristic 路徑（基於規則的關鍵詞拆解 + arXiv 檢索）代替。整個請求不中斷。

**使用者看到什麼：**  
- 主流程正常完成，但頁面頂部出現淺黃色提示條：「LLM 服務暫不可用，已切換為 heuristic 模式」。  
- 關鍵詞拆解結果不如 LLM 路徑豐富，但仍包含核心 method/task/object 關鍵詞。  
- 使用者可以在設定中切換回 `prefer=heuristic` 或等待後重試。

**面試怎麼解釋：**  
「LLM 不是系統的單點故障。所有 LLM 路徑都有對應的 heuristic fallback——關鍵詞拆解、檢索建議、報告生成都是如此。heuristic 結果比 LLM 粗糙，但保證服務不中斷。這是生產級系統的基本要求：外部 API 不可用不應該讓整個應用停擺。」

**對應測試：**  
- `test_session6_llm_path.py::test_search_assistant_heuristic_fallback`  
- `test_session6_llm_path.py::test_merge_with_heuristic_dedup`

---

## Case 8（附加）：多源檢索衝突

**輸入：**  
使用者輸入題目。系統檢索後，論文來源推薦 A 方向（如「注意力機制改進」），資料集來源推薦 B 方向（如「資料擴增」），GitHub 來源推薦 C 方向（如「蒸餾部署」）。

**系統如何攔截：**  
系統不自動選擇方向，而是透過 Gate 機制等待使用者確認。檢索結果的 `candidate_resources` 中不同來源的論文、資料、程式碼各自獨立呈現，`quality_score` 和 `relevance` 標明各自維度的匹配度。系統不強行融合衝突結果。

**使用者看到什麼：**  
- 證據工作台左欄 `system_found` 中，論文偏向注意力和檢測精度，資料集偏向資料擴增。  
- 每個候選資源旁標註 `source` 和 `quality_score`。  
- 使用者需要手動勾選哪些資源匯入，並決定研究方向。  
- 報告草稿中，如果使用者選擇的方向不同來源之間有矛盾，委員會複核的「風險視角」可能產出 `medium` issue，指出研究方向不一致。

**面試怎麼解釋：**  
「多源檢索本質上會產生衝突——不同來源對『相關』的定義不同。arXiv 論文看方法創新，HuggingFace 資料集看規模和授權，GitHub 看是否可復現。系統的設計原則是『不代替使用者做融合決策』——把選擇權交給使用者，同時用 quality_score 和委員會複核來提示風險。」

**對應測試：**  
- `test_session14_multi_source_retrieval.py`（檢索完整性）  
- `test_session24_candidate_resources.py`（候選資源獨立呈現）  
- `test_session30_review.py`（委員會 Issue 檢測方向不一致）

---

## 案例對照表

| # | 案例 | 攔截層級 | 硬攔截？ | 主要測試檔案 |
|---|---|---|---|---|
| 1 | 無公開資料集 | Feasibility (DataAvailability) | 是（不得 GO） | test_session28_feasibility.py |
| 2 | 無 Baseline | Feasibility (BaselineReadiness) | 是（不得 GO） | test_session28_feasibility.py |
| 3 | URL 404 | Evidence Promotion Gate | 是（不得晉升） | test_session26_evidence_promotion.py |
| 4 | 有論文無程式碼 | Feasibility (Discrepancy) | 是（CONDITIONAL） | test_session28_feasibility.py |
| 5 | 誇大創新詞 | Readiness (innovation_claim_safety) | 是（不得匯出） | test_session32_readiness.py |
| 6 | 缺技術路線 | Readiness (section_completeness / template_fit) | 是（不得匯出） | test_session32_readiness.py |
| 7 | LLM 掛掉 | Heuristic Fallback | 否（降級） | test_session6_llm_path.py |
| 8 | 多源檢索衝突 | Gate（使用者決策） | 否（提示） | test_session14_multi_source_retrieval.py |
| 9 | 創新點用「填補空白」 | Readiness (innovation_claim_safety) | 是（不得匯出） | test_session32_readiness.py |
| 10 | 風險章節缺失 | Readiness (risk_disclosure) | 是（不得匯出） | test_session32_readiness.py |
| 11 | Memory 壓縮後 critical 事件丟失 | Memory Compression | 是（測試守護） | test_session35_agent_memory_replay.py |
| 12 | MCP 工具調用越權（write_file） | MCP Permission | 是（直接拒） | test_session36_mcp_tools.py |
| 13 | Multi-Agent 成本超限 | Cost Budget | 否（降級到單流程） | test_session37_multi_agent_design.py |
| 14 | RAG 檢索為空 | Failure Detector | 否（fallback 擴展） | test_session34_rag_pipeline_eval.py |
| 15 | Snapshot 重建後關鍵狀態丟失 | ProjectMemory | 是（測試守護） | test_session35_agent_memory_replay.py |
| 16 | Step Deck 刷新後斷流 | Replay | 否（恢復按鈕） | test_one_topic_session35_memory_replay.py |

---

## Case 9：創新點用「填補空白」這種誇大詞

**輸入：**  
使用者輸入「基於改進 YOLOv8 的鋼材缺陷檢測」，在創新點章節寫「本研究填補了國內外學術界在該領域的空白」。

**系統如何攔截：**  
Readiness 維度 `innovation_claim_safety` 檢測到「填補空白」這種浮誇詞，標記為 warn。`export_allowed` 變為 false，導出按鈕置灰。

**使用者看到什麼：**  
- 「報告合規性」面板顯示「創新點描述」分項失敗，紅色標籤。  
- 提示：「請用具體改進點描述創新，避免使用『填補空白』『國內外首創』等詞彙」。

**面試怎麼解釋：**  
「學術誠信是開題的底線。Readiness 維度把誇大詞列為硬阻擋項，因為這類詞在答辯時會被評審老師直接挑出來。系統不只判斷『內容是否完整』，還判斷『表述是否符合學術規範』。」

**對應測試：**  
- `test_session32_readiness.py::TestInnovationSafety::test_innovation_overclaim_blocks_export`

---

## Case 10：風險章節缺失

**輸入：**  
報告草稿未包含「風險與應對」章節，雖然有方法論、實驗設計、結果分析。

**系統如何攔截：**  
Readiness 維度 `risk_disclosure` 檢測到缺「風險」章節。`overall_status = fail`，`export_allowed = false`。

**使用者看到什麼：**  
- 「8 維合規性」面板顯示「風險披露」分項失敗。  
- 提示：「請補充『可能遇到的困難與對策』章節」。

**面試怎麼解釋：**  
「開題答辯老師必問『你這個方案可能遇到什麼問題』。Readiness 把『風險章節』列為硬條件，強制要求學生提前思考困難。這是工程系統對學術標準的內化。」

**對應測試：**  
- `test_session32_readiness.py::TestRiskDisclosure::test_no_risk_section_blocks_export`

---

## Case 11：Memory 壓縮後 critical 事件丟失

**輸入：**  
事件數量超過 200 觸發自動壓縮，5 個 `user_patch` 事件混在 250 個普通事件中。

**系統如何攔截：**  
`compress_transcript()` 嚴格遵守 `keep_critical_types` 白名單，`user_patch` 永遠保留。測試斷言「5 個 gate 事件必須都在」。

**使用者看到什麼：**  
- 系統無 UI 提示（後台保證）  
- 但審計時 Trace 仍可查到所有 user_patch

**面試怎麼解釋：**  
「用戶的修正意圖不能丟——這是審計 trail 的核心。所以 `user_patch` 屬於 critical event，永遠不被壓縮。同理 `evidence_promotion`、`url_verified`、`readiness_check`、`llm_call` 這 6 類都是 critical。設計哲學：默認丟普通事件，永遠保留決策路徑。」

**對應測試：**  
- `test_session35_agent_memory_replay.py::TestCriticalEventsPreserved::test_gate_events_not_compressed`

---

## Case 12：MCP 工具調用越權（外部 Agent 嘗試調 write_file）

**輸入：**  
外部 Agent 通過 MCP 發送 `tool_name=write_file`, `arguments={path: "/etc/passwd"}`。

**系統如何攔截：**  
`check_tool_allowed()` 檢測 `write_file` 在 `FORBIDDEN_TOOLS` 黑名單 → 直接返回 `error.code = "forbidden_tool"`，HTTP 200。

**使用者看到什麼：**  
- 外部 Agent 收到 `success: false` + `error.code: "forbidden_tool"`  
- Trace 寫一條 `mcp_tool_call` action，actor=agent，包含失敗原因

**面試怎麼解釋：**  
「**默認拒絕，顯式允許**。MCP 服務器有 3 層權限：白名單（必須在 manifest）、黑名單（write_file 永拒）、Gate 前置（keyword gate / FinalPackage）。外部 Agent 不能調寫操作，所有嘗試都進 Trace 可審計。寫操作必須用戶在 Web UI 顯式確認。」

**對應測試：**  
- `test_session36_mcp_tools.py::TestForbiddenToolRejected`  
- `test_one_topic_session36_mcp.py::TestMCPWriteFileRejected`

---

## Case 13：Multi-Agent 成本超限

**輸入：**  
理論上拆分後子 Agent 開始瘋狂調 LLM，3 輪就消耗 30 次 LLM 調用。

**系統如何攔截：**  
`check_budget()` 檢測 `llm_calls > max_llm_calls(20)` → 返回失敗。`should_fallback()` 觸發 `fallback_to_single_agent = True` → 回退到單流程。

**使用者看到什麼：**  
- 系統無 UI 提示（自動降級）  
- Trace 記錄 `cost_exceeded` + `fallback_to_single_agent`

**面試怎麼解釋：**  
「Multi-Agent 容易燒錢，所以我們有 4 維硬限制 + 2 個降級開關。超限立即停止 + 回退單流程，不會無限循環燒 LLM 預算。設計哲學：寧可降級，不可失控。」

**對應測試：**  
- `test_session37_multi_agent_design.py::TestCostBudgetEnforcement::test_llm_calls_exceeded`  
- `test_session37_multi_agent_design.py::TestFallback::test_cost_exceeded_triggers_fallback`

---

## Case 14：RAG 檢索為空

**輸入：**  
冷門題目，所有檢索源（paper/dataset/repo）都返回 0 個候選。

**系統如何攔截：**  
`rag_evaluator.detect_empty_retrieval()` 檢測 `items.length == 0`，標記 `failure_code: "empty_retrieval"`。**未來**：自動擴展關鍵詞；**當前**：標記後讓用戶決定是否繼續。

**使用者看到什麼：**  
- 評估報告顯示 `empty_retrieval: true`  
- 提示用戶「檢索為空，建議調整關鍵詞或考慮 PIVOT」

**面試怎麼解釋：**  
「RAG 不是萬能。冷門領域、新興方向檢索一定為空。與其假裝「我找到了」返回空結果讓 LLM 編，不如明確告訴用戶「沒找到」並建議改方向。失敗檢測器是 RAG 系統穩定性的關鍵。」

**對應測試：**  
- `test_session34_rag_pipeline_eval.py`（多個 empty_retrieval 相關測試）

---

## Case 15：Snapshot 重建後關鍵狀態丟失

**輸入：**  
壓縮後重建 Snapshot，發現 `feasibility_verdict`、`accepted_evidence` 計數丟失。

**系統如何攔截：**  
`build_snapshot_from_run()` 反向掃描所有 events 取最後寫入值。測試斷言 `readiness_status` 在壓縮前後**都**保留。

**使用者看到什麼：**  
- 系統無 UI 提示（後台保證）  
- 但測試覆蓋了這個回歸

**面試怎麼解釋：**  
「Snapshot 不是『丟掉舊的生成新的』，而是『反向掃描所有 events 重建』。這保證壓縮後關鍵狀態（feasibility verdict、accepted count、readiness status）不丟。ProjectMemorySnapshot 是有界且不可壓縮的，獨立於 Transcript。」

**對應測試：**  
- `test_session35_agent_memory_replay.py::TestReadinessStableAcrossCompression::test_readiness_status_preserved_in_snapshot`

---

## Case 16：Step Deck 刷新後斷流

**輸入：**  
用戶在前端運行到 candidate_review 時刷新瀏覽器。

**系統如何攔截：**  
前端 `run_state.json` 檢測 `last_seq` 與 SSE 連接中斷，顯示「恢復」按鈕。點擊後調 `/memory/replay` 拿 `step_states`，前端重建 Step Deck。

**使用者看到什麼：**  
- 「系統已斷流，點擊恢復」按鈕  
- 點擊後自動跳到上次中斷的 step

**面試怎麼解釋：**  
「瀏覽器刷新是常見操作。我們不讓用戶從頭來，而是用 `replay_source` 告訴前端「從 snapshot + 最近的 events 恢復」。冷啟動時間 < 200ms，用戶無感知。這體現了 4 層 Memory 設計的價值。」

**對應測試：**  
- `test_one_topic_session35_memory_replay.py::TestReplayRestoresState`  
- `test_one_topic_session35_memory_replay.py::TestRecoveryButton`
