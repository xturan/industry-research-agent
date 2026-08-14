from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from packages.research_harness.tooling.executor import ToolExecutor
from packages.research_harness.tooling.policy import (
    DEFAULT_NODE_TOOL_POLICY,
    NODE_TOOL_POLICIES,
)
from packages.research_harness.tooling.specs import (
    FORBIDDEN_TOOL_NAMES,
    TOOL_SPECS,
    ToolTraceRecord,
)


@dataclass(frozen=True, slots=True)
class ToolAuthorizationResult:
    allowed: bool
    reason_code: str
    message: str
    validated_args: dict[str, Any] | None = None


class ToolHarness:
    def authorize_call(
        self,
        *,
        node_name: str,
        tool_name: str,
        args: dict[str, Any],
        state: dict[str, Any],
        call_count: int,
    ) -> ToolAuthorizationResult:
        _ = state
        if tool_name in FORBIDDEN_TOOL_NAMES:
            return ToolAuthorizationResult(
                allowed=False,
                reason_code="forbidden_tool",
                message=f"{tool_name} is forbidden for all LLM graph nodes.",
            )
        spec = TOOL_SPECS.get(tool_name)
        if spec is None:
            return ToolAuthorizationResult(
                allowed=False,
                reason_code="unknown_tool",
                message=f"{tool_name} is not registered in the tooling registry.",
            )
        policy = NODE_TOOL_POLICIES.get(node_name, DEFAULT_NODE_TOOL_POLICY)
        if tool_name not in policy.allowed_tools:
            return ToolAuthorizationResult(
                allowed=False,
                reason_code="tool_not_allowed_for_node",
                message=f"{node_name} is not allowed to call {tool_name}.",
            )
        if call_count >= policy.max_tool_calls:
            return ToolAuthorizationResult(
                allowed=False,
                reason_code="tool_call_budget_exceeded",
                message=f"{node_name} exceeded max tool calls for this node run.",
            )
        try:
            validated = spec.input_model.model_validate(args).model_dump(mode="json")
        except ValidationError as exc:
            return ToolAuthorizationResult(
                allowed=False,
                reason_code="invalid_tool_args",
                message=str(exc),
            )
        return ToolAuthorizationResult(
            allowed=True,
            reason_code="allowed",
            message="tool call allowed",
            validated_args=validated,
        )


class ToolSession:
    def __init__(
        self,
        *,
        node_name: str,
        agent_name: str,
        state: dict[str, Any],
        harness: ToolHarness,
        executor: ToolExecutor,
        db_session: Any | None = None,
    ) -> None:
        self.node_name = node_name
        self.agent_name = agent_name
        self.state = state
        self.harness = harness
        self.executor = executor
        self.db_session = db_session
        self._call_count = 0
        self._traces: list[dict[str, Any]] = []

    def call_tool(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        auth = self.harness.authorize_call(
            node_name=self.node_name,
            tool_name=tool_name,
            args=args,
            state=self.state,
            call_count=self._call_count,
        )
        trace_id = f"{self.node_name}_{self._call_count + 1}_{tool_name}"
        args_summary = _summarize_args(args)
        if not auth.allowed:
            trace = ToolTraceRecord(
                trace_id=trace_id,
                node_name=self.node_name,
                agent_name=self.agent_name,
                tool_name=tool_name,
                tool_kind=str(
                    TOOL_SPECS.get(tool_name).kind.value
                    if tool_name in TOOL_SPECS
                    else "unknown"
                ),
                call_index=self._call_count + 1,
                status="denied",
                reason_code=auth.reason_code,
                message=auth.message,
                args_summary=args_summary,
                result_summary={},
            )
            self._traces.append(trace.model_dump(mode="json"))
            return {
                "ok": False,
                "error_code": auth.reason_code,
                "message": auth.message,
            }

        self._call_count += 1
        result = self.executor.execute(
            tool_name=tool_name,
            args=dict(auth.validated_args or {}),
            state=self.state,
        )
        trace = ToolTraceRecord(
            trace_id=trace_id,
            node_name=self.node_name,
            agent_name=self.agent_name,
            tool_name=tool_name,
            tool_kind=TOOL_SPECS[tool_name].kind.value,
            call_index=self._call_count,
            status="allowed",
            reason_code=auth.reason_code,
            message=auth.message,
            args_summary=args_summary,
            result_summary=_summarize_result(result),
        )
        self._traces.append(trace.model_dump(mode="json"))
        return {
            "ok": True,
            "result": result,
        }

    def export_traces(self) -> list[dict[str, Any]]:
        return list(self._traces)


def _summarize_args(args: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps(args, ensure_ascii=False, sort_keys=True)
    return {
        "keys": sorted(args.keys()),
        "hash": hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16],
    }


def _summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    summary = {"keys": sorted(result.keys())}
    if "items" in result and isinstance(result["items"], list):
        summary["item_count"] = len(result["items"])
    if "rows" in result and isinstance(result["rows"], list):
        summary["row_count"] = len(result["rows"])
    if "sections" in result and isinstance(result["sections"], list):
        summary["section_count"] = len(result["sections"])
    if "proposal" in result and isinstance(result["proposal"], dict):
        summary["proposal_keys"] = sorted(result["proposal"].keys())
    return summary
