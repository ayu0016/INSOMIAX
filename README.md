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

The Resume Parsing page reuses the in-memory PDF/DOCX extraction, upload size/type checks, API origin, and configured skill vocabulary. Its endpoints are available anonymously only under the explicit local development settings above; otherwise Supabase authentication is required. The frontend supports editable resume text and editable/removable candidate details, education, experience, internships, projects, identified dates, skills, and certifications. After accepting the reviewed extraction, choose **Build Profile from Resume** to open Profile Builder and prefill the accepted typed artifact. The artifact remains a separate session snapshot; edits to the profile do not alter it. Resume text and parsed data are not saved permanently.

- `POST /api/v1/resume-parsing/extract` accepts multipart form field `file` with a PDF or DOCX and returns extracted text.
- `POST /api/v1/resume-parsing/parse` accepts `{"text":"...","source_file":"..."}` and returns a draft `source_type: resume` extraction.

Name, email, phone, section content, and dates are identified with deterministic heuristics and include evidence when found. Skills are detected only from the configured vocabulary: mentions in a Skills section are labeled `explicit`; mentions in work, internship, or project sections are labeled `inferred`. Both retain the supporting line. Other sections do not establish skill evidence. The vocabulary file remains illustrative and is not an official RADIX skill mapping. Proficiency, employability, readiness, and job-match scoring are not assessed. Unknown or ambiguous information is left empty. PDF/DOCX layout differences, multi-column documents, tables, scans/OCR, unusual date formats, and unlabeled names/sections can reduce extraction coverage. Review and correction are required; parsing accuracy is not guaranteed.

## Profile Builder

Profile Builder can start with a blank profile or prefill from an accepted Resume Parsing draft in the same browser session. It preserves resume evidence and source labels, marks later edits, and validates a stateless preview through the backend. The preview endpoint follows the same explicit local development exception as the workflow routes; otherwise it requires Supabase authentication. Profile state stays in React memory while switching modules; refreshing or closing the page clears it. The accept action is a session-only review state and does not write to Supabase, local storage, or a server-side store. No migration or candidate-profile persistence is implemented.

- `POST /api/v1/profiles/preview` accepts a typed candidate profile and returns the validated profile, missing-field list, and evidence/date/proficiency warnings. It never persists the request.

Nested education, work, internship, project, certification, hackathon, preferred-role, and skill entries retain `resume` or `manual` provenance; edits are marked separately. Skills may have an optional user-reported proficiency, but resume mentions do not fill it and no readiness/employability/job-match scores are calculated. Dates remain text as supplied; missing dates generate warnings rather than inferred values. Keep phone optional and add only data needed for the candidate profile. Preview validation uses the standard API error envelope and follows the local-only auth gate described above.

## Job Skill Matching

Job Skill Matching compares an accepted JD Analytics result with an accepted Profile Builder profile held in the current browser session. Use the Skill Matching page to select both artifacts and submit the comparison. The artifacts are sent to the API for stateless processing; they are not persisted. A refresh clears the selections and accepted artifacts.

- `POST /api/v1/skill-matches` accepts `job_description` and `candidate_profile` objects using the JD Analytics and Profile Builder contracts. It returns separate `matched`, `partially_matched`, `missing`, and `needs_review` findings with requirement type, category, explanation, and source evidence.

Matching uses case, Unicode, and whitespace normalization while preserving punctuation. Exact skill names and exact mentions in profile work, internship, or project text can be compared. Experience/project mentions are labeled inferred and classified as partial; explicit documented skill entries are matched. Unknown proficiency is kept unknown. No keyword mention verifies proficiency or qualification, and no numerical match, readiness, employability, or ranking score is produced. Same-category non-identical terms and uncatalogued `OTHER` skills require review rather than assumed equivalence.

No official alias map was available. The default `backend/app/job_skill_matching/approved_mappings.json` is empty. An optional JSON mapping file can be selected with `RADIX_MATCH_SKILL_MAPPINGS_PATH`; its format is `{"mappings":[{"canonical_skill":"...","category_code":"COD","aliases":["..."]}]}`. Only reviewed mappings should be configured; mapping conflicts or invalid files fail closed with `INVALID_MATCH_MAPPING`. The category codes are the 12 listed in the Phase 1 contract; `OTHER` is intentionally excluded from mapping configuration.

