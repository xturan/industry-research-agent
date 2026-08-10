"""G2 Capability / Provider Plane — capability-first provider routing.

G2 回答：Run 内部需要 LLM/Search 时，到底调用谁、能否调用、失败以后怎么办。

分层：
- G2.1 Capability Contract & Registry（✅ Accepted：资格判断，不调用真实 API）
- G2.2 Deterministic Routing（RoutingPlan + Router + Adapter Registry + SEARCH Shadow）
- G2.3 Concurrency Budget
- G2.4 Circuit Breaker & Runtime Fallback
- G2.5 Provider Metrics + Acceptance
- G2.6 Embed / Rerank Integration
- G2.7 Provider-plane Acceptance
"""

from packages.capability_gateway.adapters import (
    CallableAdapter,
    CapabilityAdapter,
    CapabilityInvocation,
    CapabilityResult,
    ProviderAdapterRegistry,
    RoutingInvoker,
    build_llm_adapter_registry,
    build_search_adapter_registry,
)
from packages.capability_gateway.budget import (
    BudgetWaitCancelled,
    ConcurrencyBudget,
    InProcessConcurrencyBudget,
    PostgresLeaseConcurrencyBudget,
    ProviderCapacityExhaustedError,
    ProviderConcurrencyPolicy,
    ProviderPermit,
    create_concurrency_tables,
    policy_from_instance,
)
from packages.capability_gateway.circuit import (
    AVAILABILITY_FAILURES,
    CircuitBreaker,
    CircuitStateRecord,
    CircuitStateStore,
    FailureClassifier,
    InMemoryCircuitStateStore,
    PostgresCircuitStateStore,
    ProviderFailureClass,
    create_circuit_tables,
)
from packages.capability_gateway.fallback import FallbackPolicy
from packages.capability_gateway.health import ProviderHealthSnapshot, build_health_snapshot
from packages.capability_gateway.health_shadow import (
    HealthRoutingShadow,
    build_health_aware_providers,
    compare_health_routing,
)
from packages.capability_gateway.llm_service import (
    LLMCapabilityService,
    LLMShadowResult,
    build_gateway_aware_llm_client,
    build_llm_capability_service,
)
from packages.capability_gateway.llm_tasks import (
    FALLBACK_ALLOWED_TASK_TYPES,
    LLM_TASK_PROFILES,
    STRICT_TASK_TYPES,
    LLMTaskProfile,
    LLMTaskType,
    get_llm_profile,
    legacy_llm_provider,
    legacy_primary_instance,
    legacy_provider_for_task,
    llm_capability_request,
)
from packages.capability_gateway.plan import RoutingPlan, RoutingStep, RoutingTrace
from packages.capability_gateway.registry import CapabilityRegistry, default_registry
from packages.capability_gateway.router import (
    CapabilityRouter,
    llm_policy_for_task,
    llm_routing_mode,
    search_routing_mode,
)
from packages.capability_gateway.schemas import (
    CapabilityDecision,
    CapabilityInstance,
    CapabilityRequest,
    CapabilityRole,
    CapabilityType,
    CircuitState,
    CostPolicy,
    RoutingPolicy,
)
from packages.capability_gateway.search_service import (
    SearchCapabilityService,
    build_gateway_aware_search_provider,
    search_capability_request,
)
from packages.capability_gateway.shadow import (
    RoutingShadowReport,
    shadow_compare_from_settings,
    shadow_compare_search,
)
from packages.capability_gateway.telemetry import (
    InMemoryProviderAttemptRecorder,
    PostgresProviderAttemptRecorder,
    ProviderAttemptRecord,
    ProviderAttemptRecorder,
    create_attempt_tables,
)

__all__ = [
    # contract
    "CapabilityType",
    "CapabilityInstance",
    "CapabilityRequest",
    "CapabilityDecision",
    "CapabilityRole",
    "CircuitState",
    "RoutingPolicy",
    "CostPolicy",
    # registry
    "CapabilityRegistry",
    "default_registry",
    # router / plan
    "CapabilityRouter",
    "RoutingPlan",
    "RoutingStep",
    "RoutingTrace",
    "llm_policy_for_task",
    "search_routing_mode",
    "llm_routing_mode",
    # adapters / invoker
    "CapabilityAdapter",
    "CapabilityInvocation",
    "CapabilityResult",
    "ProviderAdapterRegistry",
    "CallableAdapter",
    "RoutingInvoker",
    "build_search_adapter_registry",
    "build_llm_adapter_registry",
    # shadow
    "RoutingShadowReport",
    "shadow_compare_search",
    "shadow_compare_from_settings",
    # search facade (G2.2b)
    "SearchCapabilityService",
    "build_gateway_aware_search_provider",
    "search_capability_request",
    # g2.3 concurrency budget
    "ConcurrencyBudget",
    "ProviderConcurrencyPolicy",
    "ProviderPermit",
    "ProviderCapacityExhaustedError",
    "BudgetWaitCancelled",
    "InProcessConcurrencyBudget",
    "PostgresLeaseConcurrencyBudget",
    "create_concurrency_tables",
    "policy_from_instance",
    # g2.4 circuit + fallback
    "ProviderFailureClass",
    "AVAILABILITY_FAILURES",
    "FailureClassifier",
    "CircuitState",
    "CircuitStateRecord",
    "CircuitStateStore",
    "InMemoryCircuitStateStore",
    "PostgresCircuitStateStore",
    "CircuitBreaker",
    "create_circuit_tables",
    "FallbackPolicy",
    # g2.5 observability + health
    "ProviderAttemptRecord",
    "ProviderAttemptRecorder",
    "InMemoryProviderAttemptRecorder",
    "PostgresProviderAttemptRecorder",
    "create_attempt_tables",
    "ProviderHealthSnapshot",
    "build_health_snapshot",
    "HealthRoutingShadow",
    "build_health_aware_providers",
    "compare_health_routing",
    # llm taxonomy + shadow service (G2.2c)
    "LLMTaskType",
    "LLMTaskProfile",
    "LLM_TASK_PROFILES",
    "FALLBACK_ALLOWED_TASK_TYPES",
    "STRICT_TASK_TYPES",
    "get_llm_profile",
    "legacy_llm_provider",
    "legacy_primary_instance",
    "legacy_provider_for_task",
    "llm_capability_request",
    "LLMCapabilityService",
    "LLMShadowResult",
    "build_llm_capability_service",
    "build_gateway_aware_llm_client",
]

