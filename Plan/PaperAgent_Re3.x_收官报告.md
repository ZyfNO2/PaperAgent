# PaperAgent Re3.x 系列收官报告

> **范围**: Re3.0 → Re3.8（共 9 个版本）
> **日期**: 2026-07-08
> **总结**: 从 React search agent 原型到 50 篇回归验证的完整演进

---

## 1. 版本总览

| 版本 | 核心交付 | P0 通过率 | 关键指标 |
|---|---|---|---|
| Re3.0 | React search agent + reflection strategy + recursion_limit=100 | — | 搜索步数 3→8 |
| Re3.1 | User paper upload + arXiv fulltext + Crossref filtering | — | 新增 3 端点 |
| Re3.2 | verify.py imports + CORE/DataCite adapters + 8 tools | 6/6 | 7→8 搜索工具 |
| Re3.3 | #statusBar + BLOCK 循环 + 重复边 + 6 个展示区 + 42 张截图 | 12/13 | 前端展示完整 |
| Re3.4 | final_rec e2e + 60 legacy 归档 + retrieve.py 删除 + 6-case 回归 | 15/17 | R34-002: 0→10 papers |
| Re3.5 | 时间线调试器 + feasibility prompt 增强 + .ruff.toml | 8/17 | ruff 466→95 |
| Re3.6 | state_keys 19 文件 + F821/F822 归零 + dataset prompt | 12/12 | state_keys 96% |
| Re3.7 | 硬编码 6 项清除 + prompt 注入修复 + OUTPUT CONTRACT | 8/8 Critical | ruff 95→64 |
| Re3.8 | 收尾清理 + S1-S7 修复 + 12 篇 PASS + 50 篇扩展 | 12/12 | 6 种 feas score |

---

## 2. 核心能力建设时间线

### 2.1 搜索能力 (Re3.0 → Re3.2)

```
Re3.0: React search agent (think→call→observe, 8 steps)
  ↓
Re3.2: 7 adapters → 8 tools (+ CORE + DataCite + HuggingFace)
  ↓
Re3.5: search_agent state_keys 19 文件覆盖
  ↓
Re3.7: 硬编码清除 (domain_map, CN_EN_MAP, dataset whitelist)
  ↓
Re3.8: 防重复查询 + 强制英文 + dataset_extractor 扩大范围
```

### 2.2 评估能力 (Re3.4 → Re3.8)

```
Re3.4: feasibility_report + review_report e2e 验证
  ↓
Re3.5: feasibility prompt 域风险增强
  ↓
Re3.6: dataset_extractor prompt + known_dataset_names
  ↓
Re3.8: feasibility 精确锚点评分 + devils_advocate 三档 heuristic
```

### 2.3 可观测性 (Re3.5 → Re3.6)

```
Re3.5: 时间线调试器 (draggable slider + node detail panel)
  ↓
Re3.6: state_keys 全节点覆盖 (19 文件, 96% 非空率)
  ↓
Re3.8: citation_expander state_keys 补全
```

### 2.4 代码质量 (Re3.5 → Re3.8)

```
Re3.5: .ruff.toml 配置, ruff 466→95
  ↓
Re3.6: F821/F822 归零, ruff 95→94
  ↓
Re3.7: BaseException 清除 (7→0), prompt 注入修复, ruff 94→64
  ↓
Re3.8: BaseException 清除 (4→0), ponytail 注释删除
```

---

## 3. 回归测试演进

| 版本 | 测试篇数 | PASS | SKIP | 通过率 |
|---|---|---|---|---|
| Re3.2 | 3 | 3 | 0 | 100% |
| Re3.4 | 6 | 5 | 1 | 83% |
| Re3.5 | 8 | 5 | 3 | 63% |
| Re3.6 | 12 | 5 | 7 | 42% (SKIP) |
| Re3.8 | 12 | 12 | 0 | **100%** |
| Re3.8 (50篇) | 50 | TBD | TBD | ≥80% 目标 |

---

## 4. Re3.8 系统性问题修复成效

### 4.1 S1: feasibility 评分聚集

| 指标 | Re3.7 | Re3.8 |
|---|---|---|
| 12 篇 score 种类 | 1 (全 75) | 6 (45/55/75/78/82/85) |
| 评分一致性 | R36-015 14篇得45 vs R34-092 5篇得75 | 按baseline/repo/dataset差异化 |

### 4.2 S6: search_agent 查询重复

| 指标 | Re3.7 | Re3.8 |
|---|---|---|
| 同一 tool+query 重复 | 7-8 次 | 去重检查 + fallback |

