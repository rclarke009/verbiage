"""Pydantic models for Report Writer API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ClaimCreateRequest(BaseModel):
    title: str = Field(default="", max_length=500)
    property_metadata: dict = Field(default_factory=dict)
    field_notes: str = Field(default="")


class ClaimUpdateRequest(BaseModel):
    title: str | None = None
    property_metadata: dict | None = None
    field_notes: str | None = None
    status: str | None = None


class SectionUpdateRequest(BaseModel):
    content: str = Field(..., min_length=0)


class SectionResponse(BaseModel):
    section_key: str
    content: str
    revision_id: str | None = None
    origin: str | None = None
    sources: list[dict] = Field(default_factory=list)


class ClaimResponse(BaseModel):
    claim_id: str
    user_id: str
    title: str
    property_metadata: dict
    field_notes: str
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    sections: dict[str, SectionResponse] = Field(default_factory=dict)


class ClaimsListResponse(BaseModel):
    claims: list[ClaimResponse]


class GenerationRunResponse(BaseModel):
    run_id: str
    claim_id: str
    status: str
    thread_id: str
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    sections: dict[str, SectionResponse] | None = None


class GenerationRunsListResponse(BaseModel):
    runs: list[GenerationRunResponse]


class GenerateRequest(BaseModel):
    resume: bool = False


class RegenerateSectionRequest(BaseModel):
    section_key: str
    instruction: str | None = None


class ResumeRequest(BaseModel):
    action: str = Field(default="continue", description="continue | cancel")


class ReportTypeSectionModel(BaseModel):
    key: str
    label: str


class ReportTypeModel(BaseModel):
    id: str
    label: str
    description: str
    sections: list[ReportTypeSectionModel]


class ReportTypesListResponse(BaseModel):
    report_types: list[ReportTypeModel]
