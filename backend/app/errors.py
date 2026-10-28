from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RadixError(Exception):
    status_code: int
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


class DatabaseConfigurationRequired(RadixError):
    def __init__(self) -> None:
        super().__init__(
            503,
            "DATABASE_CONFIGURATION_REQUIRED",
            "The read-only Supabase PostgreSQL connection is not configured.",
            {"required_environment_variable": "RADIX_SUPABASE_READONLY_DSN"},
        )


class AuthConfigurationRequired(RadixError):
    def __init__(self) -> None:
        super().__init__(
            503,
            "AUTH_CONFIGURATION_REQUIRED",
            "Supabase Auth validation is not configured on the backend.",
            {"required_environment_variables": ["SUPABASE_URL", "SUPABASE_ANON_KEY"]},
        )


class DatabaseUnavailable(RadixError):
    def __init__(self) -> None:
        super().__init__(
            503,
            "DATABASE_UNAVAILABLE",
            "The competency source could not be reached. Check backend database access.",
        )


class SourceTableNotFound(RadixError):
    def __init__(self) -> None:
        super().__init__(
            503,
            "SOURCE_TABLE_NOT_FOUND",
            "The configured database does not expose staging_company_skill_levels.",
        )


class SourceSchemaAmbiguous(RadixError):
    def __init__(self, schemas: list[str]) -> None:
        super().__init__(
            409,
            "SOURCE_SCHEMA_AMBIGUOUS",
            "The source table exists in multiple schemas; set RADIX_STAGING_SCHEMA.",
            {"available_schemas": schemas},
        )


class SchemaVerificationRequired(RadixError):
    def __init__(self, source: dict[str, Any]) -> None:
        super().__init__(
            409,
            "SCHEMA_VERIFICATION_REQUIRED",
            "The staging table schema is visible, but its competency columns have not been verified and mapped.",
            {"source": source},
        )


class ScoringPolicyUnapproved(RadixError):
    def __init__(self) -> None:
        super().__init__(
            409,
            "SCORING_POLICY_UNAPPROVED",
            "Readiness scoring is disabled until an approved scoring formula is documented.",
        )
