"""Compatibility exports for the academic-tailoring policy.

The release-blocking rules live in :mod:`paperagent.academic_tailoring`.
This module performs no import-time mutation.
"""

from __future__ import annotations

from paperagent.academic_tailoring import compose_tailored_research_proposal

__all__ = ["compose_tailored_research_proposal"]
