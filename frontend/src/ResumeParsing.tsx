import { useState } from "react";

type Contact = { value: string; evidence: string } | null;
type Entry = { text: string; evidence: string; source_section: string; dates: string | null; duration: string | null };
type Skill = { skill_name: string; canonical_skill: string | null; category_code: string; evidence: string; confidence: string; source_section: string; evidence_kind: "explicit" | "inferred"; proficiency_level: number | null; proficiency_status: "not_assessed" };
export type ResumeDraft = {
  source_file: string | null; candidate_name: Contact; email: Contact; phone: Contact;
  education: Entry[]; work_experience: Entry[]; internships: Entry[]; projects: Entry[];
  skills: Skill[]; certifications: Entry[]; dates: { value: string; evidence: string; source_section: string }[];
  missing_or_ambiguous: string[]; proficiency_assessed: false; scores_available: false;
};
type DocumentText = { filename: string; text: string; character_count: number };
const apiBase = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function getError(response: Response): Promise<Error> {
  const body = await response.json().catch(() => null);
  return new Error(body?.error?.message || "The request failed. Check the backend and try again.");
}

export default function ResumeParsing({ onNavigate, onAccept, onInvalidate }: { onNavigate: (module: "jd" | "profile" | "matching" | "talent") => void; onAccept: (draft: ResumeDraft) => void; onInvalidate: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [document, setDocument] = useState<DocumentText | null>(null);
  const [resume, setResume] = useState<ResumeDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [accepted, setAccepted] = useState(false);

  async function upload() {
    if (!file) return;
    setBusy(true); setError(null); setResume(null); setAccepted(false); onInvalidate();
    try {
      const body = new FormData(); body.append("file", file);
      const response = await fetch(`${apiBase}/api/v1/resume-parsing/extract`, { method: "POST", body });
      if (!response.ok) throw await getError(response);
      setDocument(await response.json() as DocumentText);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Resume extraction failed."); }
    finally { setBusy(false); }
  }

  async function parse() {
    if (!document?.text.trim()) { setError("Add readable resume text before parsing."); return; }
    setBusy(true); setError(null); setAccepted(false);
    try {
      const response = await fetch(`${apiBase}/api/v1/resume-parsing/parse`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: document.text, source_file: document.filename }) });
      if (!response.ok) throw await getError(response);
      setResume(await response.json() as ResumeDraft);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Resume parsing failed."); }
    finally { setBusy(false); }
  }

  function editContact(key: "candidate_name" | "email" | "phone", value: string) {
    setResume(current => current ? { ...current, [key]: value.trim() ? { value, evidence: current[key]?.evidence || "Manually edited by the user." } : null } : current);
    onInvalidate();
    setAccepted(false);
  }
  function updateEntries(key: "education" | "work_experience" | "internships" | "projects" | "certifications", entries: Entry[]) {
    setResume(current => current ? { ...current, [key]: entries } : current); setAccepted(false); onInvalidate();
  }
  function updateSkills(skills: Skill[]) { setResume(current => current ? { ...current, skills } : current); setAccepted(false); onInvalidate(); }
  function updateDates(dates: ResumeDraft["dates"]) { setResume(current => current ? { ...current, dates } : current); setAccepted(false); onInvalidate(); }

  return <main className="shell">
    <header className="topbar"><div className="brand-mark">R</div><div className="brand-name">RADIX <span>TALENT MATCH</span></div><nav className="module-nav" aria-label="RADIX modules"><button className="nav-button" onClick={() => onNavigate("jd")}>JD Analytics</button><span className="nav-current" aria-current="page">Resume Parsing</span><button className="nav-button" onClick={() => onNavigate("profile")}>Profile Builder</button><button className="nav-button" onClick={() => onNavigate("matching")}>Skill Matching</button><button className="nav-button" onClick={() => onNavigate("talent")}>Talent Check</button></nav></header>
    <section className="hero"><div className="eyebrow">RESUME PARSING</div><h1>Review what’s stated.<br /><em>Keep every claim traceable.</em></h1><p>Extract editable resume details with evidence. Skill mentions do not establish proficiency, employability, readiness, or job fit.</p></section>
    <section className="panel" aria-labelledby="resume-upload-heading">
      <div className="eyebrow">STEP 1</div><h2 id="resume-upload-heading">Upload a resume</h2>
      <label className="field-label" htmlFor="resume-file">Choose a PDF or DOCX file</label><div className="upload-row"><input id="resume-file" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={event => { setFile(event.target.files?.[0] || null); setDocument(null); setResume(null); setError(null); setAccepted(false); onInvalidate(); }} /><button onClick={upload} disabled={!file || busy}>{busy ? "Extracting…" : "Extract resume text"}</button></div>
      <p className="hint">Uploads are processed in memory and are not saved. Scanned PDFs require OCR, which is not available.</p>
      {error && <div className="notice notice-error" role="alert">{error}</div>}
    </section>
    {document && <section className="panel" aria-labelledby="resume-text-heading"><div className="eyebrow">STEP 2 · TEXT REVIEW</div><h2 id="resume-text-heading">Review extracted text</h2><p className="hint">{document.filename} · {document.character_count.toLocaleString()} characters</p><label className="field-label" htmlFor="resume-text">Resume text (editable)</label><textarea id="resume-text" className="text-review" value={document.text} onChange={event => { setDocument({ ...document, text: event.target.value }); setResume(null); setAccepted(false); onInvalidate(); }} /><button onClick={parse} disabled={busy || !document.text.trim()}>{busy ? "Parsing…" : "Parse resume"}</button></section>}
    {resume && <section className="panel results" aria-labelledby="resume-results-heading">
      <div className="eyebrow">STEP 3 · REVIEW & EDIT</div><h2 id="resume-results-heading">Candidate details</h2><p className="hint">Deterministic heuristic extraction. Edit or remove incorrect findings before accepting.</p>
      <div className="contact-grid"><ContactEditor label="Candidate name" value={resume.candidate_name} onChange={value => editContact("candidate_name", value)} /><ContactEditor label="Email" value={resume.email} onChange={value => editContact("email", value)} /><ContactEditor label="Phone" value={resume.phone} onChange={value => editContact("phone", value)} /></div>
      <EntryEditor title="Education & qualifications" items={resume.education} onChange={items => updateEntries("education", items)} />
      <EntryEditor title="Work experience" items={resume.work_experience} onChange={items => updateEntries("work_experience", items)} />
      <EntryEditor title="Internships" items={resume.internships} onChange={items => updateEntries("internships", items)} />
      <EntryEditor title="Projects" items={resume.projects} onChange={items => updateEntries("projects", items)} />
      <SkillEditor skills={resume.skills} onChange={updateSkills} />
      <EntryEditor title="Certifications" items={resume.certifications} onChange={items => updateEntries("certifications", items)} />
      <section className="evidence-section"><h3>Identified dates</h3>{resume.dates.length ? resume.dates.map((date, index) => <div className="date-evidence" key={`${date.value}-${index}`}><label className="field-label">Date<input value={date.value} onChange={event => updateDates(resume.dates.map((item, i) => i === index ? { ...item, value: event.target.value } : item))} /></label><span>{date.source_section}</span><blockquote>{date.evidence}</blockquote><button className="remove-button" onClick={() => updateDates(resume.dates.filter((_, i) => i !== index))}>Remove date</button></div>) : <p className="hint">No dates were confidently identified.</p>}</section>
      {resume.missing_or_ambiguous.length > 0 && <div className="notice"><strong>Not identified or ambiguous:</strong> {resume.missing_or_ambiguous.join(", ")}. You can add or correct information while reviewing.</div>}
      <div className="notice">Proficiency is not assessed. Mentioning a skill is not evidence of mastery. Nothing is saved to a server.</div>
      <button className="accept-button" onClick={() => { setAccepted(true); onAccept(resume); }}>{accepted ? "Resume extraction accepted" : "Accept reviewed extraction"}</button>{accepted && <p className="success" role="status">Accepted in this browser session only. Open Profile Builder to prefill a candidate profile.</p>}
    </section>}
    <footer><span>RADIX TALENT MATCH</span><span>Resume claims stay evidence-linked · No scores</span></footer>
  </main>;
}

