"""多源轻验证与 URL Verified 服务 (Session 10 §5).

只做 URL / 元数据级轻验证, 不下载全文, 不深爬, 不绕过付费数据库.
对 paper / dataset / repo / note / 普通 URL 卡片做规则 + 可选 HTTP 检查.

设计原则 (§3):
- 不依赖外部 API key
- 无网络 → partial + warning, 不阻断
- LLM 不参与真伪判断, 只解释 warnings
- failed 不进 supports; assistant_intake + unverified 不进 supports

调用:
  verify_evidence_item(item)         # 单条
  verify_project_evidence(...)       # 批量
"""

from __future__ import annotations

import re
import socket
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlparse

from ..schemas_evidence import (
    EvidenceItem,
    VerificationResult,
    VerificationStatus,
    VerificationSource,
    VerificationSummary,
)


# ---------- URL 解析规则 (§5.2-5.6) ---------- #


_GH_RE = re.compile(r"github\.com/([\w.-]+)/([\w.-]+?)(?:\.git|/|$)", re.IGNORECASE)
_ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([\w./-]+)", re.IGNORECASE)
_HF_DATASET_RE = re.compile(r"huggingface\.co/datasets/([\w.-]+)", re.IGNORECASE)
_HF_MODEL_RE = re.compile(r"huggingface\.co/([\w.-]+)/([\w.-]+?)(?:/|$)", re.IGNORECASE)
_KAGGLE_DATASET_RE = re.compile(r"kaggle\.com/datasets/([\w.-]+(?:/[\w.-]+)?)", re.IGNORECASE)
_KAGGLE_COMP_RE = re.compile(r"kaggle\.com/competitions/([\w.-]+)", re.IGNORECASE)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_url(content: str | None) -> dict[str, Any]:
    """识别 URL 类型并提取关键字段.

    Returns:
      {
        "platform": "github"|"arxiv"|"huggingface_dataset"|"kaggle_dataset"|"generic"|"none",
        "url": normalized url or None,
        "owner": str|None,
        "repo": str|None,
        "arxiv_id": str|None,
        "dataset_slug": str|None,
      }
    """

    out: dict[str, Any] = {
        "platform": "none",
        "url": None,
        "owner": None,
        "repo": None,
        "arxiv_id": None,
        "dataset_slug": None,
    }
    if not content:
        return out

    content = content.strip()
    if not content.startswith("http"):
        return out

    out["url"] = content

    m = _GH_RE.search(content)
    if m:
        out["platform"] = "github"
        out["owner"] = m.group(1).lower()
        out["repo"] = m.group(2).lower().rstrip(".git")
        return out

    m = _ARXIV_RE.search(content)
    if m:
        out["platform"] = "arxiv"
        out["arxiv_id"] = m.group(1).rstrip(".pdf").rstrip("/")
        return out

    m = _HF_DATASET_RE.search(content)
    if m:
        out["platform"] = "huggingface_dataset"
        out["dataset_slug"] = m.group(1)
        return out

    m = _HF_MODEL_RE.search(content)
    if m:
        # HF model 当作 repo 处理 (复用 github-like 警告)
        out["platform"] = "github"
        out["owner"] = m.group(1).lower()
        out["repo"] = m.group(2).lower()
        return out

    m = _KAGGLE_DATASET_RE.search(content)
    if m:
        out["platform"] = "kaggle_dataset"
        out["dataset_slug"] = m.group(1).rstrip("/")
        return out

    m = _KAGGLE_COMP_RE.search(content)
    if m:
        out["platform"] = "kaggle_dataset"
        out["dataset_slug"] = m.group(1).rstrip("/")
        return out

    out["platform"] = "generic"
    return out


