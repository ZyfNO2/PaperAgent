"""Session 51: 工科学位论文可行性评估 API 端点.

SOP §11 端点设计 (Task 9):

    POST /api/v1/thesis-eval/assess
      body: { thesis_id: str, title?: str, source_url?: str, abstract_snippet?: str }
      resp: ThesisAssessment

    POST /api/v1/thesis-eval/eval/run
      body: { subset?: SubsetName, use_llm?: bool, save_baseline?: bool }
      resp: ThesisEvalReport

    GET  /api/v1/thesis-eval/eval/baseline
      resp: baseline.json (dict)

    POST /api/v1/thesis-eval/eval/baseline
      (当前 run 存为 baseline, 返回保存结果)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...schemas_thesis_eval import (
    SubsetName,
    ThesisAssessment,
    ThesisEvalReport,
)
from ...services.thesis_eval import baseline as bl_service
from ...services.thesis_eval.eval_pipeline import (
    assess_single,
    load_seed,
    run_thesis_eval,
    select_subset,
)
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/api/v1/thesis-eval", tags=["thesis-eval"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class AssessRequest(BaseModel):
    """POST /assess 请求体."""

    model_config = ConfigDict(extra="forbid")

    thesis_id: str = Field(min_length=1, description="如 ENG-THESIS-001")
    title: str | None = Field(default=None)
    source_url: str | None = Field(default=None)
    abstract_snippet: str | None = Field(default=None)


class EvalRunRequest(BaseModel):
    """POST /eval/run 请求体."""

    model_config = ConfigDict(extra="forbid")

    subset: SubsetName = "smoke_20"
    use_llm: bool = False
    save_baseline: bool = False


class BaselineSaveResponse(BaseModel):
    """POST /eval/baseline 响应."""

    ok: bool
    message: str
    metrics: dict = Field(default_factory=dict)
    baseline_path: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/assess",
    response_model=ThesisAssessment,
    summary="单条题录可行性评估 (crawl → needs → difficulty → report)",
)
def assess(body: AssessRequest) -> ThesisAssessment:
    """对一条题录 (从测试集或外部 URL) 跑完整评估链.

    传入 thesis_id + title / source_url / abstract_snippet 均可.
    title / source_url 为空时从测试集查询填充.
    抓取失败自动降级为题录级证据.
    """
    # 如果只给了 thesis_id, 从种子文件补字段
    thesis: dict | None = None
    if body.title is None and body.source_url is None and body.abstract_snippet is None:
        seed = load_seed()
        for s in seed:
            if s["id"] == body.thesis_id:
                thesis = s
                break
        if thesis is None:
            raise HTTPException(
                status_code=404,
                detail=f"thesis_id {body.thesis_id} 不在测试集中, 请提供 title/source_url",
            )
    else:
        thesis = {
            "id": body.thesis_id,
            "title": body.title or "",
            "source_url": body.source_url or "",
            "experiment_need": body.abstract_snippet or "",
            "domain": None,
            "year": None,
        }

    try:
        return assess_single(thesis, use_llm=False, http_client=None)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"评估失败: {type(exc).__name__}: {exc}"
        ) from exc


@router.post(
    "/eval/run",
    response_model=ThesisEvalReport,
    summary="跑一个子集的完整评估 (含 baseline 对比)",
)
def run_eval(body: EvalRunRequest) -> ThesisEvalReport:
    """Run evaluation on a subset.

    - subset: smoke_20 / regression_60 / hard_20 / all_100
    - use_llm: 启动 LLM 标签抽取 (默认 heuristic)
    - save_baseline: 如果 True, 存为新的 baseline
    """
    try:
        report = run_thesis_eval(
            subset=body.subset,
            use_llm=body.use_llm,
            save_baseline_flag=body.save_baseline,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"评估运行失败: {type(exc).__name__}: {exc}"
        ) from exc
    return report


@router.get(
    "/eval/baseline",
    response_model=dict,
    summary="获取当前 baseline 数据",
)
def get_baseline() -> dict:
    """返回保存的 baseline JSON."""
    baseline = bl_service.load_baseline()
    if baseline is None:
        return {"baseline": None, "message": "暂无 baseline, 请先 POST /eval/run 或 POST /eval/baseline"}
    return {"baseline": baseline, "message": "ok"}


@router.post(
    "/eval/baseline",
    response_model=BaselineSaveResponse,
    summary="把最近一次 run 存为 baseline (或手动设定值)",
)
def save_baseline(body: dict | None = None) -> BaselineSaveResponse:
    """把当前给定的指标保存为 baseline.

    不传 body 时尝试取最近一次 run 的 aggregate_metrics.
    """
    if body is None:
        # 默认 fallback: 手动保存空 baseline (用户需先跑 eval/run)
        return BaselineSaveResponse(
            ok=False,
            message="请先 POST /eval/run + 在请求体中传入 aggregate_metrics",
            baseline_path="data/thesis_eval/baseline.json",
        )

    try:
        metrics = body.get("aggregate_metrics", body)
        subset = body.get("subset", "manual")
        bl_service.save_baseline(metrics, subset=subset)
        return BaselineSaveResponse(
            ok=True,
            message=f"baseline 已保存 (subset={subset})",
            metrics=metrics,
            baseline_path="data/thesis_eval/baseline.json",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"保存 baseline 失败: {type(exc).__name__}: {exc}"
        ) from exc