function ContactEditor({ label, value, onChange }: { label: string; value: Contact; onChange: (value: string) => void }) {
  return <div className="contact-editor"><label className="field-label">{label}<input value={value?.value || ""} placeholder="Not identified" onChange={event => onChange(event.target.value)} /></label>{value?.evidence && <blockquote>{value.evidence}</blockquote>}</div>;
}

function EntryEditor({ title, items, onChange }: { title: string; items: Entry[]; onChange: (items: Entry[]) => void }) {
  return <section className="evidence-section"><h3>{title}</h3>{items.length === 0 ? <p className="hint">No items identified.</p> : items.map((entry, index) => <article className="resume-entry" key={`${title}-${index}`}><label className="field-label">{title} {index + 1}<textarea value={entry.text} onChange={event => onChange(items.map((item, i) => i === index ? { ...item, text: event.target.value } : item))} /></label><div className="skill-edit-grid"><label className="field-label">Dates<input value={entry.dates || ""} placeholder="Not identified" onChange={event => onChange(items.map((item, i) => i === index ? { ...item, dates: event.target.value || null } : item))} /></label><label className="field-label">Duration<input value={entry.duration || ""} placeholder="Not identified" onChange={event => onChange(items.map((item, i) => i === index ? { ...item, duration: event.target.value || null } : item))} /></label></div><small>Source section: {entry.source_section}</small><blockquote>{entry.evidence}</blockquote><button className="remove-button" onClick={() => onChange(items.filter((_, i) => i !== index))}>Remove finding</button></article>)}</section>;
}

function SkillEditor({ skills, onChange }: { skills: Skill[]; onChange: (skills: Skill[]) => void }) {
  return <section className="evidence-section"><h3>Skills</h3>{skills.length === 0 ? <p className="hint">No configured vocabulary skills identified. Configure reviewed terms on the backend if needed.</p> : skills.map((skill, index) => <article className="resume-entry" key={`${skill.skill_name}-${index}`}><div className="skill-edit-grid"><label className="field-label">Skill<input value={skill.skill_name} onChange={event => onChange(skills.map((item, i) => i === index ? { ...item, skill_name: event.target.value, canonical_skill: null } : item))} /></label><label className="field-label">Category<select value={skill.category_code} onChange={event => onChange(skills.map((item, i) => i === index ? { ...item, category_code: event.target.value } : item))}>{["COD","DSA","OOD","APTI","COMM","AI","CLOUD","SQL","SWE","SYSD","NETW","OS","OTHER"].map(code => <option key={code}>{code}</option>)}</select></label></div><small>Detected {skill.evidence_kind} in {skill.source_section}; confidence {skill.confidence}; proficiency not assessed.</small><blockquote>{skill.evidence}</blockquote><button className="remove-button" onClick={() => onChange(skills.filter((_, i) => i !== index))}>Remove finding</button></article>)}</section>;
}