def _normalize_url(platform: str, parsed: dict[str, Any]) -> str | None:
    """生成 canonical URL, 方便证据一致性."""

    url = parsed.get("url")
    if not url:
        return None
    parsed_url = urlparse(url)
    scheme = parsed_url.scheme or "https"
    host = parsed_url.netloc.lower()

    if platform == "github" and parsed.get("owner") and parsed.get("repo"):
        return f"https://{host}/{parsed['owner']}/{parsed['repo']}"
    if platform == "arxiv" and parsed.get("arxiv_id"):
        return f"https://arxiv.org/abs/{parsed['arxiv_id']}"
    if platform == "huggingface_dataset" and parsed.get("dataset_slug"):
        return f"https://huggingface.co/datasets/{parsed['dataset_slug']}"
    if platform == "kaggle_dataset" and parsed.get("dataset_slug"):
        return f"https://www.kaggle.com/datasets/{parsed['dataset_slug']}"
    return f"{scheme}://{parsed_url.netloc}{parsed_url.path}" if parsed_url.netloc else url


def _http_head_reachable(url: str, timeout: float = 2.0) -> tuple[bool, str | None]:
    """极简 HTTP 可达性检查 (无 requests 依赖时降级 socket).

    Returns: (reachable, error_msg)
    """

    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    if not host:
        return False, "no_host"
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            try:
                sock.sendall(f"HEAD {path} HTTP/1.0\r\nHost: {host}\r\n\r\n".encode())
                data = sock.recv(64).decode("latin-1", errors="ignore")
                if data.startswith("HTTP/"):
                    code = int(data.split()[1]) if len(data.split()) >= 2 else 0
                    if 200 <= code < 400:
                        return True, None
                    return False, f"http_{code}"
            except Exception:  # noqa: BLE001
                pass
            # HEAD 被禁, 直接 TCP 通视为可达
            return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}"


# ---------- 各平台验证器 (§5.2-5.6) ---------- #


def verify_arxiv(item: EvidenceItem, parsed: dict[str, Any]) -> VerificationResult:
    arxiv_id = parsed.get("arxiv_id") or item.arxiv_id
    url = parsed.get("url") or item.url or ""
    warnings: list[str] = []
    metadata: dict[str, Any] = {"arxiv_id": arxiv_id}

    if not arxiv_id:
        return VerificationResult(
            evidence_id=item.evidence_id,
            evidence_type=item.evidence_type,
            ok=False, url_verified=False,
            verification_status="failed",
            verification_confidence=0.0,
            verification_source="arxiv",
            normalized_url=None,
            metadata=metadata,
            warnings=["arxiv_id 无法从 URL 中提取"],
            checked_at=_utcnow_iso(),
        )

    # 格式粗校验
    if not re.match(r"^[\d.]+v?\d*$|^[\w-]+/\d+\w*\d*$", arxiv_id):
        warnings.append(f"arxiv_id 格式异常: {arxiv_id}")

    norm_url = _normalize_url("arxiv", parsed) or url
    reachable, err = _http_head_reachable(norm_url)

    if reachable and not warnings:
        confidence = 0.85
        status: VerificationStatus = "verified"
    elif reachable:
        confidence = 0.65
        status = "partial"
    elif err and "timeout" in err.lower():
        confidence = 0.45
        status = "partial"
        warnings.append("网络超时, 仅做格式校验")
    elif err and err.startswith("http_"):
        confidence = 0.30
        status = "partial"
        warnings.append(f"远端返回 {err}, URL 可能失效")
    else:
        confidence = 0.55
        status = "partial"
        warnings.append(f"无法访问 arxiv.org ({err or 'unknown'}), 仅做格式校验")

    if not item.title or "arXiv:" in (item.title or ""):
        metadata["title_known"] = False
        warnings.append("标题未知, 建议补全论文标题后再验证")

    return VerificationResult(
        evidence_id=item.evidence_id,
        evidence_type=item.evidence_type,
        ok=(status != "failed"), url_verified=(status == "verified"),
        verification_status=status,
        verification_confidence=confidence,
        verification_source="arxiv",
        normalized_url=norm_url,
        metadata=metadata,
        warnings=warnings,
        checked_at=_utcnow_iso(),
    )


