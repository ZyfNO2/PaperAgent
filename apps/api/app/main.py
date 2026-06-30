"""FastAPI 入口 — OneTopic MVP 版."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import HTTPException as FastAPIHTTPException

from app.api.v1.one_topic import router as one_topic_router
from app.api.v1.skills import router as skills_router
from app.api.v1.health import router as health_router
from app.api.v1.mcp import router as mcp_router  # Session 36: MCP tools
from app.api.v1.thesis_eval import router as thesis_eval_router  # Session 51
from app.api.v1.paper_library import router as paper_library_router  # Session 46
from app.api.v1.graduation_direction import router as graduation_direction_router  # Session 62
from app.api.v1.topic_research import router as topic_research_router  # Session 66
from app.errors import AppError, app_error_handler, http_exception_handler

app = FastAPI(
    title="TopicPilot-CN OneTopic MVP",
    version="0.2.0",
    description="一题输入 → 关键词拆解 → 三线检索 → 可行性判断 → 开题建议 → 低门槛审核",
)

# CORS: 允许 apps/web dev server (18182) 调后端 (18181)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:18182",
        "http://localhost:18182",
        "http://127.0.0.1:18181",
        "http://localhost:18181",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session 18: 统一错误处理
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(FastAPIHTTPException, http_exception_handler)

app.include_router(one_topic_router)
app.include_router(skills_router)
app.include_router(health_router, prefix="/api/v1")
app.include_router(mcp_router)  # Session 36: MCP tools
app.include_router(thesis_eval_router)  # Session 51
app.include_router(paper_library_router)  # Session 46
app.include_router(graduation_direction_router)  # Session 62
app.include_router(topic_research_router)  # Session 66


# S62 self-audit: 开发/CI 环境无 LLM key 时, 用测试桩让 e2e 可跑.
# 生产环境 (PAPERAGENT_DEV_LLM_STUB 未设置) 不影响 — 仍走真实 LLM 路径.
import os as _os
if _os.environ.get("PAPERAGENT_DEV_LLM_STUB") == "1":
    import logging as _logging
    _logging.getLogger("app.main").warning(
        "PAPERAGENT_DEV_LLM_STUB=1 detected — graduating direction planner "
        "monkeypatched with deterministic stub (DEV / CI ONLY)"
    )
    from app.services.graduation.direction_planner import generate_directions as _real_gd
    from app.services.graduation import llm_director as _llm_dir

    def _stub_directions(raw_topic: str, *, prefer: str = "auto", max_directions: int = 3):
        from app.services.graduation.llm_director import DirectorResult
        # 简单按关键词分类
        t = raw_topic or ""
        is_3d = any(k in t for k in ("三维", "3D", "点云"))
        is_nlp = any(k in t for k in ("BERT", "语言模型", "NLP", "文本"))
        if is_3d:
            return DirectorResult(
                directions=[
                    {
                        "direction_id": "dir_1_3d",
                        "title": "基于公开点云/三维缺陷数据集的轻量化三维损伤检测",
                        "research_object": "工业部件表面缺陷",
                        "task": "三维点云损伤检测",
                        "method_route": "PointNet++ + 轻量化 neck",
                        "why_graduation_friendly": ["三维公开数据集成熟", "baseline 成熟", "可消融"],
                        "fallback_route": "三维数据不足时降级为二维",
                        "recommended_baselines": [
                            {"name": "PointNet++", "rationale": "3D 点云经典 baseline",
                             "required_data": "ShapeNet", "reproducibility": "high",
                             "estimated_compute": "单卡 3090 12-24h", "risks": []},
                            {"name": "VoteNet", "rationale": "3D 投票检测",
                             "required_data": "SUN RGB-D", "reproducibility": "medium",
                             "estimated_compute": "单卡 3090 18-30h", "risks": []},
                        ],
                        "extension_modules": [
                            {"name": "CBAM 注意力模块", "attach_to": "backbone 末端",
                             "problem_solved": "小目标召回", "ablation_plan": "+CBAM 对比 mAP",
                             "effort": "S", "risks": []},
                            {"name": "Mosaic+MixUp", "attach_to": "数据加载层",
                             "problem_solved": "样本多样性", "ablation_plan": "+Mosaic 对比 mAP",
                             "effort": "S", "risks": []},
                        ],
                    },
                    {
                        "direction_id": "dir_2_2d",
                        "title": "基于二维图像的裂缝/缺陷轻量化检测",
                        "research_object": "结构表面裂缝",
                        "task": "目标检测",
                        "method_route": "YOLOv8n + CBAM",
                        "why_graduation_friendly": ["公开数据丰富", "baseline 极成熟"],
                        "fallback_route": "工业数据不可得时用 Crack500",
                        "recommended_baselines": [
                            {"name": "YOLOv8n", "rationale": "Ultralytics 官方",
                             "required_data": "COCO/VisDrone", "reproducibility": "high",
                             "estimated_compute": "单卡 3090 12-24h", "risks": []},
                        ],
                        "extension_modules": [
                            {"name": "CBAM 注意力模块", "attach_to": "backbone 末端",
                             "problem_solved": "小目标召回", "ablation_plan": "+CBAM 对比 mAP",
                             "effort": "S", "risks": []},
                            {"name": "Mosaic+MixUp", "attach_to": "数据加载层",
                             "problem_solved": "样本多样性", "ablation_plan": "+Mosaic 对比 mAP",
                             "effort": "S", "risks": []},
                        ],
                    },
                ][:max_directions],
                source="llm",
                arxiv_refs=[],
            )
        if is_nlp:
            return DirectorResult(
                directions=[
                    {
                        "direction_id": "dir_1_nlp",
                        "title": "基于 BERT 的中文领域文本预训练与下游微调",
                        "research_object": "中文领域文本",
                        "task": "预训练 + 文本分类微调",
                        "method_route": "BERT + Adapter",
                        "why_graduation_friendly": ["BERT 官方权重", "下游微调成熟"],
                        "fallback_route": "领域数据不足时用通用 wiki",
                        "recommended_baselines": [
                            {"name": "BERT-base", "rationale": "Google 官方预训练",
                             "required_data": "中文 wiki", "reproducibility": "high",
                             "estimated_compute": "单卡 A100 3-5 天", "risks": []},
                            {"name": "RoBERTa", "rationale": "BERT 改进版",
                             "required_data": "领域语料", "reproducibility": "high",
                             "estimated_compute": "单卡 A100 3-5 天", "risks": []},
                        ],
                        "extension_modules": [
                            {"name": "Adapter 模块", "attach_to": "每层 Transformer 后",
                             "problem_solved": "参数高效微调", "ablation_plan": "+Adapter 对比",
                             "effort": "M", "risks": []},
                            {"name": "DistilBERT 蒸馏", "attach_to": "训练 pipeline",
                             "problem_solved": "模型压缩", "ablation_plan": "+KD 对比",
                             "effort": "L", "risks": []},
                        ],
                    },
                ],
                source="llm",
                arxiv_refs=[],
            )
        # 通用兜底
        return DirectorResult(
            directions=[
                {
                    "direction_id": "dir_1_generic",
                    "title": f"基于公开数据集的轻量化{raw_topic[:8]}检测",
                    "research_object": "公开数据集中相近子集",
                    "task": "目标检测",
                    "method_route": "YOLOv8n baseline",
                    "why_graduation_friendly": ["公开数据充足", "baseline 成熟"],
                    "fallback_route": "降级到 COCO/VOC",
                    "recommended_baselines": [
                        {"name": "YOLOv8n", "rationale": "Ultralytics",
                         "required_data": "COCO", "reproducibility": "high",
                         "estimated_compute": "单卡 3090", "risks": []},
                    ],
                    "extension_modules": [
                        {"name": "CBAM 注意力", "attach_to": "backbone",
                         "problem_solved": "小目标", "ablation_plan": "+CBAM",
                         "effort": "S", "risks": []},
                        {"name": "Mosaic+MixUp", "attach_to": "数据加载",
                         "problem_solved": "多样性", "ablation_plan": "+Mosaic",
                         "effort": "S", "risks": []},
                    ],
                },
            ],
            source="llm",
            arxiv_refs=[],
        )

    # 替换两个引用点 (本地 + 模块属性, 因为 from import 是本地绑定)
    import app.services.graduation.direction_planner as _dp
    _dp.generate_directions = _stub_directions
    _llm_dir.generate_directions = _stub_directions


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "one_topic_mvp", "session": "18"}
