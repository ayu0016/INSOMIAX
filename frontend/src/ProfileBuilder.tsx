import { useEffect, useRef, useState } from "react";
import type { CandidateProfile as Profile, ProfileEntry as Entry, ProfileField, ProfileSkill as Skill, ProfileSource, ResumeParseArtifact } from "./contracts";
import ModuleNavigation from "./ModuleNavigation";
import type { ModuleId } from "./contracts";

type Preview = { profile: Profile; missing_fields: string[]; warnings: string[]; persistence_available: false; scores_available: false };
type Source = ProfileSource;
const apiBase = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

function fromResume(draft: ResumeParseArtifact): Profile {
  const contact = (field: ResumeParseArtifact["candidate_name"]): ProfileField | null => field ? { value: field.value, evidence: field.evidence, source: "resume", edited_by_user: false } : null;
  const entries = (items: ResumeParseArtifact["education"]): Entry[] => items.map(item => ({ text: item.text, dates: item.dates, duration: item.duration, evidence: item.evidence, source_section: item.source_section, source: "resume", edited_by_user: false }));
  return { name: contact(draft.candidate_name), email: contact(draft.email), phone: contact(draft.phone), education: entries(draft.education), work_experience: entries(draft.work_experience), internships: entries(draft.internships), projects: entries(draft.projects), certifications: entries(draft.certifications), skills: draft.skills.map(skill => ({ skill_name: skill.skill_name, category_code: skill.category_code, source: "resume", edited_by_user: false, evidence: skill.evidence, confidence: skill.confidence, canonical_skill: skill.canonical_skill, source_section: skill.source_section, evidence_kind: skill.evidence_kind, proficiency_level: null, proficiency_status: "not_assessed" })), hackathons: [], preferred_roles: [], source_file: draft.source_file };
}

