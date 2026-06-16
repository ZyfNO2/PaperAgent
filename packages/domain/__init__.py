"""domain package re-exports."""

from .models import (
    DegreeType,
    GoalLevel,
    InheritedResource,
    IntakeRating,
    MissingField,
    ProjectIntake,
    RiskLevel,
    StudentResourceProfile,
    ValidationOutcome,
    compute_intake_rating,
    derive_missing_fields,
    validate_intake,
)
from .phase2_models import (
    DecompositionRating,
    RiskTerm,
    ThesisMapping,
    TopicSpec,
    WorkPackageDraft,
)
from .phase3_models import (
    BaselineProbe,
    MaturityProbe,
    QueryLayer,
    SearchQueryPlan,
    SourceTarget,
    ThesisTemplateProbe,
    WorkPackageQuery,
)
from .phase4_models import (
    BaselineCandidate,
    DatasetCandidate,
    EvidenceLedger,
    ExperimentTemplate,
    MetricSet,
    PaperEvidence,
    SourceTag,
    ThesisTemplate,
)
from .phase5_models import (
    DimensionKey,
    DimensionScore,
    PivotCandidate,
    RiskEvaluation,
    RiskScore,
)

__all__ = [
    "DegreeType",
    "GoalLevel",
    "InheritedResource",
    "IntakeRating",
    "MissingField",
    "ProjectIntake",
    "RiskLevel",
    "StudentResourceProfile",
    "ValidationOutcome",
    "compute_intake_rating",
    "derive_missing_fields",
    "validate_intake",
    # Phase 02
    "DecompositionRating",
    "RiskTerm",
    "ThesisMapping",
    "TopicSpec",
    "WorkPackageDraft",
    # Phase 03
    "BaselineProbe",
    "MaturityProbe",
    "QueryLayer",
    "SearchQueryPlan",
    "SourceTarget",
    "ThesisTemplateProbe",
    "WorkPackageQuery",
    # Phase 04
    "BaselineCandidate",
    "DatasetCandidate",
    "EvidenceLedger",
    "ExperimentTemplate",
    "MetricSet",
    "PaperEvidence",
    "SourceTag",
    "ThesisTemplate",
    # Phase 05
    "DimensionKey",
    "DimensionScore",
    "PivotCandidate",
    "RiskEvaluation",
    "RiskScore",
]
