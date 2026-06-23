# PaperAgent Session 10 SOP：多源轻验证与 URL Verified

> 日期：2026-06-19  
> 阶段定位：承接 Session 09 的双栏证据工作台与 Agent Card Intake，把“待确认卡片”升级为“可轻量验证的证据卡片”。  
> 本轮目标：对论文、数据集、GitHub/工程、普通网页卡片做轻量来源验证，落地 `url_verified`、`verification_status`、`verification_confidence`，并接入 EvidenceRef 与 Markdown 报告。  
> 重要边界：本阶段只做 URL / 元数据级轻验证，不做全文下载、不做复杂爬虫、不绕过付费数据库、不做 PDF RAG。

---

## 1. 当前状态判断

根据 `Plan/reports/Session_09_WorkspaceBoard_CardIntake_验收报告.md`，当前已经完成：

- 证据工作台双栏化：`user_preferred / system_found / selected / rejected`；
- Agent Card Intake 最小入口：URL / 文字生成 pending EvidenceCard；
- GitHub / arXiv / HuggingFace / Kaggle URL 基础类型识别；
- `workspace_lane` 已接入 EvidenceRef priority；
- pending / assistant_intake 默认不能直接 supports；
- Markdown 报告仍可正常导出。

当前主要缺口：

```text
Agent Card Intake 生成的卡片已经能进入工作台，
但多数卡片仍只是“根据 URL 和 hint 生成的候选”，
还没有明确验证来源是否可访问、元数据是否可信、链接是否与卡片类型匹配。
```

因此 Session 10 只补一层：

```text
轻验证
+ 置信度
+ warnings
+ EvidenceRef / Markdown 联动
```

---

## 2. Session 10 目标

Session 10 名称：

```text
多源轻验证与 URL Verified
```

目标：

```text
URL / 卡片
→ 轻量验证
→ 更新 verified 字段
→ 调整 confidence / warnings
→ 影响 EvidenceRef priority
→ 影响 Markdown supports / warning / 待补证据
```

完成后，用户应能：

```text
1. 对单张证据卡片点击“验证来源”；
2. 对整个项目点击“批量验证证据”；
3. 在卡片上看到 verified / unverified / failed / skipped；
4. 看到验证置信度和 warning；
5. Markdown 报告中对未验证证据自动标注；
6. 未验证 assistant_intake 证据不能直接支撑关键结论。
```

---

## 3. 本阶段不做什么

| 不做 | 原因 |
|---|---|
| 不下载论文全文 | 只验证 URL 和元数据，全文 RAG 后置 |
| 不解析 PDF | PDF/图片卡片化属于 Session 15 |
| 不深爬网页 | 防止复杂度和合规风险 |
| 不绕过 CNKI/万方/维普权限 | 只支持用户手动导入或公开链接 |
| 不强依赖外部 API key | GitHub/HF/Kaggle 可先做无 key 或降级验证 |
| 不做大规模多源检索 | Session 14 再做主动检索扩展 |
| 不让 LLM 判断链接真伪 | 验证以规则/HTTP/公开 API 元数据为主，LLM 只可解释 warnings |

---

## 4. 数据结构设计

### 4.1 EvidenceItem 新增字段

建议在 `apps/api/app/schemas_evidence.py` 的 `EvidenceItem` 增加：

```python
url_verified: bool | None = None

verification_status: Literal[
    "unverified",
    "verified",
    "failed",
    "partial",
    "skipped"
] = "unverified"

verification_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

verification_source: Literal[
    "http",
    "arxiv",
    "openalex",
    "github",
    "huggingface",
    "kaggle",
    "manual",
    "none"
] = "none"

verification_checked_at: datetime | None = None
verification_warnings: list[str] = Field(default_factory=list)
verification_metadata: dict = Field(default_factory=dict)
```

字段说明：

| 字段 | 作用 |
|---|---|
| `url_verified` | 是否通过轻验证 |
| `verification_status` | 验证状态 |
| `verification_confidence` | 验证置信度 |
| `verification_source` | 使用的验证器 |
| `verification_checked_at` | 验证时间 |
| `verification_warnings` | 验证风险 |
| `verification_metadata` | 保存轻量元数据，例如 title/year/repo/full_name/license |

