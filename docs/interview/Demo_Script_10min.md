# Demo Script 10 分鐘

> 使用題目：**基於 YOLO 的鋼材表面缺陷檢測**（Case A）  
> 以及：**基於多模態大模型的通用工業缺陷智能診斷**（Case B，高風險）  
> 目標：10 分鐘內完整展示系統能力——主閉環 + 邊緣案例 + 架構深度。

---

## Phase 0（15 秒）— 打開頁面，輸入題目

**操作：** 打開瀏覽器 `http://127.0.0.1:18181`。輸入框預設已填入「基於YOLO的鋼材表面缺陷檢測」。

**畫面：** 輸入框 + 目標檔位下拉（保畢業）+ 「開始判斷能不能做」按鈕。

**旁白：**  
「這是 PaperAgent 的單一入口。使用者只要輸入題目，選擇目標檔位，就可以開始。」

---

## Phase 1-2（30 秒）— 關鍵詞拆解，Gate 1 + 2

**操作：** 點擊按鈕。等待 3–5 秒。

**畫面：**

- Block 1「題目理解」：`intent_zh = "改進 YOLO 模型應用於鋼材表面缺陷檢測"`
- Block 2「關鍵詞拆解」：

| 類型 | 關鍵詞 |
|---|---|
| method_keywords | YOLO, YOLOv5, YOLOv8 |
| task_keywords | 缺陷檢測, 目標檢測 |
| object_keywords | 鋼材表面, 金屬板材 |
| risk_terms | 智能, 高精度, 實時 |

- 底部出現「確認關鍵詞」按鈕（Gate 1）。點擊後觸發多源檢索（Gate 2）。

**旁白：**  
「Gate 機制確保每個階段使用者知情並確認。關鍵詞不對，後面的檢索方向就偏了——所以我們要求使用者先審視再放行。」

---

## Phase 3（30 秒）— 多源檢索，候選資源

**操作：** 確認關鍵詞後，切換到「證據工作台」Tab。

**畫面：**

- 論文 8 篇（arXiv / OpenAlex）：含 `verification_status = unverified`、`quality_score`。
- 資料集 3 個（HuggingFace）：NEU-DET、GC10-DET、Severstal Steel。
- GitHub 倉庫 3 個（GitHub）：ultralytics/yolov5、ultralytics/ultralytics 等。
- 頂部顯示「多源檢索完成，共 14 條候選資源」。

**旁白：**  
「系統同時檢索四個來源。注意所有資源剛出現時都是 `unverified`——它們是『候選』(Candidate)，還不是『證據』(Evidence)。」

**對應測試：** `test_session14_multi_source_retrieval.py`, `test_session24_candidate_resources.py`

---

## Phase 4（30 秒）— 證據晉升

**操作：**

1. 勾選 Paper A + Paper B + Dataset D1 + Repo R1 →「匯入到證據池」。
2. 選中 Paper A →「URL 驗證」→ `verification_status = verified`。
3. 點擊「確認選定」，該資源晉升為 Evidence。

**畫面：**

- 匯入後資源出現在左欄 `system_found`。
- URL 驗證後，`verification_status` 變綠（`verified`）；`verification_source` 顯示 `arxiv`。
- 確認後產生 `evidence_id`（如 `E1`），出現在右欄 `selected`。
- Trace 面板新增事件：`evidence_imported` → `evidence_verified` → `evidence_promoted`。

**旁白：**  
「Candidate 不等於 Evidence。一條資源要經過三步才能晉升：被選中、URL 驗證通過、使用者確認。驗證失敗或未驗證的資源永遠不會出現在報告中。」

**對應測試：** `test_session26_evidence_promotion.py`

---

## Phase 5（30 秒）— 可行性判斷

**操作：** 回到「一題分析」Tab → 點擊「生成可行性判斷」。

**畫面：**

- 7 維雷達圖或條形圖：EvidenceSupport 85、DataAvailability 90、BaselineReadiness 80、ScopeControl 70、…
- `verdict`：**可做**（綠色，`confidence: 0.85`）。
- `reason`：方法成熟、公開資料充足、可復現 Baseline 多。
- `missing_evidence`：空（無缺失）。
- `pivot_routes`：空（不需收斂）。

**旁白：**  
「可行性模組從證據支撐度、資料可用性、Baseline 可復現性、實驗清晰度、範圍可控性、資源適配度、創新區分度七個維度打分。YOLO 鋼材缺陷因為資料集和 Baseline 都齊全，判斷為可做。」

**對應測試：** `test_session28_feasibility.py`, `test_session31_full_chain_baseline.py` (S31-5)

---

