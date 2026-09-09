"""网关负载/运行观测 API（2026-08-11）。

暴露 capability_gateway 的运行状态：
- GET /api/gateway/health    — 综合健康概览（provider 健康快照 + circuit 状态）
- GET /api/gateway/providers — 各 provider 的健康快照详情
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies import get_db_session
from packages.capability_gateway.observability import (
    build_gateway_summary,
    build_provider_health,
)

router = APIRouter(prefix="/gateway", tags=["gateway"])


@router.get("/health")
def gateway_health(
    window_hours: float = Query(default=24.0, ge=0.5, le=720),
    session: Any = Depends(get_db_session),
) -> dict[str, Any]:
    """网关综合健康：各 provider 健康快照 + circuit 状态 + 窗口。"""
    return build_gateway_summary(session, window_hours=window_hours)


@router.get("/providers")
def gateway_providers(
    window_hours: float = Query(default=24.0, ge=0.5, le=720),
    session: Any = Depends(get_db_session),
) -> dict[str, Any]:
    """各 provider 的健康快照详情（成功率/延迟/失败分类）。"""
    return build_provider_health(session, window_hours=window_hours)