def verify_github(item: EvidenceItem, parsed: dict[str, Any]) -> VerificationResult:
    owner = parsed.get("owner")
    repo = parsed.get("repo")
    url = parsed.get("url") or item.url or ""
    warnings: list[str] = []
    metadata: dict[str, Any] = {"owner": owner, "repo": repo}

    if not owner or not repo:
        return VerificationResult(
            evidence_id=item.evidence_id,
            evidence_type=item.evidence_type,
            ok=False, url_verified=False,
            verification_status="failed",
            verification_confidence=0.0,
            verification_source="github",
            normalized_url=None,
            metadata=metadata,
            warnings=["无法从 URL 解析 owner/repo"],
            checked_at=_utcnow_iso(),
        )

    # 排除 issue / wiki / blob 等子页
    subpage = re.search(r"/(issues|pull|wiki|blob|raw|tree|releases)/", url, re.IGNORECASE)
    if subpage:
        warnings.append(f"URL 是 GitHub 子页 ({subpage.group(1)}), 非 repo 主页")

    norm_url = _normalize_url("github", parsed) or url
    reachable, err = _http_head_reachable(norm_url)

    if not reachable and not err:
        confidence = 0.0
        status: VerificationStatus = "failed"
        warnings.append("无法访问 GitHub")
    elif not reachable and err and err.startswith("http_"):
        # 404/410 → failed
        code = err
        if code in ("http_404", "http_410"):
            confidence = 0.0
            status = "failed"
            warnings.append(f"GitHub 返回 {code}, repo 不存在或私有")
        else:
            confidence = 0.40
            status = "partial"
            warnings.append(f"GitHub 返回 {code}")
    elif not reachable:
        confidence = 0.45
        status = "partial"
        warnings.append(f"GitHub 可达性检查失败 ({err or 'unknown'})")
    elif subpage:
        confidence = 0.55
        status = "partial"
        warnings.append("URL 是子页, 已规范化到 repo 主页")
    else:
        confidence = 0.72
        status = "partial"
        warnings.append("未验证 train/eval 脚本")
        warnings.append("未验证 license")

    if not item.has_training_script:
        warnings.append("未验证 train 脚本")
    if not item.has_eval_script:
        warnings.append("未验证 eval 脚本")
    if not item.has_readme:
        warnings.append("未验证 README")
    if not item.license:
        warnings.append("未验证 license")

    return VerificationResult(
        evidence_id=item.evidence_id,
        evidence_type=item.evidence_type,
        ok=(status != "failed"), url_verified=(status == "verified"),
        verification_status=status,
        verification_confidence=confidence,
        verification_source="github",
        normalized_url=norm_url,
        metadata=metadata,
        warnings=warnings,
        checked_at=_utcnow_iso(),
    )


def verify_huggingface(item: EvidenceItem, parsed: dict[str, Any]) -> VerificationResult:
    slug = parsed.get("dataset_slug")
    url = parsed.get("url") or item.url or ""
    warnings: list[str] = []
    metadata: dict[str, Any] = {"dataset_slug": slug, "platform": "huggingface"}

    if not slug:
        return VerificationResult(
            evidence_id=item.evidence_id,
            evidence_type=item.evidence_type,
            ok=False, url_verified=False,
            verification_status="failed",
            verification_confidence=0.0,
            verification_source="huggingface",
            normalized_url=None,
            metadata=metadata,
            warnings=["无法从 URL 解析 dataset slug"],
            checked_at=_utcnow_iso(),
        )

    norm_url = _normalize_url("huggingface_dataset", parsed) or url
    reachable, err = _http_head_reachable(norm_url)

    if reachable:
        confidence = 0.65
        status: VerificationStatus = "partial"
        warnings.append("未验证下载权限")
        warnings.append("未验证 license")
        if not item.modality:
            warnings.append("未验证 modality/标注类型")
    elif err and err.startswith("http_"):
        code = err
        if code in ("http_404", "http_410"):
            confidence = 0.0
            status = "failed"
            warnings.append(f"HuggingFace 返回 {code}, dataset 不存在或私有")
        else:
            confidence = 0.40
            status = "partial"
            warnings.append(f"HuggingFace 返回 {code}")
    else:
        confidence = 0.45
        status = "partial"
        warnings.append(f"HuggingFace 可达性检查失败 ({err or 'unknown'})")

    return VerificationResult(
        evidence_id=item.evidence_id,
        evidence_type=item.evidence_type,
        ok=(status != "failed"), url_verified=(status == "verified"),
        verification_status=status,
        verification_confidence=confidence,
        verification_source="huggingface",
        normalized_url=norm_url,
        metadata=metadata,
        warnings=warnings,
        checked_at=_utcnow_iso(),
    )


