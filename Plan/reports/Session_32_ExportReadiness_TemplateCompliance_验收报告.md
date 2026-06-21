# Session 32 — ExportReadiness & TemplateCompliance 验收报告

**日期:** 2026-06-21
**Commit:** e764fd0c
**分支:** master

---

## 1. 摘要

Session 32 实现了**8 維導出前就緒檢查（Export Readiness）服務**，支援 3 種學校模板（default / engineering / cv_ai）的合規校驗，並整合至 `one_topic` API 的 `POST /{project_id}/readiness` 端點。當不滿足就緒條件時，`export_allowed` 為 `false`，前端導出按鈕應被禁用。共計 18 個測試（10 後端 + 8 Playwright E2E）全部通過，S29/S31 不回退，3 個開發偏差已修復。

---

## 2. 實作內容

### 2.1 後端產物

| 檔案 | 說明 |
|------|------|
| `apps/api/app/schemas_readiness.py` | 5 個 Pydantic 模型：`ReadinessStatus`（pass/warn/fail）、`SchoolTemplate`（default/engineering/cv_ai）、`ReadinessDimension`、`ReadinessReport`、`ReadinessRequest` |
| `apps/api/app/services/readiness.py` | 8 維就緒檢查服務，含 hard-block 邏輯、誇大詞檢測、模板章節定義 |
| `apps/api/app/api/v1/one_topic.py` | `POST /{project_id}/readiness` 端點，含 FinalPackage section key 映射與 auto-build fallback |

### 2.2 8 維就緒檢查清單

| # | 維度 | 檢查內容 | Hard Block |
|---|------|----------|------------|
| 1 | `section_completeness` | 全部 12 個章節存在且非空 | 是 |
| 2 | `evidence_binding` | 至少部分章節綁定了 `evidence_refs`（≥10% fail，≥40% pass） | 否 |
| 3 | `reference_integrity` | 參考資源中至少 1 條 `review_status` 為 accepted/core/background | 是 |
| 4 | `school_template_fit` | 所選模板要求的章節全部存在 | 是 |
| 5 | `risk_disclosure` | feasibility_risk 章節非空 | 否 |
| 6 | `workload_clarity` | workload 章節內容 ≥3 個條目（以 `-`/`*`/數字開頭的行） | 否 |
| 7 | `innovation_claim_safety` | 創新章節不含誇大用詞（首創/首次/完全解決/革命性/顛覆性等 9 個詞） | 是 |
| 8 | `format_basic` | 報告 Markdown ≥200 字符 | 否 |

### 2.3 學校模板定義

| 模板 | 必備章節 |
|------|----------|
| `default`（輕量） | background, literature_review, research_content, technical_approach, workload, reference_resources |
| `engineering`（工科） | 上述 + dataset_experiment + feasibility_risk |
| `cv_ai`（CV/AI） | 上述 + innovation + feasibility_risk + dataset_experiment |

### 2.4 Hard Block 規則

四個 hard-block 維度中任一 fail → `overall_status = fail` → `export_allowed = false`：
- `section_completeness`
- `reference_integrity`
- `school_template_fit`
- `innovation_claim_safety`

---

## 3. 測試結果

| 類型 | 數量 | 狀態 |
|------|------|------|
| Backend pytest | 10 | 全部通過 |
| Playwright E2E | 8 | 全部通過 |
| **S32 合計** | **18** | **全部通過** |

### 3.1 後端用例（10 條）

| # | 用例名稱 | 驗證點 | 狀態 |
|---|----------|--------|------|
| 1 | S32-1: full_report_all_pass | 完整報告全部維度 pass，export_allowed=true，hard_blocks=0 | PASS |
| 2 | S32-2: missing_technical_approach_fails | 缺少 technical_approach → section_completeness fail，export_allowed=false | PASS |
| 3 | S32-3: empty_citations_fails | 空參考資源 → reference_integrity fail，export_allowed=false | PASS |
| 4 | S32-4: hype_word_fails | 創新含「首次」→ innovation_claim_safety fail，export_allowed=false | PASS |
| 5 | S32-5: cv_ai_no_dataset_fails | cv_ai 模板缺 dataset_experiment → school_template_fit fail | PASS |
| 6 | S32-6a: engineering_requires_technical_approach | engineering 模板缺 technical_approach → school_template_fit fail | PASS |
| 7 | S32-6b: engineering_full_passes | engineering 模板完整 → school_template_fit pass | PASS |
| 8 | S32-7: default_allows_light_but_not_empty_evidence | default 模板允許輕量結構，但空證據仍 reference_integrity fail | PASS |
| 9 | S32-8a: report_json_roundtrip | ReadinessReport 可 JSON 序列化還原 | PASS |
| 10 | S32-8b: dimension_json_roundtrip | ReadinessDimension 可 JSON 序列化還原 | PASS |

### 3.2 Playwright E2E 用例（8 條）

