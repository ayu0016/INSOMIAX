# Phase 9 workflow verification

## Implemented workflow contract

- Dashboard opens first and links directly to all five modules.
- JD Analytics draft state remains in its page. Accepting creates a typed `AcceptedArtifact<JDAnalysisResult>` in root React state; edits to the source draft do not mutate that snapshot.
- Resume Parsing draft remains separate from its accepted typed `ResumeParseArtifact`. After acceptance, **Build Profile from Resume** opens Profile Builder and triggers prefill. Prefill copies only the data fields present in the artifact; profile edits do not mutate the source snapshot. Replacing an existing non-empty profile draft requires confirmation.
- Profile Builder works with no resume draft. Accepting a validated preview creates a typed `AcceptedArtifact<CandidateProfile>` in root React state.
- Job Skill Matching selects from accepted JD/profile artifacts, shows both selected labels, reports missing inputs, and links back to their source modules.
- Company Talent Check can be opened independently. It does not gate Job Skill Matching and does not display unverified company records or readiness scores.
- All modules remain mounted while hidden, preserving in-memory drafts and accepted artifacts across navigation. Refreshing or closing the tab clears all such state.

## Manual frontend verification checklist

The repository has no frontend unit-test or browser-test framework configured. Run these checks after installing Node.js and completing the production build:

1. Open the dashboard. Verify all five module cards are direct entry points and counts are zero/absent without creating fabricated activity.
2. Open Resume Parsing first, parse a synthetic resume, accept it, and choose **Build Profile from Resume**. Verify candidate/contact fields, skills, education, experience, and projects are filled only where parsed data exists; missing values remain blank and parser warnings are visible. Edit/add/remove profile entries, preview and accept. Confirm provenance/evidence remains visible and the source parsed artifact is unchanged.
3. Create and accept a profile manually without visiting Resume Parsing.
4. Open JD Analytics directly, analyze and accept a synthetic JD. Confirm a later edit does not silently alter that accepted artifact.
5. Open Job Skill Matching. With either input missing, verify the explanatory message and direct link to the required source module. With both accepted, select each, verify labels, compare, and use both source-return actions.
6. Navigate among pages and back; confirm drafts and accepted artifact counts remain. Refresh; confirm counts and drafts clear and UI makes no persistence claim.
7. Open Company Talent Check directly. Verify health/configuration-required state in the current unconfigured environment. With a configured backend but no token, verify auth-required. No company list should appear until verified source mapping is deployed.
8. Verify protected endpoints reject unauthenticated requests outside the explicitly configured local-development mode.

## Automated and runtime verification status

- Backend tests and Python compilation are tracked in the Phase 9 implementation report.
- Frontend build, browser behavior, and frontend automated tests are not verified in this environment because Node.js/npm are unavailable and no frontend test framework is configured.
- Supabase staging schema/data and authenticated browser retrieval remain blocked on local credentials and sign-in integration.
- Readiness remains blocked on written scoring policy approval.
