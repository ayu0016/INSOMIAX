from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..jd_analytics.models import CategoryCode


class ResumeExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=200_000)
    source_file: str | None = Field(default=None, max_length=255)

    @field_validator("text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Resume text must not be blank.")
        return value


class ContactField(BaseModel):
    value: str
    evidence: str


class ResumeSkill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_name: str
    canonical_skill: str | None
    category_code: CategoryCode
    evidence: str
    confidence: Literal["high", "medium", "low"]
    source_section: str
    evidence_kind: Literal["explicit", "inferred"]
    proficiency_level: int | None = None
    proficiency_status: Literal["not_assessed"] = "not_assessed"


class ResumeEntry(BaseModel):
    text: str
    evidence: str
    source_section: str
    dates: str | None = None
    duration: str | None = None


class ResumeDate(BaseModel):
    value: str
    evidence: str
    source_section: str


class ResumeParseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["resume"] = "resume"
    source_file: str | None
    extraction_method: Literal["deterministic"] = "deterministic"
    extraction_status: Literal["draft"] = "draft"
    candidate_name: ContactField | None = None
    email: ContactField | None = None
    phone: ContactField | None = None
    education: list[ResumeEntry]
    work_experience: list[ResumeEntry]
    internships: list[ResumeEntry]
    projects: list[ResumeEntry]
    skills: list[ResumeSkill]
    certifications: list[ResumeEntry]
    dates: list[ResumeDate]
    missing_or_ambiguous: list[str]
    proficiency_assessed: Literal[False] = False
    scores_available: Literal[False] = False
