import { useEffect, useState } from "react";
import ModuleNavigation from "./ModuleNavigation";
import type { AcceptedArtifact, CandidateProfile, JDAnalysisResult, ModuleId, SkillMatchFinding, SkillMatchResponse } from "./contracts";
import type { MatchingSession } from "./localPersistence";

const apiBase = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
async function responseError(response: Response): Promise<Error> {
  const body = await response.json().catch(() => null);
  const fields = (body?.error?.details?.errors || []).map((item: { loc?: string[] }) => item.loc?.filter(part => part !== "body").join(" → ")).filter(Boolean);
  return new Error(fields.length ? `${body?.error?.message || "Matching request failed."} Check: ${fields.join(", ")}.` : body?.error?.message || "Matching is unavailable. Check the backend and try again.");
}

export default function JobSkillMatching({ jobDescriptions, candidateProfiles, session, onSessionChange, onNavigate }: {
  jobDescriptions: AcceptedArtifact<JDAnalysisResult>[];
  candidateProfiles: AcceptedArtifact<CandidateProfile>[];
  session: MatchingSession;
  onSessionChange: (session: MatchingSession) => void;
  onNavigate: (module: ModuleId) => void;
}) {
  const { jobId, profileId, result } = session;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectedJob = jobDescriptions.find(item => item.id === jobId) || null;
  const selectedProfile = candidateProfiles.find(item => item.id === profileId) || null;

  useEffect(() => {
    const valid = jobDescriptions.some(item => item.id === jobId);
    const nextId = valid ? jobId : jobDescriptions[0]?.id || "";
    if (nextId !== jobId || (!valid && session.result !== null)) onSessionChange({ ...session, jobId: nextId, result: null });
  }, [jobDescriptions, jobId, session, onSessionChange]);
  useEffect(() => {
    const valid = candidateProfiles.some(item => item.id === profileId);
    const nextId = valid ? profileId : candidateProfiles[0]?.id || "";
    if (nextId !== profileId || (!valid && session.result !== null)) onSessionChange({ ...session, profileId: nextId, result: null });
  }, [candidateProfiles, profileId, session, onSessionChange]);

  async function compare() {
    const job = jobDescriptions.find(item => item.id === jobId);
    const candidate = candidateProfiles.find(item => item.id === profileId);
    if (!job || !candidate) { setError("Accept a JD Analytics result and a Profile Builder profile before comparing."); return; }
    setBusy(true); setError(null); onSessionChange({ ...session, result: null });
    try {
      const response = await fetch(`${apiBase}/api/v1/skill-matches`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ job_description: job.data, candidate_profile: candidate.data }) });
      if (!response.ok) throw await responseError(response);
      onSessionChange({ ...session, result: await response.json() as SkillMatchResponse });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Matching failed."); }
    finally { setBusy(false); }
  }

  return <main className="shell">
    <ModuleNavigation active="matching" onNavigate={onNavigate} />
    <section className="hero"><div className="eyebrow">JOB SKILL MATCHING</div><h1>Compare documented evidence.<br /><em>Review every decision.</em></h1><p>Exact skill terms and reviewed mappings are compared deterministically. A keyword match does not establish proficiency, qualification, or fit.</p></section>
    <section className="panel" aria-labelledby="matching-input-heading"><div className="eyebrow">ACCEPTED SESSION DATA</div><h2 id="matching-input-heading">Choose inputs</h2>
      <label className="field-label" htmlFor="matching-jd">Accepted job description</label><select id="matching-jd" value={jobId} disabled={busy || !jobDescriptions.length} onChange={event => onSessionChange({ ...session, jobId: event.target.value, result: null })}><option value="">{jobDescriptions.length ? "Choose an accepted job description" : "No accepted JD available"}</option>{jobDescriptions.map(item => <option value={item.id} key={item.id}>{item.label}</option>)}</select>
      <label className="field-label" htmlFor="matching-profile">Accepted candidate profile</label><select id="matching-profile" value={profileId} disabled={busy || !candidateProfiles.length} onChange={event => onSessionChange({ ...session, profileId: event.target.value, result: null })}><option value="">{candidateProfiles.length ? "Choose an accepted candidate profile" : "No accepted profile available"}</option>{candidateProfiles.map(item => <option value={item.id} key={item.id}>{item.label}</option>)}</select>
      {(selectedJob || selectedProfile) && <div className="selected-artifacts" aria-label="Selected matching inputs">
        {selectedJob && <div><strong>Job:</strong> {selectedJob.label}<button className="text-button" onClick={() => onNavigate("jd")}>Review source</button></div>}
        {selectedProfile && <div><strong>Candidate:</strong> {selectedProfile.label}<button className="text-button" onClick={() => onNavigate("profile")}>Review source</button></div>}
      </div>}
      {!jobDescriptions.length && <div className="notice">No accepted JD Analytics result is available. Analyze and accept a job description first. <button className="text-button" onClick={() => onNavigate("jd")}>Open JD Analytics</button></div>}
      {!candidateProfiles.length && <div className="notice">No accepted candidate profile is available. Review and accept a profile in Profile Builder first. <button className="text-button" onClick={() => onNavigate("profile")}>Open Profile Builder</button></div>}
      <button onClick={compare} disabled={busy || !jobId || !profileId}>{busy ? "Comparing…" : "Compare documented skills"}</button>
      {error && <div className="notice notice-error" role="alert">{error}</div>}
    </section>
    {busy && <div className="notice" role="status">Comparing the selected session data…</div>}
    {result && <section className="panel" aria-labelledby="match-results-heading"><div className="eyebrow">DETERMINISTIC COMPARISON</div><h2 id="match-results-heading">{result.job_title || "Job requirements"}{result.candidate_name ? ` · ${result.candidate_name}` : ""}</h2><div className="notice">No numerical score is calculated. Skill mentions and mappings do not verify proficiency or qualification. Revisit the source module to correct data.</div>
      <FindingGroup title="Matched" items={result.matched} />
      <FindingGroup title="Partially matched" items={result.partially_matched} />
      <FindingGroup title="Missing" items={result.missing} />
      <FindingGroup title="Needs review / unknown" items={result.needs_review} />
      {result.matched.length + result.partially_matched.length + result.missing.length + result.needs_review.length === 0 && <p className="hint">No skill findings were returned for these inputs.</p>}
    </section>}
    <footer><span>RADIX TALENT MATCH</span><span>Evidence comparison · No score or ranking</span></footer>
  </main>;
}

