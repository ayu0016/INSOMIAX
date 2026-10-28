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


class StagingDiagnosticFailure(Exception):
    """Safe local-only diagnosis for PostgreSQL connection/catalog failures."""

    def __init__(self, category: str, next_step: str) -> None:
        self.category = category
        self.next_step = next_step
        super().__init__(f"{category}: {next_step}")


class SourceTableNotFound(RadixError):
    def __init__(self) -> None:
        super().__init__(
            503,
            "SOURCE_TABLE_NOT_FOUND",
            "The configured staging source could not be resolved.",
        )


class SourceSchemaAmbiguous(RadixError):
    def __init__(self, _schemas: list[str]) -> None:
        super().__init__(
            409,
            "SOURCE_SCHEMA_AMBIGUOUS",
            "The staging source schema is ambiguous; an operator must set RADIX_STAGING_SCHEMA.",
            {"required_environment_variable": "RADIX_STAGING_SCHEMA"},
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
