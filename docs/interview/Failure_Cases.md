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