## API foundation

- `GET /api/v1/health` reports whether backend configuration is present without returning any configured values.
- `GET /api/v1/talent-check/source` requires Supabase authentication, discovers the table's metadata, and reports row count and column metadata. It does not return table records.
- `GET /api/v1/talent-check/competencies` remains blocked with `SCHEMA_VERIFICATION_REQUIRED` until a verified mapping is implemented.
- `POST /api/v1/talent-check/readiness` remains blocked with `SCORING_POLICY_UNAPPROVED` until an approved formula exists.

## Company Talent Check status

The Company Talent Check page calls the protected source-inspection endpoint and presents authentication, configuration, source-unavailable, and schema-review states. Its current environment has neither a configured `RADIX_SUPABASE_READONLY_DSN` nor `SUPABASE_URL`/`SUPABASE_ANON_KEY`, so live source inspection and authenticated browser retrieval have not been verified. The page does not show company selectors or competencies until a validated company response contract can be built from the actual staging schema and records.

The actual Supabase table `staging_company_skill_levels` is the authoritative source under the Phase 7 instruction. The Phase 1 `company_benchmarks` migration table is not used as a replacement, and the missing `talent_check_company_skillsets.json` is not required. Never infer source column names, target company IDs, levels, category mapping, or completeness from the table name. The current `GET /api/v1/talent-check/source` query is read-only and returns metadata only to authenticated callers; database errors are sanitized. The API has no Supabase sign-in UI yet, so this page clearly reports the need for a session rather than weakening route authentication.

Readiness scoring remains disabled. Before implementing it, approve formula/version, category weights, level comparison and gap direction, behavior for missing benchmark categories and candidate proficiency, treatment of `OTHER`, critical-gap rules, and rounding. No equal-weight assumption or zero substitution is made.

## Unified workflow and persistence boundaries

The dashboard is the application home and offers direct entry to every module. No module is required before opening another. It shows the accepted job analyses, accepted resume draft, and accepted candidate profiles available in the current React session, plus the next action when Job Skill Matching lacks either input.

- **JD Analytics → Job Skill Matching:** review and accept a JD analysis. The accepted typed snapshot can then be selected in Skill Matching.
- **Resume Parsing → Profile Builder:** accept a reviewed resume draft and choose **Build Profile from Resume**. Profile Builder fills only fields present in the parsed artifact and keeps the source separate. Resume parsing is optional; a profile can be started manually. If a profile draft already contains data, Profile Builder asks before replacing it.
- **Profile Builder → Job Skill Matching:** validate and accept a candidate profile, then select it with an accepted JD in Skill Matching. The matching page shows both selected artifact labels and links back to their source modules for edits.
- **Company Talent Check:** independently accessible from the dashboard/navigation. It checks backend configuration and source status but does not show unverified company data.

Accepted artifacts and module drafts live only in root/component React memory. Navigation keeps module components mounted so draft state and accepted artifacts remain available until the page is refreshed or closed. No browser storage or durable profile/JD persistence is used. The APIs for extraction, profile preview, and job matching process requests without saving them. The staging metadata endpoint is read-only; no Talent Check result is stored.

The frontend does not yet implement Supabase sign-in/session handling. In explicitly configured local development (`RADIX_ENV=development` and `RADIX_JD_AUTH_MODE=local`), JD Analytics, Resume Parsing, Profile Builder preview, and Job Skill Matching accept anonymous requests. Outside that mode, those routes require a valid Supabase bearer token; frontend requests do not yet attach tokens, so production use needs auth UI/session integration. Company Talent Check always requires Supabase auth and also needs verified source mapping. Do not enable local mode in production or disable authentication to work around these limitations.

The PostgreSQL repository forces read-only transactions and uses parameterized metadata queries plus safely quoted discovered identifiers. It never logs a DSN or returns driver exception text.

## Tests

Run backend unit/API tests from the repository root with the venv interpreter. The tests mock database connections and do not require live Supabase credentials:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```