function FindingGroup({ title, items }: { title: string; items: SkillMatchFinding[] }) {
  return <section className="match-group"><h3>{title} <small>({items.length})</small></h3>{items.length === 0 ? <p className="hint">No items.</p> : items.map((item, index) => <article className="match-finding" key={`${item.job_skill}-${item.requirement_type}-${index}`}>
    <div className="match-title"><strong>{item.job_skill}</strong><span>{item.requirement_type} · {item.category_code}</span></div>
      <div className="match-columns"><div><h4>Job requirement evidence</h4><blockquote>{item.job_evidence}</blockquote></div><div><h4>Candidate evidence</h4>{item.candidate_evidence.length ? item.candidate_evidence.map((evidence, i) => <div className="candidate-match-evidence" key={`${evidence.source}-${evidence.evidence}-${i}`}><p><strong>{evidence.skill_name}</strong> · {evidence.source_section || evidence.source}{evidence.evidence_kind === "explicit" && <span className="evidence-badge">EXPLICIT</span>}{evidence.evidence_kind === "inferred" && <span className="evidence-badge">INFERRED</span>}{evidence.evidence_kind === "manual" && <span className="evidence-badge">MANUAL</span>}{evidence.review_note && <span className="evidence-badge">CATEGORY REVIEW</span>}</p><blockquote>{evidence.evidence}</blockquote><small>{evidence.proficiency_level === null ? "Proficiency unknown" : `Self-reported proficiency ${evidence.proficiency_level}/10`}; mention is not verification.{evidence.confidence ? ` Detection confidence: ${evidence.confidence}.` : ""}</small></div>) : <p className="hint">No direct supporting excerpt.</p>}</div></div>
    <p className="match-explanation"><strong>Why:</strong> {item.explanation}</p>
  </article>)}</section>;
}
