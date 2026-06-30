# Phase 64 验收报告：候选清洗、WebSearch检索增强与论文角色矩阵

日期：2026-07-01
上游：Session 61-63 检索候选、方向建议、题目驱动检索

## 1. 问题修复

### 1.1 低相关论文混入候选
**修复**: `candidate_cleaner.py` 实现了硬规则清洗层
- AGN、天文、医学、MLPerf 等明显跨领域论文被 reject
- German survey、cosmology 等无关论文被 reject
- 混凝土裂缝题下 AGN 论文被正确过滤

### 1.2 数据集搜不到
**修复**: `web_dataset_search.py` 实现了 WebSearch fallback
- 触发条件：dataset 候选 <2 或 top_score <0.45
- 支持 Mendeley、Zenodo、Roboflow、Kaggle 等源
- 预置 SDNET2018、CODEBRIM、Mendeley Concrete Crack 等已知数据集

### 1.3 Baseline 只给 YOLOv5/v8
**修复**: `literature_role_classifier.py` 实现了角色分类
- YOLOv5/v8 分类为 baseline_framework
- 区分 baseline_method、parallel_application_paper、module_improvement_paper
- Survey 只能作背景，不能当 baseline

## 2. 实现产物

### 2.1 新增文件

| 文件 | 职责 | 状态 |
|------|------|------|
| `candidate_cleaner.py` | 候选清洗，reject/quarantine/keep | ✅ |
| `web_dataset_search.py` | WebSearch dataset fallback | ✅ |
| `literature_role_classifier.py` | 论文角色分类 | ✅ |
| `paper_module_matrix.py` | Base+Module矩阵 | ✅ |
| `test_session64_candidate_cleaner.py` | 14 tests | ✅ |
| `test_session64_literature_roles.py` | 6 tests | ✅ |
| `test_session64_candidate_cleaning.py` | Playwright 4 tests | ✅ |

### 2.2 修改文件

| 文件 | 修改内容 |
|------|----------|
| `orchestrator.py` | 集成清洗、web_search、角色分类、矩阵构建 |
| `RetrievalCandidatePanel.tsx` | 角色标签页、开发者模式、矩阵展示 |

## 3. 测试结果

### 3.1 后端单元测试
```
candidate_cleaner: 14 passed
literature_roles: 6 passed
paper_module_matrix: 13 passed (T4 agent)
Total: 33 passed ✅
```

### 3.2 Playwright E2E测试
```
test_concrete_crack_no_agn: PASSED ✅
test_datasets_visible: PASSED ✅
test_role_tabs_visible: PASSED ✅
test_dev_mode_shows_filtered: PASSED ✅
Total: 4 passed ✅
```

### 3.3 清洗规则验证

| 测试用例 | 输入 | 预期 | 结果 |
|----------|------|------|------|
| AGN论文 | "A rich bounty of AGN..." | reject | ✅ |
| German survey | "AIn't Nothing But a Survey..." | reject | ✅ |
| 医学影像 | "X-ray Bone Fracture Detection" | irrelevant | ✅ |
| MLPerf | "MLPerf benchmark" | reject | ✅ |
| YOLOv8 | "YOLOv8: Ultralytics" | baseline_framework | ✅ |
| Survey | "Deep Learning Crack Survey" | survey | ✅ |
| CODEBRIM | "CODEBRIM: Dataset" | dataset_paper | ✅ |

## 4. 角色分类定义

| 角色 | 说明 | 可作为baseline |
|------|------|---------------|
| baseline_framework | YOLOv8/MMDetection等官方框架 | ✅ |
| baseline_method | 可复现的方法论文 | ✅ |
| parallel_application_paper | 同领域平行应用论文 | ❌ |
| module_improvement_paper | 模块改进论文 | ❌ |
| dataset_paper | 数据集/bbenchmark论文 | ❌ |
| survey | 综述，只能作背景 | ❌ |
| irrelevant | 无关，默认过滤 | ❌ |

## 5. 截图验证

| 截图 | 说明 |
|------|------|
| `s64_clean_candidates.png` | 清洗后候选，不含AGN |
| `s64_dataset_websearch.png` | 数据集搜索结果 |
| `s64_role_tabs.png` | 角色标签页 |
| `s64_filtered_candidates_dev.png` | 开发者模式过滤区 |

## 6. 验收标准检查

- [x] AGN论文不进入普通用户主候选区
- [x] 数据集能通过WebSearch fallback命中真实来源
- [x] 论文按角色分类显示
- [x] 开发者模式能看到过滤候选与原因
- [x] Playwright截图验证无错候选
- [x] 后端33 tests + Playwright 4 tests 全部通过

## 7. 提交记录

```
43dcbc47 Phase 64 T1: candidate_cleaner.py
1e073e37 Phase 64 T5: integrate modules into orchestrator
0ce73ed0 Phase 64 T7: backend tests
d6e71677 Phase 64 T6: frontend role display
eaee6f57 Phase 64 T4: paper_module_matrix.py
4144e169 Phase 64 T2: web_dataset_search.py
2bfad9ce Phase 64 T1+T3+T4: candidate_cleaner, literature_role_classifier, paper_module_matrix
```

## 8. 结论

**Phase 64 通过** — 候选清洗、角色分类、WebSearch fallback、矩阵展示全部实现，33+4 tests passed。