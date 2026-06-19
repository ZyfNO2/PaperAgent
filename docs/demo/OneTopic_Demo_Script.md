# OneTopic Demo 演示脚本（Step-by-Step）

> 演示目标：让外部读者 30 分钟内跑通**主闭环** —— 输入题目 → 工作台审核 → 开题报告导出。
> 演示题目：**基于 YOLO 的钢材表面缺陷检测**（已写在 `index.html` 输入框默认值）。
> 必备前置：`start_all.bat` 已运行，浏览器打开 <http://127.0.0.1:18181>。

---

## 演示前置检查

| 项 | 检查命令 / 期望 |
|---|---|
| 后端在 18181 | `curl http://127.0.0.1:18181/docs` 返回 200 |
| 前端在 8080 | 浏览器打开 <http://127.0.0.1:8080> |
| `.runtime/` 已存在 | `ls .runtime/` 至少有 `traces/ materials/ retrieval/` 三个子目录 |
| `.env` 已复制（或用 fallback） | 不填 `MINIMAX_API_KEY` 也能跑，但 LLM 路径走 heuristic |

---

## Step 1. 输入题目

| 字段 | 值 |
|---|---|
| 题目 | `基于 YOLO 的钢材表面缺陷检测`（默认已填） |
| 专业 | `计算机科学与技术` |
| 导师方向 | `工业质检` |
| 目标档位 | `保毕业` |
| LLM 路径 | `auto` |

操作：点击 **🚀 开始判断能不能做**。

预期页面变化：

- 页面下方依次出现 6 个 block：**题目理解 / 关键词拆解 / 证据检索 / 可行性判断 / 开题建议 / 轻量审核**。
- 右下角小字显示本次 `elapsed_ms` 和 `project_id`（记下来给 Step 9 用）。

失败降级：

- 如果“题目理解”返回兜底文本且没有 `intent_zh`，说明 LLM 调用失败且 heuristic 也失败；
  此时点击页面右上角设置 → 切换 `LLM 路径` 到 `heuristic`，重试。

---

## Step 2. 查看关键词拆解

关注点：

- **method_keywords** 至少含 `YOLO`；
- **task_keywords** 含 `缺陷检测`；
- **object_keywords** 含 `钢材表面`；
- **risk_terms** 含 `智能 / 高精度 / 实时`（如出现，证明风险词识别正常）；
- **query_keywords_en / zh** 至少各 3 条。

如果某项缺失，点击右上 **🛠 编辑关键词**（如果当前版本未提供，可跳过 —— 在 Step 6 工作台里再调整）。

---

## Step 3. 运行多源检索

切换到 **证据工作台** tab → 找到 **🔍 多源检索** 面板。

操作：

- 选择 scope：`all`（或分别试 `paper / dataset / repo`）；
- `refresh=True`（强制重新抓取）；
- 点击 **开始检索**。

预期页面变化：

- 列出候选论文 / 数据集 / GitHub，含 `source / source_mode / verification_status / quality_score`；
- 5-30s 内返回（取决于外部 API 速度）；
- 顶部出现 **📥 导入候选** 按钮。

失败降级：

- 显示 *网络异常或被限流* → 等 30s 重试或切换 `refresh=False`（用上次结果）；
- OpenAlex / arXiv 失败时 GitHub / HuggingFace 仍可能成功；面板会标红失败的源但不影响其他源。

---

## Step 4. 导入候选论文 / 数据集 / GitHub

操作（演示用）：

- 勾选前 3 条 papers → 点击 **📥 导入到证据池**；
- 勾选 1-2 条 datasets → 导入；
- 勾选 1 条 GitHub repo（最好含训练脚本）→ 导入。

预期：

- 顶部提示 “已导入 N 条证据”；
- 工作台双栏的 `system_found` 出现新条目；
- 每条证据显示 `verification_status = unverified / partial`（取决于源）。

---

## Step 5. 运行 URLVerified

在工作台选中刚导入的 1-2 条 → 点击 **✅ URL 验证**。

预期：

- 几秒后 `verification_status` 从 `unverified` 变为 `verified / partial / failed`；
- `verification_source` 显示 `arxiv / openalex / github / huggingface / manual` 之一；
- 工作台右上小角标 **Trace 事件 +1**（见 Step 8）。

---

## Step 6. 上传或粘贴一条用户资料

切换到 **📎 资料工作台** tab。

演示两种入口：

1. **粘贴文字**：
   - tab 选 “文字 / URL / 备注”；
   - 选 `manual_note` → 粘贴一段导师备注（例：“优先做带钢表面划痕，建议引入 NEU-DET”）；
   - 点击 **生成草稿卡片**。
2. **上传 PDF**（如有）：
   - tab 切回 “上传文件”；
   - 选一个小 PDF（< 5MB），点击 **上传 + 生成草稿**。

预期：

- 草稿卡片列表出现新条目，含 `suggested_type / confidence / page_refs / warnings`；
- 草稿可**编辑标题 / 摘要 / 类型**（双击字段）；
- 点击 **📥 导入证据池**，弹出 `review_status / workspace_lane / created_by_skill` 选择对话框。

---

## Step 7. 在工作台移动 / 审核证据

