from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScientificReadinessSignals:
    baseline_readiness_confirmed: bool = False
    evaluation_protocol_validated: bool = False
    comparison_readiness_confirmed: bool = False
    module_validation_confirmed: bool = False
    failure_policy_confirmed: bool = False
    explicit_evaluation_protocol_invalid: bool = False


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _contains_all_groups(text: str, groups: tuple[tuple[str, ...], ...]) -> bool:
    return all(_contains_any(text, group) for group in groups)


def _invalid_evaluation(text: str) -> bool:
    direct = _contains_any(
        text,
        (
            "data leakage",
            "target leakage",
            "train-test leakage",
            "train/test leakage",
            "train-test overlap",
            "training-test overlap",
            "数据泄漏",
            "目标泄漏",
            "训练测试泄漏",
            "評価リーク",
            "データリーク",
        ),
    )
    split_overlap = _contains_all_groups(
        text,
        (
            (
                "train set",
                "training set",
                "训练集",
                "訓練データ",
                "訓練セット",
            ),
            (
                "test set",
                "testing set",
                "测试集",
                "テストデータ",
                "テストセット",
            ),
            (
                "overlap",
                "appears in both",
                "appear in both",
                "present in both",
                "duplicate",
                "同时出现",
                "同時出現",
                "重叠",
                "重複",
                "交叉污染",
            ),
        ),
    )
    return direct or split_overlap


def _baseline_ready(text: str) -> bool:
    return _contains_all_groups(
        text,
        (
            ("baseline", "基线", "ベースライン"),
            ("reproduced", "replicated", "复现", "再現"),
            (
                "frozen",
                "fixed version",
                "pinned version",
                "冻结",
                "固定版本",
                "代码版本",
                "固定済み",
                "バージョン固定",
            ),
        ),
    )


def _evaluation_ready(text: str) -> bool:
    return _contains_any(
        text,
        (
            "independent test split",
            "independent holdout",
            "grouped test split",
            "group-wise test split",
            "entity-level split",
            "subject-level split",
            "独立测试划分",
            "独立测试集",
            "按组划分的独立测试",
            "分组的独立测试",
            "独立テスト分割",
            "グループ単位のテスト分割",
        ),
    )


def _comparison_ready(text: str) -> bool:
    return _contains_all_groups(
        text,
        (
            (
                "strong comparator",
                "strong comparison",
                "strong baseline",
                "强对比",
                "强基线",
                "強い比較手法",
                "強力な比較手法",
            ),
            (
                "verified",
                "identified",
                "found",
                "matched protocol",
                "已验证",
                "找到",
                "同协议",
                "確認済み",
                "同一プロトコル",
            ),
        ),
    )


def _module_ready(text: str) -> bool:
    compatibility = _contains_all_groups(
        text,
        (
            ("compatible", "compatibility", "兼容", "互換"),
            (
                "input semantics",
                "output semantics",
                "interface",
                "输入语义",
                "输出语义",
                "接口",
                "入出力意味",
                "インターフェース",
            ),
        ),
    )
    isolated_effect = _contains_all_groups(
        text,
        (
            (
                "single-module ablation",
                "isolated ablation",
                "single component ablation",
                "单模块消融",
                "単一モジュールのアブレーション",
            ),
            (
                "stable improvement",
                "consistently improved",
                "multiple seeds",
                "three seeds",
                "稳定改善",
                "三个种子",
                "複数シード",
                "三つのシード",
            ),
        ),
    )
    return compatibility and isolated_effect


def _failure_policy_ready(text: str) -> bool:
    return _contains_all_groups(
        text,
        (
            (
                "failure cases",
                "failure samples",
                "negative cases",
                "失败样本",
                "失败案例",
                "失敗例",
            ),
            (
                "stop conditions",
                "stopping conditions",
                "stopping criteria",
                "停止条件",
            ),
            ("recorded", "documented", "已记录", "记录完成", "記録済み"),
        ),
    )


def derive_scientific_readiness(user_request: str) -> ScientificReadinessSignals:
    """Derive only explicit, domain-independent completion or invalidity claims.

    These signals are user declarations, not independently verified scientific facts.
    They may advance the workflow to a controlled evaluation stage, but they never
    manufacture evidence identities, numeric results, or publication claims.
    """

    text = " ".join(user_request.casefold().split())
    invalid = _invalid_evaluation(text)
    return ScientificReadinessSignals(
        baseline_readiness_confirmed=_baseline_ready(text),
        evaluation_protocol_validated=_evaluation_ready(text) and not invalid,
        comparison_readiness_confirmed=_comparison_ready(text),
        module_validation_confirmed=_module_ready(text),
        failure_policy_confirmed=_failure_policy_ready(text),
        explicit_evaluation_protocol_invalid=invalid,
    )


__all__ = ["ScientificReadinessSignals", "derive_scientific_readiness"]
