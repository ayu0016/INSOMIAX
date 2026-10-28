"""Run a local, read-only permission diagnostic for staging_company_skill_levels.

From the repository root:
    .venv\\Scripts\\python.exe backend\\diagnose_staging_access.py

The report is written only to this terminal. It contains catalog metadata and
effective permission flags, never the DSN or staging-table rows.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import ENV_FILE, database_dsn_source, get_settings  # noqa: E402
from app.errors import RadixError, StagingDiagnosticFailure  # noqa: E402
from app.repository import StagingCompetencyRepository  # noqa: E402


def environment_report() -> dict[str, object]:
    """Describe configuration provenance without exposing any configured value."""
    return {
        "expected_env_file": str(ENV_FILE),
        "env_file_exists": ENV_FILE.is_file(),
        "dsn_configured": get_settings().database_configured,
        "dsn_source": database_dsn_source(),
    }


def main() -> int:
    environment = environment_report()
    try:
        diagnostic = StagingCompetencyRepository().diagnose_access()
    except StagingDiagnosticFailure as exc:
        print(json.dumps({
            "status": "failed",
            "category": exc.category,
            "next_step": exc.next_step,
            "environment": environment,
        }, indent=2))
        return 2
    except RadixError as exc:
        output = {"status": "failed", "code": exc.code, "message": exc.message, "environment": environment}
        if exc.code == "DATABASE_CONFIGURATION_REQUIRED":
            output["category"] = "missing_configuration"
            output["next_step"] = "Set RADIX_SUPABASE_READONLY_DSN in the repository-root .env, then rerun this diagnostic."
        elif exc.code == "SOURCE_TABLE_NOT_FOUND":
            output["category"] = "source_not_found_or_not_visible"
            output["next_step"] = "Confirm the actual staging table name and schema with the database owner; set RADIX_STAGING_SCHEMA if needed."
        elif exc.code == "SOURCE_SCHEMA_AMBIGUOUS":
            output["category"] = "schema_ambiguous"
            output["next_step"] = "Set RADIX_STAGING_SCHEMA to the owner-confirmed schema, then rerun this diagnostic."
        print(json.dumps(output, indent=2))
        return 2
    except Exception:
        # Fail closed without printing driver details, SQL, or connection settings.
        print(json.dumps({
            "status": "failed",
            "category": "diagnostic_failure",
            "next_step": "Review the local backend installation and rerun; no driver details were printed.",
            "environment": environment,
        }, indent=2))
        return 2

    report = diagnostic.as_dict()
    report["status"] = "diagnostic_complete_manual_review_required"
    report["read_only_privilege_candidate"] = diagnostic.read_only_candidate
    report["live_competency_integration_verified"] = False
    report["environment"] = environment
    print(json.dumps(report, indent=2))
    # RLS policy expressions are deliberately not read, so an RLS-enabled
    # source must receive a separate human policy review before proceeding.
    return 0 if diagnostic.read_only_candidate and not diagnostic.rls_enabled else 3


if __name__ == "__main__":
    raise SystemExit(main())
