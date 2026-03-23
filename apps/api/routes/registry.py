from __future__ import annotations

from fastapi import APIRouter

from packages.registry.schemas import RegistryPoliciesResponse, RegistryTemplatesResponse
from packages.registry.service import RegistryService

router = APIRouter(prefix="/registry", tags=["registry"])


@router.get("/templates", response_model=RegistryTemplatesResponse)
def list_templates() -> RegistryTemplatesResponse:
    return RegistryService().list_templates()


@router.get("/policies", response_model=RegistryPoliciesResponse)
def list_policies() -> RegistryPoliciesResponse:
    return RegistryService().list_policies()
