from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

BENCHMARK_SKILLSETS = frozenset({
    "COD", "DSA", "OOD", "APTI", "COMM", "AI", "CLOUD", "SQL", "SWE", "SYSD", "NETW", "OS"
})


class ApiErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict[str, Any]


class ApiErrorResponse(BaseModel):
    error: ApiErrorBody


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "radix-api"
    database_configured: bool
    auth_configured: bool
    schema_mapping: Literal["pending"] = "pending"
    scoring_policy: Literal["unapproved"] = "unapproved"


class ColumnMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column_name: str
    data_type: str
    database_type: str
    nullable: bool
    ordinal_position: int


class SourceInspectionResponse(BaseModel):
    status: Literal["schema_verification_required"]
    source_table: str
    source_schema: str
    row_count: int
    columns: list[ColumnMetadata]
    competencies_available: Literal[False] = False
    readiness_scoring_available: Literal[False] = False
    reason: str


class ReadinessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_identifier: str = Field(min_length=1)
    candidate_skill_levels: dict[str, StrictInt | None] = Field(default_factory=dict)

    @field_validator("candidate_skill_levels")
    @classmethod
    def validate_skillset_keys_and_levels(cls, values: dict[str, int | None]) -> dict[str, int | None]:
        unknown = set(values) - BENCHMARK_SKILLSETS
        if unknown:
            raise ValueError("Candidate readiness inputs must use the 12 benchmark skillset codes; OTHER is excluded.")
        invalid = {code: level for code, level in values.items() if level is not None and not 1 <= level <= 10}
        if invalid:
            raise ValueError("Candidate competency levels must be between 1 and 10, or null when unknown.")
        return values