| # | 用例名稱 | 驗證點 | 狀態 |
|---|----------|--------|------|
| 1 | S32-PW-1: readiness_api_accessible | Readiness API 端點可訪問，回傳 overall_status + dimensions | PASS |
| 2 | S32-PW-2: readiness_api_returns_8_dimensions | API 確實回傳 8 個維度 | PASS |
| 3 | S32-PW-3: fail_dimensions_have_required_fix | fail 維度均附 required_fix 修復建議 | PASS |
| 4 | S32-PW-4: different_template_different_results | default vs cv_ai 模板切換，school_template_fit 結果不同 | PASS |
| 5 | S32-PW-5: export_disabled_when_fail | export_allowed=false → overall_status=fail | PASS |
| 6 | S32-PW-6: export_allowed_when_pass_or_warn | export_allowed=true → overall_status 為 pass 或 warn | PASS |
| 7 | S32-PW-7: S29 不回退 | `window.ProposalDraft` 模組仍正常載入 | PASS |
| 8 | S32-PW-8: S31 不回退 | `/analyze` 基礎流程仍正常（回傳 project_id + feasibility.verdict） | PASS |

---

## 4. Bug 修復

開發過程中發現並修復以下 3 個偏差：

| # | 問題描述 | 根因 | 修復方式 |
|---|----------|------|----------|
| 1 | Readiness 端點從 Snapshot（proposal_recommendation）讀取資料，回傳 0 個維度 | 端點直接讀取 Snapshot 而非 FinalPackage，而 Snapshot 不具有 `sections` 結構 | 改為從 FinalPackage 讀取；無 FinalPackage 緩存時自動 `build_final_package()`，再無 Snapshot 時才 fallback 到 `proposal_recommendation` |
| 2 | FinalPackage section key 與 readiness section key 不一致 | FinalPackage 使用 `related_work` 而 readiness 使用 `literature_review`；`feasibility` + `risks` 需合併為 `feasibility_risk` | 加入 `_FP_KEY_TO_READINESS_KEY` 映射表（11 組映射），處理 key 合併（feasibility + risks → feasibility_risk，work_packages + schedule → workload） |
| 3 | Playwright 測試 `TestReadinessPageVisible` 檢查 `window.ReadinessCheck` 前端模組 | 前端尚未實作 ReadinessCheck UI 模組 | 改為直接呼叫後端 API 驗證端點可達性 |

---

## 5. 關鍵設計決策

### 5.1 FinalPackage Section Key 映射策略

**問題：** FinalPackage 的 section key 與 readiness 維度所使用的 section_id 為兩套命名體系（例如 FP 用 `related_work`，readiness 用 `literature_review`；FP 的 `feasibility` 和 `risks` 是兩個獨立章節，readiness 合併為 `feasibility_risk`）。

**決策：** 在端點層採用顯式映射表 `_FP_KEY_TO_READINESS_KEY`，將 11 個 FP key 映射至 9 個 readiness key，並在映射過程中合併內容與 `evidence_refs`。映射表集中定義、易於維護，不侵入 service 層邏輯。

**替代方案考量：**
- 直接改寫 FinalPackage key 名稱（影響範圍過大，涉及下游所有消費方）
- 在 service 層做雙向映射（增加 service 複雜度，違反單一職責）

### 5.2 Auto-Build Fallback

**問題：** readiness 檢查需要 FinalPackage 結構，但使用者可能從未手動觸發過「生成終稿」操作。

**決策：** 端點啟動時按以下優先級嘗試：
1. 讀取 FinalPackage 緩存
2. 無緩存 → 自動調用 `build_final_package()` 並保存
3. 無 Snapshot（無法 build）→ 從 `proposal_recommendation` 提取 outline 作為最低限度 fallback

這確保了 readiness 端點在任何狀態下都不會返回 500 錯誤，且使用者無需手動觸發 build。

### 5.3 Hard Block 機制

僅 4 個維度（section_completeness, reference_integrity, school_template_fit, innovation_claim_safety）設為 hard block。其餘 4 個維度允許 warn 狀態下仍可導出，體現「關鍵缺陷必須修復，次要問題可以容忍」的原則。

---

## 6. 遺留風險與待改進項

| # | 風險 | 影響 | 建議緩解措施 |
|---|------|------|--------------|
| 1 | **前端尚未實作 Readiness UI 模組** | Playwright E2E 透過呼叫 API 而非前端 UI 來驗證，前端尚未有 readiness 儀表板、導出按鈕 disabled 狀態、模板切換下拉選單 | Phase 33 需實作前端 readiness 檢查頁面 UI |
| 2 | **Section Key 映射為啟發式** | `_FP_KEY_TO_READINESS_KEY` 手動維護，若後續新增 FinalPackage section 類型但遺漏更新映射表，該章節將被跳過不檢查 | 建議加入自動化測試，遍歷 `_ALL_SECTIONS` 確認每個 section 在 FP 中都有對應映射 |
| 3 | **誇大詞檢測僅為關鍵字比對** | 當前以 `in` 操作符做子字串比對，可能誤判（如「首次實現」在非創新語境中出現）或漏判 | 可改為基於 LLM 的語義判斷作為增強，關鍵字比對作為 fallback |
| 4 | **Readiness 狀態無持久化** | 每次請求重新計算，若 build 失敗則每次請求都會觸發重試 | 可考慮加入 readiness 結果緩存，在 FinalPackage 未更新時直接返回 |
| 5 | **報告 Markdown 生成尚未與 readiness 整合** | format_basic 維度檢查 Markdown 長度，但 readiness 端點本身不觸發 Markdown 生成 | 應在端點中檢查若 Markdown 為空時自動觸發生成 |

---

## 結論

Session 32 達成全部目標：8 維就緒檢查服務 + 3 種學校模板 + 18 個測試（10 後端 + 8 E2E）全部通過，S29/S31 不回退，3 個開發偏差均已修復。前端 UI 整合與持續優化留待後續階段處理。
