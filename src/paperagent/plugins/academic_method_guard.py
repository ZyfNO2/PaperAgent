"""Compatibility exports for the academic-method plugin policy.

The audit rules and ``propose`` operation live in
:mod:`paperagent.plugins.academic_method`. This module performs no rebinding.
"""

from __future__ import annotations

from paperagent.plugins.academic_method import (
    AcademicMethodTailoringPlugin,
    audit_method_plan,
)

__all__ = ["AcademicMethodTailoringPlugin", "audit_method_plan"]