def verify_kaggle(item: EvidenceItem, parsed: dict[str, Any]) -> VerificationResult:
    slug = parsed.get("dataset_slug")
    url = parsed.get("url") or item.url or ""
    warnings: list[str] = []
    metadata: dict[str, Any] = {"dataset_slug": slug, "platform": "kaggle"}

    if not slug:
        return VerificationResult(
            evidence_id=item.evidence_id,
            evidence_type=item.evidence_type,
            ok=False, url_verified=False,
            verification_status="failed",
            verification_confidence=0.0,
            verification_source="kaggle",
            normalized_url=None,
            metadata=metadata,
            warnings=["无法从 URL 解析 Kaggle dataset slug"],
            checked_at=_utcnow_iso(),
        )

    norm_url = _normalize_url("kaggle_dataset", parsed) or url
    reachable, err = _http_head_reachable(norm_url)

    if reachable:
        confidence = 0.60
        status: VerificationStatus = "partial"
        warnings.append("未验证下载权限")
        warnings.append("未验证 license")
        warnings.append("可能需要注册 Kaggle 账号才能下载")
    elif err and err.startswith("http_"):
        code = err
        if code in ("http_404", "http_410"):
            confidence = 0.0
            status = "failed"
            warnings.append(f"Kaggle 返回 {code}, dataset 不存在或私有")
        else:
            confidence = 0.35
            status = "partial"
            warnings.append(f"Kaggle 返回 {code}")
    else:
        confidence = 0.40
        status = "partial"
        warnings.append(f"Kaggle 可达性检查失败 ({err or 'unknown'})")

    return VerificationResult(
        evidence_id=item.evidence_id,
        evidence_type=item.evidence_type,
        ok=(status != "failed"), url_verified=(status == "verified"),
        verification_status=status,
        verification_confidence=confidence,
        verification_source="kaggle",
        normalized_url=norm_url,
        metadata=metadata,
        warnings=warnings,
        checked_at=_utcnow_iso(),
    )


def verify_generic_url(item: EvidenceItem, parsed: dict[str, Any]) -> VerificationResult:
    url = parsed.get("url") or item.url or ""
    warnings: list[str] = []
    metadata: dict[str, Any] = {"url": url}

    reachable, err = _http_head_reachable(url)
    if reachable:
        confidence = 0.55
        status: VerificationStatus = "partial"
        warnings.append("通用 URL, 未识别为论文/数据集/repo")
    elif err and err.startswith("http_"):
        code = err
        confidence = 0.30
        status = "partial"
        warnings.append(f"远端返回 {code}")
    else:
        confidence = 0.30
        status = "partial"
        warnings.append(f"URL 可达性检查失败 ({err or 'unknown'})")

    return VerificationResult(
        evidence_id=item.evidence_id,
        evidence_type=item.evidence_type,
        ok=(status != "failed"), url_verified=False,
        verification_status=status,
        verification_confidence=confidence,
        verification_source="http",
        normalized_url=url,
        metadata=metadata,
        warnings=warnings,
        checked_at=_utcnow_iso(),
    )