---

### 4.2 VerificationResult 模型

建议新增：

```python
class VerificationResult(BaseModel):
    evidence_id: str
    evidence_type: str
    ok: bool
    url_verified: bool
    verification_status: Literal["verified", "failed", "partial", "skipped"]
    verification_confidence: float
    verification_source: str
    normalized_url: str | None = None
    metadata: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    checked_at: str
```

批量响应：

```python
class VerificationSummary(BaseModel):
    project_id: str
    total: int
    verified: int
    partial: int
    failed: int
    skipped: int
    avg_confidence: float
    high_risk_items: list[VerificationResult]
```

---

## 5. 验证器设计

### 5.1 验证器总入口

新增服务：

```text
apps/api/app/services/verification.py
```

核心函数：

```python
def verify_evidence_item(item: EvidenceItem) -> VerificationResult:
    verifier = choose_verifier(item)
    return verifier.verify(item)


def verify_project_evidence(project_id: str, scope: str = "all") -> VerificationSummary:
    items = evidence.get_pool_items(project_id)
    results = [verify_evidence_item(item) for item in filtered_items]
    update_items(results)
    return summarize(results)
```

---

### 5.2 arXiv 验证

触发：

```text
url contains arxiv.org/abs
or arxiv_id exists
```

验证内容：

```text
arxiv_id 是否可解析；
URL 是否规范；
标题是否能从已有 item / URL / arXiv API 匹配；
年份是否合理；
source 是否标记 arxiv。
```

MVP 可先做：

```text
URL 规则验证 + arxiv_id 提取 + HTTP HEAD/GET 轻请求；
如网络不可用，保留 partial + warning。
```

输出规则：

```text
verified: arxiv_id 可解析且 URL 格式正确；
partial: URL 格式正确但无法访问 API；
failed: URL 格式错误或明显不是 arXiv。
```

---

### 5.3 OpenAlex 验证

触发：

```text
doi exists
or url contains openalex.org
or paper title 有 DOI-like 元数据
```

验证内容：

```text
DOI / OpenAlex ID 格式；
title/year/venue 是否能轻量补全；
OpenAlex 来源只作为公开元数据验证，不作为论文全文。
```

边界：

```text
没有网络或 API 失败时不阻断；
结果标 partial；
不把 OpenAlex 查不到直接判定论文不存在。
```

参考：

```text
ResearchMCP：OpenAlex paper fetcher 分层
```

---

### 5.4 GitHub 验证

触发：

```text
url contains github.com/{owner}/{repo}
or evidence_type=repo
```

验证内容：

```text
owner/repo 是否可解析；
README 是否可能存在；
license 是否可见；
默认分支是否可访问；
repo URL 是否不是 issue/wiki/blob 子页；
是否能轻量识别 train/eval/requirements 等路径。
```

MVP 可先做：

```text
GitHub URL canonical normalize；
HTTP HEAD/GET repo 页面；
无需 GitHub token；
无法查 API 时保留 warning。
```

输出 warning 示例：

```text
未验证 train/eval 脚本；
未验证 license；
GitHub 页面可访问但未验证可复现性；
```

---

### 5.5 HuggingFace / Kaggle 数据集验证

触发：

```text
url contains huggingface.co/datasets
url contains kaggle.com/datasets
evidence_type=dataset and url exists
```

验证内容：

```text
URL 是否符合数据集页面；
dataset slug 是否可解析；
是否能识别来源平台；
是否有 license/下载/标注字段；
```

MVP：

```text
URL 格式 + 页面可访问轻检查；
不要求 API key；
不下载数据。
```

warning 示例：

```text
未验证下载权限；
未验证 license；
未验证标注类型；
可能需要注册或手动确认；
```

参考：

```text
DatasetResearch：gated check_exist
```

---

### 5.6 普通 URL / 文本卡片验证

触发：

```text
普通网页 URL
纯文本描述
note evidence
```

规则：

```text
普通 URL 可做 HTTP 轻检查；
纯文本无法 URL 验证，status=skipped；
用户手动确认可设置 verification_source=manual；
```

