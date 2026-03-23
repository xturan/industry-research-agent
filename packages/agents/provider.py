from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from packages.agents.evidence_judge import EvidenceJudgeAgent
from packages.agents.interfaces import (
    EvidenceJudgeAgentContract,
    OpponentAgentContract,
    RiskAnalystAgentContract,
    SupervisorAgentContract,
    ThesisBuilderAgentContract,
)
from packages.agents.llm_agents import (
    LlmCallSettings,
    LlmEvidenceJudgeAgent,
    LlmOpponentAgent,
    LlmRiskAnalystAgent,
    LlmRuntimeState,
    LlmSupervisorAgent,
    LlmThesisBuilderAgent,
)
from packages.agents.opponent import OpponentAgent
from packages.agents.risk_analyst import RiskAnalystAgent
from packages.agents.schemas import RESEARCH_MODEL_STEPS, ResearchMode, ResearchProvider
from packages.agents.supervisor import SupervisorAgent
from packages.agents.thesis_builder import ThesisBuilderAgent
from packages.core.config import get_settings
from packages.providers import DeepSeekProviderClient, ProviderConfigError


class AgentProvider(Protocol):
    mode: ResearchMode
    provider_name: ResearchProvider
    model: str | None
    thinking_enabled: bool
    debug_reasoning: bool
    notes: list[str]
    supervisor: SupervisorAgentContract
    thesis_builder: ThesisBuilderAgentContract
    opponent: OpponentAgentContract
    evidence_judge: EvidenceJudgeAgentContract
    risk_analyst: RiskAnalystAgentContract

    def pop_step_metadata(self, step_name: str) -> dict[str, Any] | None:
        """Return provider metadata for a completed step, if available."""


@dataclass(slots=True)
class DeterministicAgentProvider:
    mode: ResearchMode = ResearchMode.MOCK
    provider_name: ResearchProvider = ResearchProvider.MOCK
    model: str | None = None
    thinking_enabled: bool = False
    debug_reasoning: bool = False
    notes: list[str] = field(default_factory=list)
    supervisor: SupervisorAgent = field(default_factory=SupervisorAgent)
    thesis_builder: ThesisBuilderAgent = field(default_factory=ThesisBuilderAgent)
    opponent: OpponentAgent = field(default_factory=OpponentAgent)
    evidence_judge: EvidenceJudgeAgent = field(default_factory=EvidenceJudgeAgent)
    risk_analyst: RiskAnalystAgent = field(default_factory=RiskAnalystAgent)

    def pop_step_metadata(self, step_name: str) -> dict[str, Any] | None:
        return None


@dataclass(slots=True)
class LlmAgentProvider:
    mode: ResearchMode
    provider_name: ResearchProvider
    model: str | None
    thinking_enabled: bool
    debug_reasoning: bool
    notes: list[str]
    supervisor: LlmSupervisorAgent
    thesis_builder: LlmThesisBuilderAgent
    opponent: LlmOpponentAgent
    evidence_judge: LlmEvidenceJudgeAgent
    risk_analyst: LlmRiskAnalystAgent
    runtime_state: LlmRuntimeState

    def pop_step_metadata(self, step_name: str) -> dict[str, Any] | None:
        return self.runtime_state.pop(step_name)


@dataclass(slots=True)
class ProviderResolution:
    provider: AgentProvider
    resolved_mode: ResearchMode
    resolved_provider: ResearchProvider
    resolved_model: str | None
    resolved_step_models: dict[str, str]
    thinking_enabled: bool
    debug_reasoning: bool
    notes: list[str]


