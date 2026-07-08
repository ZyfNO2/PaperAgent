# PaperAgent Re1.3 Loop 6 — 自动种子选取测试报告

> 日期: 2026-07-05
> 执行者: Codely CLI (执行 AI)

## 测试内容

验证 citation_expander 自动从 verified_papers 中选取种子, 无需用户手动上传。

## 测试用例

| # | 测试 | 结果 | 说明 |
|---|---|---|---|
| 1 | `test_auto_seed_selection_basic` | ✅ PASS | 从 verified_papers 自动选取种子 |
| 2 | `test_auto_seed_has_relevance_score` | ✅ PASS | 种子有 relevance_score 字段 |
| 3 | `test_auto_seed_has_selection_reason` | ✅ PASS | 种子有 seed_selection_reason 字段 |
| 4 | `test_auto_seed_requires_identifier` | ✅ PASS | 无 paperId/DOI/arXiv ID 的论文被跳过 |
| 5 | `test_auto_seed_top1_is_highest_score` | ✅ PASS | 第一篇种子 relevance_score 最高 |
| 6 | `test_citation_expander_auto_selects_seeds` | ✅ PASS | 全节点自动选种+扩展 |

## 种子选取算法验证

```
评分公式:
  base = len(hit_keywords ∩ topic_keywords) × 2
  relation baseline/parallel → +3
  has paperId/DOI/arXiv ID → +2 (必须, 否则跳过)
  citation_count > 10 → +1
```

验证结果:
- ✅ 重合度最高的论文排在种子列表第一位
- ✅ 种子论文有 relevance_score 和 seed_selection_reason 字段
- ✅ 种子论文有 S2 paperId 或 DOI 或 arXiv ID
- ✅ 无标识符的论文被跳过, 取下一篇
- ✅ 引文扩展对种子论文做了 references + citations 获取
- ✅ 扩展论文经过 verify 后并入 verified_papers

## 测试结果

```
6 passed, 0 failed
```

## 结论

Loop 6 自动种子选取测试全部通过。种子完全由系统自动选取, 无需用户上传, 符合 SOP §P0-3 要求。
