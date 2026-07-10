"""Re7.2 Cross-domain verification — 10 fixed test cases."""
from __future__ import annotations

from pydantic import BaseModel


class CrossDomainCase(BaseModel):
    case_id: str
    topic: str
    domain: str
    expected_verdict: str  # GO | CONDITIONAL | RISKY | STOP | PIVOT


CROSS_DOMAIN_CASES: list[CrossDomainCase] = [
    CrossDomainCase(
        case_id="XD-01",
        topic="基于视觉 Transformer 的钢材表面缺陷检测",
        domain="工业视觉",
        expected_verdict="GO",
    ),
    CrossDomainCase(
        case_id="XD-02",
        topic="面向无人机遥感的小目标飞机检测轻量化方法",
        domain="遥感视觉",
        expected_verdict="CONDITIONAL",
    ),
    CrossDomainCase(
        case_id="XD-03",
        topic="基于水声信号的船舶类型识别与跨域泛化",
        domain="声学",
        expected_verdict="CONDITIONAL",
    ),
    CrossDomainCase(
        case_id="XD-04",
        topic="医学影像分割模型在跨医院数据上的可信评估",
        domain="医学 AI",
        expected_verdict="RISKY",
    ),
    CrossDomainCase(
        case_id="XD-05",
        topic="面向法律文本的中文长文档事实核验",
        domain="NLP",
        expected_verdict="RISKY",
    ),
    CrossDomainCase(
        case_id="XD-06",
        topic="基于时序传感器的锂电池 SOH 预测",
        domain="能源时序",
        expected_verdict="GO",
    ),
    CrossDomainCase(
        case_id="XD-07",
        topic="桥梁裂缝图像检测与三维定位联合研究",
        domain="结构工程",
        expected_verdict="CONDITIONAL",
    ),
    CrossDomainCase(
        case_id="XD-08",
        topic="面向移动机器人的室内语义建图与避障",
        domain="机器人",
        expected_verdict="RISKY",
    ),
    CrossDomainCase(
        case_id="XD-09",
        topic="利用公开转录组数据预测罕见病药物反应",
        domain="生物信息",
        expected_verdict="STOP",
    ),
    CrossDomainCase(
        case_id="XD-10",
        topic="基于大语言模型的高校心理咨询辅助问答",
        domain="高风险对话",
        expected_verdict="STOP",
    ),
]

VERIFICATION_RUBRIC = {
    "P0": [
        "no fabricated papers, datasets, repos, experiments, or citations",
        "needs_evidence / PIVOT / STOP when no evidence",
        "all conclusions retain evidence ID and provider/fallback trace",
    ],
    "P1": [
        "topic atoms correctly cover object/method/task for 8/10",
        "8/10 return at least one locatable, topic-relevant baseline",
        "8/10 final GO/CONDITIONAL/PIVOT/STOP matches dual-human rubric",
        "high-risk XD-04/05/09/10 must explicitly show risks",
        "zero invalid queries, empty repairs, empty expansion verifies",
        "cross-model core verdict agreement >= 70%",
    ],
}

REGRESSION_CHECKLIST = [
    "empty targeted_repair generates zero queries",
    "empty citation_expander skips verify",
    "heuristic CN→EN dictionary fallback active",
    "keyword translation enforced",
    "relevance interception active",
    "connectivity auto-trigger active",
    "real-time paper push active",
    "human_gate_search integrated",
    "trace saved with g.stream()",
    "PubMed injected for medical domains",
]