## Phase 6（30 秒）— 報告草稿 + 委員會複核

**操作：** 點擊「生成開題報告」→ 再點「委員會複核」。

**畫面：**

- 報告草稿區顯示 12 個章節。每個章節內容非空，部分綁定 `evidence_refs`。
- 委員會複核面板：導師視角（2 個 issue）、實驗視角（1 個 issue）、風險視角（0 個 issue）。
- `verdict`：`conditional_pass`。
- `required_actions`：列出 2 條修改建議。

**旁白：**  
「報告草稿包含從題目方向到工作量拆解、從風險分析到參考文獻的完整架構。委員會模擬多角色審查，在導出前把問題抓出來。」

**對應測試：** `test_session29_proposal_draft.py`, `test_session30_review.py`

---

## Phase 7（15 秒）— Readiness 檢查

**操作：** 切換到 Readiness 面板，模板選 `default`。

**畫面：**

- 8 維 Readiness：全部 `pass`（綠色）。
- `export_allowed = true`，導出按鈕可用。
- 切換模板到 `cv_ai` → 多出 `dataset_experiment` 要求，狀態仍為 `pass`。

**旁白：**  
「導出前 Readiness 檢查涵蓋章節完整性、證據綁定、參考文獻驗證、模板適配、風險揭露、工作量清晰度、創新詞安全、格式基本要求 8 個維度。支援三種學校模板切換。」

**對應測試：** `test_session32_readiness.py`, `test_one_topic_session32_readiness.py`

---

## 附加展示 1（60 秒）— Trace 回放

**操作：** 切換到「Trace」面板。

**畫面：**

- 時間線倒序列出 Phase 1–7 所有關鍵事件：
  - `analyze_completed` → `keyword_review_approved` → `retrieval_completed` → `evidence_imported` → `evidence_verified` → `evidence_promoted` → `feasibility_generated` → `report_generated` → `review_completed` → `readiness_checked`
- 每條 Trace 顯示 `action`、`actor`、`elapsed_ms`、`delta`（狀態變化）。
- 點擊某條 `evidence_id` 可看該證據的完整時間線。
- 示範：在輸入框加一條使用者備註（如「優先做帶鋼表面」），Trace 面板即時出現 `user_patch_applied`。

**旁白：**  
「每個操作都記錄在 Trace 中，包括自動事件和使用者手動修正。回放模式可以重現整個開題決策過程，對導師審查和答辯準備很有價值。」

**對應測試：** `test_session11_trace_persistence.py`, `test_session27_run_event.py`

---

## 附加展示 2（60 秒）— 失敗案例展示

**操作：** 輸入高風險題目「基於多模態大模型的通用工業缺陷智能診斷」。

**畫面：**

- 關鍵詞拆解：risk_terms 多達 5 條（通用、智能、高精度、實時、跨場景）。
- 檢索結果：論文僅 5 篇，公開資料集幾乎沒有，Baseline 為 0。
- 可行性：`verdict = 暫緩 / 可轉向`（紅色），`confidence: 0.55`。
- 7 維評分：DataAvailability 20、BaselineReadiness 10。
- 3 條 PIVOT 路線顯示：
  - 保守：聚焦半導體晶圓缺陷分類
  - 平衡：視覺-語言預訓練的少樣本學習
  - 進取：CLIP 微調鋼材表面異常檢測
- `missing_evidence`：工業缺陷統一基準、MLLM 推理硬體成本估算。

**旁白：**  
「高風險題目會被系統攔下。關鍵字『通用』觸發多條風險詞，檢索找不到公開資料集和可復現 Baseline，可行性直接判定為暫緩。但系統不是簡單說『NO』——它給出三條收斂路線，引導使用者把題目縮到可執行範圍。」

**對應測試：** `test_session31_full_chain_baseline.py` (S31-6, S31-7), `test_session17_demo_baseline.py`

---

## 附加展示 3（60 秒）— Candidate ≠ Evidence

**操作：** 在證據工作台，選一條未驗證的資源，點「URL 驗證」時選一個無效 URL。

**畫面：**

- 驗證結果：`verification_status = failed`，顯示 `verification_source = http`，`verification_confidence = 0`。
- 該資源無法晉升為 Evidence——`promote_to_evidence` 返回 `status = blocked`，blocker 提示「URL verification failed」。
- 進入報告生成時，該資源不在 citation_list 中。
- 對比：另一條 verified 的資源正常晉升，出現在報告引用表。

**旁白：**  
「Candidate 到 Evidence 之間有一道 Gate：URL 必須經過驗證。如果連結 404 或無法存取，系統不允許它進入報告。這是為了防止開題報告引用不可追溯的來源。」

