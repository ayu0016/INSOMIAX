# RADIX Talent Match requirements traceability

This document maps the participant brief and event plan to the Phase 1 contract. **Specified** means the brief states the requirement; **proposed** means an application contract detail not prescribed by RADIX; **unresolved** means a policy or source input is missing and must not be guessed.

## Source inventory

| Source | Availability | Notes |
| --- | --- | --- |
| `RADIX_Talent_Match_Hackathon_Brief.pdf` | Available at `C:\Users\Abhishek\Downloads\RADIX_Talent_Match_Hackathon_Brief.pdf` | 14 pages. Text extraction substitutes special glyphs for some characters, but the requirements below are readable. |
| `TGL_Blitz_Event_Plan.pdf` | Available at `C:\Users\Abhishek\Downloads\TGL_Blitz_Event_Plan.pdf` | 7 pages. Primarily describes event phases, panels, and presentations. Some extracted glyphs are substituted. |
| Six official job descriptions | Not found in the workspace or Downloads | The brief says the pack contains six JDs in PDF and DOCX. |
| Four official sample resumes | Not found in the workspace or Downloads | The brief says the pack contains four sample resumes in PDF and DOCX. |
| `talent_check_company_skillsets.json` | Not found in the workspace or Downloads | Phase 7 specifies the existing Supabase `staging_company_skill_levels` table as the runtime source of truth; no JSON substitute is used. |
| `RADIX_Talent_Match_Milestone_Checklist.xlsx` | Not found in the workspace or Downloads | Named by the participant brief; not required for the candidate-facing product contract. |

No official JD, resume, benchmark, or milestone data is seeded by Phase 1. The runtime staging table has not been verified because this workspace has no configured read-only DSN or Supabase Auth settings. The repository contained no application files, dependency manifests, or configuration before these Phase 1 artifacts.

## Traceability matrix

