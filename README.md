# RADIX Talent Match — Integration Foundation

This repository contains a FastAPI foundation and a React application with a unified dashboard for JD Analytics, Resume Parsing, Profile Builder, Job Skill Matching, and Company Talent Check. Company Talent Check remains blocked on verified staging schema/data and approved scoring policy.

The backend reads `staging_company_skill_levels` using a read-only PostgreSQL connection. Until the live schema is inspected and mapped, it returns schema-verification status only. It does not return raw rows, invent company or skill identifiers, or calculate readiness. Scoring remains disabled until an approved formula is documented.

## Windows setup in VS Code

1. Open this folder in VS Code and open its integrated PowerShell terminal.
2. Create a virtual environment and install the backend requirements. These commands call the venv interpreter directly, so PowerShell script activation policy does not need to change:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
   ```

3. Edit the existing root `.env` file. It is git-ignored. Set:
   - `RADIX_SUPABASE_READONLY_DSN` to a PostgreSQL DSN for a database role that has only the read access required for `staging_company_skill_levels` and metadata discovery.
   - `SUPABASE_URL` and `SUPABASE_ANON_KEY` so the API can validate a user's Supabase access token. These values are consumed by the backend; no database DSN or service-role key is sent to the browser.
   - Optionally, `RADIX_STAGING_SCHEMA` after the table's schema has been verified. Leave it blank if the table name is unique.
4. Start the API:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
   ```

5. In another terminal, install and start the React application:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

The Talent Check source endpoint requires a valid Supabase user access token; a sign-in UI is outside this phase. Install Node.js 20.19+ or 22.12+ before running the frontend commands.

## JD Analytics local development

JD Analytics processes uploads in memory and does not require Supabase when explicitly enabled for local development. The root `.env` is ignored by Git. Preserve any existing `.env`; if absent, copy `.env.example` and configure these local-only settings:

```dotenv
RADIX_ENV=development
RADIX_JD_AUTH_MODE=local
RADIX_JD_MAX_UPLOAD_BYTES=10485760
```

Start the backend from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

Then start the frontend in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

The page calls `http://127.0.0.1:8000` by default; set the non-secret `VITE_API_BASE_URL` to change the API origin.

- `POST /api/v1/jd-analytics/extract` accepts multipart form field `file` with PDF or DOCX bytes and returns extracted text.
- `POST /api/v1/jd-analytics/analyze` accepts `{"text":"..."}` and returns deterministic, evidence-linked findings.

The upload limit defaults to 10 MiB (`RADIX_JD_MAX_UPLOAD_BYTES`). Parsing is in memory; scanned PDFs need OCR, which is not included. `backend/app/jd_analytics/skill_vocabulary.json` is an explicitly illustrative baseline, not official RADIX vocabulary or aliases. The configuration format supports aliases, but the baseline seeds none; add only reviewed aliases in a configured vocabulary file via `RADIX_JD_SKILL_VOCAB_PATH`. Unknown terms stay unmatched. The module calculates no readiness or job-match scores. Anonymous access to JD Analytics, Resume Parsing, Profile Builder preview, and Job Skill Matching is allowed only when both `RADIX_ENV=development` and `RADIX_JD_AUTH_MODE=local`; otherwise Supabase bearer-token validation applies. Company Talent Check always requires Supabase authentication. Never enable local auth mode in a deployed environment.

## Resume Parsing

The Resume Parsing page reuses the in-memory PDF/DOCX extraction, upload size/type checks, API origin, and configured skill vocabulary. Its endpoints are available anonymously only under the explicit local development settings above; otherwise Supabase authentication is required. The frontend supports editable resume text and editable/removable candidate details, education, experience, internships, projects, identified dates, skills, and certifications. After accepting the reviewed extraction, choose **Build Profile from Resume** to open Profile Builder and prefill the accepted typed artifact. The accepted artifact is stored separately in browser local storage; edits to the profile do not alter it. Uploaded files, extracted resume text, and unaccepted parse drafts are not stored by the persistence feature.

- `POST /api/v1/resume-parsing/extract` accepts multipart form field `file` with a PDF or DOCX and returns extracted text.
- `POST /api/v1/resume-parsing/parse` accepts `{"text":"...","source_file":"..."}` and returns a draft `source_type: resume` extraction.