def resolve_provider(
    *,
    mode: ResearchMode,
    provider: ResearchProvider | None = None,
    model: str | None = None,
    step_models: dict[str, str] | None = None,
    enable_thinking: bool | None = None,
    debug_reasoning: bool = False,
) -> ProviderResolution:
    settings = get_settings()
    if mode == ResearchMode.MOCK:
        deterministic = DeterministicAgentProvider(mode=ResearchMode.MOCK)
        return ProviderResolution(
            provider=deterministic,
            resolved_mode=ResearchMode.MOCK,
            resolved_provider=ResearchProvider.MOCK,
            resolved_model=None,
            resolved_step_models={},
            thinking_enabled=False,
            debug_reasoning=False,
            notes=[],
        )

    requested_provider = provider or _default_llm_provider(settings.llm_provider)
    if requested_provider != ResearchProvider.DEEPSEEK:
        fallback = DeterministicAgentProvider(
            mode=ResearchMode.MOCK,
            notes=[
                f"Unsupported llm provider '{requested_provider.value}', fell back to mock mode."
            ],
        )
        return ProviderResolution(
            provider=fallback,
            resolved_mode=ResearchMode.MOCK,
            resolved_provider=ResearchProvider.MOCK,
            resolved_model=None,
            resolved_step_models={},
            thinking_enabled=False,
            debug_reasoning=False,
            notes=fallback.notes,
        )

    thinking_flag = (
        enable_thinking if enable_thinking is not None else settings.deepseek_enable_thinking
    )
    chosen_model = model or settings.deepseek_research_model
    resolved_step_models = _resolve_step_models(
        default_model=chosen_model,
        settings=settings,
        request_step_models=step_models,
    )
    json_client = DeepSeekProviderClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=chosen_model,
        timeout_seconds=settings.deepseek_timeout_seconds,
        max_retries=settings.deepseek_max_retries,
        max_tokens=settings.deepseek_max_tokens,
        store_reasoning_content=settings.deepseek_store_reasoning_content,
    )
    runtime_state = LlmRuntimeState()
    call_settings = LlmCallSettings(
        provider_name=ResearchProvider.DEEPSEEK.value,
        model=chosen_model,
        enable_thinking=thinking_flag,
        debug_reasoning=debug_reasoning,
        allow_store_reasoning=settings.deepseek_store_reasoning_content,
        step_models=resolved_step_models,
        retry_attempts=1,
        retry_backoff_seconds=1.0,
    )

    llm_provider = LlmAgentProvider(
        mode=ResearchMode.LLM,
        provider_name=ResearchProvider.DEEPSEEK,
        model=chosen_model,
        thinking_enabled=thinking_flag,
        debug_reasoning=debug_reasoning,
        notes=[],
        supervisor=LlmSupervisorAgent(
            step_name="supervisor_intake",
            json_client=json_client,
            settings=call_settings,
            runtime_state=runtime_state,
        ),
        thesis_builder=LlmThesisBuilderAgent(
            step_name="thesis_builder",
            json_client=json_client,
            settings=call_settings,
            runtime_state=runtime_state,
        ),
        opponent=LlmOpponentAgent(
            step_name="opponent",
            json_client=json_client,
            settings=call_settings,
            runtime_state=runtime_state,
        ),
        evidence_judge=LlmEvidenceJudgeAgent(
            step_name="evidence_judge",
            json_client=json_client,
            settings=call_settings,
            runtime_state=runtime_state,
        ),
        risk_analyst=LlmRiskAnalystAgent(
            step_name="risk_analyst",
            json_client=json_client,
            settings=call_settings,
            runtime_state=runtime_state,
        ),
        runtime_state=runtime_state,
    )
    return ProviderResolution(
        provider=llm_provider,
        resolved_mode=ResearchMode.LLM,
        resolved_provider=ResearchProvider.DEEPSEEK,
        resolved_model=chosen_model,
        resolved_step_models=resolved_step_models,
        thinking_enabled=thinking_flag,
        debug_reasoning=debug_reasoning,
        notes=[],
    )


def _default_llm_provider(value: str) -> ResearchProvider:
    normalized = value.strip().lower()
    if normalized in {"", "mock"}:
        return ResearchProvider.MOCK
    if normalized == ResearchProvider.DEEPSEEK.value:
        return ResearchProvider.DEEPSEEK
    raise ProviderConfigError(f"Unsupported LLM_PROVIDER value: {value}")


def _resolve_step_models(
    *,
    default_model: str,
    settings: Any,
    request_step_models: dict[str, str] | None,
) -> dict[str, str]:
    resolved = {step_name: default_model for step_name in RESEARCH_MODEL_STEPS}

    config_overrides = {
        "supervisor_intake": settings.deepseek_model_supervisor_intake,
        "thesis_builder": settings.deepseek_model_thesis_builder,
        "opponent": settings.deepseek_model_opponent,
        "evidence_judge": settings.deepseek_model_evidence_judge,
        "risk_analyst": settings.deepseek_model_risk_analyst,
        "synthesize_memo": settings.deepseek_model_synthesize_memo,
    }
    for step_name, model_name in config_overrides.items():
        if model_name and model_name.strip():
            resolved[step_name] = model_name.strip()

    if request_step_models:
        for step_name, model_name in request_step_models.items():
            if step_name in resolved:
                resolved[step_name] = model_name.strip()
    return resolved
