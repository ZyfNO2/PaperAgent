from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one match in {path}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/paperagent/academic_methodology.py",
    '''        has_error = any(not item.passed and item.severity is AuditSeverity.ERROR for item in checks)
        if has_critical:
            return AuditVerdict.NO_GO
        if has_error:
            return AuditVerdict.REVISE
        return AuditVerdict.GO
''',
    '''        has_error = any(not item.passed and item.severity is AuditSeverity.ERROR for item in checks)
        has_warning = any(
            not item.passed and item.severity is AuditSeverity.WARNING for item in checks
        )
        if has_critical:
            return AuditVerdict.NO_GO
        if has_error or has_warning:
            return AuditVerdict.REVISE
        return AuditVerdict.GO
''',
)
replace_once(
    "tests/literature/test_adaptive_search_edges.py",
    '    assert service.calls == ["openalex", "semantic_scholar", "arxiv", "tavily"]\n'
    '    assert len(candidates) == 1\n',
    '    assert service.calls == ["openalex", "semantic_scholar", "tavily"]\n'
    '    assert len(candidates) == 1\n',
)
replace_once(
    "tests/providers/test_openai_llm_unit.py",
    '    assert exc_info.value.code == "LLM_PROVIDER_HTTP_ERROR"\n'
    '    assert exc_info.value.retryable is False\n',
    '    assert exc_info.value.code == "LLM_AUTHENTICATION"\n'
    '    assert exc_info.value.retryable is False\n',
)
replace_once(
    "tests/providers/test_openai_llm_unit.py",
    '    assert calls == 2\n'
    '    assert exc_info.value.code == "LLM_PROVIDER_HTTP_ERROR"\n'
    '    assert exc_info.value.retryable is True\n',
    '    assert calls == 2\n'
    '    assert exc_info.value.code == "LLM_CONNECT"\n'
    '    assert exc_info.value.retryable is True\n',
)
