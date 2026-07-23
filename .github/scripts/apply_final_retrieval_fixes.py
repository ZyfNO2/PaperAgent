from pathlib import Path

path = Path("src/paperagent/academic_methodology.py")
text = path.read_text(encoding="utf-8")
old = '''    critical_failures = tuple(
        item for item in checks if not item.passed and item.severity is AuditSeverity.CRITICAL
    )
    blocking_failures = tuple(
        item
        for item in checks
        if not item.passed and item.severity in {AuditSeverity.CRITICAL, AuditSeverity.ERROR}
    )
    reported_failures = tuple(item for item in checks if not item.passed)
    if critical_failures:
        verdict = AuditVerdict.NO_GO
    elif blocking_failures:
        verdict = AuditVerdict.REVISE
    else:
        verdict = AuditVerdict.GO
'''
new = '''    reported_failures = tuple(item for item in checks if not item.passed)
    verdict = MethodAuditReport._verdict_from_checks(tuple(checks))
'''
if text.count(old) != 1:
    raise SystemExit("expected exactly one duplicated verdict block")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