Name, email, phone, section content, and dates are identified with deterministic heuristics and include evidence when found. Skills are detected only from the configured vocabulary: mentions in a Skills section are labeled `explicit`; mentions in work, internship, or project sections are labeled `inferred`. Both retain the supporting line. Other sections do not establish skill evidence. The vocabulary file remains illustrative and is not an official RADIX skill mapping. Proficiency, employability, readiness, and job-match scoring are not assessed. Unknown or ambiguous information is left empty. PDF/DOCX layout differences, multi-column documents, tables, scans/OCR, unusual date formats, and unlabeled names/sections can reduce extraction coverage. Review and correction are required; parsing accuracy is not guaranteed.

## Profile Builder

Profile Builder can start with a blank profile or prefill from an accepted Resume Parsing draft. It preserves resume evidence and source labels, marks later edits, and validates a stateless preview through the backend. The preview endpoint follows the same explicit local development exception as the workflow routes; otherwise it requires Supabase authentication. The editable draft and accepted profile snapshots are temporarily stored in versioned browser local storage for local development; no profile is written to Supabase or a server-side store. No migration or server-side candidate-profile persistence is implemented.

- `POST /api/v1/profiles/preview` accepts a typed candidate profile and returns the validated profile, missing-field list, and evidence/date/proficiency warnings. It never persists the request.

Nested education, work, internship, project, certification, hackathon, preferred-role, and skill entries retain `resume` or `manual` provenance; edits are marked separately. Skills may have an optional user-reported proficiency, but resume mentions do not fill it and no readiness/employability/job-match scores are calculated. Dates remain text as supplied; missing dates generate warnings rather than inferred values. Keep phone optional and add only data needed for the candidate profile. Preview validation uses the standard API error envelope and follows the local-only auth gate described above.

## Job Skill Matching

Job Skill Matching compares an accepted JD Analytics result with an accepted Profile Builder profile. The selected artifact IDs and typed comparison result are temporarily stored in browser local storage. The artifacts are sent to the API for stateless processing; the backend does not persist them.

- `POST /api/v1/skill-matches` accepts `job_description` and `candidate_profile` objects using the JD Analytics and Profile Builder contracts. It returns separate `matched`, `partially_matched`, `missing`, and `needs_review` findings with requirement type, category, explanation, and source evidence.

Matching uses case, Unicode, and whitespace normalization while preserving punctuation. Exact skill names and exact mentions in profile work, internship, or project text can be compared. Experience/project mentions are labeled inferred and classified as partial; explicit documented skill entries are matched. Unknown proficiency is kept unknown. No keyword mention verifies proficiency or qualification, and no numerical match, readiness, employability, or ranking score is produced. Same-category non-identical terms and uncatalogued `OTHER` skills require review rather than assumed equivalence.

No official alias map was available. The default `backend/app/job_skill_matching/approved_mappings.json` is empty. An optional JSON mapping file can be selected with `RADIX_MATCH_SKILL_MAPPINGS_PATH`; its format is `{"mappings":[{"canonical_skill":"...","category_code":"COD","aliases":["..."]}]}`. Only reviewed mappings should be configured; mapping conflicts or invalid files fail closed with `INVALID_MATCH_MAPPING`. The category codes are the 12 listed in the Phase 1 contract; `OTHER` is intentionally excluded from mapping configuration.

## API foundation

- `GET /api/v1/health` reports whether backend configuration is present without returning any configured values.
- `GET /api/v1/talent-check/source` requires Supabase authentication and returns a sanitized schema-review status only. It does not expose database object metadata or table records.
- `GET /api/v1/talent-check/competencies` remains blocked with `SCHEMA_VERIFICATION_REQUIRED` until a verified mapping is implemented.
- `POST /api/v1/talent-check/readiness` remains blocked with `SCORING_POLICY_UNAPPROVED` until an approved formula exists.

## Company Talent Check status

The Company Talent Check page calls the protected source-inspection endpoint and presents authentication, configuration, source-unavailable, and schema-review states. Detailed schema and role diagnostics are available only through the local backend CLI described in the Phase 11 access guide, not through API responses. Its current environment has neither a configured `RADIX_SUPABASE_READONLY_DSN` nor `SUPABASE_URL`/`SUPABASE_ANON_KEY`, so live source inspection and authenticated browser retrieval have not been verified. The page does not show company selectors or competencies until a validated company response contract can be built from the actual staging schema and records.

