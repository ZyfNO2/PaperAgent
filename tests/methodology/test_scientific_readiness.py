from __future__ import annotations

import pytest

from paperagent.scientific_readiness import derive_scientific_readiness


def test_chinese_completed_workflow_is_detected() -> None:
    signals = derive_scientific_readiness(
        "项目已经复现并冻结具体基线及代码版本;使用独立测试划分;"
        "找到同协议强对比;验证模块与基线输入语义兼容;"
        "单模块消融在三个种子上稳定改善;失败样本和停止条件已记录。"
    )

    assert signals.baseline_readiness_confirmed is True
    assert signals.evaluation_protocol_validated is True
    assert signals.comparison_readiness_confirmed is True
    assert signals.module_validation_confirmed is True
    assert signals.failure_policy_confirmed is True
    assert signals.explicit_evaluation_protocol_invalid is False
    assert signals.declared_ready is True
    assert signals.basis == "user_declaration"
    assert signals.independently_verified is False


def test_train_test_overlap_is_invalid_and_overrides_independence() -> None:
    signals = derive_scientific_readiness(
        "We planned an independent test split, but the same subjects appear in both "
        "the training set and test set."
    )

    assert signals.explicit_evaluation_protocol_invalid is True
    assert signals.evaluation_protocol_validated is False


def test_chinese_train_test_overlap_is_invalid() -> None:
    signals = derive_scientific_readiness(
        "检查发现相同对象同时出现在训练集和测试集,当前随机划分分数不能作为证据。"
    )

    assert signals.explicit_evaluation_protocol_invalid is True


def test_planned_or_desired_work_does_not_count_as_completed() -> None:
    signals = derive_scientific_readiness(
        "We want to reproduce a baseline, plan an independent split, and hope to find "
        "a strong comparator. We will later run a single-module ablation."
    )

    assert signals.baseline_readiness_confirmed is False
    assert signals.evaluation_protocol_validated is False
    assert signals.comparison_readiness_confirmed is False
    assert signals.module_validation_confirmed is False
    assert signals.failure_policy_confirmed is False


def test_japanese_explicit_completion_is_detected() -> None:
    signals = derive_scientific_readiness(
        "ベースラインは再現済みでバージョン固定済みです。独立テスト分割を使用し、"
        "同一プロトコルの強い比較手法を確認済みです。インターフェースの入出力意味の"
        "互換性を確認し、単一モジュールのアブレーションを複数シードで安定改善しました。"
        "失敗例と停止条件は記録済みです。"
    )

    assert signals.baseline_readiness_confirmed is True
    assert signals.evaluation_protocol_validated is True
    assert signals.comparison_readiness_confirmed is True
    assert signals.module_validation_confirmed is True
    assert signals.failure_policy_confirmed is True


@pytest.mark.parametrize(
    "text",
    [
        "The model may have generalization issues.",
        "The test set is difficult, but there is no known overlap.",
        "我们还没有确定训练集和测试集的划分。",
    ],
)
def test_ambiguous_risk_language_does_not_create_leakage(text: str) -> None:
    assert derive_scientific_readiness(text).explicit_evaluation_protocol_invalid is False