---

## 6. API 设计

### 6.1 验证单条证据

```text
POST /api/v1/one-topic/{project_id}/evidence/{evidence_id}/verify
```

输出：

```json
{
  "evidence_id": "repo_xxx",
  "ok": true,
  "url_verified": true,
  "verification_status": "partial",
  "verification_confidence": 0.62,
  "verification_source": "github",
  "warnings": ["未验证 train/eval 脚本"],
  "metadata": {
    "owner": "ultralytics",
    "repo": "ultralytics"
  }
}
```

---

### 6.2 批量验证项目证据

```text
POST /api/v1/one-topic/{project_id}/evidence/verify
```

请求：

```json
{
  "scope": "all",
  "include_rejected": false,
  "include_pending": true,
  "refresh": false
}
```

scope 可选：

```text
all
paper
dataset
repo
assistant_intake
user_preferred
selected
```

---

### 6.3 获取验证摘要

```text
GET /api/v1/one-topic/{project_id}/evidence/verification-summary
```

输出：

```json
{
  "project_id": "ot_xxx",
  "total": 12,
  "verified": 5,
  "partial": 4,
  "failed": 1,
  "skipped": 2,
  "avg_confidence": 0.68,
  "high_risk_items": [
    {
      "evidence_id": "dataset_xxx",
      "warnings": ["未验证 license", "未验证下载权限"]
    }
  ]
}
```

---

### 6.4 手动确认验证

```text
PATCH /api/v1/one-topic/{project_id}/evidence/{evidence_id}/verification
```

请求：

```json
{
  "verification_status": "verified",
  "verification_confidence": 0.90,
  "verification_source": "manual",
  "reason": "用户已打开网页确认可访问"
}
```

要求：

```text
写入 Trace；
不自动改 review_status；
但可影响 EvidenceRef priority。
```

---

## 7. EvidenceRef 联动

### 7.1 priority 更新

当前 EvidenceRef priority 已有：

```text
review_weight
score
type_weight
recency
url_verified
workspace_lane bonus
```

Session 10 调整为：

```text
ref_priority =
  0.32 × review_weight
+ 0.22 × evidence_score
+ 0.13 × type_weight
+ 0.08 × recency_or_activity
+ 0.15 × verification_confidence
+ 0.10 × workspace_lane_bonus
```

硬规则：

```text
verification_status=failed 不得作为 supports；
assistant_intake + unverified 不得作为 supports；
manual + user_preferred + unverified 可以作为 background/warns，但不支撑关键结论；
selected/core + partial 可以 supports，但 Markdown 需显示 warning；
```

---

### 7.2 EvidenceRef 字段补齐

`EvidenceRef` 当前已有：

```text
url_verified
```

建议补充：

```python
verification_status: str | None = None
verification_confidence: float | None = None
verification_warnings: list[str] = []
```

用于前端引用卡和 Markdown 引用清单展示。

---

## 8. FinalPackage / Markdown 联动

Markdown 证据引用清单增加：

```text
验证状态
验证置信度
验证警告
```

示例：

```markdown
| 编号 | 类型 | 标题 | 审核状态 | 验证 | 置信度 | 警告 | 链接 |
|---|---|---|---|---|---:|---|---|
| R1 | repo | ultralytics/ultralytics | core | partial | 0.62 | 未验证 train/eval 脚本 | https://... |
```

报告顶部增加：

```text
证据验证率：verified + partial / total
```

如果关键 supports 中存在 `partial`：

```text
在“风险预案”和“待补证据与修改清单”中列出。
```

如果关键 supports 中存在 `failed`：

```text
构建 FinalPackage 时应降级为 warning 或 unsupported_claim，不得正向引用。
```

---

## 9. 前端设计

### 9.1 卡片验证状态

每张 EvidenceCard 显示：

```text
验证：verified / partial / failed / unverified / skipped
置信度：0.72
警告：license 未确认
按钮：验证来源
```

视觉建议：

```text
verified: 绿色
partial: 黄色
failed: 红色
unverified: 灰色
skipped: 灰色
```

---

### 9.2 批量验证按钮

工作台顶部增加：