操作：

- 选 1 条 paper → 移到 `core`；
- 选 1 条 dataset → 移到 `accepted`；
- 选 1 条 repo → 移到 `background`；
- 选 1 条不相关的 → 移到 `rejected`（演示 **rejected 不引用**）。

预期：

- 顶部状态栏实时更新 `paper_count / dataset_count / accepted_count / core_count / rejected_count`；
- 每次移动触发一条 trace 事件（**workspace_lane_changed**）。

---

## Step 8. 查看 Trace

切换到 **🔍 Trace** 面板。

预期：

- 列出 Step 1-7 所有关键事件：`analyze_completed / evidence_imported / evidence_verified / material_uploaded / draft_card_imported / workspace_lane_changed / report_reviewed`；
- 时间线倒序，可按 action / actor 过滤；
- 点某条 `evidence_id` 的 **Timeline** 按钮，跳出该证据的小弹窗。

---

## Step 9. 生成 FinalPackage Markdown

切回 **📦 FinalPackage** 面板：

- `style`：`proposal_mvp`（13 章初稿）；
- `language`：`zh`；
- `include_low_confidence_refs`：关闭；
- `include_rejected_as_appendix`：关闭。

点击 **📝 生成报告**。

预期：

- 几秒后页面下方出现 Markdown 全文；
- 底部有 **引用清单表格**，列含：编号 / 类型 / 标题 / 来源 / 页码 / 解析 / 审核状态 / 验证 / 置信度 / Skill / 警告 / 链接；
- `coverage_score` 显示百分比（如 0.62）；若 < 0.5 顶部黄条警告。

---

## Step 10. 运行 ReportQuality

在 FinalPackage 面板下方点 **🧪 报告质量审核**。

预期：

- 8 维评分逐项显示（coverage / verification / provenance / skill_sources / contradictions / unsupported_claims / trace_consistency / format）；
- 顶部 `verdict`：PASS / WARN / FAIL；
- `defense_questions` 列出 2-5 条可能问到的答辩问题；
- `revision_checklist` 列出 3-8 条改进项。

如果 verdict 是 WARN / FAIL：演示用户回到 Step 7 移动更多证据到 `core / accepted`，再点 **🔁 重新生成报告**，重跑 ReportQuality。

---

## Step 11. 展示最终开题报告与修改清单

操作：

- 把 Markdown 复制到剪贴板（或下载 `.md`）；
- 把 `revision_checklist` 截图保存（演示可追踪的修改建议）。

收尾要点：

- 强调系统**不替代导师**：所有选题、收缩、实验方案都由学生 + 导师决定；
- 强调**可追溯**：每条引用都有 `evidence_id` 和 trace 时间线；
- 强调**不强升分**：pending + unverified 不进 supports，verification failed 不进 supports。

---

## 演示常见 Q&A

| 问题 | 简短回答 |
|---|---|
| LLM 没接能用吗？ | 能，heuristic fallback 兜底；只是某些题目 LLM 路径会显示降级提示。 |
| 资料 OCR 为什么不做？ | 明确边界（见 Scope_And_Compliance），避免误识别污染证据池。 |
| rejected 会不会出现在报告里？ | 不会，默认排除；可选 `include_rejected_as_appendix=True` 加进附录。 |
| 外部 API 失败怎么办？ | 显示降级结果，其他源继续；UI 红字标注失败源。 |
| 如何把 Demo 存为基线？ | 这是 Session 17 候选 —— 固化为回归基线数据。 |

---

## 演示后清理

```bash
# 停止服务
stop_all.bat

# 清理 .runtime（可选，会丢 trace / materials）
rm -rf .runtime/traces/* .runtime/materials/* .runtime/retrieval/*
```

---

## 演示项目的回归基线

Session 17 已把这两个 Demo 固化为可重复执行的回归基线：

```bash
# 后端基线 (YOLO + 高风险 MLLM, 共 15 项合同断言)
.venv/Scripts/python.exe -m pytest apps/api/tests/test_session17_demo_baseline.py -v

# 前端主路径 (YOLO + 高风险, 共 10 项)
.venv/Scripts/python.exe -m pytest apps/web/e2e/test_one_topic_session17_demo_baseline.py -v
```

基线文件位于 `docs/demo/baselines/`，详见该目录 README。

---

## 11.5 （补充）运行基线回归

```bash
# 仅基线
.venv/Scripts/python.exe -m pytest apps/api/tests/test_session17_demo_baseline.py -v

# Session 10-17 全量
.venv/Scripts/python.exe -m pytest \
  apps/api/tests/test_session10_verification.py \
  apps/api/tests/test_session11_trace_persistence.py \
  apps/api/tests/test_session12_report_quality.py \
  apps/api/tests/test_session13_skill_registry.py \
  apps/api/tests/test_session14_multi_source_retrieval.py \
  apps/api/tests/test_session15_material_card_intake.py \
  apps/api/tests/test_session17_demo_baseline.py -v
```

如果失败：检查 `verdict / 引用数 / coverage / 缺失证据` 是否仍在 `expected.json` 区间；如确认系统破坏，修复代码；如确认业务调整，按 [baselines/README.md](baselines/README.md) §4 更新基线。