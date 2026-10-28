# Phase 9 workflow verification

## Implemented workflow contract

- Dashboard opens first and links directly to all five modules.
- JD Analytics draft state remains in its page. Accepting creates a typed `AcceptedArtifact<JDAnalysisResult>` in root React state; edits to the source draft do not mutate that snapshot.
- Resume Parsing draft remains separate from its accepted typed `ResumeParseArtifact`. After acceptance, **Build Profile from Resume** opens Profile Builder and triggers prefill. Prefill copies only the data fields present in the artifact; profile edits do not mutate the source snapshot. Replacing an existing non-empty profile draft requires confirmation.
- Profile Builder works with no resume draft. Accepting a validated preview creates a typed `AcceptedArtifact<CandidateProfile>` in root React state.
- Job Skill Matching selects from accepted JD/profile artifacts, shows both selected labels, reports missing inputs, and links back to their source modules.
- Company Talent Check can be opened independently. It does not gate Job Skill Matching and does not display unverified company records or readiness scores.
- Accepted workflow artifacts, the editable profile draft, and matching selection/result are restored from versioned browser local storage after refresh. Unaccepted resume extraction and raw uploaded files remain transient.

## Manual frontend verification checklist

The repository has no frontend unit-test or browser-test framework configured. Run these checks after installing Node.js and completing the production build:

1. Open the dashboard. Verify all five module cards are direct entry points and counts are zero/absent without creating fabricated activity.
2. Open Resume Parsing first, parse a synthetic resume, accept it, and choose **Build Profile from Resume**. Verify candidate/contact fields, skills, education, experience, and projects are filled only where parsed data exists; missing values remain blank and parser warnings are visible. Edit/add/remove profile entries, preview and accept. Confirm provenance/evidence remains visible and the source parsed artifact is unchanged.
3. Create and accept a profile manually without visiting Resume Parsing.
4. Open JD Analytics directly, analyze and accept a synthetic JD. Confirm a later edit does not silently alter that accepted artifact.
5. Open Job Skill Matching. With either input missing, verify the explanatory message and direct link to the required source module. With both accepted, select each, verify labels, compare, and use both source-return actions.
6. Navigate among pages and back; confirm drafts and accepted artifact counts remain. Refresh and reopen the app; confirm accepted JD/resume/profile artifacts, profile edits, and matching selections/results restore.
7. Open Company Talent Check directly. Verify health/configuration-required state in the current unconfigured environment. With a configured backend but no token, verify auth-required. No company list should appear until verified source mapping is deployed.
8. Verify protected endpoints reject unauthenticated requests outside the explicitly configured local-development mode.

## Phase 10 UX verification additions

1. Confirm the dashboard progress row reports accepted JD, optional resume, accepted profile, and matching status from actual browser-local artifacts; each **Open** control reaches the named module.
2. Confirm the next-step action changes when JD/profile artifacts are missing or matching has completed. Manual Profile Builder remains available when no resume was accepted.
3. Accept a profile, change its editable draft, and verify the UI explains that the old accepted snapshot remains unchanged until a new preview is accepted. Verify matching can still select the original snapshot and the newly accepted one.
4. Accept a JD analysis and use its direct continuation action to open Job Skill Matching.
5. At a narrow viewport, verify workflow progress stacks without horizontal page overflow, navigation buttons remain keyboard reachable, and the active destination is announced as the current page.
6. Enter an invalid non-empty email address in Profile Builder and select **Preview profile**; browser validation should identify the field and prevent the API request. Correct it and confirm preview proceeds.
7. Open Company Talent Check independently and verify it stays outside candidate workflow progress and continues to explain auth/configuration/schema blockers without showing unverified company values.

## Local persistence verification checklist

1. Accept a JD analysis, accept a parsed resume, prefill and edit a profile, accept it, and run matching. Refresh and verify these typed artifacts and matching inputs/result return without re-uploading a file.
2. Confirm the accepted parsed-resume artifact remains unchanged when editing the profile draft.
3. In browser developer tools, verify RADIX data uses only `radix-talent-match:local-state`; confirm no token, DSN, credentials, raw upload, or unaccepted extraction is stored.
4. Corrupt that key or change its `schema_version`, reload, and verify the app resets to empty state and shows a recovery notice instead of crashing.
5. Disable browser storage or simulate quota failure, make an edit, and verify the app remains usable and shows a storage warning.
6. Choose **Clear local data**, cancel once and confirm data remains; choose it again and confirm. Verify the RADIX key is removed and an unrelated localStorage key remains untouched.
7. Confirm no profile/JD/matching data is synced to another browser/device and use synthetic data only; avoid sensitive real resumes.

## Automated and runtime verification status

- Backend tests and Python compilation are tracked in the Phase 9 implementation report.
- Frontend build, browser behavior, and frontend automated tests are not verified in this environment because Node.js/npm are unavailable and no frontend test framework is configured. Complete the persistence and Phase 10 UX checklists above when a browser is available.
- Supabase staging schema/data and authenticated browser retrieval remain blocked on local credentials and sign-in integration.
- Readiness remains blocked on written scoring policy approval.
