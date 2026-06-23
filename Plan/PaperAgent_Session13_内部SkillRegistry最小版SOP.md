# PaperAgent Session 13 SOP：内部 Skill Registry 最小版

> 日期：2026-06-19  
> 阶段定位：在证据工作台、验证、Trace 和报告复核都具备后，把已有内部科研 Skill 从“文档散落”整理为可注册、可索引、可引用的内部能力层。  
> 本轮目标：建立最小 Skill Registry，不下载第三方 Skill，不执行外部代码，只管理本项目已适配的内部 Skill。

---

## 1. 当前状态判断

当前已有内部 Skill：

```text
skills/research/paper-card/SKILL.md
skills/dataset/dataset-validation/SKILL.md
skills/engineering/github-baseline/SKILL.md
skills/evidence/evidence-ledger/SKILL.md
```

这些文档已经描述了证据工作台核心能力，但还缺少：

```text
统一 metadata；
统一 input/output schema；
安全状态；
调用位置索引；
测试任务；
前端/报告中引用 skill 来源。
```

---

## 2. Session 13 目标

Session 13 名称：

```text
内部 Skill Registry 最小版
```

目标：

```text
SKILL.md
→ SkillMetadata
→ SkillRegistry
→ API 查询
→ 工作台/报告可显示“由哪个 skill 支撑”
```

完成后：

```text
1. 系统能列出内部 skill；
2. 每个 skill 有 category / version / status / risk_level；
3. 每个 skill 有 input/output schema 描述；
4. EvidenceRef / ReportQuality / FinalPackage 可记录 skill 来源；
5. 不引入第三方未审查代码。
```

---

## 3. 本阶段不做什么

| 不做 | 原因 |
|---|---|
| 不下载第三方 Skill | 安全审查未做 |
| 不执行 Skill 内 shell 命令 | Registry 只做管理层 |
| 不做 Marketplace | 后续再考虑 |
| 不做自动安装 | 本地内置优先 |
| 不让 skill 绕过 EvidenceRef | 所有输出仍必须绑定 evidence_id |

---

## 4. SkillMetadata 模型

建议新增：

```python
class SkillMetadata(BaseModel):
    name: str
    category: Literal["research", "dataset", "engineering", "evidence", "topic", "writing", "defense"]
    version: str = "0.1.0"
    path: str
    description: str
    status: Literal["candidate", "reviewed", "adapted", "enabled", "disabled", "deprecated"]
    risk_level: Literal["low", "medium", "high"]
    input_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)
    requires_tools: list[str] = []
    forbidden_actions: list[str] = []
    used_by: list[str] = []
```

Registry 响应：

```python
class SkillRegistryResponse(BaseModel):
    skills: list[SkillMetadata]
    enabled_count: int
    disabled_count: int
    high_risk_count: int
```

---

## 5. Registry 来源

MVP 不需要解析复杂 frontmatter，可先用一个本地 manifest：

```text
skills/registry.json
```

示例：

```json
[
  {
    "name": "paper-card",
    "category": "research",
    "path": "skills/research/paper-card/SKILL.md",
    "status": "enabled",
    "risk_level": "low",
    "used_by": ["card_intake", "evidence_scoring", "final_package"]
  }
]
```

后续再支持自动扫描 `SKILL.md` frontmatter。

---

## 6. API 设计

### 6.1 列出 Skill

```text
GET /api/v1/skills
```

### 6.2 获取单个 Skill

```text
GET /api/v1/skills/{name}
```

返回 metadata + SKILL.md 摘要。

### 6.3 Skill 健康检查

```text
GET /api/v1/skills/health
```

检查：

```text
path 是否存在；
status 是否 enabled；
risk_level 是否缺失；
input/output schema 是否缺失；
```

---

## 7. 与现有流程联动

### 7.1 EvidenceItem

可选新增：

```python
created_by_skill: str | None = None
scored_by_skill: str | None = None
validated_by_skill: str | None = None
```

### 7.2 EvidenceRef

可选新增：

```python
skill_sources: list[str] = []
```

### 7.3 FinalPackage / ReportQuality

报告中可以显示：

```text
本报告使用内部 Skill：paper-card、dataset-validation、github-baseline、evidence-ledger。
```

注意：

```text
Skill 只能说明生成/检查来源，不能替代 EvidenceRef。
```

---

## 8. 安全规则

每个 enabled skill 必须声明：

```text
risk_level；
forbidden_actions；
requires_tools；
status；
```

默认禁止：

```text
shell 执行；
读写工作区外文件；
上传用户文件；
调用未知外部 API；
自动安装依赖；
绕过证据审核；
生成不存在的引用。
```

---

## 9. 前端设计

新增轻量区块：

```text
内部科研 Skill
├── enabled skill 数量
├── paper-card
├── dataset-validation
├── github-baseline
└── evidence-ledger
```

可放在设置/调试面板，不必主流程突出。

每个 skill 展示：

```text
名称；
分类；
状态；
风险等级；
用途；
```

---

## 10. 测试要求

### 10.1 后端测试

新增：

```text
apps/api/tests/test_session13_skill_registry.py
```

覆盖：

```text
1. registry 能列出 4 个内部 skill
2. 每个 path 存在
3. 每个 skill 有 status 和 risk_level
4. GET /skills 返回 enabled_count
5. GET /skills/{name} 返回单个 metadata
6. health 能发现缺失字段
7. high risk skill 默认不能 enabled
8. EvidenceItem 可记录 created_by_skill
9. FinalPackage 可显示 skill_sources
10. Registry 不执行任何外部命令
```

### 10.2 Playwright

新增：

```text
apps/web/e2e/test_one_topic_session13_skill_registry.py
```

覆盖：

```text
1. 页面能看到内部 Skill 区块
2. 显示 4 个 skill
3. 显示 enabled / risk_level
4. 点击 skill 可展开用途
```

---

## 11. 验收标准

通过条件：

```text
1. 存在 skills/registry.json 或等价 registry；
2. API 能列出内部 skill；
3. 4 个现有 skill 均被注册；
4. skill 有 status / risk_level / used_by；
5. Registry health 可运行；
6. 不执行第三方代码；
7. Evidence/Report 可记录 skill 来源；
8. 后端测试通过；
9. Playwright 测试通过。
```

---

## 12. 完工报告要求

完成后新增：

```text
Plan/reports/Session_13_SkillRegistry_验收报告.md
```

报告包含：

```text
范围；
registry manifest；
新增 API；
已注册 skill；
安全规则；
流程联动；
测试结果；
未做项；
下一 Session 建议。
```

---

## 13. 下一 Session 预告

Session 14：多源检索增强。

理由：

```text
有了证据工作台、验证、Trace、质量检查和 Skill Registry 后，
再扩展 OpenAlex / Semantic Scholar / GitHub / HuggingFace 主动检索会更稳，
因为候选证据可以直接进入 Card Intake、Verification、EvidenceRef 和 ReportQuality 链路。
```