| Requirement | Source | Proposed database mapping | Proposed Pydantic contract | Proposed API | Test specification | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Use the 12 skill categories and `OTHER`; each skill has one category | Participant brief pp. 9–10 | `candidate_profiles.skills`, `documents.extraction`, `job_descriptions.extraction`; category checks in JSON validation | `Skill.category_code: SkillCategory` | `GET /v1/skill-taxonomy`; extraction review endpoints | Accept every listed code; reject unknown code; one category per skill | Specified |
| Skill record includes name, category, evidence, confidence (`high\|medium\|low`) | Participant brief p. 9 | Skill JSON arrays on profile/extraction | `Skill` | `POST /v1/documents/{id}/extract`, `PUT /v1/documents/{id}/extraction` | Required fields, confidence enum, evidence validation | Specified |
| JD extraction accepts PDF/DOCX and hands a structured list to Skill Matching | Participant brief pp. 7, 10 | `documents`, `job_descriptions` | `ExtractedSkillList` | Upload/extract/review endpoints | PDF/DOCX paths, invalid file, malformed extraction, evidence traceability | Specified |
| Resume extraction returns skills and reliably parsed education/projects/experience signals for Profile Builder | Participant brief pp. 7–8, 10 | `documents`, `candidate_profiles` | `ExtractedSkillList`, `CandidateProfile` | Upload/extract/review and profile endpoints | Resume variation, optional fields, malformed extraction, editable output | Specified |
| Profile contains name, email, education, skills, hackathons, internships, certifications, preferred roles, CV file | Participant brief pp. 8, 10 | `candidate_profiles` | `CandidateProfile` | `GET/PUT /v1/profiles/me` | Field validation and save/load contract checks | Specified |
| A saved profile is compared with a selected company across all categories; return score and per-category gaps | Participant brief pp. 8, 10–11 | `company_benchmarks`, `analysis_runs` | `CompanyBenchmark`, `TalentCheckResult` | `GET /v1/companies`, `POST /v1/talent-checks` | Missing benchmark and proficiency behavior; formula tests blocked pending approved policy | Specified output; scoring policy unresolved |
| Match a candidate/profile to one specific JD; return score, matched and missing skills | Participant brief pp. 8, 10 | `job_descriptions`, `analysis_runs` | `SkillMatchResult` | `POST /v1/skill-matches` | Exact, partial, missing, and unclassified requirements; score tests blocked pending approved formula | Specified output; scoring policy unresolved |
| Distinguish required from preferred JD skills | Not specified in either brief; requested for this implementation | JD extraction JSON | `Skill.requirement_type: required\|preferred\|null` | Extraction review and match endpoint | Null/unreviewed classification excluded from score and exposed for review | Proposed product contract; classification policy unresolved |
| Canonical skill normalization and configurable aliases | Not specified in either brief; requested for this implementation | `skill_aliases`, `related_skill_edges` | `Skill.canonical_skill`; taxonomy configuration model | `GET /v1/skill-taxonomy` | Unicode/case/spacing/punctuation normalization; aliases; alias conflicts; configured related mappings | Proposed |
| Preserve source traceability for extracted skills | Brief requires evidence; page/offset representation unspecified | `documents` plus skill evidence JSON | `Skill.evidence`, `Skill.evidence_source` | Extraction and review endpoints | Evidence references correct owned document and page when available | Proposed technical detail |
| Keep company benchmark values and provenance; do not invent values | Participant brief pp. 8, 11; Phase 7 makes the existing staging table authoritative | Existing `staging_company_skill_levels` (schema unmapped); `company_benchmarks` is not a runtime substitute | `SourceInspectionResponse`; validated competency model blocked pending verified columns/records | `GET /api/v1/talent-check/source` (metadata only), `/competencies` (blocked) | Test source discovery/errors with mocks; data validation and company completeness await actual schema and rows | Required source specified; schema/data unavailable |
| Company Talent Check exposes honest auth/configuration/source states and no fabricated values | Phase 7 implementation request | Existing staging table only; no new benchmark table or seed data | `SourceInspectionResponse`, `ApiErrorResponse` | `GET /api/v1/talent-check/source` | Auth failure, missing config, unavailable DB, schema ambiguity, safe metadata, no raw row leakage | Status UI implemented; live competencies blocked |
| Authenticated, owner-isolated profile/document/result access | Not prescribed by brief; required by implementation request | Owner IDs, RLS on user tables, private Storage bucket | Authenticated API context | All protected endpoints | JWT required; cross-user reads/writes/storage denied | Proposed security requirement |
| Python, LangChain/LLM where useful, React, Supabase/JSON storage; all pieces integrated | Participant brief pp. 12–13; TGL plan p. 2 | Schema supports these handoffs | Contracts in this document | API list in `phase-1-contracts.md` | Phase 2 integration and Docker checks | Specified stack; implementation deferred |
| Five modules work independently and end-to-end; results vary by candidate | Participant brief p. 13 | Modules map to profile, document, benchmark, and run tables | All proposed contracts | All listed endpoints | Phase 2 module and full workflow checks | Specified acceptance target; Phase 2 |
| Event phases, presentations, certificates, panel selections | TGL plan pp. 3–7; participant brief pp. 4–5 | None | None | None | None | Out of candidate-tool scope |

## Unresolved source and product decisions

1. Obtain the six official JDs and four official resumes. Configure read-only access to `staging_company_skill_levels`, then verify its actual columns and records; do not substitute an invented benchmark JSON dataset.
2. Approve readiness and job-match formulas, weights, treatment of preferred requirements, critical-gap definition, rounding, and behavior when no required skills are classified. Neither brief defines these rules.
3. Approve how a JD requirement is classified as required or preferred. The brief does not establish this distinction.
4. Supply any RADIX-approved skill aliases or related-skill mappings. Phase 1 seeds none.
5. Decide upload size limits, retention/deletion policy, and whether extracted document text is retained. Phase 1 does not invent these operational policies.
6. If exact event wording or dates become in-scope, review the source PDFs visually because text extraction substitutes glyphs.
