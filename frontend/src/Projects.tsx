import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  archiveProject, archiveWorkPackage, createProject, createWorkPackage, getContacts,
  getProjectAssignees, getProjectControlling, getProjects, getProjectTimeSummary, getWorkPackages, updateProject,
  updateWorkPackage, type AssigneeOption, type Contact, type Project, type ProjectControlling,
  type ProjectInput, type ProjectTimeSummary, type User, type WorkPackage, type WorkPackageInput,
} from "./api";

const inputClass = "mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 font-normal outline-none transition focus:border-violet-600 focus:ring-4 focus:ring-violet-100";
const projectStatusLabels = { quotation: "Angebot", active: "Aktiv", paused: "Pausiert", completed: "Abgeschlossen" } as const;
const packageStatusLabels = { planned: "Geplant", in_progress: "In Arbeit", blocked: "Blockiert", done: "Erledigt" } as const;
const packageStatusColors = { planned: "bg-slate-100 text-slate-700", in_progress: "bg-blue-100 text-blue-800", blocked: "bg-amber-100 text-amber-900", done: "bg-emerald-100 text-emerald-800" } as const;

function emptyProject(): ProjectInput {
  return { customer: "", name: "", description: "", status: "quotation", start_date: null, end_date: null, budget_amount: null, budget_hours: null, default_hourly_rate: null };
}

function projectToInput(project: Project): ProjectInput {
  return { customer: project.customer, name: project.name, description: project.description, status: project.status, start_date: project.start_date, end_date: project.end_date, budget_amount: project.budget_amount, budget_hours: project.budget_hours, default_hourly_rate: project.default_hourly_rate };
}

