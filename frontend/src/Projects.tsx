import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  archiveProject, createProject, getContacts, getProjects, updateProject,
  type Contact, type Project, type ProjectInput, type User,
} from "./api";

const inputClass = "mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 font-normal outline-none transition focus:border-violet-600 focus:ring-4 focus:ring-violet-100";
const statusLabels = { quotation: "Angebot", active: "Aktiv", paused: "Pausiert", completed: "Abgeschlossen" } as const;

function emptyProject(): ProjectInput {
  return {
    customer: "", name: "", description: "", status: "quotation",
    start_date: null, end_date: null, budget_amount: null, budget_hours: null,
    default_hourly_rate: null,
  };
}

function projectToInput(project: Project): ProjectInput {
  return {
    customer: project.customer, name: project.name, description: project.description,
    status: project.status, start_date: project.start_date, end_date: project.end_date,
    budget_amount: project.budget_amount, budget_hours: project.budget_hours,
    default_hourly_rate: project.default_hourly_rate,
  };
}

function ProjectForm({ project, user, onCancel, onSaved }: {
  project: Project | null; user: User; onCancel: () => void; onSaved: () => void;
}) {
  const [form, setForm] = useState<ProjectInput>(() => project ? projectToInput(project) : emptyProject());
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [contactSearch, setContactSearch] = useState(project?.customer_name ?? "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      getContacts({ search: contactSearch.trim() }).then((result) => setContacts(result.results)).catch(() => setContacts([]));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [contactSearch]);

  function field(key: keyof ProjectInput, value: string | null) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      if (project) await updateProject(project, form);
      else await createProject(form);
      onSaved();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Projekt konnte nicht gespeichert werden.");
    } finally { setBusy(false); }
  }

  async function archive() {
    if (!project || !window.confirm(`${project.name} wirklich archivieren?`)) return;
    setBusy(true); setError("");
    try { await archiveProject(project); onSaved(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Projekt konnte nicht archiviert werden."); }
    finally { setBusy(false); }
  }

  return <form className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm sm:p-8" onSubmit={submit}>
    <div className="flex items-start justify-between gap-4"><div><p className="text-sm font-bold uppercase tracking-[0.18em] text-violet-700">{project?.project_number ?? "Neues Projekt"}</p><h2 className="mt-2 text-2xl font-bold text-slate-950">{project?.name ?? "Projekt anlegen"}</h2></div><button type="button" className="text-sm font-semibold text-slate-600" onClick={onCancel}>Schließen</button></div>
    <div className="mt-7 grid gap-5 sm:grid-cols-2">
      <label className="text-sm font-semibold text-slate-800 sm:col-span-2">Kunde suchen
        <input className={inputClass} value={contactSearch} onChange={(event) => setContactSearch(event.target.value)} placeholder="Name oder Kundennummer" />
        <select className={inputClass} value={form.customer} onChange={(event) => field("customer", event.target.value)} required>
          <option value="">Kunde auswählen …</option>
          {project && !contacts.some((contact) => contact.id === project.customer) && <option value={project.customer}>{project.customer_number} · {project.customer_name}</option>}
          {contacts.map((contact) => <option key={contact.id} value={contact.id}>{contact.customer_number} · {contact.display_name}</option>)}
        </select>
      </label>
      <label className="text-sm font-semibold text-slate-800 sm:col-span-2">Projektname<input className={inputClass} value={form.name} onChange={(event) => field("name", event.target.value)} required /></label>
      <label className="text-sm font-semibold text-slate-800 sm:col-span-2">Beschreibung<textarea className={`${inputClass} min-h-28`} value={form.description ?? ""} onChange={(event) => field("description", event.target.value)} /></label>
      <label className="text-sm font-semibold text-slate-800">Status<select className={inputClass} value={form.status} onChange={(event) => field("status", event.target.value)}>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <span />
      <label className="text-sm font-semibold text-slate-800">Startdatum<input className={inputClass} type="date" value={form.start_date ?? ""} onChange={(event) => field("start_date", event.target.value || null)} /></label>
      <label className="text-sm font-semibold text-slate-800">Enddatum<input className={inputClass} type="date" value={form.end_date ?? ""} onChange={(event) => field("end_date", event.target.value || null)} /></label>
      <label className="text-sm font-semibold text-slate-800">Budget netto (€)<input className={inputClass} type="number" min="0" step="0.01" value={form.budget_amount ?? ""} onChange={(event) => field("budget_amount", event.target.value || null)} /></label>
      <label className="text-sm font-semibold text-slate-800">Stundenbudget<input className={inputClass} type="number" min="0" step="0.25" value={form.budget_hours ?? ""} onChange={(event) => field("budget_hours", event.target.value || null)} /></label>
      <label className="text-sm font-semibold text-slate-800">Standard-Stundensatz netto (€)<input className={inputClass} type="number" min="0" step="0.01" value={form.default_hourly_rate ?? ""} onChange={(event) => field("default_hourly_rate", event.target.value || null)} /></label>
    </div>
    {error && <p className="mt-6 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    <div className="mt-7 flex flex-wrap items-center justify-between gap-3">{project && user.role === "admin" ? <button type="button" className="rounded-xl border border-red-200 px-4 py-3 text-sm font-semibold text-red-700 hover:bg-red-50" onClick={archive} disabled={busy}>Archivieren</button> : <span />}<div className="flex gap-3"><button type="button" className="rounded-xl border border-slate-300 px-4 py-3 font-semibold text-slate-700" onClick={onCancel}>Abbrechen</button><button className="rounded-xl bg-violet-700 px-5 py-3 font-semibold text-white hover:bg-violet-800 disabled:opacity-60" disabled={busy}>{busy ? "Wird gespeichert …" : "Speichern"}</button></div></div>
  </form>;
}

export function ProjectsPage({ user, onBack }: { user: User; onBack: () => void }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [count, setCount] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"quotation" | "active" | "paused" | "completed" | "">("");
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [selected, setSelected] = useState<Project | null | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true); setError("");
    getProjects({ search, status, page })
      .then((result) => { setProjects(result.results); setCount(result.count); setHasNext(Boolean(result.next)); setHasPrevious(Boolean(result.previous)); })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Projekte konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }, [search, status, page]);
  useEffect(() => { load(); }, [load]);

  if (selected !== undefined) return <main className="mx-auto max-w-5xl px-6 py-10"><ProjectForm project={selected} user={user} onCancel={() => setSelected(undefined)} onSaved={() => { setSelected(undefined); load(); }} /></main>;

  return <main className="mx-auto max-w-7xl px-6 py-10">
    <button className="text-sm font-semibold text-violet-700 hover:text-violet-900" onClick={onBack}>← Zurück zum Dashboard</button>
    <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-sm font-bold uppercase tracking-[0.18em] text-violet-700">Projekte</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Projektstamm</h1><p className="mt-2 text-sm text-slate-600">{count} aktive Projekte · Budget und Sätze als Basis für Arbeitspakete</p></div><button className="rounded-xl bg-violet-700 px-5 py-3 font-semibold text-white hover:bg-violet-800" onClick={() => setSelected(null)}>+ Projekt anlegen</button></div>
    <form className="mt-7 grid gap-3 rounded-2xl bg-white p-4 shadow-sm sm:grid-cols-[1fr_220px_auto]" onSubmit={(event) => { event.preventDefault(); setPage(1); setSearch(searchInput.trim()); }}><input className="rounded-xl border border-slate-300 px-4 py-3" placeholder="Projekt, Nummer oder Kunde" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} /><select className="rounded-xl border border-slate-300 px-4 py-3" value={status} onChange={(event) => { setStatus(event.target.value as typeof status); setPage(1); }}><option value="">Alle Status</option>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><button className="rounded-xl bg-slate-950 px-5 py-3 font-semibold text-white">Suchen</button></form>
    {error && <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    <div className="mt-5 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">{loading ? <p className="p-6 text-sm text-slate-500">Projekte werden geladen …</p> : projects.length ? projects.map((project) => <button key={project.id} className="grid w-full gap-2 border-b border-slate-100 p-5 text-left transition last:border-0 hover:bg-violet-50 sm:grid-cols-[130px_1.3fr_1fr_160px_auto] sm:items-center" onClick={() => setSelected(project)}><span className="font-mono text-sm font-semibold text-slate-500">{project.project_number}</span><span><strong className="block text-slate-950">{project.name}</strong><small className="text-slate-500">{project.customer_number} · {project.customer_name}</small></span><span className="text-sm text-slate-600">{project.budget_hours ? `${project.budget_hours} Std.` : "Kein Stundenbudget"}<br />{project.budget_amount ? `${project.budget_amount} €` : "Kein Betragsbudget"}</span><span className="w-fit rounded-full bg-violet-100 px-3 py-1 text-xs font-bold text-violet-800">{project.status_label}</span><span className="text-sm font-semibold text-violet-700">Bearbeiten →</span></button>) : <p className="p-8 text-center text-sm text-slate-500">Keine Projekte gefunden.</p>}</div>
    <div className="mt-5 flex items-center justify-between"><button className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold disabled:opacity-40" disabled={!hasPrevious} onClick={() => setPage((value) => value - 1)}>← Zurück</button><span className="text-sm text-slate-500">Seite {page}</span><button className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold disabled:opacity-40" disabled={!hasNext} onClick={() => setPage((value) => value + 1)}>Weiter →</button></div>
  </main>;
}
