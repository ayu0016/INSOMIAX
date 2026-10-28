import { useEffect, useState } from "react";
import type { AcceptedArtifact, CandidateProfile, JDAnalysisResult, SkillMatchFinding, SkillMatchResponse } from "./contracts";

const apiBase = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
type ModuleName = "jd" | "resume" | "profile" | "talent";

async function responseError(response: Response): Promise<Error> {
  const body = await response.json().catch(() => null);
  const fields = (body?.error?.details?.errors || []).map((item: { loc?: string[] }) => item.loc?.filter(part => part !== "body").join(" → ")).filter(Boolean);
  return new Error(fields.length ? `${body?.error?.message || "Matching request failed."} Check: ${fields.join(", ")}.` : body?.error?.message || "Matching is unavailable. Check the backend and try again.");
}

export default function JobSkillMatching({ jobDescriptions, candidateProfiles, onNavigate }: {
  jobDescriptions: AcceptedArtifact<JDAnalysisResult>[];
  candidateProfiles: AcceptedArtifact<CandidateProfile>[];
  onNavigate: (module: ModuleName) => void;
}) {
  const [jobId, setJobId] = useState("");
  const [profileId, setProfileId] = useState("");
  const [result, setResult] = useState<SkillMatchResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { if (!jobDescriptions.some(item => item.id === jobId)) setJobId(jobDescriptions[0]?.id || ""); }, [jobDescriptions, jobId]);
  useEffect(() => { if (!candidateProfiles.some(item => item.id === profileId)) setProfileId(candidateProfiles[0]?.id || ""); }, [candidateProfiles, profileId]);

  async function compare() {
    const job = jobDescriptions.find(item => item.id === jobId);
    const candidate = candidateProfiles.find(item => item.id === profileId);
    if (!job || !candidate) { setError("Accept a JD Analytics result and a Profile Builder profile before comparing."); return; }
    setBusy(true); setError(null); setResult(null);
    try {
      const response = await fetch(`${apiBase}/api/v1/skill-matches`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ job_description: job.data, candidate_profile: candidate.data }) });
      if (!response.ok) throw await responseError(response);
      setResult(await response.json() as SkillMatchResponse);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Matching failed."); }
    finally { setBusy(false); }
  }

  return <main className="shell">
    <header className="topbar"><div className="brand-mark">R</div><div className="brand-name">RADIX <span>TALENT MATCH</span></div><nav className="module-nav" aria-label="RADIX modules"><button className="nav-button" onClick={() => onNavigate("jd")}>JD Analytics</button><button className="nav-button" onClick={() => onNavigate("resume")}>Resume Parsing</button><button className="nav-button" onClick={() => onNavigate("profile")}>Profile Builder</button><span className="nav-current" aria-current="page">Skill Matching</span><button className="nav-button" onClick={() => onNavigate("talent")}>Talent Check</button></nav></header>
    <section className="hero"><div className="eyebrow">JOB SKILL MATCHING</div><h1>Compare documented evidence.<br /><em>Review every decision.</em></h1><p>Exact skill terms and reviewed mappings are compared deterministically. A keyword match does not establish proficiency, qualification, or fit.</p></section>
    <section className="panel" aria-labelledby="matching-input-heading"><div className="eyebrow">ACCEPTED SESSION DATA</div><h2 id="matching-input-heading">Choose inputs</h2>
      <label className="field-label" htmlFor="matching-jd">Accepted job description</label><select id="matching-jd" value={jobId} disabled={!jobDescriptions.length} onChange={event => { setJobId(event.target.value); setResult(null); }}><option value="">{jobDescriptions.length ? "Choose an accepted job description" : "No accepted JD available"}</option>{jobDescriptions.map(item => <option value={item.id} key={item.id}>{item.label}</option>)}</select>
      <label className="field-label" htmlFor="matching-profile">Accepted candidate profile</label><select id="matching-profile" value={profileId} disabled={!candidateProfiles.length} onChange={event => { setProfileId(event.target.value); setResult(null); }}><option value="">{candidateProfiles.length ? "Choose an accepted candidate profile" : "No accepted profile available"}</option>{candidateProfiles.map(item => <option value={item.id} key={item.id}>{item.label}</option>)}</select>
      {!jobDescriptions.length && <div className="notice">No accepted JD Analytics result is available. Analyze and accept a job description first.</div>}
      {!candidateProfiles.length && <div className="notice">No accepted candidate profile is available. Review and accept a profile in Profile Builder first.</div>}
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
