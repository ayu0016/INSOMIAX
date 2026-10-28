import ModuleNavigation from "./ModuleNavigation";
import type { AcceptedArtifact, CandidateProfile, JDAnalysisResult, ModuleId } from "./contracts";

export default function Dashboard({
  onNavigate,
  acceptedResume,
  acceptedJds,
  acceptedProfiles,
}: {
  onNavigate: (module: ModuleId) => void;
  acceptedResume: boolean;
  acceptedJds: AcceptedArtifact<JDAnalysisResult>[];
  acceptedProfiles: AcceptedArtifact<CandidateProfile>[];
}) {
  const cards: { id: Exclude<ModuleId, "dashboard">; title: string; description: string; next: string }[] = [
    { id: "jd", title: "JD Analytics", description: "Extract, review, and accept job requirements.", next: "Upload or analyze a job description." },
    { id: "resume", title: "Resume Parsing", description: "Extract editable candidate details with evidence.", next: "Upload a resume; accepting its draft makes it available to Profile Builder." },
    { id: "profile", title: "Profile Builder", description: "Create a profile manually or prefill from a reviewed resume.", next: "Edit and accept a profile for Job Skill Matching." },
    { id: "matching", title: "Job Skill Matching", description: "Compare an accepted job analysis with an accepted profile.", next: acceptedJds.length && acceptedProfiles.length ? "Both required inputs are available." : "Accept a JD analysis and a candidate profile first." },
    { id: "talent", title: "Company Talent Check", description: "Inspect company competency expectations from the official staging source.", next: "Company data requires verified Supabase access; readiness scoring is not approved." },
  ];

  return <main className="shell">
    <ModuleNavigation active="dashboard" onNavigate={onNavigate} />
    <section className="hero"><div className="eyebrow">RADIX TALENT MATCH</div><h1>Start with the task<br /><em>you came to do.</em></h1><p>Each module can be opened independently. Accepted artifacts connect the workflows during this browser session; nothing is permanently saved.</p></section>
    <section className="workflow-status panel" aria-labelledby="workflow-status-heading">
      <div><div className="eyebrow">CURRENT SESSION</div><h2 id="workflow-status-heading">Available artifacts</h2><p>Refreshing this page clears these artifacts and module drafts.</p></div>
      <div className="artifact-counts">
        <div><strong>{acceptedJds.length}</strong><span>accepted job analyses</span></div>
        <div><strong>{acceptedResume ? "Yes" : "No"}</strong><span>accepted resume draft</span></div>
        <div><strong>{acceptedProfiles.length}</strong><span>accepted candidate profiles</span></div>
      </div>
      {!acceptedResume && acceptedProfiles.length === 0 && <p className="hint">To prepare a candidate artifact, open Resume Parsing or start a manual profile in Profile Builder.</p>}
    </section>
    <section className="dashboard-grid" aria-label="RADIX modules">
      {cards.map(card => <article className="module-card" key={card.id}>
        <div className="eyebrow">{card.id === "matching" ? "USES ACCEPTED ARTIFACTS" : card.id === "talent" ? "SOURCE-DEPENDENT" : "INDEPENDENT ENTRY"}</div>
        <h2>{card.title}</h2><p>{card.description}</p>
        {card.id === "matching" && <div className="artifact-availability"><span>{acceptedJds.length ? `${acceptedJds.length} job analysis available` : "No accepted job analysis"}</span><span>{acceptedProfiles.length ? `${acceptedProfiles.length} profile available` : "No accepted profile"}</span></div>}
        {card.id === "resume" && <p className="hint">{acceptedResume ? "An accepted resume draft is available for profile prefill." : "No accepted resume draft in this session."}</p>}
        <p className="module-next">{card.next}</p><button onClick={() => onNavigate(card.id)}>Open {card.title}</button>
      </article>)}
    </section>
    <footer><span>RADIX TALENT MATCH</span><span>Session-only artifacts · No fabricated activity or scores</span></footer>
  </main>;
}