### 4.3 S7: devils_advocate verdict

| 指标 | Re3.7 | Re3.8 |
|---|---|---|
| heuristic verdict | ACCEPT (有 baseline 即 ACCEPT) | 3 档 (ACCEPT/MINOR_REVISION/BLOCK) |

---

## 5. 推迟至 Re4.0 的系统性 TODO

| TODO | 首次提出 | 推迟版本数 | Re4.0 计划 |
|---|---|---|---|
| 100 篇全量回归 | Re3.1 | 8 | 50 篇通过后扩展 |
| PubMed E-utilities | Re3.1 | 8 | 医学领域覆盖 |
| LangSmith 集成 | Re3.0 | 8 | 可观测性 |
| React+Vite 前端 | Re3.1 | 8 | index.html 800+ 行 |
| research_agent.py 拆分 | Re3.5 | 4 | 2821 行 → 多模块 |
| StageContract 机制 | Re3.5 | 4 | 节点间契约 |
| search_agent think→call→observe 明细 | Re3.5 | 4 | trace 细化 |
| 时间线键盘导航 | Re3.5 | 4 | a11y |
| S3 仓库覆盖率不均 | Re3.8 | 0 | search_agent 行为优化 |
| S4 baseline/parallel 分类 | Re3.8 | 0 | prompt 级优化 |
| S2 API 退避策略 | Re3.8 | 0 | 架构级改造 |

---

## 6. Re4.0 方向建议

| 方向 | 内容 | 优先级 | 理由 |
|---|---|---|---|
| React+Vite 前端 | 替换 vanilla JS | P0 | index.html 已 800+ 行，维护困难 |
| research_agent.py 拆分 | 2821 行 → 多模块 | P0 | 组织债影响可维护性 |
| LangSmith 集成 | 可观测性 | P1 | 50 篇回归需要调试工具 |
| PubMed / Unpaywall | 搜索源补强 | P1 | 医学领域覆盖不足 |
| StageContract 机制 | 架构级 | P1 | 节点间契约保证 |
| S3 仓库覆盖优化 | search_agent | P2 | 非核心功能 |
| S4 分类优化 | baseline_classifier | P2 | prompt 级 |
| 100 篇全量回归 | 测试扩展 | P2 | 50 篇通过后按需 |

---

## 7. Re3.x 系列技术债总结

### 已清偿

| 债务 | 清偿版本 | 方式 |
|---|---|---|
| 硬编码 domain_map | Re3.7 | 删除，改 LLM 推断 |
| 硬编码 CN→EN 翻译 | Re3.7 | 删除，改 prompt 指令 |
| 短关键词过滤 (len<4) | Re3.7 | 改为 len<2 |
| Dataset whitelist 注入 | Re3.7 | 删除，改 LLM 自主推断 |
| BaseException 滥用 | Re3.7+Re3.8 | 全部 → Exception |
| F821/F822 undefined | Re3.6 | 逐个修复归零 |
| retrieve.py 死代码 | Re3.4 | 296 行删除 |
| recursion_limit 默认 | Re3.0 | 25→100 |
| state_keys 空节点 | Re3.6+Re3.8 | 19 文件 + citation_expander |
| feasibility 评分聚集 | Re3.8 | 精确锚点评分 |
| search_agent 查询重复 | Re3.8 | _llm_decide 去重 |

### 未清偿（推迟 Re4.0+）

| 债务 | 原因 | 影响 |
|---|---|---|
| index.html 单文件 800+ 行 | 需 React+Vite 迁移 | 维护困难 |
| research_agent.py 2821 行 | 需架构级拆分 | 组织债 |
| S2 API 429 无退避 | 需架构级改造 | citation_expander 受限 |
| S3 仓库覆盖不均 | search_agent 行为 | GitHub 对理论话题失效 |
| S4 分类不均衡 | LLM 机械匹配 | baseline/parallel 偏差 |

---

## 8. 结论

Re3.x 系列（Re3.0→Re3.8）历时 9 个版本，完成了：

1. **搜索能力**：从固定检索到 8 工具 React agent + reflection 策略
2. **评估能力**：从无到 feasibility 5 档精确评分 + devils_advocate 3 档 heuristic
3. **可观测性**：时间线调试器 + state_keys 96% 覆盖 + trace 持久化
4. **代码质量**：ruff 466→64，BaseException 全清除，硬编码全清除
5. **回归验证**：12/12 PASS（100%），50 篇扩展进行中

**Re3.x 系列收官条件**：50 篇 PASS 率 ≥ 80% 后正式收官，进入 Re4.0。
