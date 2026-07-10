"""Router unification package — Re6.2."""
from .model_policy import (
    ModelPolicy,
    TaskRole,
    ProviderModelRef,
    ALLOWED_MODEL_IDS,
    default_primary_for_role,
    create_default_policy,
)
from .envelope import ResponseEnvelope, TokenUsage
from .contracts import (
    StructuredOutputContract,
    ContractRegistry,
    get_contract_registry,
    reset_contract_registry,
)
from .repair import (
    execute_repair_strategy,
)
from .snapshot import (
    RunModelSnapshot,
    SnapshotStore,
    get_snapshot_store,
    reset_snapshot_store,
)
from .unified_router import (
    ContractResult,
    call_with_contract,
    call_json_contract,
)