```text
验证全部证据
只验证用户栏
只验证 Agent 导入
```

点击后显示：

```text
验证完成：verified 5 / partial 4 / failed 1 / skipped 2
```

---

### 9.3 Agent Intake 后自动提示

当 `/cards/intake` 生成 pending 卡片后：

```text
如果是 URL，前端提示“建议先验证来源”；
可以提供按钮“生成并验证”。
```

MVP 可以先做两步：

```text
生成卡片
→ 用户点击验证来源
```

---

## 10. 测试要求

### 10.1 后端测试

新增：

```text
apps/api/tests/test_session10_verification.py
```

必须覆盖：

```text
1. arXiv URL 能提取 arxiv_id 并 verified/partial
2. GitHub URL 能提取 owner/repo
3. HuggingFace dataset URL 能识别 dataset
4. Kaggle dataset URL 能识别 dataset
5. 普通文本 note verification_status=skipped
6. 批量 verify 返回 summary
7. failed verification 不进入 supports
8. assistant_intake + unverified 不进入 supports
9. manual verification 能写入 Trace
10. verification_confidence 影响 EvidenceRef priority
11. Markdown citation list 显示验证状态
12. verification 不改变 review_status
```

---

### 10.2 前端 Playwright

新增：

```text
apps/web/e2e/test_one_topic_session10_verification.py
```

必须覆盖：

```text
1. 证据卡片显示验证状态
2. 单张卡片点击“验证来源”后状态更新
3. 批量验证按钮显示 summary
4. GitHub intake 卡片验证后显示 owner/repo metadata 或 warning
5. failed/unverified assistant card 不能出现在报告 supports
6. Markdown 引用清单显示验证状态
7. partial 证据在报告风险预案中出现
8. 手动确认验证按钮可用
```

---

### 10.3 回归测试

必须继续通过：

```text
Session 07 EvidenceRef
Session 08 FinalPackage Markdown
Session 09 WorkspaceBoard / CardIntake
OneTopic happy path
```

网络相关测试建议使用 mock：

```text
真实网络验证作为 smoke；
CI / 常规测试以 URL parser + fake response 为主。
```

---

## 11. 验收标准

Session 10 通过条件：

```text
1. EvidenceItem 有 verification 字段；
2. 可以验证单条 evidence；
3. 可以批量验证 project evidence；
4. arXiv / GitHub / HuggingFace / Kaggle URL 有轻量识别和验证结果；
5. 普通文本/不可验证内容能 skipped，不误判 verified；
6. verification_status=failed 不进入 supports；
7. assistant_intake + unverified 不进入 supports；
8. verification_confidence 影响 EvidenceRef priority；
9. Markdown 证据清单显示验证状态；
10. 前端卡片显示验证状态和 warnings；
11. 新增后端测试通过；
12. 新增 Playwright 测试通过。
```

最低可接受 MVP：

```text
verification 字段
+ 单条 verify API
+ 批量 verify API
+ URL parser for arXiv/GitHub/HF/Kaggle
+ EvidenceRef priority 联动
+ Markdown citation 显示 verified/partial/failed
```

---

## 12. 完工报告要求

完成后新增：

```text
Plan/reports/Session_10_Verification_URLVerified_验收报告.md
```

报告必须包含：

```text
1. 本阶段范围
2. 新增字段
3. 新增 API
4. 验证器规则
5. EvidenceRef 联动
6. Markdown 联动
7. 前端 UI 变化
8. 后端测试结果
9. Playwright 测试结果
10. 网络测试 / mock 测试边界
11. 未做项
12. 下一 Session 建议
```

---

## 13. 下一 Session 预告

Session 11 建议：

```text
Trace 持久化与操作回放
```

原因：

```text
Session 09/10 后，用户对证据的移动、导入、验证、确认、拒绝动作越来越多；
如果 Trace 仍然 in-memory，重启后无法回放决策过程；
开题报告也无法解释“为什么这条证据被采用/排除”。
```

Session 11 应重点：

```text
Trace jsonl 持久化；
project 操作历史；
报告附关键决策记录；
用户可查看证据从 intake → verify → selected → report 的路径。
```

