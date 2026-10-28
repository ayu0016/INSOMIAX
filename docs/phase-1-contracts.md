# RADIX Talent Match Phase 1 contracts

## Scope and source boundary

Phase 1 records the data and security contract before application routes or frontend modules are implemented. The participant brief is the source for the five modules, the listed fields, category codes, stack, and intended handoffs. The separate TGL event plan is treated as event context, not product behavior.

Official JDs, resumes, the participant-brief company benchmark JSON, and milestone workbook were not found. The later Phase 7 instruction identifies the existing `staging_company_skill_levels` Supabase table as the runtime source, but access and its schema/records remain unverified. No benchmark rows, aliases, JD records, candidate records, or purported official scoring rules are included in the migration.

## Database proposal

Migration: `supabase/migrations/20261028000000_radix_core.sql` (timestamped for Supabase CLI migration discovery).

| Table | Purpose and key columns | Access |
| --- | --- | --- |
| `candidate_profiles` | One row per `auth.users.id`; `name`, `email`, `education`, `skills`, `hackathons`, `internships`, `certifications`, `preferred_roles`, `cv_file`, timestamps | Owner select/insert/update/delete via RLS |
| `documents` | Owner, source type (`jd`/`resume`), original filename, content type, byte size, checksum, private `storage_path`, extraction status and editable extraction JSON, timestamps | Owner only via RLS |
| `job_descriptions` | Owner, document, company/role/location metadata, reviewed extraction JSON, timestamps; composite FK to document owner | Owner only via RLS |
| `company_benchmarks` | Company name, expected level per category, `source_kind`, source reference, timestamps | Authenticated read; no client writes; no seed rows |
| `analysis_runs` | Owner, kind (`talent_check`/`skill_match`), profile/JD/benchmark references, status, input/result JSON, config/scoring version, timestamps | Owner only via RLS |
| `skill_aliases` | Category, normalized alias, canonical skill, config version | Authenticated read; writes reserved for trusted administration; no seed rows |
| `related_skill_edges` | Category and explicitly configured related-skill pair used only for partial-match proposals, config version | Authenticated read; writes reserved for trusted administration; no seed rows |

All user-owned references include owner-scoped composite foreign keys where applicable. JSON arrays and objects receive structural checks. The participant brief defines these 12 skillsets and codes:

| Code | Skillset |
| --- | --- |
| `COD` | Coding |
| `DSA` | Data Structures & Algorithms |
| `OOD` | Object-Oriented Design |
| `APTI` | Aptitude |
| `COMM` | Communication |
| `AI` | AI |
| `CLOUD` | Cloud |
| `SQL` | SQL |
| `SWE` | Software Engineering |
| `SYSD` | System Design |
| `NETW` | Networking |
| `OS` | Operating Systems |

Every skill may also use `OTHER` for anything outside those twelve. `OTHER` is not a thirteenth benchmark skillset.

The original participant brief describes a company benchmark JSON input. The later Phase 7 project instruction establishes the existing Supabase table `staging_company_skill_levels` as the operational source of truth instead; a separate JSON file must not be required or used as a substitute. Its columns, company identifiers, proficiency representation, completeness rules, and record provenance have not yet been verified. Do not assume the proposed JSON shape or levels apply to that table until the actual schema and records have been inspected. Phase 1 inserts no benchmark values.

## Pydantic contract proposal

The eventual Python API models should use strict validation and serialize the following fields. These are proposals for Phase 2 implementation; Phase 1 does not add application code.

### `Skill`

```json
{
  "skill_name": "string",
  "category_code": "COD|DSA|OOD|APTI|COMM|AI|CLOUD|SQL|SWE|SYSD|NETW|OS|OTHER",
  "evidence": "short quote or reason",
  "confidence": "high|medium|low",
  "canonical_skill": "string|null",
  "proficiency_level": "integer 1-10|null",
  "requirement_type": "required|preferred|null",
  "evidence_source": {
    "document_id": "uuid|null",
    "page": "integer|null"
  }
}
```

