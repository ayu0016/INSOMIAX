import { useState } from "react";
import ModuleNavigation from "./ModuleNavigation";
import type { ModuleId } from "./contracts";

const apiBase = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

type SourceMetadata = {
  source_table: string;
  source_schema: string;
  row_count: number;
  columns: { column_name: string; data_type: string; database_type: string; nullable: boolean; ordinal_position: number }[];
};
type ApiErrorPayload = { error?: { code?: string; message?: string; details?: { source?: SourceMetadata } } };
type HealthPayload = { database_configured?: boolean; auth_configured?: boolean };
type ViewState = "idle" | "loading" | "authentication" | "configuration" | "unavailable" | "schema" | "error";

export default function CompanyTalentCheck({ onNavigate }: { onNavigate: (module: ModuleId) => void }) {
  const [state, setState] = useState<ViewState>("idle");
  const [message, setMessage] = useState<string>("");
  const [source, setSource] = useState<SourceMetadata | null>(null);

  async function inspectSource() {
    setState("loading"); setMessage(""); setSource(null);
    try {
      const healthResponse = await fetch(`${apiBase}/api/v1/health`, { headers: { Accept: "application/json" } });
      if (!healthResponse.ok) throw new Error("The RADIX API health check failed.");
      const health = await healthResponse.json() as HealthPayload;
      if (!health.database_configured || !health.auth_configured) {
        setState("configuration");
        setMessage(`Backend configuration is incomplete (database: ${health.database_configured ? "configured" : "not configured"}; Supabase Auth: ${health.auth_configured ? "configured" : "not configured"}).`);
        return;
      }
      const response = await fetch(`${apiBase}/api/v1/talent-check/source`, { headers: { Accept: "application/json" } });
      const payload = await response.json().catch(() => ({})) as ApiErrorPayload;
      if (response.ok) {
        setState("schema");
        setMessage("The source responded without the documented verified-company contract. No company values are shown until the API mapping is reviewed.");
        return;
      }
      const code = payload.error?.code || "REQUEST_FAILED";
      setMessage(payload.error?.message || "The source could not be inspected.");
      setSource(payload.error?.details?.source || null);
      if (code === "AUTHENTICATION_REQUIRED" || code === "INVALID_ACCESS_TOKEN") setState("authentication");
      else if (code === "AUTH_CONFIGURATION_REQUIRED" || code === "DATABASE_CONFIGURATION_REQUIRED") setState("configuration");
      else if (["DATABASE_UNAVAILABLE", "SOURCE_TABLE_NOT_FOUND", "AUTH_PROVIDER_UNAVAILABLE"].includes(code)) setState("unavailable");
      else if (["SCHEMA_VERIFICATION_REQUIRED", "SOURCE_SCHEMA_AMBIGUOUS"].includes(code)) setState("schema");
      else setState("error");
    } catch {
      setState("unavailable");
      setMessage("The RADIX API could not be reached. Start the backend and try again.");
    }
  }

  return <main className="shell">
    <ModuleNavigation active="talent" onNavigate={onNavigate} />
    <section className="hero"><div className="eyebrow">COMPANY TALENT CHECK</div><h1>Inspect verified competencies.<br /><em>Keep the source visible.</em></h1><p>Company expectations must come from the official staging table. Readiness stays disabled until source mapping and an approved scoring policy are available.</p></section>
    <section className="panel" aria-labelledby="source-heading"><div className="eyebrow">OFFICIAL SOURCE</div><h2 id="source-heading">Company competency data</h2>
      <p className="hint">This page never substitutes demo records or illustrative company benchmarks for the staging table.</p>
      <button onClick={inspectSource} disabled={state === "loading"}>{state === "loading" ? "Checking source…" : state === "idle" ? "Check source availability" : "Check again"}</button>
      {state === "loading" && <p role="status" className="notice">Checking authentication and source availability…</p>}
      {state === "authentication" && <div className="notice notice-error" role="alert"><strong>Authentication required.</strong> {message} The application does not currently provide a Supabase sign-in flow, so authenticated company data cannot be loaded from this screen.</div>}
      {state === "configuration" && <div className="notice notice-error" role="alert"><strong>Configuration required.</strong> {message} Configure the backend-only read-only database DSN and Supabase Auth settings in the local environment. Do not put database credentials in React.</div>}
      {state === "unavailable" && <div className="notice notice-error" role="alert"><strong>Source unavailable.</strong> {message}</div>}
      {state === "error" && <div className="notice notice-error" role="alert"><strong>Request failed.</strong> {message}</div>}
      {state === "schema" && <div className="notice" role="status"><strong>Competency data unavailable pending verification.</strong> {message}</div>}
      {source && <div className="source-metadata"><h3>Safe source metadata</h3><p>Table: <code>{source.source_schema}.{source.source_table}</code> · rows: {source.row_count}</p><p>Column names and types only; no source records or competency values were returned.</p><ul>{source.columns.map(column => <li key={`${column.ordinal_position}-${column.column_name}`}><code>{column.column_name}</code> — {column.database_type}{column.nullable ? " (nullable)" : " (required)"}</li>)}</ul></div>}
      <div className="notice">No verified company list or competency mapping is currently available. The three target company identifiers and exact source columns must be verified before a selector can be populated. Readiness scoring is disabled because the formula, category weights, missing-proficiency behavior, and critical-gap policy are not approved.</div>
    </section>
    <footer><span>RADIX TALENT MATCH</span><span>Staging source only · No fabricated values or scores</span></footer>
  </main>;
}
