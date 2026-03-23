from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from packages.agents.evidence_judge import EvidenceJudgeAgent
from packages.agents.opponent import OpponentAgent
from packages.agents.risk_analyst import RiskAnalystAgent
from packages.agents.schemas import (
    EvidenceJudgeOutput,
    FinalResearchMemo,
    ObjectionItem,
    OpponentOutput,
    ResearchAnalyzeRequest,
    RiskAnalystOutput,
    RiskItem,
    SupervisorIntake,
    ThesisBuilderOutput,
    ThesisItem,
)
from packages.agents.supervisor import SupervisorAgent
from packages.agents.thesis_builder import ThesisBuilderAgent
from packages.providers import JsonProviderClient, ProviderParseError, ProviderRetryableError
from packages.rag.schemas import EvidenceBundle
from packages.registry.research_prompts import (
    EVIDENCE_JUDGE_PROMPT,
    FINAL_SYNTHESIZER_PROMPT,
    OPPONENT_PROMPT,
    RISK_ANALYST_PROMPT,
    SUPERVISOR_INTAKE_PROMPT,
    THESIS_BUILDER_PROMPT,
)

CJK_PATTERN = re.compile(r"[\u3400-\u9fff]")


@dataclass(slots=True)
class LlmCallSettings:
    provider_name: str
    model: str | None
    enable_thinking: bool
    debug_reasoning: bool
    allow_store_reasoning: bool
    step_models: dict[str, str] = field(default_factory=dict)
    retry_attempts: int = 2
    retry_backoff_seconds: float = 0.8


@dataclass(slots=True)
class LlmRuntimeState:
    step_metadata: dict[str, dict[str, Any]] = field(default_factory=dict)

    def record(
        self,
        *,
        step_name: str,
        metadata: dict[str, Any],
    ) -> None:
        self.step_metadata[step_name] = metadata

    def pop(self, step_name: str) -> dict[str, Any] | None:
        return self.step_metadata.pop(step_name, None)


class LlmAgentBase:
    def __init__(
        self,
        *,
        step_name: str,
        json_client: JsonProviderClient,
        settings: LlmCallSettings,
        runtime_state: LlmRuntimeState,
    ) -> None:
        self.step_name = step_name
        self.json_client = json_client
        self.settings = settings
        self.runtime_state = runtime_state

    def _call_schema(
        self,
        *,
        step_name: str,
        schema_type: type[BaseModel],
        system_prompt: str,
        user_payload: dict[str, Any],
    ) -> BaseModel:
        output_language = self._infer_output_language(user_payload)
        effective_system_prompt = self._with_language_policy(
            base_prompt=system_prompt,
            output_language=output_language,
        )
        step_model = self._model_for_step(step_name)
        # Keep payload transport ASCII-safe to avoid provider/client-side
        # codec issues on non-ASCII queries (for example Chinese input).
        user_prompt = json.dumps(user_payload, ensure_ascii=True, indent=2)
        response = self._generate_json_with_retry(
            system_prompt=effective_system_prompt,
            user_prompt=user_prompt,
            model=step_model,
            enable_thinking=self.settings.enable_thinking,
        )

        validated, error = self._validate_schema(schema_type=schema_type, data=response.json_data)
        if validated is None:
            repair_payload = {
                "instruction": (
                    "Previous response failed schema validation. "
                    "Return strict JSON only."
                ),
                "schema": schema_type.model_json_schema(),
                "original_input": user_payload,
                "validation_error": error,
            }
            repaired = self._generate_json_with_retry(
                system_prompt=effective_system_prompt,
                user_prompt=json.dumps(repair_payload, ensure_ascii=True, indent=2),
                model=step_model,
                enable_thinking=self.settings.enable_thinking,
            )
            validated, error = self._validate_schema(
                schema_type=schema_type,
                data=repaired.json_data,
            )
            response = repaired
            if validated is None:
                raise ProviderParseError(
                    f"Schema validation failed after repair for step={self.step_name}: {error}"
                )

        step_meta: dict[str, Any] = {
            "provider": response.provider,
            "model": response.model,
            "request_id": response.metadata.request_id,
            "usage": response.metadata.usage,
            "finish_reason": response.metadata.finish_reason,
            "response_ms": response.metadata.response_ms,
            "reasoning_available": bool(response.reasoning_content),
            "thinking_enabled": self.settings.enable_thinking,
            "output_language": output_language,
        }
        if (
            self.settings.debug_reasoning
            and self.settings.allow_store_reasoning
            and response.reasoning_content
        ):
            step_meta["reasoning_content"] = response.reasoning_content

        self.runtime_state.record(step_name=step_name, metadata=step_meta)
        return validated

    def _record_deterministic_fallback(
        self,
        *,
        step_name: str,
        error: Exception,
        fallback_agent: str,
    ) -> None:
        self.runtime_state.record(
            step_name=step_name,
            metadata={
                "provider": self.settings.provider_name,
                "model": self._model_for_step(step_name),
                "thinking_enabled": self.settings.enable_thinking,
                "fallback": "deterministic",
                "fallback_agent": fallback_agent,
                "fallback_reason": f"{type(error).__name__}: {error}",
            },
        )

    def _generate_json_with_retry(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None,
        enable_thinking: bool,
    ):
        attempts = max(self.settings.retry_attempts, 1)
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                return self.json_client.generate_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=model,
                    enable_thinking=enable_thinking,
                )
            except ProviderRetryableError as exc:
                last_error = exc
                if attempt >= attempts - 1:
                    break
                delay = min(
                    self.settings.retry_backoff_seconds * float(attempt + 1),
                    3.0,
                )
                time.sleep(delay)
        if last_error is not None:
            raise last_error
        raise ProviderRetryableError("Provider call failed with unknown retryable error.")

    def _validate_schema(
        self, *, schema_type: type[BaseModel], data: dict[str, Any]
    ) -> tuple[BaseModel | None, str | None]:
        try:
            return schema_type.model_validate(data), None
        except ValidationError as exc:
            return None, str(exc)

    def _infer_output_language(self, user_payload: dict[str, Any]) -> str:
        payload_text = json.dumps(user_payload, ensure_ascii=False)
        if CJK_PATTERN.search(payload_text):
            return "zh-CN"
        return "en-US"

    def _with_language_policy(self, *, base_prompt: str, output_language: str) -> str:
        if output_language == "zh-CN":
            language_instruction = (
                "Language consistency requirement:\n"
                "- Output all natural-language fields in Simplified Chinese.\n"
                "- Keep the same language across all fields.\n"
                "- Do not mix English sentences unless a proper noun requires it."
            )
        else:
            language_instruction = (
                "Language consistency requirement:\n"
                "- Output all natural-language fields in English.\n"
                "- Keep the same language across all fields."
            )
        return f"{base_prompt.strip()}\n\n{language_instruction}\n"

    def _model_for_step(self, step_name: str) -> str | None:
        return self.settings.step_models.get(step_name) or self.settings.model