`skill_name`, `category_code`, `evidence`, and `confidence` preserve the brief's skill fields. Candidate proficiency is optional and must be candidate-entered or explicitly supported by an approved derivation rule; extraction must not silently infer it. `requirement_type` is applicable to JD requirements. Null means unresolved and requires review before scoring.

### `ExtractedSkillList`

```json
{
  "source_type": "jd|resume",
  "source_file": "string",
  "company": "string|null",
  "role": "string|null",
  "skills": ["Skill"],
  "document_id": "uuid",
  "extraction_status": "draft|reviewed",
  "extraction_method": "llm|deterministic"
}
```

### `CandidateProfile`

```json
{
  "name": "string",
  "email": "string",
  "education": "string",
  "skills": ["Skill"],
  "hackathons": ["string"],
  "internships": ["string"],
  "certifications": ["string"],
  "preferred_roles": ["string"],
  "cv_file": "private storage path|null"
}
```

The list representation above makes the brief's ellipsis fields concrete as lists of text. This shape is an application proposal, not a RADIX-prescribed nested schema.

### `CompanyBenchmark`, `TalentCheckResult`, `SkillMatchResult`

- `CompanyBenchmark`: `company`, `expected_levels` keyed by all 12 category codes with integer values 1–10, `source_kind`, `source_reference`.
- `TalentCheckResult`: preserve `company`, `skillset_gap[]` (`category_code`, `required_level`, `candidate_level`, `gap`), `readiness_score`; add `assessment_status`, `missing_proficiency_categories`, `benchmark_source_kind`, and `formula_version`. `candidate_level`, `gap`, and `readiness_score` may be null when inputs/policy are absent. `skillset_gap` preserves the brief fields while making unknowns explicit.
- `SkillMatchResult`: preserve `jd_source_file`, `match_score`, `matched_skills`, `missing_skills`; add `partially_matched_skills`, `unclassified_skills`, separate required/preferred coverage, status, and config/formula version.

No scoring formula is proposed here. Until approved policy and source inputs exist, Talent Check and Skill Matching return an explicit not-scored/unavailable status and reason rather than a numeric score.

## Normalization and extraction contract

1. Normalize Unicode, trim, case-fold, collapse whitespace, and apply punctuation normalization deterministically.
2. Resolve exact configured aliases to a canonical skill. Alias configuration is versioned and conflict-checked. Phase 1 does not seed skill-specific aliases.
3. Treat related skills separately from aliases. Only an explicitly configured `related_skill_edges` entry may propose a partial match; no edges are seeded.
4. Keep raw skill name, category, evidence, confidence, and source-document reference alongside canonical value.
5. Keep extracted JD/resume results editable. Missing or uncertain `required`/`preferred` labels remain null and are excluded from scoring pending review.
6. LLM extraction output must validate against the response model. Invalid/unavailable output should be marked and handled by a deterministic parser/normalizer in Phase 2; no fabricated evidence or proficiency values.

## API contract proposal

Every route except health requires `Authorization: Bearer <Supabase access token>`. The API validates the token and derives `owner_id` from its subject; it never accepts a caller-selected owner ID as authority.

| Method and path | Request | Response |
| --- | --- | --- |
| `GET /v1/health` | None | Service health only |
| `POST /v1/uploads` | `source_type`, `filename`, `content_type`, `byte_size` | `document_id`, owner-scoped private path, signed upload URL and expiry |
| `POST /v1/documents/{document_id}/extract` | None | `ExtractedSkillList` draft with provenance and extraction method |
| `PUT /v1/documents/{document_id}/extraction` | Edited `ExtractedSkillList` | Validated saved extraction |
| `POST /v1/job-descriptions` | Reviewed JD document ID and optional confirmed company/role/location | Saved owner-linked JD record |
| `GET /v1/profiles/me` | None | `CandidateProfile` or not found |
| `PUT /v1/profiles/me` | `CandidateProfile` | Saved profile |
| `GET /v1/job-descriptions` | Optional pagination | Owner's JDs only |
| `GET /v1/companies` | None | Available benchmarks with source kind; empty/unavailable where no source exists |
| `POST /v1/talent-checks` | Profile reference (`me` or owned ID), benchmark ID | `TalentCheckResult`, including not-scored status/reason as applicable |
| `POST /v1/skill-matches` | Profile reference and owned JD ID | `SkillMatchResult`, including unclassified skills and not-scored status/reason as applicable |
| `GET /v1/skill-taxonomy` | None | Category codes and active normalization configuration version |

