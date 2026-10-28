import type { AcceptedArtifact, CandidateProfile, JDAnalysisResult, ResumeParseArtifact, SkillMatchResponse } from "./contracts";

export const RADIX_STORAGE_KEY = "radix-talent-match:local-state";
const RADIX_KEY_PREFIX = "radix-talent-match:";
const SCHEMA_VERSION = 1;

export type MatchingSession = { jobId: string; profileId: string; result: SkillMatchResponse | null };
export type RadixLocalState = {
  acceptedJds: AcceptedArtifact<JDAnalysisResult>[];
  acceptedResume: AcceptedArtifact<ResumeParseArtifact> | null;
  profileDraft: CandidateProfile;
  acceptedProfiles: AcceptedArtifact<CandidateProfile>[];
  matching: MatchingSession;
};
export type LoadResult = { state: RadixLocalState; notice: string | null };

export function emptyCandidateProfile(): CandidateProfile {
  return { name: null, email: null, phone: null, education: [], work_experience: [], internships: [], projects: [], skills: [], certifications: [], hackathons: [], preferred_roles: [], source_file: null };
}

export function createInitialRadixState(): RadixLocalState {
  return { acceptedJds: [], acceptedResume: null, profileDraft: emptyCandidateProfile(), acceptedProfiles: [], matching: { jobId: "", profileId: "", result: null } };
}

type RecordValue = Record<string, unknown>;
function record(value: unknown): value is RecordValue { return typeof value === "object" && value !== null && !Array.isArray(value); }
function str(value: unknown): value is string { return typeof value === "string"; }
function nullableString(value: unknown): value is string | null { return value === null || str(value); }
function array(value: unknown, check: (item: unknown) => boolean): value is unknown[] { return Array.isArray(value) && value.every(check); }
function evidenceText(value: unknown): boolean { return record(value) && str(value.text) && str(value.evidence); }
function skill(value: unknown): boolean { return record(value) && str(value.skill_name) && str(value.category_code) && ["required", "preferred", "unspecified"].includes(String(value.requirement_type)) && str(value.evidence) && ["high", "medium", "low"].includes(String(value.confidence)) && nullableString(value.canonical_skill); }
function jd(value: unknown): value is JDAnalysisResult {
  return record(value) && value.source_type === "jd" && nullableString(value.source_file) && nullableString(value.company) && nullableString(value.role)
    && value.extraction_status === "draft" && value.extraction_method === "deterministic" && value.analysis_method === "deterministic" && value.scoring_available === false
    && array(value.skills, skill) && nullableString(value.job_title) && nullableString(value.job_title_evidence)
    && array(value.required_skills, skill) && array(value.preferred_skills, skill) && array(value.unclassified_requirement_skills, skill)
    && record(value.skills_by_category) && Object.values(value.skills_by_category).every(items => array(items, skill))
    && array(value.experience_requirements, evidenceText) && array(value.education_requirements, evidenceText) && array(value.responsibilities, evidenceText) && array(value.key_qualifications, evidenceText);
}
function resumeEntry(value: unknown): boolean { return record(value) && str(value.text) && str(value.evidence) && str(value.source_section) && nullableString(value.dates) && nullableString(value.duration); }
function resumeSkill(value: unknown): boolean { return record(value) && str(value.skill_name) && nullableString(value.canonical_skill) && str(value.category_code) && str(value.evidence) && ["high", "medium", "low"].includes(String(value.confidence)) && str(value.source_section) && ["explicit", "inferred"].includes(String(value.evidence_kind)) && (value.proficiency_level === null || typeof value.proficiency_level === "number") && value.proficiency_status === "not_assessed"; }
function contact(value: unknown): boolean { return value === null || (record(value) && str(value.value) && str(value.evidence)); }
function resume(value: unknown): value is ResumeParseArtifact {
  return record(value) && value.source_type === "resume" && nullableString(value.source_file) && value.extraction_method === "deterministic" && value.extraction_status === "draft"
    && contact(value.candidate_name) && contact(value.email) && contact(value.phone)
    && array(value.education, resumeEntry) && array(value.work_experience, resumeEntry) && array(value.internships, resumeEntry) && array(value.projects, resumeEntry)
    && array(value.skills, resumeSkill) && array(value.certifications, resumeEntry)
    && array(value.dates, item => record(item) && str(item.value) && str(item.evidence) && str(item.source_section)) && array(value.missing_or_ambiguous, str)
    && value.proficiency_assessed === false && value.scores_available === false;
}
function profileField(value: unknown): boolean { return value === null || (record(value) && str(value.value) && ["resume", "manual"].includes(String(value.source)) && typeof value.edited_by_user === "boolean" && nullableString(value.evidence)); }
function profileEntry(value: unknown): boolean { return record(value) && str(value.text) && ["resume", "manual"].includes(String(value.source)) && typeof value.edited_by_user === "boolean" && nullableString(value.evidence) && nullableString(value.source_section) && nullableString(value.dates) && nullableString(value.duration); }
function profileSkill(value: unknown): boolean { return record(value) && str(value.skill_name) && str(value.category_code) && ["resume", "manual"].includes(String(value.source)) && typeof value.edited_by_user === "boolean" && nullableString(value.evidence) && nullableString(value.confidence) && nullableString(value.canonical_skill) && nullableString(value.source_section) && ["explicit", "inferred", "manual"].includes(String(value.evidence_kind)) && (value.proficiency_level === null || (typeof value.proficiency_level === "number" && value.proficiency_level >= 1 && value.proficiency_level <= 10)) && ["not_assessed", "user_reported"].includes(String(value.proficiency_status)); }
function profile(value: unknown): value is CandidateProfile {
  return record(value) && profileField(value.name) && profileField(value.email) && profileField(value.phone)
    && ["education", "work_experience", "internships", "projects", "certifications", "hackathons", "preferred_roles"].every(key => array(value[key], profileEntry))
    && array(value.skills, profileSkill) && nullableString(value.source_file);
}
function finding(value: unknown): boolean {
  return record(value) && str(value.job_skill) && str(value.category_code) && ["required", "preferred", "unspecified"].includes(String(value.requirement_type))
    && ["matched", "partially_matched", "missing", "needs_review"].includes(String(value.classification)) && str(value.explanation) && str(value.job_evidence)
    && array(value.candidate_evidence, item => record(item) && str(item.skill_name) && nullableString(item.category_code) && str(item.source) && str(item.evidence) && nullableString(item.source_section) && (item.review_note === null || item.review_note === "category_mismatch") && ["explicit", "inferred", "manual"].includes(String(item.evidence_kind)) && nullableString(item.confidence) && (item.proficiency_level === null || typeof item.proficiency_level === "number") && ["not_assessed", "user_reported"].includes(String(item.proficiency_status)))
    && value.proficiency_verified === false;
}
function matchResult(value: unknown): value is SkillMatchResponse {
  return record(value) && nullableString(value.job_title) && nullableString(value.job_source_file) && nullableString(value.candidate_name) && nullableString(value.candidate_source_file)
    && array(value.matched, finding) && array(value.partially_matched, finding) && array(value.missing, finding) && array(value.needs_review, finding)
    && value.numerical_score_available === false && value.persisted === false;
}
function accepted<T>(value: unknown, dataCheck: (data: unknown) => data is T): value is AcceptedArtifact<T> { return record(value) && str(value.id) && str(value.label) && dataCheck(value.data); }
function isState(value: unknown): value is RadixLocalState {
  return record(value) && array(value.acceptedJds, item => accepted(item, jd)) && (value.acceptedResume === null || accepted(value.acceptedResume, resume))
    && profile(value.profileDraft) && array(value.acceptedProfiles, item => accepted(item, profile))
    && record(value.matching) && str(value.matching.jobId) && str(value.matching.profileId) && (value.matching.result === null || matchResult(value.matching.result));
}