function ProjectForm({ project, user, onCancel, onSaved }: { project: Project | null; user: User; onCancel: () => void; onSaved: () => void }) {
  const [form, setForm] = useState<ProjectInput>(() => project ? projectToInput(project) : emptyProject());
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [contactSearch, setContactSearch] = useState(project?.customer_name ?? "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => getContacts({ search: contactSearch.trim() }).then((result) => setContacts(result.results)).catch(() => setContacts([])), 250);
    return () => window.clearTimeout(timer);
  }, [contactSearch]);

  function field(key: keyof ProjectInput, value: string | null) { setForm((current) => ({ ...current, [key]: value })); }

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { if (project) await updateProject(project, form); else await createProject(form); onSaved(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Projekt konnte nicht gespeichert werden."); }
    finally { setBusy(false); }
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
      <label className="text-sm font-semibold text-slate-800 sm:col-span-2">Kunde suchen<input className={inputClass} value={contactSearch} onChange={(event) => setContactSearch(event.target.value)} placeholder="Name oder Kundennummer" /><select className={inputClass} value={form.customer} onChange={(event) => field("customer", event.target.value)} required><option value="">Kunde auswählen …</option>{project && !contacts.some((contact) => contact.id === project.customer) && <option value={project.customer}>{project.customer_number} · {project.customer_name}</option>}{contacts.map((contact) => <option key={contact.id} value={contact.id}>{contact.customer_number} · {contact.display_name}</option>)}</select></label>
      <label className="text-sm font-semibold text-slate-800 sm:col-span-2">Projektname<input className={inputClass} value={form.name} onChange={(event) => field("name", event.target.value)} required /></label>
      <label className="text-sm font-semibold text-slate-800 sm:col-span-2">Beschreibung<textarea className={`${inputClass} min-h-28`} value={form.description ?? ""} onChange={(event) => field("description", event.target.value)} /></label>
      <label className="text-sm font-semibold text-slate-800">Status<select className={inputClass} value={form.status} onChange={(event) => field("status", event.target.value)}>{Object.entries(projectStatusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><span />
      <label className="text-sm font-semibold text-slate-800">Startdatum<input className={inputClass} type="date" value={form.start_date ?? ""} onChange={(event) => field("start_date", event.target.value || null)} /></label>
      <label className="text-sm font-semibold text-slate-800">Enddatum<input className={inputClass} type="date" value={form.end_date ?? ""} onChange={(event) => field("end_date", event.target.value || null)} /></label>
      <label className="text-sm font-semibold text-slate-800">Budget netto (€)<input className={inputClass} type="number" min="0" step="0.01" value={form.budget_amount ?? ""} onChange={(event) => field("budget_amount", event.target.value || null)} /></label>
      <label className="text-sm font-semibold text-slate-800">Stundenbudget<input className={inputClass} type="number" min="0" step="0.25" value={form.budget_hours ?? ""} onChange={(event) => field("budget_hours", event.target.value || null)} /></label>
      <label className="text-sm font-semibold text-slate-800">Standard-Stundensatz netto (€)<input className={inputClass} type="number" min="0" step="0.01" value={form.default_hourly_rate ?? ""} onChange={(event) => field("default_hourly_rate", event.target.value || null)} /></label>
    </div>
    {error && <p className="mt-6 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    <div className="mt-7 flex flex-wrap items-center justify-between gap-3">{project && user.role === "admin" ? <button type="button" className="rounded-xl border border-red-200 px-4 py-3 text-sm font-semibold text-red-700 hover:bg-red-50" onClick={archive} disabled={busy}>Archivieren</button> : <span />}<div className="flex gap-3"><button type="button" className="rounded-xl border border-slate-300 px-4 py-3 font-semibold text-slate-700" onClick={onCancel}>Abbrechen</button><button className="rounded-xl bg-violet-700 px-5 py-3 font-semibold text-white hover:bg-violet-800 disabled:opacity-60" disabled={busy}>{busy ? "Wird gespeichert …" : "Projekt speichern"}</button></div></div>
  </form>;
}

function emptyWorkPackage(projectId: string): WorkPackageInput {
  return { project: projectId, title: "", description: "", status: "planned", planned_hours: "0.00", assignee: null, hourly_rate_override: null };
}

function workPackageToInput(item: WorkPackage): WorkPackageInput {
  return { project: item.project, title: item.title, description: item.description, status: item.status, planned_hours: item.planned_hours, assignee: item.assignee, hourly_rate_override: item.hourly_rate_override };
}

function WorkPackageForm({ project, item, assignees, user, onCancel, onSaved }: { project: Project; item: WorkPackage | null; assignees: AssigneeOption[]; user: User; onCancel: () => void; onSaved: () => void }) {
  const [form, setForm] = useState<WorkPackageInput>(() => item ? workPackageToInput(item) : emptyWorkPackage(project.id));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { if (item) await updateWorkPackage(item, form); else await createWorkPackage(form); onSaved(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Arbeitspaket konnte nicht gespeichert werden."); }
    finally { setBusy(false); }
  }

  async function archive() {
    if (!item || !window.confirm(`${item.title} wirklich archivieren?`)) return;
    setBusy(true); setError("");
    try { await archiveWorkPackage(item); onSaved(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Arbeitspaket konnte nicht archiviert werden."); }
    finally { setBusy(false); }
  }

  return <form className="mt-5 rounded-2xl border border-violet-200 bg-violet-50/50 p-5" onSubmit={submit}>
    <div className="flex items-center justify-between"><h3 className="font-bold text-slate-950">{item ? "Arbeitspaket bearbeiten" : "Arbeitspaket anlegen"}</h3><button type="button" className="text-sm font-semibold text-slate-600" onClick={onCancel}>Schließen</button></div>
    <div className="mt-4 grid gap-4 sm:grid-cols-2">
      <label className="text-sm font-semibold text-slate-800 sm:col-span-2">Titel<input className={inputClass} value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} required /></label>
      <label className="text-sm font-semibold text-slate-800 sm:col-span-2">Beschreibung<textarea className={`${inputClass} min-h-24`} value={form.description ?? ""} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
      <label className="text-sm font-semibold text-slate-800">Status<select className={inputClass} value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value as WorkPackageInput["status"] })}>{Object.entries(packageStatusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label className="text-sm font-semibold text-slate-800">Mitarbeiter<select className={inputClass} value={form.assignee ?? ""} onChange={(event) => setForm({ ...form, assignee: event.target.value ? Number(event.target.value) : null })}><option value="">Nicht zugeordnet</option>{assignees.map((assignee) => <option key={assignee.id} value={assignee.id}>{assignee.display_name}</option>)}</select></label>
      <label className="text-sm font-semibold text-slate-800">Planaufwand (Std.)<input className={inputClass} type="number" min="0" step="0.25" value={form.planned_hours} onChange={(event) => setForm({ ...form, planned_hours: event.target.value })} required /></label>
      <label className="text-sm font-semibold text-slate-800">Abweichender Stundensatz (€)<input className={inputClass} type="number" min="0" step="0.01" value={form.hourly_rate_override ?? ""} onChange={(event) => setForm({ ...form, hourly_rate_override: event.target.value || null })} placeholder={project.default_hourly_rate ? `Projektstandard: ${project.default_hourly_rate} €` : "Kein Projektstandard"} /></label>
    </div>
    {error && <p className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    <div className="mt-5 flex justify-between">{item && user.role === "admin" ? <button type="button" className="rounded-xl border border-red-200 bg-white px-4 py-2 text-sm font-semibold text-red-700" onClick={archive}>Archivieren</button> : <span />}<button className="rounded-xl bg-violet-700 px-5 py-2.5 font-semibold text-white disabled:opacity-60" disabled={busy}>{busy ? "Wird gespeichert …" : "Arbeitspaket speichern"}</button></div>
  </form>;
}

function Metric({ label, value, warning = false }: { label: string; value: string; warning?: boolean }) {
  return <div className={`rounded-2xl border p-4 ${warning ? "border-amber-200 bg-amber-50" : "border-slate-200 bg-slate-50"}`}><p className="text-xs font-bold uppercase tracking-wider text-slate-500">{label}</p><p className={`mt-2 text-xl font-bold ${warning ? "text-amber-900" : "text-slate-950"}`}>{value}</p></div>;
}

function WorkPackagesPanel({ project, user }: { project: Project; user: User }) {
  const [items, setItems] = useState<WorkPackage[]>([]);
  const [controlling, setControlling] = useState<ProjectControlling | null>(null);
  const [actual, setActual] = useState<ProjectTimeSummary | null>(null);
  const [assignees, setAssignees] = useState<AssigneeOption[]>([]);
  const [editing, setEditing] = useState<WorkPackage | null | undefined>(undefined);
  const [mode, setMode] = useState<"board" | "list">("board");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setError("");
    Promise.all([getWorkPackages(project.id), getProjectControlling(project.id), getProjectTimeSummary(project.id), getProjectAssignees()])
      .then(([packages, plan, actuals, people]) => { setItems(packages.results); setControlling(plan); setActual(actuals); setAssignees(people); })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Arbeitspakete konnten nicht geladen werden."));
  }, [project.id]);
  useEffect(() => { load(); }, [load]);

  async function move(item: WorkPackage, status: WorkPackageInput["status"]) {
    setError("");
    try { await updateWorkPackage(item, { ...workPackageToInput(item), status }); load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Status konnte nicht geändert werden."); }
  }

  const card = (item: WorkPackage) => <article key={item.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
    <button className="w-full text-left" onClick={() => setEditing(item)}><strong className="block text-slate-950">{item.title}</strong><span className="mt-1 block text-xs text-slate-500">{item.assignee_name ?? "Nicht zugeordnet"}</span><span className="mt-3 block text-sm text-slate-700">{item.planned_hours} Std. · {item.planned_value ? `${item.planned_value} €` : "Satz fehlt"}</span></button>
    <select aria-label={`Status von ${item.title}`} className={`mt-3 w-full rounded-lg border-0 px-3 py-2 text-xs font-bold ${packageStatusColors[item.status]}`} value={item.status} onChange={(event) => move(item, event.target.value as WorkPackageInput["status"])}>{Object.entries(packageStatusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
  </article>;

  return <section className="mt-7 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
    <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm font-bold uppercase tracking-[0.18em] text-violet-700">Planung</p><h2 className="mt-2 text-2xl font-bold text-slate-950">Arbeitspakete &amp; Controlling</h2></div><div className="flex gap-2"><button className={`rounded-lg px-4 py-2 text-sm font-semibold ${mode === "board" ? "bg-slate-950 text-white" : "bg-slate-100 text-slate-700"}`} onClick={() => setMode("board")}>Board</button><button className={`rounded-lg px-4 py-2 text-sm font-semibold ${mode === "list" ? "bg-slate-950 text-white" : "bg-slate-100 text-slate-700"}`} onClick={() => setMode("list")}>Liste</button><button className="rounded-lg bg-violet-700 px-4 py-2 text-sm font-semibold text-white" onClick={() => setEditing(null)}>+ Arbeitspaket</button></div></div>
    {controlling && <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5"><Metric label="Fortschritt" value={`${controlling.progress_percent} %`} /><Metric label="Planstunden" value={`${controlling.planned_hours} / ${project.budget_hours ?? "—"}`} warning={controlling.remaining_hours !== null && Number(controlling.remaining_hours) < 0} /><Metric label="Planwert" value={`${controlling.planned_value} €`} /><Metric label="Rest Stunden" value={controlling.remaining_hours === null ? "Kein Budget" : `${controlling.remaining_hours} Std.`} warning={controlling.remaining_hours !== null && Number(controlling.remaining_hours) < 0} /><Metric label="Rest Betrag" value={controlling.remaining_amount === null ? "Kein Budget" : `${controlling.remaining_amount} €`} warning={controlling.remaining_amount !== null && Number(controlling.remaining_amount) < 0} /></div>}
    {actual && <><h3 className="mt-6 text-sm font-bold uppercase tracking-[0.18em] text-violet-700">Ist aus Zeit &amp; Leistung</h3><div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-6"><Metric label="Ist-Stunden" value={`${actual.actual_hours} Std.`} /><Metric label="Abrechenbar" value={`${actual.billable_hours} Std.`} /><Metric label="Noch offen" value={`${actual.unbilled_hours} Std.`} /><Metric label="Leistungswert" value={`${actual.service_value} €`} /><Metric label="Ist-Wert gesamt" value={`${actual.actual_value} €`} /><Metric label="Rest Ist-Budget" value={actual.remaining_budget_amount === null ? "Kein Budget" : `${actual.remaining_budget_amount} €`} warning={actual.remaining_budget_amount !== null && Number(actual.remaining_budget_amount) < 0} /></div></>}
    {controlling && controlling.unpriced_work_package_count > 0 && <p className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">{controlling.unpriced_work_package_count} Arbeitspaket(e) haben weder einen eigenen noch einen Projekt-Stundensatz und fehlen deshalb im Planwert.</p>}
    {error && <p className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    {editing !== undefined && <WorkPackageForm project={project} item={editing} assignees={assignees} user={user} onCancel={() => setEditing(undefined)} onSaved={() => { setEditing(undefined); load(); }} />}
    {mode === "board" ? <div className="mt-6 grid gap-4 lg:grid-cols-4">{Object.entries(packageStatusLabels).map(([status, label]) => <section key={status} className="rounded-2xl bg-slate-100 p-4"><div className="flex items-center justify-between"><h3 className="font-bold text-slate-900">{label}</h3><span className="rounded-full bg-white px-2.5 py-1 text-xs font-bold text-slate-600">{items.filter((item) => item.status === status).length}</span></div><div className="mt-4 space-y-3">{items.filter((item) => item.status === status).map(card)}{!items.some((item) => item.status === status) && <p className="py-4 text-center text-xs text-slate-500">Keine Pakete</p>}</div></section>)}</div> : <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200">{items.length ? items.map((item) => <button key={item.id} className="grid w-full gap-2 border-b border-slate-100 p-4 text-left last:border-0 hover:bg-violet-50 sm:grid-cols-[1fr_160px_140px_140px]" onClick={() => setEditing(item)}><strong>{item.title}</strong><span className="text-sm text-slate-600">{item.assignee_name ?? "Nicht zugeordnet"}</span><span className="text-sm">{item.planned_hours} Std.</span><span className={`w-fit rounded-full px-3 py-1 text-xs font-bold ${packageStatusColors[item.status]}`}>{item.status_label}</span></button>) : <p className="p-6 text-center text-sm text-slate-500">Noch keine Arbeitspakete.</p>}</div>}
  </section>;
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
    getProjects({ search, status, page }).then((result) => { setProjects(result.results); setCount(result.count); setHasNext(Boolean(result.next)); setHasPrevious(Boolean(result.previous)); }).catch((reason) => setError(reason instanceof Error ? reason.message : "Projekte konnten nicht geladen werden.")).finally(() => setLoading(false));
  }, [search, status, page]);
  useEffect(() => { load(); }, [load]);

  if (selected !== undefined) return <main className="mx-auto max-w-7xl px-6 py-10"><ProjectForm project={selected} user={user} onCancel={() => setSelected(undefined)} onSaved={() => { setSelected(undefined); load(); }} />{selected && <WorkPackagesPanel project={selected} user={user} />}</main>;

  return <main className="mx-auto max-w-7xl px-6 py-10">
    <button className="text-sm font-semibold text-violet-700 hover:text-violet-900" onClick={onBack}>← Zurück zum Dashboard</button>
    <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-sm font-bold uppercase tracking-[0.18em] text-violet-700">Projekte</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Projektstamm</h1><p className="mt-2 text-sm text-slate-600">{count} aktive Projekte · Budgets, Arbeitspakete und Plancontrolling</p></div><button className="rounded-xl bg-violet-700 px-5 py-3 font-semibold text-white hover:bg-violet-800" onClick={() => setSelected(null)}>+ Projekt anlegen</button></div>
    <form className="mt-7 grid gap-3 rounded-2xl bg-white p-4 shadow-sm sm:grid-cols-[1fr_220px_auto]" onSubmit={(event) => { event.preventDefault(); setPage(1); setSearch(searchInput.trim()); }}><input className="rounded-xl border border-slate-300 px-4 py-3" placeholder="Projekt, Nummer oder Kunde" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} /><select className="rounded-xl border border-slate-300 px-4 py-3" value={status} onChange={(event) => { setStatus(event.target.value as typeof status); setPage(1); }}><option value="">Alle Status</option>{Object.entries(projectStatusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><button className="rounded-xl bg-slate-950 px-5 py-3 font-semibold text-white">Suchen</button></form>
    {error && <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    <div className="mt-5 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">{loading ? <p className="p-6 text-sm text-slate-500">Projekte werden geladen …</p> : projects.length ? projects.map((project) => <button key={project.id} className="grid w-full gap-2 border-b border-slate-100 p-5 text-left transition last:border-0 hover:bg-violet-50 sm:grid-cols-[130px_1.3fr_1fr_160px_auto] sm:items-center" onClick={() => setSelected(project)}><span className="font-mono text-sm font-semibold text-slate-500">{project.project_number}</span><span><strong className="block text-slate-950">{project.name}</strong><small className="text-slate-500">{project.customer_number} · {project.customer_name}</small></span><span className="text-sm text-slate-600">{project.budget_hours ? `${project.budget_hours} Std.` : "Kein Stundenbudget"}<br />{project.budget_amount ? `${project.budget_amount} €` : "Kein Betragsbudget"}</span><span className="w-fit rounded-full bg-violet-100 px-3 py-1 text-xs font-bold text-violet-800">{project.status_label}</span><span className="text-sm font-semibold text-violet-700">Öffnen →</span></button>) : <p className="p-8 text-center text-sm text-slate-500">Keine Projekte gefunden.</p>}</div>
    <div className="mt-5 flex items-center justify-between"><button className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold disabled:opacity-40" disabled={!hasPrevious} onClick={() => setPage((value) => value - 1)}>← Zurück</button><span className="text-sm text-slate-500">Seite {page}</span><button className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold disabled:opacity-40" disabled={!hasNext} onClick={() => setPage((value) => value + 1)}>Weiter →</button></div>
  </main>;
}
