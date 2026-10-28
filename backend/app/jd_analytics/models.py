from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..schemas import BENCHMARK_SKILLSETS

CategoryCode = Literal["COD", "DSA", "OOD", "APTI", "COMM", "AI", "CLOUD", "SQL", "SWE", "SYSD", "NETW", "OS", "OTHER"]


class ExtractedDocument(BaseModel):
    filename: str
    media_type: Literal["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
    text: str
    character_count: int = Field(ge=1)


class SkillEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_name: str = Field(min_length=1, max_length=120)
    category_code: CategoryCode
    requirement_type: Literal["required", "preferred", "unspecified"]
    evidence: str = Field(min_length=1, max_length=1000)
    confidence: Literal["high", "medium", "low"]
    canonical_skill: str | None = None
    proficiency_level: int | None = Field(default=None, ge=1, le=10)
    document_id: str | None = None
    page: int | None = Field(default=None, ge=1)


class EvidenceText(BaseModel):
    text: str
    evidence: str


class JDAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=200_000)
    source_file: str | None = Field(default=None, max_length=255)

    @field_validator("text")
    @classmethod
    def require_readable_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Job description text must not be blank.")
        return value


class JDAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["jd"] = "jd"
    source_file: str | None
    company: str | None = None
    role: str | None
    extraction_status: Literal["draft"] = "draft"
    extraction_method: Literal["deterministic"] = "deterministic"
    skills: list[SkillEvidence]
    job_title: str | None
    job_title_evidence: str | None
    required_skills: list[SkillEvidence]
    preferred_skills: list[SkillEvidence]
    unclassified_requirement_skills: list[SkillEvidence]
    skills_by_category: dict[str, list[SkillEvidence]]
    experience_requirements: list[EvidenceText]
    education_requirements: list[EvidenceText]
    responsibilities: list[EvidenceText]
    key_qualifications: list[EvidenceText]
    analysis_method: Literal["deterministic"] = "deterministic"
    scoring_available: Literal[False] = False


def valid_category_codes() -> set[str]:
    return set(BENCHMARK_SKILLSETS) | {"OTHER"}