export default function ProfileBuilder({ resumeDraft, prefillRequest, profile, acceptedProfileCount, onDraftChange, onNavigate, onAccept }: { resumeDraft: ResumeParseArtifact | null; prefillRequest: number; profile: Profile; acceptedProfileCount: number; onDraftChange: (profile: Profile) => void; onNavigate: (module: ModuleId) => void; onAccept: (profile: Profile) => void }) {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [resumeWarnings, setResumeWarnings] = useState<string[]>([]);
  const [prefillConfirmation, setPrefillConfirmation] = useState(false);
  const [processedPrefillRequest, setProcessedPrefillRequest] = useState(0);
  const emailInput = useRef<HTMLInputElement | null>(null);

  function changeProfile(next: Profile) { onDraftChange(next); setPreview(null); setAccepted(false); setError(null); }
  function prefill() { if (resumeDraft) { changeProfile(fromResume(resumeDraft)); setResumeWarnings(resumeDraft.missing_or_ambiguous); setPrefillConfirmation(false); } }
  function requestResumePrefill() {
    if (!resumeDraft) return;
    if (isProfileBlank(profile)) prefill();
    else setPrefillConfirmation(true);
  }

  useEffect(() => {
    if (prefillRequest <= processedPrefillRequest) return;
    setProcessedPrefillRequest(prefillRequest);
    requestResumePrefill();
  }, [prefillRequest, processedPrefillRequest, resumeDraft, profile]);
  function addEntry(section: keyof Pick<Profile, "education" | "work_experience" | "internships" | "projects" | "certifications" | "hackathons" | "preferred_roles">) {
    changeProfile({ ...profile, [section]: [...profile[section], { text: "", source: "manual", edited_by_user: false, evidence: null, source_section: null, dates: null, duration: null }] } as Profile);
  }
  function updateEntry(section: keyof Pick<Profile, "education" | "work_experience" | "internships" | "projects" | "certifications" | "hackathons" | "preferred_roles">, index: number, patch: Partial<Entry>) {
    changeProfile({ ...profile, [section]: profile[section].map((entry, i) => i === index ? { ...entry, ...patch, edited_by_user: true } : entry) } as Profile);
  }
  function removeEntry(section: keyof Pick<Profile, "education" | "work_experience" | "internships" | "projects" | "certifications" | "hackathons" | "preferred_roles">, index: number) {
    changeProfile({ ...profile, [section]: profile[section].filter((_, i) => i !== index) } as Profile);
  }
  function updateSkill(index: number, patch: Partial<Skill>) {
    changeProfile({ ...profile, skills: profile.skills.map((skill, i) => i === index ? { ...skill, ...patch, edited_by_user: true, evidence_kind: skill.source === "resume" ? skill.evidence_kind : "manual" } : skill) });
  }
  function addSkill() { changeProfile({ ...profile, skills: [...profile.skills, { skill_name: "", category_code: "OTHER", source: "manual", edited_by_user: false, evidence: null, confidence: null, canonical_skill: null, source_section: null, evidence_kind: "manual", proficiency_level: null, proficiency_status: "not_assessed" }] }); }
  async function requestPreview() {
    if (emailInput.current && !emailInput.current.reportValidity()) return;
    setBusy(true); setError(null); setAccepted(false);
    try {
      const response = await fetch(`${apiBase}/api/v1/profiles/preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(profile) });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        const fields = (body?.error?.details?.errors || []).map((item: { loc?: string[] }) => item.loc?.filter(part => part !== "body").join(" → ")).filter(Boolean);
        throw new Error(fields.length ? `${body?.error?.message || "Profile validation failed."} Check: ${fields.join(", ")}.` : body?.error?.message || "Profile validation failed.");
      }
      setPreview(body as Preview);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Profile preview is unavailable."); }
    finally { setBusy(false); }
  }

  function setContact(key: "name" | "email" | "phone", value: string) {
    const current = profile[key];
    changeProfile({ ...profile, [key]: value.trim() ? { value, source: current?.source || "manual", edited_by_user: true, evidence: current?.evidence || null } : null });
  }

  return <main className="shell">
    <ModuleNavigation active="profile" onNavigate={onNavigate} />
    <section className="hero"><div className="eyebrow">PROFILE BUILDER</div><h1>Build your profile.<br /><em>Keep your sources clear.</em></h1><p>Start manually or prefill from an accepted resume draft. The editable draft is saved in this browser only; profile preview remains stateless and no profile is saved on the server.</p></section>
    <section className="panel"><div className="card-heading"><div><div className="eyebrow">CANDIDATE PROFILE</div><h2>Contact details</h2></div>{resumeDraft ? <button className="secondary-button" onClick={requestResumePrefill}>Prefill from accepted resume</button> : <span className="hint">No accepted resume draft is saved in this browser; you can build this profile manually.</span>}</div>
      {acceptedProfileCount > 0 && <div className="notice">{acceptedProfileCount} accepted profile snapshot{acceptedProfileCount === 1 ? " is" : "s are"} available to Job Skill Matching. Changes here affect only this editable draft; preview and accept again to create a new snapshot for matching.</div>}
      {resumeDraft && <div className="notice">Using the accepted parsed-resume artifact saved in this browser. Fields absent from that artifact stay blank; editing this profile does not change the parsed source.</div>}
      {prefillConfirmation && <div className="notice notice-error" role="alert"><strong>This profile already has content.</strong> Replace the current editable draft with the accepted resume prefill? The accepted resume artifact itself will remain unchanged.<div className="builder-actions"><button onClick={prefill}>Replace draft with resume details</button><button className="secondary-button" onClick={() => setPrefillConfirmation(false)}>Keep current draft</button></div></div>}
      <div className="contact-grid">{(["name", "email", "phone"] as const).map(key => <label className="field-label" key={key}>{key === "name" ? "Name" : key === "email" ? "Email" : "Phone"}<input ref={key === "email" ? emailInput : undefined} type={key === "email" ? "email" : "text"} maxLength={255} value={profile[key]?.value || ""} placeholder="Not provided" onChange={event => setContact(key, event.target.value)} />{profile[key]?.source && <small>Source: {profile[key]?.source === "resume" ? "Resume extraction" : "Manual entry"}</small>}{profile[key]?.evidence && <blockquote>{profile[key]?.evidence}</blockquote>}</label>)}</div>
      {profile.source_file && <p className="hint">Prefilled from {profile.source_file}; the resume file itself was not retained.</p>}{resumeWarnings.length > 0 && <div className="notice"><strong>Resume parser marked these fields missing or ambiguous:</strong> {resumeWarnings.join(", ")}. Blank profile fields remain unknown until you provide them.</div>}
    </section>
    <section className="panel"><h2>Profile sections</h2>
      <ProfileEntries title="Education" section="education" profile={profile} onAdd={addEntry} onEdit={updateEntry} onRemove={removeEntry} />
      <ProfileEntries title="Work experience" section="work_experience" profile={profile} onAdd={addEntry} onEdit={updateEntry} onRemove={removeEntry} />
      <ProfileEntries title="Internships" section="internships" profile={profile} onAdd={addEntry} onEdit={updateEntry} onRemove={removeEntry} />
      <ProfileEntries title="Projects" section="projects" profile={profile} onAdd={addEntry} onEdit={updateEntry} onRemove={removeEntry} />
      <ProfileSkills skills={profile.skills} onAdd={addSkill} onEdit={updateSkill} onRemove={i => changeProfile({ ...profile, skills: profile.skills.filter((_, index) => index !== i) })} />
      <ProfileEntries title="Certifications" section="certifications" profile={profile} onAdd={addEntry} onEdit={updateEntry} onRemove={removeEntry} />
      <ProfileEntries title="Hackathons" section="hackathons" profile={profile} onAdd={addEntry} onEdit={updateEntry} onRemove={removeEntry} />
      <ProfileEntries title="Preferred roles" section="preferred_roles" profile={profile} onAdd={addEntry} onEdit={updateEntry} onRemove={removeEntry} />
      <div className="builder-actions"><button onClick={requestPreview} disabled={busy}>{busy ? "Validating…" : "Preview profile"}</button><span className="hint">Preview validation is stateless. No profile record is created.</span></div>
      {error && <div className="notice notice-error" role="alert">{error}</div>}
    </section>
    {preview && <section className="panel" aria-labelledby="profile-preview-heading"><div className="eyebrow">REVIEW</div><h2 id="profile-preview-heading">Profile preview</h2>
      {preview.missing_fields.length > 0 && <div className="notice"><strong>Missing fields:</strong> {preview.missing_fields.join(", ")}</div>}{preview.warnings.map((warning, index) => <div className="notice" key={index}>{warning}</div>)}
      <ProfileSummary profile={preview.profile} />
      <button className="accept-button" disabled={accepted} onClick={() => { setAccepted(true); onAccept(preview.profile); }}>{accepted ? "Profile accepted locally" : "Accept reviewed profile"}</button>{accepted && <div className="success workflow-next-step" role="status"><p>Accepted in this browser only. No server-side profile was created.</p><button onClick={() => onNavigate("matching")}>Continue to Job Skill Matching</button></div>}
    </section>}
    <footer><span>RADIX TALENT MATCH</span><span>Browser-local profile · No scores or server save</span></footer>
  </main>;
}

type Section = keyof Pick<Profile, "education" | "work_experience" | "internships" | "projects" | "certifications" | "hackathons" | "preferred_roles">;
function isProfileBlank(profile: Profile): boolean {
  return !profile.name && !profile.email && !profile.phone
    && !profile.education.length && !profile.work_experience.length && !profile.internships.length
    && !profile.projects.length && !profile.skills.length && !profile.certifications.length
    && !profile.hackathons.length && !profile.preferred_roles.length;
}

function ProfileEntries({ title, section, profile, onAdd, onEdit, onRemove }: { title: string; section: Section; profile: Profile; onAdd: (section: Section) => void; onEdit: (section: Section, index: number, patch: Partial<Entry>) => void; onRemove: (section: Section, index: number) => void }) {
  return <section className="builder-section"><div className="builder-section-heading"><h3>{title}</h3><button className="secondary-button" onClick={() => onAdd(section)}>Add {title.toLowerCase()}</button></div>{profile[section].length === 0 && <p className="hint">No {title.toLowerCase()} added.</p>}{profile[section].map((entry, index) => <article className="resume-entry" key={`${section}-${index}`}><label className="field-label">Details<textarea value={entry.text} placeholder="Enter details" onChange={event => onEdit(section, index, { text: event.target.value })} /></label><div className="skill-edit-grid"><label className="field-label">Dates<input value={entry.dates || ""} placeholder="Unknown" onChange={event => onEdit(section, index, { dates: event.target.value || null })} /></label><label className="field-label">Duration<input value={entry.duration || ""} placeholder="Unknown" onChange={event => onEdit(section, index, { duration: event.target.value || null })} /></label></div><small>Source: {entry.source === "resume" ? `Resume extraction${entry.source_section ? ` · ${entry.source_section}` : ""}` : "Manual entry or edit"}</small>{entry.evidence && <blockquote>{entry.evidence}</blockquote>}<button className="remove-button" onClick={() => onRemove(section, index)}>Remove entry</button></article>)}</section>;
}

function ProfileSkills({ skills, onAdd, onEdit, onRemove }: { skills: Skill[]; onAdd: () => void; onEdit: (index: number, patch: Partial<Skill>) => void; onRemove: (index: number) => void }) {
  return <section className="builder-section"><div className="builder-section-heading"><h3>Skills</h3><button className="secondary-button" onClick={onAdd}>Add skill</button></div>{skills.length === 0 && <p className="hint">No skills added.</p>}{skills.map((skill, index) => <article className="resume-entry" key={`skill-${index}`}><div className="skill-edit-grid"><label className="field-label">Skill<input value={skill.skill_name} onChange={event => onEdit(index, { skill_name: event.target.value, canonical_skill: null })} /></label><label className="field-label">Category<select value={skill.category_code} onChange={event => onEdit(index, { category_code: event.target.value })}>{["COD","DSA","OOD","APTI","COMM","AI","CLOUD","SQL","SWE","SYSD","NETW","OS","OTHER"].map(code => <option key={code}>{code}</option>)}</select></label></div><label className="field-label">Self-reported proficiency (optional)<select value={skill.proficiency_level ?? ""} onChange={event => onEdit(index, event.target.value ? { proficiency_level: Number(event.target.value), proficiency_status: "user_reported" } : { proficiency_level: null, proficiency_status: "not_assessed" })}><option value="">Not assessed</option>{Array.from({ length: 10 }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1}</option>)}</select></label><small>Source: {skill.source === "resume" ? `Resume extraction · ${skill.evidence_kind} mention` : "Manual entry or edit"}; a mention does not verify proficiency.</small>{skill.evidence && <blockquote>{skill.evidence}</blockquote>}<button className="remove-button" onClick={() => onRemove(index)}>Remove skill</button></article>)}</section>;
}

function ProfileSummary({ profile }: { profile: Profile }) {
  const fields = (["education", "work_experience", "internships", "projects", "skills", "certifications", "hackathons", "preferred_roles"] as const);
  return <div className="profile-summary"><h3>{profile.name?.value || "Candidate profile"}</h3><p>{[profile.email?.value, profile.phone?.value].filter(Boolean).join(" · ") || "No contact details provided"}</p>{[profile.name, profile.email, profile.phone].filter((field): field is ProfileField => field !== null).map((field, index) => <p key={`contact-source-${index}`}><small>{field.source === "resume" ? "Resume extraction" : "Manual entry"}{field.edited_by_user ? " · edited" : ""}</small>{field.evidence && <blockquote>{field.evidence}</blockquote>}</p>)}{fields.map(key => {
    const entries = profile[key];
    return <section key={key}><h4>{key.replaceAll("_", " ")}</h4>{entries.length ? entries.map((item, index) => <div key={`${key}-${index}`}><p>{"skill_name" in item ? item.skill_name : item.text}{"dates" in item && item.dates ? ` · ${item.dates}` : ""}{"skill_name" in item && item.proficiency_level !== null ? ` · self-reported proficiency ${item.proficiency_level}/10` : ""} <small>({item.source === "resume" ? "Resume extraction" : "Manual entry"}{item.edited_by_user ? " · edited" : ""})</small></p>{item.evidence && <blockquote>{item.evidence}</blockquote>}</div>) : <p className="hint">None provided</p>}</section>;
  })}</div>;
}