def verify_paper_metadata(item: EvidenceItem) -> VerificationResult:
    """无 URL 论文: 仅校验 DOI / arxiv_id 格式 + 已有元数据."""

    warnings: list[str] = []
    metadata: dict[str, Any] = {}
    confidence = 0.0
    source: VerificationSource = "none"

    if item.arxiv_id:
        source = "arxiv"
        metadata["arxiv_id"] = item.arxiv_id
        if re.match(r"^[\d.]+v?\d*$|^[\w-]+/\d+\w*\d*$", item.arxiv_id):
            confidence = 0.55
            warnings.append("仅有 arxiv_id, 未访问 arxiv.org (无 URL)")
        else:
            confidence = 0.20
            warnings.append(f"arxiv_id 格式异常: {item.arxiv_id}")
    elif item.doi:
        source = "openalex"
        metadata["doi"] = item.doi
        if re.match(r"^10\.\d{4,9}/[\w./:()<>;\-]+$", item.doi):
            confidence = 0.50
            warnings.append("仅有 DOI, 未访问 openalex.org (无 URL)")
        else:
            confidence = 0.20
            warnings.append(f"DOI 格式异常: {item.doi}")
    else:
        warnings.append("无 URL/arxiv_id/DOI, 仅基于已有元数据校验")

    if not item.title or item.title == "(未匹配公开数据集)":
        warnings.append("标题缺失")

    return VerificationResult(
        evidence_id=item.evidence_id,
        evidence_type=item.evidence_type,
        ok=True, url_verified=False,
        verification_status="partial",
        verification_confidence=confidence,
        verification_source=source,
        normalized_url=None,
        metadata=metadata,
        warnings=warnings,
        checked_at=_utcnow_iso(),
    )


def verify_skipped(item: EvidenceItem, reason: str = "纯文本或无可验证 URL") -> VerificationResult:
    """文本类 / 无 URL 内容: skipped (不误判 verified)."""

    return VerificationResult(
        evidence_id=item.evidence_id,
        evidence_type=item.evidence_type,
        ok=True, url_verified=False,
        verification_status="skipped",
        verification_confidence=0.0,
        verification_source="none",
        normalized_url=None,
        metadata={},
        warnings=[reason],
        checked_at=_utcnow_iso(),
    )


# ---------- 验证器选择 (§5.1) ---------- #


def choose_verifier(item: EvidenceItem) -> VerificationResult:
    """根据 item 类型 + URL 选择对应验证器."""

    raw_ref = item.raw_input_ref or ""
    url = item.url or raw_ref
    parsed = parse_url(url if url else raw_ref)
    platform = parsed["platform"]

    # assistant_intake + 文本 → skipped
    if item.source_mode == "assistant_intake" and not item.url and not raw_ref.startswith("http"):
        return verify_skipped(item, "assistant_intake 纯文本, 无法 URL 验证")

    # note / custom 类型无 URL → skipped
    if item.evidence_type in ("note", "custom") and not url:
        return verify_skipped(item, reason=f"{item.evidence_type} 无 URL, skipped")

    # 平台分发
    if platform == "arxiv" or (item.arxiv_id and not platform.startswith("github")):
        if platform == "arxiv":
            return verify_arxiv(item, parsed)
        # 仅 arxiv_id 走 paper metadata fallback
    if platform == "github":
        return verify_github(item, parsed)
    if platform == "huggingface_dataset":
        return verify_huggingface(item, parsed)
    if platform == "kaggle_dataset":
        return verify_kaggle(item, parsed)

    # 有 URL 但非已知平台
    if url and platform == "generic":
        return verify_generic_url(item, parsed)

    # paper 无 URL: 走 metadata
    if item.evidence_type == "paper":
        return verify_paper_metadata(item)

    # dataset / repo 无 URL: skipped
    if not url:
        return verify_skipped(item, reason=f"{item.evidence_type} 无 URL/handle, skipped")

    return verify_generic_url(item, parsed)


# ---------- 单条 / 批量入口 (§5.1) ---------- #


def verify_evidence_item(
    item: EvidenceItem,
    *,
    refresh: bool = False,
) -> VerificationResult:
    """单条验证. refresh=True 时强制重跑, 否则若已有 verified/partial/failed 跳过.

    手动验证过的 (verification_source=manual) 不被 refresh 覆盖.
    """

    if not refresh and item.verification_status not in ("unverified",) and item.verification_source != "manual":
        # 已验证, 直接返回
        return VerificationResult(
            evidence_id=item.evidence_id,
            evidence_type=item.evidence_type,
            ok=item.verification_status != "failed",
            url_verified=item.verification_status == "verified",
            verification_status=item.verification_status,
            verification_confidence=item.verification_confidence or 0.0,
            verification_source=item.verification_source,
            normalized_url=item.url,
            metadata=item.verification_metadata,
            warnings=item.verification_warnings,
            checked_at=item.verification_checked_at.isoformat() if item.verification_checked_at else _utcnow_iso(),
        )

    return choose_verifier(item)