function storage(): Storage {
  if (typeof window === "undefined") throw new Error("Browser storage is unavailable.");
  return window.localStorage;
}

export function loadRadixState(): LoadResult {
  const initial = createInitialRadixState();
  let store: Storage;
  try { store = storage(); } catch { return { state: initial, notice: "Local storage is unavailable. Workflow data will only remain until you leave or reload this page." }; }
  let raw: string | null;
  try { raw = store.getItem(RADIX_STORAGE_KEY); } catch { return { state: initial, notice: "Saved RADIX data could not be read. This session will continue without restored data." }; }
  if (raw === null) return { state: initial, notice: null };
  try {
    const envelope: unknown = JSON.parse(raw);
    if (record(envelope) && envelope.schema_version === SCHEMA_VERSION && isState(envelope.state)) return { state: envelope.state, notice: null };
  } catch { /* Invalid JSON is handled like an incompatible stored version below. */ }
  try { store.removeItem(RADIX_STORAGE_KEY); } catch { /* Continue with clean in-memory state even if stale data cannot be removed. */ }
  return { state: initial, notice: "Saved RADIX data was invalid or from an unsupported version and has been reset for this session." };
}

export function saveRadixState(state: RadixLocalState): string | null {
  try { storage().setItem(RADIX_STORAGE_KEY, JSON.stringify({ schema_version: SCHEMA_VERSION, state })); return null; }
  catch { return "RADIX data could not be saved. Browser storage may be unavailable or full; keep this tab open to retain the current session."; }
}

export function clearRadixState(): string | null {
  try {
    const store = storage();
    for (let index = store.length - 1; index >= 0; index -= 1) {
      const key = store.key(index);
      if (key?.startsWith(RADIX_KEY_PREFIX)) store.removeItem(key);
    }
    return null;
  } catch { return "RADIX local data could not be cleared because browser storage is unavailable."; }
}
