# Demo Script 3分鐘

> 題目：**基於 YOLO 的鋼材表面缺陷檢測**
> 目標：3 分鐘走完主閉環。

---

## Phase 0（15 秒）— 輸入題目

頁面輸入「基於YOLO的鋼材表面缺陷檢測」，選「保畢業」，點「開始」。

旁白：只需輸入題目，系統自動判斷能不能開題。

---

## Phase 1（30 秒）— 關鍵詞拆解

顯示 method/dataset/metric 三類關鍵詞。

**核心邊界**：Candidate ≠ Evidence。
候選未驗證 URL，不能直接寫進報告。

旁白：拆出 YOLO/鋼材/缺陷，再去查論文和數據集。

---

## Phase 2（45 秒）— 三線檢索

論文 / 數據集 / 代碼庫三線並行。

旁白：每條線獨立 mock 來源，3-5 個候選。

---

## Phase 3（45 秒）— 可行性裁決

**5 檔裁決**：GO / CONDITIONAL / PIVOT / PARK / STOP。

**硬否決**：無數據集、無指標、無 baseline 都直接 PIVOT。

旁白：7 維風險評估，命中硬否決就給替代路線。

---

## Phase 4（30 秒）— 報告導出

顯示 FinalPackage 預覽，**readiness 8 維**全綠才允許導出。

關鍵詞 Gate：未過 keyword gate 的 evidence 不會進報告。

---

## 收尾（15 秒）

「PaperAgent 把『能不能做』變成可追溯、可審計、可降級的閉環。」

**演示文件**：`apps/web/src/views/OneTopicView.vue`、`apps/api/app/services/readiness.py`。