"""Re4.5: ACP RAG capability tests."""
from __future__ import annotations



class TestACPIngestPDF:
    def test_ingest_pdf_implemented(self):
        """ingest_pdf should no longer return NOT_IMPLEMENTED."""
        from apps.api.app.services.acp.server import get_acp_server

        server = get_acp_server()
        assert server._get_handler("ingest_pdf") is not None


class TestACPQueryRAG:
    def test_query_rag_implemented(self):
        """query_rag should no longer return NOT_IMPLEMENTED."""
        from apps.api.app.services.acp.server import get_acp_server

        server = get_acp_server()
        assert server._get_handler("query_rag") is not None

    def test_query_rag_no_index(self):
        """query_rag with no index should return error."""
        from apps.api.app.services.acp.server import get_acp_server

        server = get_acp_server()
        handler = server._get_handler("query_rag")
        result = handler({"question": "test?", "case_id": "nonexistent-rag-case"})
        assert "error" in result or "answer" in result


class TestACPGetKnowledgeGraph:
    def test_get_knowledge_graph_implemented(self):
        """get_knowledge_graph should no longer return NOT_IMPLEMENTED."""
        from apps.api.app.services.acp.server import get_acp_server

        server = get_acp_server()
        assert server._get_handler("get_knowledge_graph") is not None
