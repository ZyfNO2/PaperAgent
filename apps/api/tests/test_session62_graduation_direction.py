"""Session 62: GraduationDirection tests.

覆盖 (SOP §8.1):
1. 输入题目能生成 2-3 个方向
2. 每个方向都有 score / risk_level / evidence_bundle
3. 推荐方向必须有 baseline
4. baseline 至少包含名称、理由、复现难度
5. extension_modules 数量在 2-4
6. 数据集缺失时必须生成降级方向
7. 无证据时不得给高分
8. 响应必须包含 stop_reason, 且说明不生成开题报告
9. schema 拒绝多余字段
10. LLM 失败时直接 503 (用户要求: 不做物理分词 fallback)
11. 屏蔽 NLP 论文题目 → 系统能产生 NLP baseline + 创新点

LLM 路径通过 monkeypatch llm_director.generate_directions 注入; 避免依赖真实 API key.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.graduation import build_decision_report


# ---------- 测试用的 LLM stub ---------- #


def _stub_llm_3d(_topic: str, *, prefer: str = "auto", max_directions: int = 3):
    """模拟 LLM 给"基于三维成像的损伤智能检测"返回的方向 (含 3D baseline)."""
    from app.services.graduation.llm_director import DirectorResult
    if prefer == "heuristic":
        return DirectorResult(directions=[], source="heuristic")
    return DirectorResult(
        directions=[
            {
                "direction_id": "dir_1_3d_detection",
                "title": "基于公开点云/三维缺陷数据集的轻量化三维损伤检测",
                "research_object": "工业部件/建筑结构表面缺陷",
                "task": "三维点云损伤检测",
                "method_route": "PointNet++ + 轻量化 neck",
                "why_graduation_friendly": ["三维公开数据集成熟", "baseline 成熟", "可消融"],
                "fallback_route": "数据不足时降级为二维",
                "recommended_baselines": [
                    {
                        "name": "PointNet++",
                        "rationale": "3D 点云检测经典 baseline",
                        "required_data": "ShapeNet/CodeMBI",
                        "reproducibility": "high",
                        "estimated_compute": "单卡 3090 12-24h",
                        "risks": ["小目标敏感度不足"],
                    },
                    {
                        "name": "VoteNet",
                        "rationale": "3D 投票检测",
                        "required_data": "SUN RGB-D",
                        "reproducibility": "medium",
                        "estimated_compute": "单卡 3090 18-30h",
                        "risks": ["室外弱"],
                    },
                ],
                "extension_modules": [
                    {
                        "name": "CBAM 注意力模块",
                        "attach_to": "backbone 末端",
                        "problem_solved": "小目标召回",
                        "ablation_plan": "+CBAM 对比 mAP",
                        "effort": "S",
                        "risks": ["FPS 略降"],
                    },
                    {
                        "name": "Mosaic+MixUp",
                        "attach_to": "数据加载层",
                        "problem_solved": "样本多样性",
                        "ablation_plan": "+Mosaic 对比 mAP",
                        "effort": "S",
                        "risks": [],
                    },
                    {
                        "name": "Focal Loss",
                        "attach_to": "loss 头",
                        "problem_solved": "正负样本不均",
                        "ablation_plan": "+Focal 对比 mAP",
                        "effort": "S",
                        "risks": [],
                    },
                ],
            },
            {
                "direction_id": "dir_2_2d_detection",
                "title": "基于二维图像的裂缝/缺陷轻量化检测",
                "research_object": "结构表面裂缝",
                "task": "目标检测",
                "method_route": "YOLOv8n + CBAM",
                "why_graduation_friendly": ["公开数据丰富", "baseline 极成熟", "易消融"],
                "fallback_route": "工业数据不可得时用 Crack500",
                "recommended_baselines": [
                    {
                        "name": "YOLOv8n",
                        "rationale": "Ultralytics 官方",
                        "required_data": "COCO/VisDrone",
                        "reproducibility": "high",
                        "estimated_compute": "单卡 3090 12-24h",
                        "risks": [],
                    },
                ],
                "extension_modules": [
                    {
                        "name": "CBAM 注意力模块",
                        "attach_to": "backbone 末端",
                        "problem_solved": "小目标召回",
                        "ablation_plan": "+CBAM 对比 mAP",
                        "effort": "S",
                        "risks": [],
                    },
                    {
                        "name": "Mosaic+MixUp",
                        "attach_to": "数据加载层",
                        "problem_solved": "样本多样性",
                        "ablation_plan": "+Mosaic 对比 mAP",
                        "effort": "S",
                        "risks": [],
                    },
                ],
            },
        ],
        source="llm",
        arxiv_refs=[{"arxiv_id": "1234.5678", "title": "PointNet++", "summary": "stub"}],
    )


def _stub_llm_nlp(_topic: str, *, prefer: str = "auto", max_directions: int = 3):
    """模拟 LLM 给 BERT 题目返回的方向 (含 NLP baseline)."""
    from app.services.graduation.llm_director import DirectorResult
    if prefer == "heuristic":
        return DirectorResult(directions=[], source="heuristic")
    return DirectorResult(
        directions=[
            {
                "direction_id": "dir_1_bert_pretrain",
                "title": "基于 BERT 的中文领域文本预训练与下游微调",
                "research_object": "中文领域文本",
                "task": "预训练 + 文本分类微调",
                "method_route": "BERT/RoBERTa 预训练 + Adapter 微调",
                "why_graduation_friendly": ["BERT 官方权重可下载", "下游微调路径成熟", "可加 Adapter/LoRA"],
                "fallback_route": "领域数据不足时用通用中文 wiki",
                "recommended_baselines": [
                    {
                        "name": "BERT-base",
                        "rationale": "Google 官方预训练, 引用过万",
                        "required_data": "中文 wiki / 领域文本",
                        "reproducibility": "high",
                        "estimated_compute": "单卡 A100 3-5 天",
                        "risks": ["显存高"],
                    },
                    {
                        "name": "RoBERTa",
                        "rationale": "BERT 改进版",
                        "required_data": "领域语料",
                        "reproducibility": "high",
                        "estimated_compute": "单卡 A100 3-5 天",
                        "risks": [],
                    },
                ],
                "extension_modules": [
                    {
                        "name": "Adapter 模块",
                        "attach_to": "每层 Transformer 后",
                        "problem_solved": "参数高效微调",
                        "ablation_plan": "+Adapter 对比全参数微调",
                        "effort": "M",
                        "risks": [],
                    },
                    {
                        "name": "DistilBERT 蒸馏",
                        "attach_to": "训练 pipeline",
                        "problem_solved": "模型压缩",
                        "ablation_plan": "+KD 对比精度",
                        "effort": "L",
                        "risks": [],
                    },
                ],
            },
        ],
        source="llm",
        arxiv_refs=[],
    )


def _stub_llm_fail(_topic: str, *, prefer: str = "auto", max_directions: int = 3):
    """模拟 LLM 不可用 / arXiv 无命中."""
    from app.services.graduation.llm_director import DirectorResult
    return DirectorResult(directions=[], source="heuristic", arxiv_refs=[])


@pytest.fixture
def patch_llm_3d(monkeypatch):
    """默认给所有测试打 3D 题的 LLM stub.

    ponytail: 必须 patch direction_planner 里的本地引用 (from .llm_director import generate_directions),
    而不是 llm_director 模块属性.
    """
    monkeypatch.setattr(
        "app.services.graduation.direction_planner.generate_directions",
        _stub_llm_3d,
    )


@pytest.fixture
def patch_llm_nlp(monkeypatch):
    monkeypatch.setattr(
        "app.services.graduation.direction_planner.generate_directions",
        _stub_llm_nlp,
    )


@pytest.fixture
def patch_llm_fail(monkeypatch):
    monkeypatch.setattr(
        "app.services.graduation.direction_planner.generate_directions",
        _stub_llm_fail,
    )


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch, tmp_path):
    monkeypatch.setenv("PAPERAGENT_PAPER_LIBRARY_DIR", str(tmp_path / "paper_library"))
    from app.services import evidence as ev_store
    from app.services.paper_library import embedding
    ev_store.reset_all()
    embedding.reset_vocab()
    yield
    ev_store.reset_all()
    embedding.reset_vocab()


@pytest.fixture()
def client(patch_llm_3d):
    """默认 client 用 3D 题的 stub (覆盖大多数测试)."""
    return TestClient(app)


PROJECT = "s62-test"
TOPIC = "基于三维成像的损伤智能检测"


# ---------------------------------------------------------------------------
# 1) 输入题目能生成 2-3 个方向
# ---------------------------------------------------------------------------


def test_plan_returns_2_to_3_directions(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": TOPIC, "use_last_retrieval": False, "use_local_rag": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert 2 <= len(body["directions"]) <= 3, body["directions"]
    assert body["recommended_direction_id"], "recommended_direction_id 必填"
    assert body["project_id"] == PROJECT
    assert body["topic"] == TOPIC


# ---------------------------------------------------------------------------
# 2) 每个方向都有 score / risk_level / evidence_bundle
# ---------------------------------------------------------------------------


def test_each_direction_has_score_risk_bundle(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": TOPIC, "use_last_retrieval": False, "use_local_rag": False},
    )
    body = resp.json()
    for d in body["directions"]:
        assert "score" in d and 0 <= d["score"] <= 100, d
        assert d["risk_level"] in ("low", "medium", "high"), d
        assert "evidence_bundle" in d, d
        eb = d["evidence_bundle"]
        for k in ("papers", "datasets", "repos", "rag_refs", "gaps"):
            assert k in eb, eb


# ---------------------------------------------------------------------------
# 3) 推荐方向必须有 baseline; baseline 至少包含 name/rationale/reproducibility
# ---------------------------------------------------------------------------


def test_recommended_direction_has_baselines(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": TOPIC, "use_last_retrieval": False, "use_local_rag": False},
    )
    body = resp.json()
    rec = next(d for d in body["directions"] if d["direction_id"] == body["recommended_direction_id"])
    assert rec["recommended_baselines"], "推荐方向必须有 baseline"
    for b in rec["recommended_baselines"]:
        assert b["name"], b
        assert b["rationale"], b
        assert b["reproducibility"] in ("low", "medium", "high"), b


# ---------------------------------------------------------------------------
# 4) extension_modules 数量在 2-4
# ---------------------------------------------------------------------------


def test_extension_modules_count_in_range(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": TOPIC, "use_last_retrieval": False, "use_local_rag": False},
    )
    body = resp.json()
    for d in body["directions"]:
        assert 2 <= len(d["extension_modules"]) <= 4, d
        for m in d["extension_modules"]:
            assert m["name"] and m["attach_to"] and m["ablation_plan"], m


# ---------------------------------------------------------------------------
# 5) 数据集缺失时, 降级方向必须存在
# ---------------------------------------------------------------------------


def test_fallback_direction_present_when_no_dataset(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": TOPIC, "use_last_retrieval": False, "use_local_rag": False},
    )
    body = resp.json()
    has_fallback = any(d["fallback_route"] for d in body["directions"])
    assert has_fallback, "无证据时必须给出降级方向"


# ---------------------------------------------------------------------------
# 6) 无证据时不得给高分 (risk_scorer 应扣分)
# ---------------------------------------------------------------------------


def test_no_evidence_lowers_score(patch_llm_3d, monkeypatch):
    """直接调用 service 层, 对比有/无证据下推荐方向分数."""

    # 无证据
    rpt_no = build_decision_report(
        "ot_test", TOPIC,
        use_last_retrieval=False, use_local_rag=False, max_directions=3,
    )
    score_no = max(d.score for d in rpt_no.directions)

    # mock local_rag.ask_local_rag → 模拟有命中
    from app.services.graduation import evidence_bundle
    from app.services.paper_library import local_rag as lr_mod
    from app.schemas_graduation_direction import EvidenceBundleRef

    class _StubOutcome:
        no_hit = False
        evidence_refs = [
            type("R", (), {"paper_id": "p1", "chunk_id": "c1", "section_title": "Method",
                           "chunk_type": "body", "page_start": 1, "page_end": 2,
                           "quote": "crack detection dataset", "score": 0.8})()
        ]

    def _stub(*args, **kwargs):
        return _StubOutcome()

    monkeypatch.setattr(evidence_bundle.local_rag, "ask_local_rag", _stub)
    rpt_yes = build_decision_report(
        "ot_test", TOPIC,
        use_last_retrieval=False, use_local_rag=True,
        local_rag_query="裂缝检测", max_directions=3,
    )
    score_yes = max(d.score for d in rpt_yes.directions)

    assert score_no < 70, f"无证据时 score 应偏低, got {score_no}"
    assert score_yes > score_no, (score_no, score_yes)


# ---------------------------------------------------------------------------
# 7) 响应必须包含 stop_reason, 且明确不生成开题报告
# ---------------------------------------------------------------------------


def test_stop_reason_present(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": TOPIC},
    )
    body = resp.json()
    assert "stop_reason" in body, body
    assert "不生成开题报告" in body["stop_reason"], body["stop_reason"]


# ---------------------------------------------------------------------------
# 8) schema 拒绝多余字段
# ---------------------------------------------------------------------------


def test_schema_rejects_extra_fields(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": TOPIC, "extra_field": "should_be_rejected"},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# 9) LLM 失败 → 503 (用户要求: 不做物理分词 fallback)
# ---------------------------------------------------------------------------


def test_llm_unavailable_returns_503(patch_llm_fail):
    client = TestClient(app)
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": TOPIC},
    )
    assert resp.status_code == 503, resp.text
    assert "物理分词" in resp.text or "DirectionPlannerError" in resp.text or "方向生成服务暂不可用" in resp.text, resp.text


# ---------------------------------------------------------------------------
# 10) 空题目 422
# ---------------------------------------------------------------------------


def test_empty_topic_422(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": ""},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# 11) 普通 2-3 方向题 (无三维) 仍能跑
# ---------------------------------------------------------------------------


def test_generic_topic_returns_directions(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": "钢材表面缺陷识别"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert 2 <= len(body["directions"]) <= 3, body["directions"]


# ---------------------------------------------------------------------------
# 12) 服务层 direct 调用: 必须有 stop_reason + warnings 可选
# ---------------------------------------------------------------------------


def test_service_layer_direct(client):
    rpt = build_decision_report("ot_x", TOPIC, max_directions=3)
    assert rpt.stop_reason
    assert rpt.generated_at
    assert isinstance(rpt.warnings, list)
    # 至少一条 warning 暴露 source/arxiv_refs (供开发者调试)
    assert any("方向生成来源" in w for w in rpt.warnings), rpt.warnings


# ---------------------------------------------------------------------------
# 13) 三维题必须出现 3D baseline (不能只推 2D YOLO/U-Net)
# ---------------------------------------------------------------------------


def test_3d_topic_baselines_are_3d_models(client):
    """S62 self-audit: '基于三维成像的损伤智能检测' 不应只推荐 YOLO/U-Net.

    用户的怀疑是系统直接套了之前的 YOLO 模板. 这里强制要求
    推荐方向必须包含至少一个 3D baseline (PointNet++/VoteNet/PointRCNN/MVSNet/NeRF).
    LLM stub 已经给了 PointNet++ / VoteNet.
    """
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": TOPIC},
    )
    body = resp.json()
    all_baseline_names = []
    for d in body["directions"]:
        for b in d["recommended_baselines"]:
            all_baseline_names.append(b["name"])
    three_d_keywords = ("PointNet", "VoteNet", "PointRCNN", "MVSNet", "NeRF", "Occupancy")
    has_3d = any(any(k in n for k in three_d_keywords) for n in all_baseline_names)
    assert has_3d, f"3D 题必须出现 3D baseline, 实际: {all_baseline_names}"


# ---------------------------------------------------------------------------
# 14) 屏蔽 NLP 论文标题的 stress test
# ---------------------------------------------------------------------------


def test_masked_nlp_paper_topic_generates_nlp_baselines(patch_llm_nlp):
    """S62 self-audit: 屏蔽原文, 只给主题词, 看 LLM 是否能产生 NLP baseline + 创新点.

    原论文 (Devlin et al. 2018):
    'BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding'
    屏蔽后只给主题: '基于深度双向自注意力的预训练语言模型与下游微调'

    期望: LLM 路径 → NLP baseline (BERT/RoBERTa) + 可加模块 (Adapter/蒸馏).
    这里用 NLP stub 模拟 LLM 返回.
    """
    client = TestClient(app)
    masked_topic = "基于深度双向自注意力的预训练语言模型与下游微调"
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": masked_topic},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    all_baseline_names = []
    for d in body["directions"]:
        for b in d["recommended_baselines"]:
            all_baseline_names.append(b["name"])
    nlp_keywords = ("BERT", "RoBERTa", "DistilBERT", "TextCNN", "BiLSTM")
    has_nlp = any(any(k in n for k in nlp_keywords) for n in all_baseline_names)
    assert has_nlp, f"NLP 题应出现 NLP baseline, 实际: {all_baseline_names}"

    all_module_names = []
    for d in body["directions"]:
        for m in d["extension_modules"]:
            all_module_names.append(m["name"])
    # 模块里至少有一个能消融 (attention / distill / Adapter / LoRA)
    ablation_keywords = ("注意力", "蒸馏", "Adapter", "LoRA", "损失函数", "数据增强")
    has_ablation = any(any(k in n for k in ablation_keywords) for n in all_module_names)
    assert has_ablation, f"NLP 题可加模块应含可消融项, 实际: {all_module_names}"

    rec_title = next(d["title"] for d in body["directions"] if d["direction_id"] == body["recommended_direction_id"])
    assert any(k in rec_title for k in ("预训练", "BERT", "语言模型", "文本")), rec_title


# ---------------------------------------------------------------------------
# 15) NLP 题不应混入 2D 检测 baseline (旧 bug: YOLO/U-Net)
# ---------------------------------------------------------------------------


def test_nlp_topic_no_2d_detection_leak(patch_llm_nlp):
    """S62 self-audit: NLP 题不应再被 M4 强行加 YOLO/U-Net 2D baseline."""
    client = TestClient(app)
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": "基于 BERT 的中文文本分类"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    two_d_keywords = ("YOLO", "U-Net", "ResNet", "PointNet", "VoteNet")
    for d in body["directions"]:
        for b in d["recommended_baselines"]:
            assert not any(k in b["name"] for k in two_d_keywords), (
                f"NLP 题不应出现 2D/3D 视觉 baseline, 实际: {b['name']}"
            )