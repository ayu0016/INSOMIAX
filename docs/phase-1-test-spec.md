# RADIX Talent Match Phase 1 test specification

These are acceptance and automated-test specifications for implementation. Phase 1 adds no application test code because no runnable app or dependencies exist yet. Formula-dependent score tests remain blocked until the scoring policy is approved.

## Contract and validation unit tests

- Accept exactly the 12 benchmark skillset codes `COD`, `DSA`, `OOD`, `APTI`, `COMM`, `AI`, `CLOUD`, `SQL`, `SWE`, `SYSD`, `NETW`, and `OS`, plus `OTHER` for a skill outside those categories; reject unknown codes and never treat `OTHER` as a benchmark skillset.
- Preserve the four brief skill fields: name, category, evidence, and confidence. Accept confidence `high`, `medium`, `low`; reject other values and absent evidence.
- Accept proficiency `null` or integer 1–10; reject 0, 11, fractional values, booleans, and coercions. Null stays unknown in serialized outputs.
- Validate profile fields and proposed list shapes; reject malformed skills, unsupported requirement types, and invalid document references.
- Validate extraction source type (`jd`/`resume`), required source fields, document provenance, and extraction status/method.
- Reject a request to score a JD with null required/preferred classification until reviewed; preserve unclassified entries in the response instead of silently assigning a class.

## Skill normalization unit tests

- Unicode normalization, case-folding, whitespace collapse, and punctuation handling are deterministic and idempotent.
- Raw `skill_name` and evidence remain intact while canonical form is computed.
- Configured aliases resolve to the configured canonical skill; conflicting aliases are rejected at configuration load/validation.
- No alias or relation is inferred from absent configuration.
- Only an explicit configured related-skill edge can produce a partial-match proposal; no relation produces a missing/unmatched result.
- Alias/config version is captured with an analysis result so later config changes do not silently rewrite prior results.

## Scoring and missing-data unit tests

- With no official benchmark, Talent Check returns an unavailable/not-scored status, reason, and null score; it does not fabricate a company benchmark.
- Missing candidate proficiency remains null and is reported as unassessed, not treated as 0 or 10.
- Missing scoring formula returns not-scored; no guessed score or critical-gap threshold is emitted.
- Once an approved scoring policy exists, test minimum/maximum inputs, exact boundaries, rounding, per-category contributions, gaps, critical gaps, required/preferred handling, and empty/incomplete input according to that versioned policy.
- Skill match classification tests cover matched, configured partial, missing, and unclassified required/preferred items. Score assertions are blocked until a formula and preferred-skill policy are approved.

## Security and persistence integration tests

- Unauthenticated requests to every protected endpoint return the standard 401 error envelope.
- User A can create/read/update only their own profile, documents, JDs, and analysis runs; User B cannot select, mutate, or infer User A's resources.
- RLS policies deny cross-owner access even when requests bypass the API and query Postgres as an authenticated user.
- A document/JD/profile reference cannot cross owner boundaries; composite foreign keys and API ownership checks both reject it.
- Private Storage rejects anonymous access and rejects another user's object path for read, insert, update, and delete.
- Company benchmark/taxonomy reads work for authenticated users while client insert/update/delete is denied.
- Migration applies to a clean Supabase database and creates RLS, indexes, constraints, and private bucket policies; no data rows are seeded.

## Upload and error contract tests for Phase 2

- Accept valid supported PDF/DOCX files and reject mismatched extension/MIME, invalid or unparseable files, and missing documents.
- Verify configured maximum upload size once approved; before a limit is configured, upload implementation is not accepted.
- Invalid/expired JWT, malformed body, invalid field, unsupported file type, oversize file, inaccessible ID, parser failure, invalid LLM JSON, and internal failure all produce the standard error envelope and do not leak secrets or cross-user existence.
- LLM output schema failures never overwrite user-reviewed extraction; deterministic fallback is marked in the extraction metadata.

## Phase 2 acceptance gates

- Each of the five modules can run independently against the official sample pack when supplied.
- The integrated candidate workflow selects a JD, parses a resume, reviews/saves a profile, runs Talent Check, and runs Skill Matching.
- Results visibly change when candidate inputs change; absent official source data stays labeled unavailable or demo, never official.
- Docker startup, health endpoint, migrations, and end-to-end seeded/official workflow checks are added when runnable services are implemented.

## Phase 7 Company Talent Check gates

- Verify `staging_company_skill_levels` columns from `information_schema` and inspect a limited sample using read-only credentials before defining any competency model. Test the exact verified schema with mocked rows; mocks do not establish live compatibility.
- Once mapped, validate all official category identifiers, the three target company identifiers, source value domains, and provenance. Report duplicate keys, missing company/category pairs, unexpected categories, and unmapped rows explicitly. Do not coerce or silently drop invalid values.
- Test that missing DSN, missing Supabase Auth configuration, auth provider failure, database connection failure, table absence, duplicate schema discovery, and schema ambiguity have distinct sanitized error responses.
- Test the source-inspection endpoint requires a valid Supabase access token and returns metadata only. Assert response/log output contains no DSN, raw database exception, or unrequested record payload.
- Test company/competency response models only after they derive from inspected columns. Do not write fixtures that imply official values; synthetic repository fixtures must be marked test-only.
- Keep readiness endpoint blocked until scoring policy is approved. After approval, test formula version, category weights, gap direction, required and optional proficiency data, all missing-data branches, critical gaps, and round-off; null proficiency must never default to zero or full credit.
- Frontend checks cover health/configuration-required, authentication-required, source unavailable, schema review, loading, and successful verified-company response states. A success-state fixture must be labeled synthetic test data and never shipped as benchmark content.
- Phase 7 acceptance is blocked until live read-only schema and limited records are inspected and the company/category mapping is reviewed. Backend mocks and passing local tests alone do not satisfy this gate.
