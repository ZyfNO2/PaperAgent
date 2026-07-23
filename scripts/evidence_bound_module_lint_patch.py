from __future__ import annotations

from pathlib import Path

from evidence_bound_module_prepatch import replace_exact

ADAPTER = Path("src/paperagent/claw_benchmark_adapter.py")
METHOD_DESIGN = Path("src/paperagent/method_design_draft.py")
METHOD_NODE = Path("src/paperagent/nodes/method_design.py")


def patch_import_order() -> None:
    replace_exact(
        ADAPTER,
        '''from paperagent.academic_methodology import ExperimentArmType
from paperagent.module_compatibility import (
    ModuleCompatibilityResult,
    evaluate_module_compatibility,
)
from paperagent.claw_academic_benchmark import (
''',
        '''from paperagent.academic_methodology import ExperimentArmType
from paperagent.claw_academic_benchmark import (
''',
        "adapter import prefix",
    )
    replace_exact(
        ADAPTER,
        '''    ObservedDecision,
)
from paperagent.schemas.base import FrozenModel
''',
        '''    ObservedDecision,
)
from paperagent.module_compatibility import (
    ModuleCompatibilityResult,
    evaluate_module_compatibility,
)
from paperagent.schemas.base import FrozenModel
''',
        "adapter module compatibility import order",
    )
    replace_exact(
        METHOD_DESIGN,
        '''from paperagent.academic_methodology import (
    EvidenceItem as MethodEvidenceItem,
)
from paperagent.schemas.base import FrozenModel
''',
        '''from paperagent.academic_methodology import (
    EvidenceItem as MethodEvidenceItem,
)
from paperagent.module_compatibility import (
    MODULE_EVIDENCE_RELATIONS,
    evaluate_module_compatibility,
)
from paperagent.schemas.base import FrozenModel
''',
        "method design module import order",
    )
    replace_exact(
        METHOD_DESIGN,
        '''from paperagent.schemas.method import (
    AblationPlan,
    BaselineProposal,
    ExperimentPlan,
    IntegrationContract,
    MethodModule,
    MethodProposal,
)
from paperagent.module_compatibility import (
    MODULE_EVIDENCE_RELATIONS,
    evaluate_module_compatibility,
)
from paperagent.scientific_readiness import derive_scientific_readiness
''',
        '''from paperagent.schemas.method import (
    AblationPlan,
    BaselineProposal,
    ExperimentPlan,
    IntegrationContract,
    MethodModule,
    MethodProposal,
)
from paperagent.scientific_readiness import derive_scientific_readiness
''',
        "method design old module import position",
    )


def patch_requirement_lines() -> None:
    replace_exact(
        METHOD_NODE,
        '''_MODULE_CONTRACT_REQUIREMENTS = (
    "Use one independently retrieved accepted module-lane paper that is distinct from the baseline.",
    "Bind the module name and original role to the selected paper title, summary, or verified metadata.",
    "State the exact baseline insertion point; do not use generic phrases such as selected representation stage.",
    "Specify input and output semantics and explicit tensor ranks/shapes, or an explicit projection path.",
    "Specify normalization and masking behavior for the target task rather than inheriting unspecified defaults.",
    "Specify gradient path, trainable parameters, frozen parameters, loss terms, and numeric loss weighting separately.",
    "Defer the module design when any required interface contract is unsupported by accepted evidence.",
)
''',
        '''_MODULE_CONTRACT_REQUIREMENTS = (
    "Use one independently retrieved accepted module-lane paper that is distinct "
    "from the baseline.",
    "Bind the module name and original role to the selected paper title, summary, "
    "or verified metadata.",
    "State the exact baseline insertion point; do not use generic phrases such as "
    "selected representation stage.",
    "Specify input and output semantics and explicit tensor ranks/shapes, or an "
    "explicit projection path.",
    "Specify normalization and masking behavior for the target task rather than "
    "inheriting unspecified defaults.",
    "Specify gradient path, trainable parameters, frozen parameters, loss terms, "
    "and numeric loss weighting separately.",
    "Defer the module design when any required interface contract is unsupported "
    "by accepted evidence.",
)
''',
        "method node contract requirements",
    )


def apply_lint_repairs() -> None:
    patch_import_order()
    patch_requirement_lines()


if __name__ == "__main__":
    apply_lint_repairs()
