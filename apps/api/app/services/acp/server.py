"""Re4.4: ACP REST Server — routes capability calls to PaperAgent services.

Inspired by AutoResearchClaw mcp/server.py ResearchClawMCPServer (MIT):
  - handle_tool_call routing pattern
  - _validated_run_id path safety (adapted from _validated_run_dir)
  - unified error response on unknown tool / exception
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .registry import get_registry
from .errors import (
    internal_error,
    permission_denied,
    unknown_capability,
)

logger = logging.getLogger(__name__)


class ACPServer:
    """Routes ACP capability calls to PaperAgent services."""

    def __init__(self) -> None:
        self.registry = get_registry()

    def list_capabilities(self) -> list[dict[str, Any]]:
        return self.registry.list_all()

    def invoke(
        self,
        capability_name: str,
        params: dict[str, Any],
        has_write_permission: bool = False,
    ) -> dict[str, Any]:
        """Invoke a capability."""
        cap = self.registry.get(capability_name)
        if cap is None:
            return {"success": False, "error": unknown_capability(capability_name).model_dump()}

        if cap["permission"] == "write" and not has_write_permission:
            return {"success": False, "error": permission_denied(capability_name, "write").model_dump()}

        val_err = self.registry.validate_params(capability_name, params)
        if val_err:
            return {"success": False, "error": val_err.model_dump()}

        try:
            handler = self._get_handler(capability_name)
            if handler is None:
                return {"success": False, "error": {
                    "error_code": "NOT_IMPLEMENTED",
                    "message": f"Capability '{capability_name}' is declared but not yet implemented",
                    "capability": capability_name,
                }}
            result = handler(params)
            self._record_ledger(capability_name, cap["permission"], params)
            return {"success": True, "result": result}
        except Exception as exc:
            logger.error("ACP invoke %s failed: %s", capability_name, exc, exc_info=True)
            return {"success": False, "error": internal_error(capability_name, str(exc)).model_dump()}

    def _record_ledger(self, capability_name: str, permission: str, params: dict[str, Any]) -> None:
        """Record ACP invocation to RunLedger."""
        case_id = params.get("case_id")
        if not case_id:
            return
        try:
            from apps.api.app.services.run_state import RunLedger
            ledger = RunLedger(Path(f"tmp_re13_eval/{case_id}") / "acp_ledger.jsonl")
            ledger.append("acp_invoke", {
                "capability": capability_name,
                "permission": permission,
                "params_keys": list(params.keys()),
            })
        except Exception:
            pass

    def _get_handler(self, name: str):
        handlers = {
            "list_cases": self._h_list_cases,
            "get_run_status": self._h_get_run_status,
            "get_evidence_graph": self._h_get_evidence_graph,
            "get_papers": self._h_get_papers,
            "get_work_packages": self._h_get_work_packages,
            "get_feasibility": self._h_get_feasibility,
            "get_review": self._h_get_review,
            "get_innovation": self._h_get_innovation,
            "search_literature": self._h_search_literature,
            "upload_paper": self._h_upload_paper,
            "ingest_pdf": self._h_ingest_pdf,
            "query_rag": self._h_query_rag,
            "get_knowledge_graph": self._h_get_knowledge_graph,
        }
        return handlers.get(name)

    # ===== READ handlers =====

    def _h_list_cases(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _list_cases_impl
        return _list_cases_impl()

    def _h_get_run_status(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _get_status_impl
        return _get_status_impl(params["case_id"])

    def _h_get_evidence_graph(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _get_evidence_graph_impl
        return _get_evidence_graph_impl(params["case_id"])

    def _h_get_papers(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _list_user_papers_impl
        return _list_user_papers_impl(params["case_id"])

    def _h_get_work_packages(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _get_work_packages_impl
        return _get_work_packages_impl(params["case_id"])

    def _h_get_feasibility(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _get_feasibility_impl
        return _get_feasibility_impl(params["case_id"])

    def _h_get_review(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _get_review_impl
        return _get_review_impl(params["case_id"])

    def _h_get_innovation(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _get_innovation_impl
        return _get_innovation_impl(params["case_id"])

    # ===== WRITE handlers =====

    def _h_search_literature(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _submit_topic_impl
        return _submit_topic_impl(params["topic"], params.get("case_id"))

    def _h_upload_paper(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _upload_paper_impl
        return _upload_paper_impl(params["case_id"], params)

    # ===== RAG handlers (Re4.5) =====

    def _h_ingest_pdf(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.services.rag.pdf_extractor import extract_pdf_from_url
        from apps.api.app.services.rag.chunker import chunk_text
        from apps.api.app.services.rag.indexer import merge_index

        case_id = params.get("case_id", "global")
        pdf_url = params["pdf_url"]

        result = extract_pdf_from_url(pdf_url)
        if result["status"] != "ok":
            return result

        chunks = chunk_text(result["text"])
        if not chunks:
            return {"status": "extraction_failed", "reason": "no chunks generated"}

        return merge_index(case_id, chunks, source=pdf_url)

    def _h_query_rag(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.services.rag.indexer import load_index
        from apps.api.app.services.rag.qa import answer_question

        case_id = params.get("case_id", "global")
        question = params["question"]

        index = load_index(case_id)
        if index is None:
            return {"error": "no RAG index found", "case_id": case_id}

        return answer_question(question, index, case_id)

    def _h_get_knowledge_graph(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.services.rag.indexer import load_index
        from apps.api.app.services.rag.knowledge_graph import build_knowledge_graph

        case_id = params["case_id"]
        index = load_index(case_id)
        if index is None:
            return {"nodes": [], "edges": [], "n_nodes": 0, "n_edges": 0}

        return build_knowledge_graph(index, case_id)


_server: ACPServer | None = None


def get_acp_server() -> ACPServer:
    global _server
    if _server is None:
        _server = ACPServer()
    return _server
