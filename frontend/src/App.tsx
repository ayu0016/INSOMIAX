import { useState } from "react";
import ResumeParsing from "./ResumeParsing";
import ProfileBuilder from "./ProfileBuilder";
import JobSkillMatching from "./JobSkillMatching";
import CompanyTalentCheck from "./CompanyTalentCheck";
import Dashboard from "./Dashboard";
import ModuleNavigation from "./ModuleNavigation";
import type { AcceptedArtifact, CandidateProfile, EvidenceText, JDAnalysisResult, ModuleId, ResumeParseArtifact, SkillEvidence } from "./contracts";
type Extracted = { filename: string; text: string; character_count: number };

const apiBase = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function apiError(response: Response): Promise<Error> {
  const body = await response.json().catch(() => null);
  return new Error(body?.error?.message || "The request failed. Check the backend and try again.");
}

export default function App() {
  const [activeModule, setActiveModule] = useState<ModuleId>("dashboard");
  const [acceptedResume, setAcceptedResume] = useState<AcceptedArtifact<ResumeParseArtifact> | null>(null);
  const [profilePrefillRequest, setProfilePrefillRequest] = useState(0);
  const [acceptedJds, setAcceptedJds] = useState<AcceptedArtifact<JDAnalysisResult>[]>([]);
  const [acceptedProfiles, setAcceptedProfiles] = useState<AcceptedArtifact<CandidateProfile>[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [extracted, setExtracted] = useState<Extracted | null>(null);
  const [analysis, setAnalysis] = useState<JDAnalysisResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [accepted, setAccepted] = useState(false);

  async function upload() {
    if (!file) return;
    setBusy(true); setError(null); setAnalysis(null); setAccepted(false);
    try {
      const body = new FormData(); body.append("file", file);
      const response = await fetch(`${apiBase}/api/v1/jd-analytics/extract`, { method: "POST", body });
      if (!response.ok) throw await apiError(response);
      setExtracted(await response.json() as Extracted);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Document extraction failed."); }
    finally { setBusy(false); }
  }

  async function analyze() {
    if (!extracted?.text.trim()) { setError("Add readable job description text before analysis."); return; }
    setBusy(true); setError(null); setAccepted(false);
    try {
      const response = await fetch(`${apiBase}/api/v1/jd-analytics/analyze`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: extracted.text, source_file: extracted.filename }) });
      if (!response.ok) throw await apiError(response);
      setAnalysis(await response.json() as JDAnalysisResult);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Analysis failed."); }
    finally { setBusy(false); }
  }

  function acceptJobDescription(data: JDAnalysisResult) {
    const label = [data.job_title, data.source_file].filter(Boolean).join(" · ") || "Job description";
    setAcceptedJds(current => [...current, { id: crypto.randomUUID(), label, data }]);
  }

  function acceptCandidateProfile(data: CandidateProfile) {
    const label = [data.name?.value, data.source_file].filter(Boolean).join(" · ") || "Candidate profile";
    setAcceptedProfiles(current => [...current, { id: crypto.randomUUID(), label, data }]);
  }

  function acceptResumeDraft(data: ResumeParseArtifact) {
    const label = [data.candidate_name?.value, data.source_file].filter(Boolean).join(" · ") || "Reviewed resume";
    setAcceptedResume({ id: crypto.randomUUID(), label, data });
  }

  function buildProfileFromResume() {
    if (!acceptedResume) return;
    setProfilePrefillRequest(request => request + 1);
    setActiveModule("profile");
  }

  function updateSkill(group: keyof Pick<JDAnalysisResult, "required_skills" | "preferred_skills" | "unclassified_requirement_skills">, index: number, patch: Partial<SkillEvidence>) {
    setAccepted(false);
    setAnalysis(current => {
      if (!current) return current;
      const values = [...allSkills(current)];
      const target = current[group][index];
      const rowIndex = values.findIndex(skill => skill.skill_name === target.skill_name && skill.category_code === target.category_code && skill.requirement_type === target.requirement_type && skill.evidence === target.evidence);
      if (rowIndex < 0) return current;
      values[rowIndex] = { ...values[rowIndex], ...patch };
      return {
        ...current,
        skills: values,
        required_skills: values.filter(skill => skill.requirement_type === "required"),
        preferred_skills: values.filter(skill => skill.requirement_type === "preferred"),
        unclassified_requirement_skills: values.filter(skill => skill.requirement_type === "unspecified"),
        skills_by_category: skillsByCategory(values),
      };
    });
  }

  function updateEvidence(field: "experience_requirements" | "education_requirements" | "responsibilities" | "key_qualifications", index: number, text: string) {
    setAccepted(false);
    setAnalysis(current => current ? { ...current, [field]: current[field].map((entry, i) => i === index ? { text, evidence: entry.evidence } : entry) } : current);
  }

  return <>
  <div hidden={activeModule !== "dashboard"}><Dashboard onNavigate={setActiveModule} acceptedResume={acceptedResume !== null} acceptedJds={acceptedJds} acceptedProfiles={acceptedProfiles} /></div>
  <div hidden={activeModule !== "jd"}><main className="shell">
    <ModuleNavigation active="jd" onNavigate={setActiveModule} />
    <section className="hero"><div className="eyebrow">JOB DESCRIPTION ANALYTICS</div><h1>Understand the role.<br /><em>Keep evidence in view.</em></h1><p>Extract a job description, review its text, then inspect and correct the deterministic analysis. This does not assess candidate readiness or match scores.</p></section>

    <section className="panel" aria-labelledby="upload-heading">
      <div className="eyebrow">STEP 1</div><h2 id="upload-heading">Upload a job description</h2>
      <label className="field-label" htmlFor="jd-file">Choose a PDF or DOCX file</label>
      <div className="upload-row"><input id="jd-file" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={event => { setFile(event.target.files?.[0] || null); setExtracted(null); setAnalysis(null); setAccepted(false); setError(null); }} /><button onClick={upload} disabled={!file || busy}>{busy ? "Working…" : "Extract text"}</button></div>
      <p className="hint">Files are processed in memory and are not stored. Scanned PDFs need OCR, which is not provided.</p>
      {error && <div className="notice notice-error" role="alert">{error}</div>}
    </section>

    {extracted && <section className="panel" aria-labelledby="review-heading">
      <div className="eyebrow">STEP 2 · REVIEW</div><h2 id="review-heading">Review extracted text</h2><p className="hint">{extracted.filename} · {extracted.character_count.toLocaleString()} characters</p>
      <label className="field-label" htmlFor="jd-text">Job description text (editable)</label><textarea id="jd-text" className="text-review" value={extracted.text} onChange={event => { setExtracted({ ...extracted, text: event.target.value }); setAnalysis(null); setAccepted(false); }} />
      <button onClick={analyze} disabled={busy || !extracted.text.trim()}>{busy ? "Analyzing…" : "Analyze job description"}</button>
    </section>}

    {analysis && <section className="panel results" aria-labelledby="results-heading">
      <div className="eyebrow">STEP 3 · ANALYSIS</div><h2 id="results-heading">Review and edit analysis</h2>
      <div className="notice">Deterministic keyword baseline · Evidence is a text match, not proof of candidate proficiency. No scoring is available.</div>
      <label className="field-label" htmlFor="job-title">Job title</label><input id="job-title" value={analysis.job_title || ""} placeholder="Not identified" onChange={event => { const title = event.target.value || null; setAnalysis({ ...analysis, job_title: title, role: title }); setAccepted(false); }} />
      {analysis.job_title_evidence && <Evidence>{analysis.job_title_evidence}</Evidence>}
      <h3>Skills by category</h3>{allSkills(analysis).length === 0 && <p className="hint">No terms from the configured vocabulary were detected. Add/configure vocabulary in the backend if needed.</p>}
      {Object.entries(groupSkills(analysis)).map(([category, skills]) => <div className="category" key={category}><h4>{category}</h4>{skills.map(({ skill, group, index }) => <div className="skill-card" key={`${group}-${index}-${skill.skill_name}-${skill.evidence}`}>
          <label>Skill<input aria-label="Skill name" value={skill.skill_name} onChange={event => group && updateSkill(group, index, { skill_name: event.target.value, canonical_skill: null })} /></label>
          <label>Category<select aria-label="Skill category" value={skill.category_code} onChange={event => group && updateSkill(group, index, { category_code: event.target.value })}>{["COD","DSA","OOD","APTI","COMM","AI","CLOUD","SQL","SWE","SYSD","NETW","OS","OTHER"].map(code => <option key={code}>{code}</option>)}</select></label>
          <label>Classification<select aria-label="Requirement classification" value={skill.requirement_type} onChange={event => group && updateSkill(group, index, { requirement_type: event.target.value as SkillEvidence["requirement_type"] })}><option value="required">Required</option><option value="preferred">Preferred</option><option value="unspecified">Unspecified</option></select></label>
          <Evidence>{skill.evidence}</Evidence><small>Detection confidence: {skill.confidence}</small>
        </div>)}</div>)}
      <EditableEvidence title="Experience requirements" items={analysis.experience_requirements} onEdit={(i, text) => updateEvidence("experience_requirements", i, text)} />
      <EditableEvidence title="Education requirements" items={analysis.education_requirements} onEdit={(i, text) => updateEvidence("education_requirements", i, text)} />
      <EditableEvidence title="Responsibilities" items={analysis.responsibilities} onEdit={(i, text) => updateEvidence("responsibilities", i, text)} />
      <EditableEvidence title="Key qualifications" items={analysis.key_qualifications} onEdit={(i, text) => updateEvidence("key_qualifications", i, text)} />
      <button className="accept-button" disabled={accepted} onClick={() => { setAccepted(true); acceptJobDescription(analysis); }}>{accepted ? "Analysis accepted" : "Accept reviewed analysis"}</button>{accepted && <p className="success" role="status">Accepted in this browser session. Nothing has been saved to a server.</p>}
    </section>}
    <footer><span>RADIX TALENT MATCH</span><span>Evidence linked · No fabricated scores</span></footer>
  </main></div>
  <div hidden={activeModule !== "resume"}><ResumeParsing onNavigate={setActiveModule} onAccept={acceptResumeDraft} onInvalidate={() => setAcceptedResume(null)} onBuildProfile={buildProfileFromResume} /></div>
  <div hidden={activeModule !== "profile"}><ProfileBuilder resumeDraft={acceptedResume?.data || null} prefillRequest={profilePrefillRequest} onNavigate={setActiveModule} onAccept={acceptCandidateProfile} /></div>
  <div hidden={activeModule !== "matching"}><JobSkillMatching jobDescriptions={acceptedJds} candidateProfiles={acceptedProfiles} onNavigate={setActiveModule} /></div>
  <div hidden={activeModule !== "talent"}><CompanyTalentCheck onNavigate={setActiveModule} /></div>
  </>;
}