**對應測試：** `test_session26_evidence_promotion.py` (S26-B-2, S26-B-3), `test_session10_verification.py`

---

## 附加展示 4（60 秒）— 高風險 PIVOT / STOP 流程

**操作：** 繼續使用 Case B，比對 `verdict` 在切換 `goal_level` 時變化。

**畫面：**

- `goal_level = 衝高水平`：`verdict = PIVOT`，3 條路線。
- 切換到 `goal_level = 保畢業`：`verdict = STOP`，系統認為該題目無法在低強度下完成。
- PIVOT 路線每個都有 `required_evidence` 和 `risk_delta`。
- 選定一條路線後，工作包自動生成。

**旁白：**  
「PIVOT 路線有三個層級。保守路線保留 MLLM 但縮場景，平衡路線保留多模態但縮任務，進取路線直接回到 Vision-only 的成熟方案。同一題目在不同目標檔位下可行性不同——衝高水平可能 PIVOT，保畢業可能直接 STOP。」

**對應測試：** `test_session28_feasibility.py` (S28-B-6), `test_session4_pivot.py`

---

## 附加展示 5（60 秒）— Playwright / Baseline 回歸

**操作：** 終端機執行測試命令。

**畫面（終端機輸出）：**

```bash
.venv/Scripts/python.exe -m pytest apps/api/tests/test_session31_full_chain_baseline.py -v
```

輸出 10 條測試全部 PASS。

```bash
.venv/Scripts/python.exe -m pytest apps/web/e2e/test_one_topic_session32_readiness.py -v
```

輸出 8 條 Playwright 測試全部 PASS。

**旁白：**  
「每個 Session 的交互主線都固化為可重複執行的回歸基線。前端 Playwright 測試模擬真實使用者操作，後端 Baseline 測試用 fixture 數據做合同斷言。改 UI、改 Prompt、改證據邏輯後，跑一次基線就知道有沒有回退。」

---

## 附加展示 6（60 秒）— 架構圖講解

**展示架構圖（配合白板或 PDF）：**

```
┌─────────────────────────────────────────────────────┐
│                  使用者介面 (Web)                       │
│  輸入題目 → Gate 確認 → 工作台 → 報告 → Readiness → 導出  │
└──────────┬──────────────────────────────────────────┘
           │ HTTP / SSE
┌──────────▼──────────────────────────────────────────┐
│          FastAPI 後端 (單一入口 /api/v1/one-topic)     │
│  ┌───────┐ ┌────────┐ ┌─────────┐ ┌──────────────┐  │
│  │ Analyze│ │Evidence│ │Feasibility│ │ Readiness    │  │
│  │ Keyword│ │ 升降級 │ │ PIVOT    │ │ 8 維檢查      │  │
│  │ Gate   │ │ URL驗證│ │ 7 維評分 │ │ 模板適配      │  │
│  └───────┘ └────────┘ └─────────┘ └──────────────┘  │
│  ┌───────┐ ┌────────┐ ┌─────────┐                   │
│  │ Report│ │Review  │ │ Trace   │                   │
│  │ 草稿   │ │委員審查 │ │ 回放     │                   │
│  └───────┘ └────────┘ └─────────┘                   │
└──────────┬──────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────┐
│          外部服務層                                   │
│  arXiv / OpenAlex / HuggingFace / GitHub             │
│  Minimax LLM (可降級為 heuristic)                     │
│  URL Verified (CDP / requests)                       │
└─────────────────────────────────────────────────────┘
┌──────────┬──────────────────────────────────────────┐
│      Docs/demo/baselines/ (回歸 fixture 數據)          │
│      test_session31_full_chain_baseline (10 項斷言)    │
│      e2e/test_one_topic_session32_readiness (8 項)    │
└─────────────────────────────────────────────────────┘
```

**旁白：**  
「架構分三層。上層是 Web UI，中間是 FastAPI 後端——所有業務邏輯集中在這裡，以 `/api/v1/one-topic` 為單一入口。下層是外部服務，所有外部呼叫都有 heuristic fallback。最下層是回歸基線，每個 Session 的交互主線都固化成測試，確保後續開發不回退。」

---

## 收尾總結（30 秒）

> PaperAgent 的核心不是生成開題報告，而是在生成之前幫使用者降低風險：  
> - Gate 機制確保每一步使用者知情  
> - Candidate ≠ Evidence 防止未經驗證的引用  
> - 7 維可行性 + PIVOT 路線引導題目收斂  
> - 8 維 Readiness 確保導出品質  
> - Trace 回放讓決策過程可追溯  
> - 回歸基線鎖定每個交互階段  

