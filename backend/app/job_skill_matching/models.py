from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..jd_analytics.models import JDAnalysisResult
from ..profile_builder.models import CandidateProfile

MatchClass = Literal["matched", "partially_matched", "missing", "needs_review"]


class SkillMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_skill: str = Field(min_length=1, max_length=120)
    category_code: Literal["COD", "DSA", "OOD", "APTI", "COMM", "AI", "CLOUD", "SQL", "SWE", "SYSD", "NETW", "OS"]
    aliases: list[str] = Field(default_factory=list, max_length=50)


class SkillMappings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mappings: list[SkillMapping] = Field(default_factory=list, max_length=500)


class SkillMatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_description: JDAnalysisResult
    candidate_profile: CandidateProfile

    @model_validator(mode="after")
    def require_comparable_data(self):
        if not self.job_description.skills:
            raise ValueError("The accepted job description contains no extracted skill requirements to compare.")
        profile = self.candidate_profile
        evidence_sections = profile.skills or profile.work_experience or profile.internships or profile.projects
        if not evidence_sections:
            raise ValueError("The accepted candidate profile contains no documented skills, work, internship, or project evidence.")
        return self


class CandidateEvidence(BaseModel):
    skill_name: str
    category_code: str | None = None
    source: Literal["resume", "manual", "work_experience", "internship", "project"]
    evidence: str
    source_section: str | None = None
    review_note: Literal["category_mismatch"] | None = None
    evidence_kind: Literal["explicit", "inferred", "manual"]
    confidence: Literal["high", "medium", "low"] | None = None
    proficiency_level: int | None = None
    proficiency_status: Literal["not_assessed", "user_reported"]


class MatchFinding(BaseModel):
    job_skill: str
    category_code: str
    requirement_type: Literal["required", "preferred", "unspecified"]
    classification: MatchClass
    explanation: str
    job_evidence: str
    candidate_evidence: list[CandidateEvidence]
    proficiency_verified: Literal[False] = False


class SkillMatchResponse(BaseModel):
    job_title: str | None
    job_source_file: str | None
    candidate_name: str | None
    candidate_source_file: str | None
    matched: list[MatchFinding]
    partially_matched: list[MatchFinding]
    missing: list[MatchFinding]
    needs_review: list[MatchFinding]
    numerical_score_available: Literal[False] = False
    persisted: Literal[False] = False
