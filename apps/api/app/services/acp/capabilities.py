"""Re4.4: ACP capability declarations.

Each capability declares name, description, permission, input_schema,
output_schema, error_code, and example.

Inspired by AutoResearchClaw mcp/tools.py TOOL_DEFINITIONS (MIT, A-level reuse).
"""
from __future__ import annotations

from typing import Any

CAPABILITIES: list[dict[str, Any]] = [
    # ===== READ capabilities =====
    {
        "name": "list_cases",
        "description": "List all research cases with their status.",
        "permission": "read",
        "input_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "object", "properties": {"cases": {"type": "array"}, "n": {"type": "integer"}}},
        "error_code": "E44_LIST_CASES",
        "example": {"input": {}, "output": {"cases": [{"case_id": "re41-verify-001"}], "n": 1}},
    },
    {
        "name": "get_run_status",
        "description": "Get the current status of a research run.",
        "permission": "read",
        "input_schema": {"type": "object", "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]},
        "output_schema": {"type": "object", "properties": {"status": {"type": "string"}, "current_node": {"type": "string"}}},
        "error_code": "E44_GET_STATUS",
        "example": {"input": {"case_id": "re41-verify-001"}, "output": {"status": "done"}},
    },
    {
        "name": "get_evidence_graph",
        "description": "Get the evidence graph (nodes + edges) for a case.",
        "permission": "read",
        "input_schema": {"type": "object", "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]},
        "output_schema": {"type": "object", "properties": {"nodes": {"type": "array"}, "edges": {"type": "array"}}},
        "error_code": "E44_GET_GRAPH",
        "example": {"input": {"case_id": "re41-verify-001"}, "output": {"nodes": [], "edges": []}},
    },
    {
        "name": "get_papers",
        "description": "Get verified papers and user-uploaded papers for a case.",
        "permission": "read",
        "input_schema": {"type": "object", "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]},
        "output_schema": {"type": "object", "properties": {"papers": {"type": "array"}, "n": {"type": "integer"}}},
        "error_code": "E44_GET_PAPERS",
        "example": {"input": {"case_id": "re41-verify-001"}, "output": {"papers": [], "n": 0}},
    },
    {
        "name": "get_work_packages",
        "description": "Get work packages with dependency DAG for a case.",
        "permission": "read",
        "input_schema": {"type": "object", "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]},
        "output_schema": {"type": "object", "properties": {"work_packages": {"type": "array"}, "dag": {"type": "object"}}},
        "error_code": "E44_GET_WP",
        "example": {"input": {"case_id": "re41-verify-001"}, "output": {"work_packages": [], "dag": {}}},
    },
    {
        "name": "get_feasibility",
        "description": "Get the feasibility report for a case.",
        "permission": "read",
        "input_schema": {"type": "object", "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]},
        "output_schema": {"type": "object"},
        "error_code": "E44_GET_FEAS",
        "example": {"input": {"case_id": "re41-verify-001"}, "output": {"score": 85, "verdict": "feasible"}},
    },
    {
        "name": "get_review",
        "description": "Get the final review report for a case.",
        "permission": "read",
        "input_schema": {"type": "object", "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]},
        "output_schema": {"type": "object"},
        "error_code": "E44_GET_REVIEW",
        "example": {"input": {"case_id": "re41-verify-001"}, "output": {"review_status": "ACCEPT"}},
    },
    {
        "name": "get_innovation",
        "description": "Get innovation points with evidence binding for a case.",
        "permission": "read",
        "input_schema": {"type": "object", "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]},
        "output_schema": {"type": "object"},
        "error_code": "E44_GET_INNOV",
        "example": {"input": {"case_id": "re41-verify-001"}, "output": {"innovation_points": []}},
    },
    # ===== WRITE capabilities =====
    {
        "name": "search_literature",
        "description": "Submit a topic for background research graph run.",
        "permission": "write",
        "input_schema": {
            "type": "object",
            "properties": {"topic": {"type": "string"}, "case_id": {"type": "string"}},
            "required": ["topic"],
        },
        "output_schema": {"type": "object", "properties": {"case_id": {"type": "string"}, "status": {"type": "string"}}},
        "error_code": "E44_SEARCH_LIT",
        "example": {"input": {"topic": "基于YOLO的钢材表面缺陷检测"}, "output": {"case_id": "abc123", "status": "running"}},
    },
    {
        "name": "upload_paper",
        "description": "Upload a user-known paper (enriched via Crossref/arXiv).",
        "permission": "write",
        "input_schema": {
            "type": "object",
            "properties": {"case_id": {"type": "string"}, "title": {"type": "string"}, "doi": {"type": "string"}, "arxiv_id": {"type": "string"}},
            "required": ["case_id"],
        },
        "output_schema": {"type": "object", "properties": {"paper": {"type": "object"}, "stored": {"type": "boolean"}}},
        "error_code": "E44_UPLOAD_PAPER",
        "example": {"input": {"case_id": "abc123", "doi": "10.1234/example"}, "output": {"stored": True}},
    },
    # ===== RAG capabilities (Re4.5 — now implemented) =====
    {
        "name": "ingest_pdf",
        "description": "Ingest a PDF for full-text indexing. Downloads, extracts text, chunks, and builds TF-IDF index.",
        "permission": "write",
        "input_schema": {"type": "object", "properties": {"case_id": {"type": "string"}, "pdf_url": {"type": "string"}}, "required": ["pdf_url"]},
        "output_schema": {"type": "object"},
        "error_code": "E44_INGEST_PDF",
        "example": {"input": {"pdf_url": "https://arxiv.org/pdf/2401.00001"}, "output": {"status": "ok", "n_chunks": 42}},
    },
    {
        "name": "query_rag",
        "description": "Query the RAG system for evidence-grounded answers with chunk citations.",
        "permission": "read",
        "input_schema": {"type": "object", "properties": {"case_id": {"type": "string"}, "question": {"type": "string"}}, "required": ["question"]},
        "output_schema": {"type": "object"},
        "error_code": "E44_QUERY_RAG",
        "example": {"input": {"question": "What datasets are used?"}, "output": {"answer": "...", "cited_chunks": ["chunk-0"]}},
    },
    {
        "name": "get_knowledge_graph",
        "description": "Get the knowledge graph (paper/dataset/method nodes + edges) for a case.",
        "permission": "read",
        "input_schema": {"type": "object", "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]},
        "output_schema": {"type": "object"},
        "error_code": "E44_GET_KG",
        "example": {"input": {"case_id": "abc123"}, "output": {"nodes": [], "edges": []}},
    },
    {
        "name": "review_human_gate",
        "description": "Submit a human gate review decision. [Future — not yet implemented]",
        "permission": "write",
        "input_schema": {
            "type": "object",
            "properties": {"case_id": {"type": "string"}, "decision": {"type": "string", "enum": ["approve", "reject", "modify"]}},
            "required": ["case_id", "decision"],
        },
        "output_schema": {"type": "object"},
        "error_code": "E44_REVIEW_GATE",
        "example": {"input": {"case_id": "abc123", "decision": "approve"}, "output": {"status": "NOT_IMPLEMENTED"}},
    },
]


def get_capability(name: str) -> dict[str, Any] | None:
    for cap in CAPABILITIES:
        if cap["name"] == name:
            return cap
    return None


def list_capability_names() -> list[str]:
    return [c["name"] for c in CAPABILITIES]
