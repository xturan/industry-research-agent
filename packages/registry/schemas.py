from __future__ import annotations

from pydantic import BaseModel, Field


class TemplateEntry(BaseModel):
    template_id: str
    version: str
    content_format: str
    description: str
    sections: list[str]
    style_pack: str


class PolicyEntry(BaseModel):
    policy_id: str
    version: str
    description: str
    rules: list[str]
    disclaimer_text: str | None = None


class RegistryTemplatesResponse(BaseModel):
    templates: list[TemplateEntry]


class RegistryPoliciesResponse(BaseModel):
    policies: list[PolicyEntry]


class StylePackEntry(BaseModel):
    style_pack_id: str
    description: str
    tone_keywords: list[str] = Field(default_factory=list)