class LlmSupervisorAgent(LlmAgentBase):
    name = "supervisor-agent-llm"

    def intake(self, request: ResearchAnalyzeRequest, bundle: EvidenceBundle) -> SupervisorIntake:
        step_name = "supervisor_intake"
        payload = {
            "query": request.query,
            "mode": request.mode.value,
            "filters": request.to_retrieval_filters().to_dict(),
            "bundle": _bundle_payload(bundle),
        }
        try:
            response = self._call_schema(
                step_name=step_name,
                schema_type=SupervisorIntake,
                system_prompt=SUPERVISOR_INTAKE_PROMPT.system_prompt,
                user_payload=payload,
            )
            return SupervisorIntake.model_validate(response.model_dump(mode="json"))
        except (ProviderRetryableError, ProviderParseError) as exc:
            self._record_deterministic_fallback(
                step_name=step_name,
                error=exc,
                fallback_agent="supervisor-agent",
            )
            return SupervisorAgent().intake(request, bundle)

    def synthesize_memo(
        self,
        *,
        query: str,
        theses: list[ThesisItem],
        objections: list[ObjectionItem],
        evidence_judge: EvidenceJudgeOutput,
        risks: list[RiskItem],
        insufficient_evidence: bool,
    ) -> FinalResearchMemo:
        step_name = "synthesize_memo"
        payload = {
            "query": query,
            "insufficient_evidence": insufficient_evidence,
            "theses": [item.model_dump(mode="json") for item in theses],
            "objections": [item.model_dump(mode="json") for item in objections],
            "evidence_judge": evidence_judge.model_dump(mode="json"),
            "risks": [item.model_dump(mode="json") for item in risks],
        }
        try:
            response = self._call_schema(
                step_name=step_name,
                schema_type=FinalResearchMemo,
                system_prompt=FINAL_SYNTHESIZER_PROMPT.system_prompt,
                user_payload=payload,
            )
            return FinalResearchMemo.model_validate(response.model_dump(mode="json"))
        except (ProviderRetryableError, ProviderParseError) as exc:
            self._record_deterministic_fallback(
                step_name=step_name,
                error=exc,
                fallback_agent="supervisor-agent",
            )
            return SupervisorAgent().synthesize_memo(
                query=query,
                theses=theses,
                objections=objections,
                evidence_judge=evidence_judge,
                risks=risks,
                insufficient_evidence=insufficient_evidence,
            )