Request models must reject malformed IDs, invalid enums, out-of-range proficiency, missing evidence, foreign-owned references, malformed lists, and unreviewed JD classifications where scoring is requested. File size limits and retention duration remain unresolved and must be set before upload implementation.

## Error response format

All API errors use one envelope:

```json
{
  "error": {
    "code": "string",
    "message": "human-readable summary",
    "request_id": "string",
    "details": {}
  }
}
```

Proposed HTTP mapping: `400` malformed request; `401` absent/invalid token; `403` authenticated but disallowed operation; `404` absent or inaccessible resource (avoid confirming cross-user existence); `413` upload exceeds configured limit; `415` unsupported type; `422` semantic/schema validation failure; `500` unexpected internal error. Do not expose secrets, SQL, raw stack traces, or another user's identifiers in messages/details.

## Authentication, RLS, and private storage requirements

- Use Supabase Auth JWTs. Validate issuer/signature/audience/expiry; protected API handlers derive identity from validated JWT claims.
- Access user data with the caller identity so Postgres RLS applies. Never expose the service-role secret to the React client or use it as the normal protected-request database identity.
- Enable RLS on every user-data table. Policies constrain `SELECT`, `INSERT`, `UPDATE`, and `DELETE` to `owner_id = auth.uid()`; composite foreign keys prevent a user's row from referencing another user's document/profile/JD.
- Keep uploaded resumes and JDs in a private Storage bucket. Use paths beginning with the authenticated user's UUID and a document UUID. Storage object policies require the bucket ID and first path segment to match `auth.uid()` for read/write/delete.
- Company benchmark and taxonomy configuration are authenticated-read-only to users. Client writes have no policy; trusted administration is outside the user API.
- The staging source is accessed by the backend using `RADIX_SUPABASE_READONLY_DSN` in a read-only transaction. Keep this credential on the backend; it is not a browser/RLS identity. The current protected API validates a Supabase user token before querying metadata. A database role with table and metadata read access only is required.
- Upload flow validates allowed PDF/DOCX MIME and extension, declared and actual byte size, ownership, and parseability before extraction. Exact size limit and data retention/deletion policy are unresolved and must be selected before Phase 2 upload implementation.

## Migration scope

`20261028000000_radix_core.sql` creates the above tables, checks, references, indexes, RLS enablement/policies, and private storage bucket/policies. It contains no official or illustrative seed rows. Apply only after reviewing with a Supabase project; migration application is not performed as part of this Phase 1 documentation/specification pass.

Phase 7 does not alter or apply this migration. `company_benchmarks` remains an empty proposed application table and is not the Company Talent Check data source. Runtime source inspection targets the existing `staging_company_skill_levels` table only.

## Phase 7 verified-source status

The local environment was checked without displaying values: `RADIX_SUPABASE_READONLY_DSN` is not configured, and Supabase Auth (`SUPABASE_URL` plus `SUPABASE_ANON_KEY`) is not configured. Therefore no live schema, records, target company identifiers, category mapping, or benchmark completeness can be asserted. The API's `GET /api/v1/talent-check/source` currently exposes safe schema metadata only after authentication and otherwise returns explicit auth/database errors. Competencies remain blocked until the actual schema is mapped and source rows are validated. No company listing or company-level values should be returned from metadata guesses.

Readiness remains unscored. Decisions required before implementation include the approved formula and version, category weights, level-gap direction/scale, missing benchmark category behavior, missing candidate proficiency behavior, treatment of candidate `OTHER`, required proficiency source, critical-gap policy, and rounding. The participant brief's requested output fields do not define these rules.