def verify_project_evidence(
    project_id: str,
    pool_items: list[EvidenceItem],
    *,
    scope: str = "all",
    include_rejected: bool = False,
    include_pending: bool = True,
    refresh: bool = False,
) -> list[VerificationResult]:
    """批量验证 + 过滤 (§5.1)."""

    filtered = _filter_by_scope(pool_items, scope, include_rejected, include_pending)
    results: list[VerificationResult] = []
    for item in filtered:
        try:
            results.append(verify_evidence_item(item, refresh=refresh))
        except Exception as exc:  # noqa: BLE001
            results.append(VerificationResult(
                evidence_id=item.evidence_id,
                evidence_type=item.evidence_type,
                ok=False, url_verified=False,
                verification_status="failed",
                verification_confidence=0.0,
                verification_source="none",
                normalized_url=None,
                metadata={"error": f"{type(exc).__name__}"},
                warnings=[f"verifier 异常: {exc}"],
                checked_at=_utcnow_iso(),
            ))
    return results


def _filter_by_scope(
    items: list[EvidenceItem],
    scope: str,
    include_rejected: bool,
    include_pending: bool,
) -> list[EvidenceItem]:
    if not include_pending:
        items = [i for i in items if i.review_status != "pending"]
    if not include_rejected:
        items = [i for i in items if i.review_status != "rejected"]
    if scope == "all":
        return items
    if scope in ("paper", "dataset", "repo", "note"):
        return [i for i in items if i.evidence_type == scope]
    if scope == "assistant_intake":
        return [i for i in items if i.source_mode == "assistant_intake"]
    if scope == "user_preferred":
        return [i for i in items if i.workspace_lane == "user_preferred"]
    if scope == "selected":
        return [i for i in items if i.workspace_lane == "selected"]
    return items


def build_summary(project_id: str, results: list[VerificationResult]) -> VerificationSummary:
    verified = sum(1 for r in results if r.verification_status == "verified")
    partial = sum(1 for r in results if r.verification_status == "partial")
    failed = sum(1 for r in results if r.verification_status == "failed")
    skipped = sum(1 for r in results if r.verification_status == "skipped")

    confs = [r.verification_confidence for r in results if r.verification_confidence]
    avg = round(sum(confs) / len(confs), 3) if confs else 0.0

    high_risk = [
        r for r in results
        if r.verification_status == "failed"
        or (r.verification_status == "partial" and (r.verification_confidence or 0) < 0.4)
    ]

    return VerificationSummary(
        project_id=project_id,
        total=len(results),
        verified=verified,
        partial=partial,
        failed=failed,
        skipped=skipped,
        avg_confidence=avg,
        high_risk_items=high_risk[:10],
    )


# ---------- 把验证结果写回 EvidenceItem (§6) ---------- #


def apply_verification(item: EvidenceItem, result: VerificationResult) -> EvidenceItem:
    """用验证结果原地更新 item (返回新 EvidenceItem). 不改 review_status."""

    # Session 13: 根据 verification_source 标 validated_by_skill
    source_to_skill = {
        "arxiv": "paper-card",
        "github": "github-baseline",
        "huggingface": "dataset-validation",
        "kaggle": "dataset-validation",
        "http": "paper-card",
        "manual": None,  # 手动确认不强制标 skill
    }
    new_data = item.model_dump()
    new_data["url_verified"] = result.url_verified
    new_data["verification_status"] = result.verification_status
    new_data["verification_confidence"] = result.verification_confidence
    new_data["verification_source"] = result.verification_source
    new_data["verification_checked_at"] = datetime.fromisoformat(result.checked_at)
    new_data["verification_warnings"] = list(result.warnings)
    new_data["verification_metadata"] = dict(result.metadata)
    skill = source_to_skill.get(result.verification_source)
    if skill and result.verification_source != "manual":
        new_data["validated_by_skill"] = skill
    return EvidenceItem(**new_data)