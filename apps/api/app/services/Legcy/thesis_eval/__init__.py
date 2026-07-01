"""Session 51: 工科学位论文题录可行性评估模块.

8 文件 (SOP §6):
- crawler.py          URL → 题录页 HTML → title/year/abstract_snippet (三态降级)
- parser.py           HTML 解析 + 启发式字段抽取
- need_extractor.py   题名+摘要 → 9 标签多标签 (heuristic + LLM fallback)
- difficulty_scorer.py 难度/周期/repeatability/feasibility (映射 RealityCheck 资源四层)
- report_builder.py   区分 4 类信息的评估报告 (题录事实/模型推断/未验证/用户建议)
- evaluator.py        4 任务指标计算 (URL保真/标签F1/难度/报告质量)
- eval_pipeline.py    跑测试集 → 聚合 → baseline 对比 → 回归警告
- baseline.py         baseline 存读

核心原则 (SOP §1):
- 题录链接是事实, 必须 URL verified, 不许替换伪造.
- 网络抓取失败必须降级为题录级证据, 绝不编造全文/摘要/作者结论.
- LLM 路径必须配 heuristic fallback, 不许让 LLM 挂掉服务.
- H100 不是默认需求; 真正风险是数据和硬件.
"""

from __future__ import annotations

from .crawler import crawl_thesis_record
from .difficulty_scorer import score_difficulty
from .eval_pipeline import run_thesis_eval
from .evaluator import compute_task_metrics, aggregate_metrics
from .need_extractor import extract_experiment_needs
from .parser import parse_cnki_html
from .report_builder import build_assessment_report
from .baseline import load_baseline, save_baseline, diff_against_baseline

__all__ = [
    "crawl_thesis_record",
    "parse_cnki_html",
    "extract_experiment_needs",
    "score_difficulty",
    "build_assessment_report",
    "compute_task_metrics",
    "aggregate_metrics",
    "run_thesis_eval",
    "load_baseline",
    "save_baseline",
    "diff_against_baseline",
]
