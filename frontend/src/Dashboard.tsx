import ModuleNavigation from "./ModuleNavigation";
import type { AcceptedArtifact, CandidateProfile, JDAnalysisResult, ModuleId } from "./contracts";

export default function Dashboard({
  onNavigate,
  acceptedResume,
  acceptedJds,
  acceptedProfiles,
  matchingResult,
  onClearLocalData,
}: {
  onNavigate: (module: ModuleId) => void;
  acceptedResume: boolean;
  acceptedJds: AcceptedArtifact<JDAnalysisResult>[];
  acceptedProfiles: AcceptedArtifact<CandidateProfile>[];
  matchingResult: boolean;
  onClearLocalData: () => void;
}) {
  const cards: { id: Exclude<ModuleId, "dashboard">; title: string; description: string; next: string }[] = [
    { id: "jd", title: "JD Analytics", description: "Extract, review, and accept job requirements.", next: "Upload or analyze a job description." },
    { id: "resume", title: "Resume Parsing", description: "Extract editable candidate details with evidence.", next: "Upload a resume; accepting its draft makes it available to Profile Builder." },
    { id: "profile", title: "Profile Builder", description: "Create a profile manually or prefill from a reviewed resume.", next: "Edit and accept a profile for Job Skill Matching." },
    { id: "matching", title: "Job Skill Matching", description: "Compare an accepted job analysis with an accepted profile.", next: acceptedJds.length && acceptedProfiles.length ? "Both required inputs are available." : "Accept a JD analysis and a candidate profile first." },
    { id: "talent", title: "Company Talent Check", description: "Inspect company competency expectations from the official staging source.", next: "Company data requires verified Supabase access; readiness scoring is not approved." },
  ];
  const nextStep = acceptedJds.length === 0
    ? { text: "Next: analyze and accept a job description. You can prepare a candidate profile now or later.", module: "jd" as const, label: "Open JD Analytics" }
    : acceptedProfiles.length === 0
      ? acceptedResume
        ? { text: "Next: build a profile from the accepted resume, or create one manually.", module: "profile" as const, label: "Open Profile Builder" }
        : { text: "Next: accept a resume and build a profile, or create a profile manually.", module: "resume" as const, label: "Open Resume Parsing" }
      : !matchingResult
        ? { text: "Next: choose the accepted job and profile in Skill Matching.", module: "matching" as const, label: "Open Job Skill Matching" }
        : { text: "A comparison is available. Review it or create another accepted input first.", module: "matching" as const, label: "Review Skill Matching" };
  const progressSteps = [
    { module: "jd" as const, label: "JD Analytics", status: acceptedJds.length ? `${acceptedJds.length} accepted` : "Not accepted", complete: acceptedJds.length > 0 },
    { module: "resume" as const, label: "Resume Parsing", status: acceptedResume ? "Accepted · optional" : "Optional", complete: acceptedResume !== null },
    { module: "profile" as const, label: "Profile Builder", status: acceptedProfiles.length ? `${acceptedProfiles.length} accepted` : "Not accepted", complete: acceptedProfiles.length > 0 },
    { module: "matching" as const, label: "Job Skill Matching", status: matchingResult ? "Compared" : "Needs accepted inputs", complete: matchingResult },
  ];

  return <main className="shell">
    <ModuleNavigation active="dashboard" onNavigate={onNavigate} />
    <section className="hero"><div className="eyebrow">RADIX TALENT MATCH</div><h1>Start with the task<br /><em>you came to do.</em></h1><p>Accepted workflow artifacts and the profile draft are saved in this browser only to support local development. They do not sync between devices.</p><div className="notice">Anyone with access to this browser profile may be able to access saved data. Use synthetic data during development and avoid storing sensitive real resumes.</div></section>
    <section className="workflow-status panel" aria-labelledby="workflow-status-heading">
      <div><div className="eyebrow">THIS BROWSER</div><h2 id="workflow-status-heading">Available artifacts</h2><p>Workflow artifacts and the editable profile draft are restored after a refresh.</p><button className="secondary-button" onClick={() => { if (window.confirm("Clear RADIX Talent Match data saved by this application in this browser? This does not clear other website data.")) onClearLocalData(); }}>Clear local data</button></div>
      <div className="artifact-counts">
        <div><strong>{acceptedJds.length}</strong><span>accepted job analyses</span></div>
        <div><strong>{acceptedResume ? "Yes" : "No"}</strong><span>accepted resume draft</span></div>
        <div><strong>{acceptedProfiles.length}</strong><span>accepted candidate profiles</span></div>
      </div>
      {!acceptedResume && acceptedProfiles.length === 0 && <p className="hint">To prepare a candidate artifact, open Resume Parsing or start a manual profile in Profile Builder.</p>}
    </section>
    <section className="panel workflow-progress" aria-labelledby="workflow-progress-heading">
      <div className="eyebrow">CANDIDATE WORKFLOW</div><h2 id="workflow-progress-heading">Progress and next step</h2>
      <ol aria-label="JD to candidate skill comparison progress">{progressSteps.map((step, index) => <li key={step.module} className={step.complete ? "complete" : "pending"}>
        <span className="workflow-step-number" aria-hidden="true">{step.complete ? "✓" : index + 1}</span>
        <div><strong>{step.label}</strong><span>{step.status}</span></div>
        <button className="text-button" onClick={() => onNavigate(step.module)}>Open</button>
      </li>)}</ol>
      <div className="workflow-next"><p>{nextStep.text}</p><button onClick={() => onNavigate(nextStep.module)}>{nextStep.label}</button></div>
      <p className="hint">Resume Parsing is optional; Profile Builder also supports manual entry. Company Talent Check is independent of this workflow.</p>
    </section>
    <section className="dashboard-grid" aria-label="RADIX modules">
      {cards.map(card => <article className="module-card" key={card.id}>
        <div className="eyebrow">{card.id === "matching" ? "USES ACCEPTED ARTIFACTS" : card.id === "talent" ? "SOURCE-DEPENDENT" : "INDEPENDENT ENTRY"}</div>
        <h2>{card.title}</h2><p>{card.description}</p>
        {card.id === "matching" && <div className="artifact-availability"><span>{acceptedJds.length ? `${acceptedJds.length} job analysis available` : "No accepted job analysis"}</span><span>{acceptedProfiles.length ? `${acceptedProfiles.length} profile available` : "No accepted profile"}</span></div>}
        {card.id === "resume" && <p className="hint">{acceptedResume ? "An accepted resume draft is available for profile prefill." : "No accepted resume draft is saved in this browser."}</p>}
        <p className="module-next">{card.next}</p><button onClick={() => onNavigate(card.id)}>Open {card.title}</button>
      </article>)}
    </section>
    <footer><span>RADIX TALENT MATCH</span><span>Browser-local workflow data · No fabricated activity or scores</span></footer>
  </main>;
}