The actual Supabase table `staging_company_skill_levels` is the authoritative source under the Phase 7 instruction. The Phase 1 `company_benchmarks` migration table is not used as a replacement, and the missing `talent_check_company_skillsets.json` is not required. Never infer source column names, target company IDs, levels, category mapping, or completeness from the table name. The current `GET /api/v1/talent-check/source` query is read-only and returns metadata only to authenticated callers; database errors are sanitized. The API has no Supabase sign-in UI yet, so this page clearly reports the need for a session rather than weakening route authentication.

For a local, read-only database role/schema/permission diagnostic, configure `RADIX_SUPABASE_READONLY_DSN` in the ignored backend `.env` and run `.\.venv\Scripts\python.exe backend\diagnose_staging_access.py` from the repository root. See [Phase 11 access verification](docs/phase-11-company-talent-access.md) for output interpretation and manual review steps. The diagnostic reads PostgreSQL catalogs only; it does not retrieve competency rows or verify column meaning.

Readiness scoring remains disabled. Before implementing it, approve formula/version, category weights, level comparison and gap direction, behavior for missing benchmark categories and candidate proficiency, treatment of `OTHER`, critical-gap rules, and rounding. No equal-weight assumption or zero substitution is made.

## Unified workflow and persistence boundaries

The dashboard is the application home and offers direct entry to every module. No module is required before opening another. Its workflow progress reflects accepted job analyses, the optional accepted resume draft, accepted candidate profiles, and whether a matching result exists in browser-local state. The next action changes as those artifacts become available. Company Talent Check is independent.

- **JD Analytics → Job Skill Matching:** review and accept a JD analysis. The accepted typed snapshot can then be selected in Skill Matching.
- **Resume Parsing → Profile Builder:** accept a reviewed resume draft and choose **Build Profile from Resume**. Profile Builder fills only fields present in the parsed artifact and keeps the source separate. Resume parsing is optional; a profile can be started manually. If a profile draft already contains data, Profile Builder asks before replacing it.
- **Profile Builder → Job Skill Matching:** validate and accept a candidate profile, then select it with an accepted JD in Skill Matching. The matching page shows both selected artifact labels and links back to their source modules for edits.
- **Company Talent Check:** independently accessible from the dashboard/navigation. It checks backend configuration and source status but does not show unverified company data.

Accepted JD analyses, the accepted parsed-resume artifact, the editable profile draft, accepted candidate profiles, and typed Job Skill Matching selections/results are saved under the single versioned browser key `radix-talent-match:local-state`. This is temporary local-development persistence: it does not sync between browsers or devices. The raw uploaded file, unaccepted extraction drafts, auth tokens, Supabase credentials, database connection strings, and Company Talent Check data are not stored by this feature. Extraction, profile preview, and matching APIs remain stateless; the staging metadata endpoint remains read-only.

Anyone with access to the browser profile may be able to access locally stored workflow data. Use synthetic data during development and avoid storing sensitive real resumes. On the dashboard, **Clear local data** asks for confirmation and removes only keys owned by RADIX (`radix-talent-match:`); it does not clear unrelated website data. Invalid, corrupted, or unsupported stored versions are discarded with an in-app notice. If browser storage is blocked or full, the app continues for the current page session and displays a warning. This local storage feature does not change authentication, Supabase access, or server persistence.

The frontend does not yet implement Supabase sign-in/session handling. In explicitly configured local development (`RADIX_ENV=development` and `RADIX_JD_AUTH_MODE=local`), JD Analytics, Resume Parsing, Profile Builder preview, and Job Skill Matching accept anonymous requests. Outside that mode, those routes require a valid Supabase bearer token; frontend requests do not yet attach tokens, so production use needs auth UI/session integration. Company Talent Check always requires Supabase auth and also needs verified source mapping. Do not enable local mode in production or disable authentication to work around these limitations.

The PostgreSQL repository forces read-only transactions and uses parameterized metadata queries plus safely quoted discovered identifiers. It never logs a DSN or returns driver exception text.

## Tests

Run backend unit/API tests from the repository root with the venv interpreter. The tests mock database connections and do not require live Supabase credentials:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```
