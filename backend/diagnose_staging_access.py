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

from app.errors import RadixError  # noqa: E402
from app.repository import StagingCompetencyRepository  # noqa: E402


def main() -> int:
    try:
        diagnostic = StagingCompetencyRepository().diagnose_access()
    except RadixError as exc:
        print(json.dumps({"status": "failed", "code": exc.code, "message": exc.message}, indent=2))
        return 2
    except Exception:
        # Fail closed without printing driver details, SQL, or connection settings.
        print(json.dumps({"status": "failed", "code": "DIAGNOSTIC_FAILED", "message": "The read-only source diagnostic failed."}, indent=2))
        return 2

    report = diagnostic.as_dict()
    report["status"] = "diagnostic_complete_manual_review_required"
    report["read_only_privilege_candidate"] = diagnostic.read_only_candidate
    report["live_competency_integration_verified"] = False
    print(json.dumps(report, indent=2))
    # RLS policy expressions are deliberately not read, so an RLS-enabled
    # source must receive a separate human policy review before proceeding.
    return 0 if diagnostic.read_only_candidate and not diagnostic.rls_enabled else 3


if __name__ == "__main__":
    raise SystemExit(main())
