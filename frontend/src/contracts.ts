export type SkillEvidence = {
  skill_name: string;
  category_code: string;
  requirement_type: "required" | "preferred" | "unspecified";
  evidence: string;
  confidence: "high" | "medium" | "low";
  canonical_skill: string | null;
};
export type EvidenceText = { text: string; evidence: string };
export type JDAnalysisResult = {
  source_type: "jd";
  source_file: string | null;
  company: string | null;
  role: string | null;
  extraction_status: "draft";
  extraction_method: "deterministic";
  skills: SkillEvidence[];
  job_title: string | null;
  job_title_evidence: string | null;
  required_skills: SkillEvidence[];
  preferred_skills: SkillEvidence[];
  unclassified_requirement_skills: SkillEvidence[];
  skills_by_category: Record<string, SkillEvidence[]>;
  experience_requirements: EvidenceText[];
  education_requirements: EvidenceText[];
  responsibilities: EvidenceText[];
  key_qualifications: EvidenceText[];
  analysis_method: "deterministic";
  scoring_available: false;
};

export type ProfileSource = "resume" | "manual";
export type ProfileField = { value: string; source: ProfileSource; edited_by_user: boolean; evidence: string | null };
export type ProfileEntry = { text: string; source: ProfileSource; edited_by_user: boolean; evidence: string | null; source_section: string | null; dates: string | null; duration: string | null };
export type ProfileSkill = {
  skill_name: string; category_code: string; source: ProfileSource; edited_by_user: boolean; evidence: string | null;
  confidence: string | null; canonical_skill: string | null; source_section: string | null;
  evidence_kind: "explicit" | "inferred" | "manual"; proficiency_level: number | null;
  proficiency_status: "not_assessed" | "user_reported";
};
export type CandidateProfile = {
  name: ProfileField | null; email: ProfileField | null; phone: ProfileField | null;
  education: ProfileEntry[]; work_experience: ProfileEntry[]; internships: ProfileEntry[]; projects: ProfileEntry[];
  skills: ProfileSkill[]; certifications: ProfileEntry[]; hackathons: ProfileEntry[]; preferred_roles: ProfileEntry[];
  source_file: string | null;
};

export type SkillMatchFinding = {
  job_skill: string; category_code: string; requirement_type: "required" | "preferred" | "unspecified";
  classification: "matched" | "partially_matched" | "missing" | "needs_review";
  explanation: string; job_evidence: string;
  candidate_evidence: { skill_name: string; category_code: string | null; source: string; evidence: string; source_section: string | null; review_note: "category_mismatch" | null; evidence_kind: "explicit" | "inferred" | "manual"; confidence: string | null; proficiency_level: number | null; proficiency_status: "not_assessed" | "user_reported" }[];
  proficiency_verified: false;
};
export type SkillMatchResponse = {
  job_title: string | null; job_source_file: string | null; candidate_name: string | null; candidate_source_file: string | null;
  matched: SkillMatchFinding[]; partially_matched: SkillMatchFinding[]; missing: SkillMatchFinding[]; needs_review: SkillMatchFinding[];
  numerical_score_available: false; persisted: false;
};
export type AcceptedArtifact<T> = { id: string; label: string; data: T };
export type ModuleId = "dashboard" | "jd" | "resume" | "profile" | "matching" | "talent";
