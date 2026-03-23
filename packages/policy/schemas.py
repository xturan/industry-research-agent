from __future__ import annotations

from pydantic import BaseModel


class PolicyIssue(BaseModel):
    code: str
    severity: str
    message: str
    location: str | None = None


class PolicyReport(BaseModel):
    passed: bool
    issues: list[PolicyIssue]


class DeliveryPolicyResult(BaseModel):
    passed: bool
    blocked_asset_ids: list[int]
    asset_reports: dict[int, PolicyReport]