class LlmThesisBuilderAgent(LlmAgentBase):
    name = "thesis-builder-agent-llm"

    def run(self, *, query: str, bundle: EvidenceBundle, max_theses: int = 3) -> list[ThesisItem]:
        step_name = "thesis_builder"
        payload = {
            "query": query,
            "max_theses": max_theses,
            "bundle": _bundle_payload(bundle),
        }
        try:
            response = self._call_schema(
                step_name=step_name,
                schema_type=ThesisBuilderOutput,
                system_prompt=THESIS_BUILDER_PROMPT.system_prompt,
                user_payload=payload,
            )
            parsed = ThesisBuilderOutput.model_validate(response.model_dump(mode="json"))
            return parsed.theses[:max_theses]
        except (ProviderRetryableError, ProviderParseError) as exc:
            self._record_deterministic_fallback(
                step_name=step_name,
                error=exc,
                fallback_agent="thesis-builder-agent",
            )
            return ThesisBuilderAgent().run(query=query, bundle=bundle, max_theses=max_theses)


class LlmOpponentAgent(LlmAgentBase):
    name = "opponent-agent-llm"

    def run(self, *, theses: list[ThesisItem], bundle: EvidenceBundle) -> list[ObjectionItem]:
        step_name = "opponent"
        payload = {
            "theses": [item.model_dump(mode="json") for item in theses],
            "bundle": _bundle_payload(bundle),
        }
        try:
            response = self._call_schema(
                step_name=step_name,
                schema_type=OpponentOutput,
                system_prompt=OPPONENT_PROMPT.system_prompt,
                user_payload=payload,
            )
            parsed = OpponentOutput.model_validate(response.model_dump(mode="json"))
            return parsed.objections
        except (ProviderRetryableError, ProviderParseError) as exc:
            self._record_deterministic_fallback(
                step_name=step_name,
                error=exc,
                fallback_agent="opponent-agent",
            )
            return OpponentAgent().run(theses=theses, bundle=bundle)


class LlmEvidenceJudgeAgent(LlmAgentBase):
    name = "evidence-judge-agent-llm"

    def run(
        self,
        *,
        theses: list[ThesisItem],
        objections: list[ObjectionItem],
        bundle: EvidenceBundle,
    ) -> EvidenceJudgeOutput:
        step_name = "evidence_judge"
        payload = {
            "theses": [item.model_dump(mode="json") for item in theses],
            "objections": [item.model_dump(mode="json") for item in objections],
            "bundle": _bundle_payload(bundle),
        }
        try:
            response = self._call_schema(
                step_name=step_name,
                schema_type=EvidenceJudgeOutput,
                system_prompt=EVIDENCE_JUDGE_PROMPT.system_prompt,
                user_payload=payload,
            )
            return EvidenceJudgeOutput.model_validate(response.model_dump(mode="json"))
        except (ProviderRetryableError, ProviderParseError) as exc:
            self._record_deterministic_fallback(
                step_name=step_name,
                error=exc,
                fallback_agent="evidence-judge-agent",
            )
            return EvidenceJudgeAgent().run(
                theses=theses,
                objections=objections,
                bundle=bundle,
            )


class LlmRiskAnalystAgent(LlmAgentBase):
    name = "risk-analyst-agent-llm"

    def run(
        self,
        *,
        theses: list[ThesisItem],
        evidence_judge: EvidenceJudgeOutput,
        objections: list[ObjectionItem],
    ) -> list[RiskItem]:
        step_name = "risk_analyst"
        payload = {
            "theses": [item.model_dump(mode="json") for item in theses],
            "evidence_judge": evidence_judge.model_dump(mode="json"),
            "objections": [item.model_dump(mode="json") for item in objections],
        }
        try:
            response = self._call_schema(
                step_name=step_name,
                schema_type=RiskAnalystOutput,
                system_prompt=RISK_ANALYST_PROMPT.system_prompt,
                user_payload=payload,
            )
            parsed = RiskAnalystOutput.model_validate(response.model_dump(mode="json"))
            return parsed.risks
        except (ProviderRetryableError, ProviderParseError) as exc:
            self._record_deterministic_fallback(
                step_name=step_name,
                error=exc,
                fallback_agent="risk-analyst-agent",
            )
            return RiskAnalystAgent().run(
                theses=theses,
                evidence_judge=evidence_judge,
                objections=objections,
            )


def _bundle_payload(bundle: EvidenceBundle) -> dict[str, Any]:
    items = []
    for item in bundle.items:
        items.append(
            {
                "chunk_id": item.chunk_id,
                "document_id": item.document_id,
                "document_title": item.document_title,
                "source_type": item.source_type,
                "section_name": item.section_name,
                "chunk_index": item.chunk_index,
                "chunk_text": item.chunk_text[:800],
                "citation_locator": item.citation_locator,
                "score": item.score,
            }
        )
    return {
        "bundle_id": bundle.bundle_id,
        "query": bundle.query,
        "retrieval_mode": bundle.retrieval_mode,
        "total_candidates": bundle.total_candidates,
        "total_items": len(items),
        "items": items,
    }
