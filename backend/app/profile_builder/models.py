from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..jd_analytics.models import CategoryCode

ProfileSource = Literal["resume", "manual"]


class ProfileField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, max_length=255)
    source: ProfileSource
    edited_by_user: bool = False
    evidence: str | None = Field(default=None, max_length=1000)

    @field_validator("value")
    @classmethod
    def trim_required_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank.")
        return value


class ProfileEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=4000)
    source: ProfileSource = "manual"
    edited_by_user: bool = False
    evidence: str | None = Field(default=None, max_length=1000)
    source_section: str | None = Field(default=None, max_length=100)
    dates: str | None = Field(default=None, max_length=120)
    duration: str | None = Field(default=None, max_length=120)

    @field_validator("text")
    @classmethod
    def trim_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Entry text must not be blank.")
        return value


class ProfileSkill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_name: str = Field(min_length=1, max_length=120)
    category_code: CategoryCode
    source: ProfileSource = "manual"
    edited_by_user: bool = False
    evidence: str | None = Field(default=None, max_length=1000)
    confidence: Literal["high", "medium", "low"] | None = None
    canonical_skill: str | None = Field(default=None, max_length=120)
    source_section: str | None = Field(default=None, max_length=100)
    evidence_kind: Literal["explicit", "inferred", "manual"] = "manual"
    proficiency_level: int | None = Field(default=None, ge=1, le=10)
    proficiency_status: Literal["not_assessed", "user_reported"] = "not_assessed"

    @field_validator("skill_name")
    @classmethod
    def trim_skill_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Skill name must not be blank.")
        return value

    @model_validator(mode="after")
    def require_manual_proficiency_source(self):
        if self.proficiency_level is not None and (self.source != "manual" or self.proficiency_status != "user_reported"):
            raise ValueError("Proficiency may only be supplied as a user-reported manual value.")
        if self.proficiency_level is None and self.proficiency_status == "user_reported":
            raise ValueError("A user-reported proficiency requires a level.")
        return self


class CandidateProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ProfileField | None = None
    email: ProfileField | None = None
    phone: ProfileField | None = None
    education: list[ProfileEntry] = Field(default_factory=list, max_length=30)
    work_experience: list[ProfileEntry] = Field(default_factory=list, max_length=50)
    internships: list[ProfileEntry] = Field(default_factory=list, max_length=30)
    projects: list[ProfileEntry] = Field(default_factory=list, max_length=50)
    skills: list[ProfileSkill] = Field(default_factory=list, max_length=200)
    certifications: list[ProfileEntry] = Field(default_factory=list, max_length=50)
    hackathons: list[ProfileEntry] = Field(default_factory=list, max_length=30)
    preferred_roles: list[ProfileEntry] = Field(default_factory=list, max_length=30)
    source_file: str | None = Field(default=None, max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: ProfileField | None) -> ProfileField | None:
        if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value.value):
            raise ValueError("Enter a valid email address.")
        return value


class ProfilePreviewResponse(BaseModel):
    profile: CandidateProfile
    missing_fields: list[str]
    warnings: list[str]
    persistence_available: Literal[False] = False
    scores_available: Literal[False] = False
