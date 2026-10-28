import type { ModuleId } from "./contracts";

const modules: { id: ModuleId; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "jd", label: "JD Analytics" },
  { id: "resume", label: "Resume Parsing" },
  { id: "profile", label: "Profile Builder" },
  { id: "matching", label: "Skill Matching" },
  { id: "talent", label: "Talent Check" },
];

export default function ModuleNavigation({ active, onNavigate }: { active: ModuleId; onNavigate: (module: ModuleId) => void }) {
  return <header className="topbar">
    <div className="brand-mark" aria-hidden="true">R</div>
    <div className="brand-name">RADIX <span>TALENT MATCH</span></div>
    <nav className="module-nav" aria-label="RADIX modules">
      {modules.map(module => module.id === active
        ? <span className="nav-current" aria-current="page" key={module.id}>{module.label}</span>
        : <button className="nav-button" onClick={() => onNavigate(module.id)} key={module.id}>{module.label}</button>)}
    </nav>
  </header>;
}
