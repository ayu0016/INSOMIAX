# Phase 11 — Company Talent Check access verification

## Current state

The application uses a direct PostgreSQL connection through `psycopg`, configured only on the backend with `RADIX_SUPABASE_READONLY_DSN`. It does not retrieve the staging table through the Supabase REST API. The table name is fixed as `staging_company_skill_levels`; the schema must be configured with `RADIX_STAGING_SCHEMA` when discovery would otherwise find more than one matching non-system schema.

The authenticated `/api/v1/talent-check/source` endpoint now returns only a sanitized schema-review status. Detailed schema, column, role, and permission metadata is available through the local CLI only; raw competency rows are not part of either response.

The current local environment has no usable `RADIX_SUPABASE_READONLY_DSN`, `SUPABASE_URL`, or `SUPABASE_ANON_KEY`; no live connection or schema/permission verification was possible. `RADIX_STAGING_SCHEMA` is unset, which is acceptable only if discovery finds one matching table. Company Talent Check remains protected by Supabase bearer authentication. The frontend does not yet have a Supabase sign-in flow. Company competency retrieval and readiness scoring remain blocked.

## Local diagnostic

After configuring the local `.env`, run from the repository root:

```powershell
.\.venv\Scripts\python.exe backend\diagnose_staging_access.py
```

The diagnostic starts a PostgreSQL read-only transaction and inspects catalog metadata only. It prints the connected role name, discovered schema/table/columns, effective table and schema privileges, role flags, RLS enabled/forced status and policy count, plus counts of other readable/owned objects. It never reads staging rows, prints a DSN, or sends this report through an API. Exit code `2` means configuration/connection/schema discovery failed; exit code `3` means permission or RLS review is still needed. Exit code `0` means the limited least-privilege checks passed with RLS disabled; it still does not validate the meaning of columns or authorize competency mapping.

`read_only_privilege_candidate` is a conservative assessment, not a security certification. Any role membership, source-table ownership, write grant, database temporary-object privilege, create privilege, superuser-like role flag, unrelated readable relation, or other owned database object fails it. The catalog checks do not cover external systems or prove the safety of every database object class. A DBA should review the role's complete grants and ownership before accepting it.

When RLS is enabled, the diagnostic reports whether direct role access is subject to RLS and the policy count, but intentionally does not read policy expressions. Have the Supabase administrator verify that the policy behavior is appropriate for this direct PostgreSQL role. Direct PostgreSQL access has no browser user's Supabase JWT claims unless separately configured; do not bypass RLS or change policies merely to make the diagnostic pass.

## Manual setup and verification

1. In the ignored local `.env`, set `RADIX_SUPABASE_READONLY_DSN` to a dedicated database login created for this source. Do not use a PostgreSQL administrator, project owner, service-role key, or application user's credential.
2. Ask the database administrator to grant only the metadata visibility and source-table `SELECT` needed for inspection. The role must have no `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `REFERENCES`, or `TRIGGER` rights; no source-table/schema/database ownership; no persistent or temporary create privileges; no elevated role memberships; and no `SELECT` on unrelated sensitive relations.
3. Run the diagnostic. If it reports ambiguous schemas, have the administrator identify the intended schema from the actual deployment, then set `RADIX_STAGING_SCHEMA` to that exact value and rerun. Do not guess `public`.
4. Review RLS enablement, force status, policy count and policy definitions with the administrator. The CLI output deliberately does not reveal policy expressions.
5. Configure `SUPABASE_URL` and `SUPABASE_ANON_KEY` only if the protected API is to validate bearer tokens. These are backend settings; never paste them into chat or place the database DSN in frontend configuration. The frontend currently lacks sign-in/session support, so authenticated browser retrieval remains unavailable.
6. Review actual column semantics and official category/company mappings with an authoritative source. Column names/types alone do not establish meaning. Only after that review may competency retrieval be mapped and tested against verified rows.

No migration, database write, grant, policy change, or readiness formula is included in this phase. Readiness stays disabled until the official scoring policy is approved.

## Tests

The diagnostic tests use mocked catalog responses. They verify read-only transaction setup, schema ambiguity handling, sanitized connection/catalog failures, effective permission-denial reporting, and no source-row query. These tests do not establish live Supabase connectivity, actual RLS behavior, or the configured role's effective grants.