function Evidence({ children }: { children: string }) { return <blockquote>{children}</blockquote>; }
function allSkills(analysis: JDAnalysisResult) {
  return (["required_skills", "preferred_skills", "unclassified_requirement_skills"] as const).flatMap(group => analysis[group]);
}
function skillsByCategory(skills: SkillEvidence[]) {
  return skills.reduce<Record<string, SkillEvidence[]>>((groups, skill) => { (groups[skill.category_code] ||= []).push(skill); return groups; }, {});
}
function groupSkills(analysis: JDAnalysisResult) {
  const groups = ["required_skills", "preferred_skills", "unclassified_requirement_skills"] as const;
  return allSkills(analysis).reduce<Record<string, { skill: SkillEvidence; group: typeof groups[number]; index: number }[]>>((result, skill) => {
    const group = groups.find(key => analysis[key].includes(skill))!;
    const index = analysis[group].indexOf(skill);
    (result[skill.category_code] ||= []).push({ skill, group, index });
    return result;
  }, {});
}
function EditableEvidence({ title, items, onEdit }: { title: string; items: EvidenceText[]; onEdit: (index: number, text: string) => void }) {
  return <section className="evidence-section"><h3>{title}</h3>{items.length ? items.map((item, index) => <div key={`${title}-${index}`}><label className="field-label">{title} {index + 1}<textarea value={item.text} onChange={event => onEdit(index, event.target.value)} /></label><Evidence>{item.evidence}</Evidence></div>) : <p className="hint">Not identified in the text.</p>}</section>;
}
