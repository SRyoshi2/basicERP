import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  archiveServiceEntry, createServiceEntry, getCatalogItems, getProjects, getServiceEntries,
  getWorkPackages, updateServiceEntry, type CatalogItem, type Project, type ServiceEntry,
  type ServiceEntryInput, type User, type WorkPackage,
} from "./api";

const inputClass = "mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 font-normal outline-none transition focus:border-amber-600 focus:ring-4 focus:ring-amber-100";

function dateString(value: Date): string {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

function mondayOf(value: Date): Date {
  const result = new Date(value.getFullYear(), value.getMonth(), value.getDate());
  result.setDate(result.getDate() - ((result.getDay() + 6) % 7));
  return result;
}

function addDays(value: Date, days: number): Date {
  const result = new Date(value); result.setDate(result.getDate() + days); return result;
}

function emptyEntry(): ServiceEntryInput {
  return {
    project: "", work_package: "", catalog_item: "", service_date: dateString(new Date()),
    quantity: "1.000", description: "", billable: true,
  };
}

function entryToInput(entry: ServiceEntry): ServiceEntryInput {
  return {
    project: entry.project, work_package: entry.work_package, catalog_item: entry.catalog_item,
    service_date: entry.service_date, quantity: entry.quantity, description: entry.description,
    billable: entry.billable,
  };
}

function ServiceForm({ entry, projects, catalog, onCancel, onSaved }: {
  entry: ServiceEntry | null; projects: Project[]; catalog: CatalogItem[];
  onCancel: () => void; onSaved: () => void;
}) {
  const [form, setForm] = useState<ServiceEntryInput>(() => entry ? entryToInput(entry) : emptyEntry());
  const [packages, setPackages] = useState<WorkPackage[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!form.project) { setPackages([]); return; }
    getWorkPackages(form.project).then((result) => setPackages(result.results)).catch(() => setPackages([]));
  }, [form.project]);

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      if (entry) await updateServiceEntry(entry, form); else await createServiceEntry(form);
      onSaved();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Leistung konnte nicht gespeichert werden.");
    } finally { setBusy(false); }
  }

  async function archive() {
    if (!entry || !window.confirm("Diesen Leistungseintrag wirklich archivieren?")) return;
    setBusy(true); setError("");
    try { await archiveServiceEntry(entry); onSaved(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Leistung konnte nicht archiviert werden."); }
    finally { setBusy(false); }
  }

  return <form className="rounded-[2rem] border border-amber-200 bg-white p-6 shadow-sm sm:p-8" onSubmit={submit}>
    <div className="flex items-center justify-between"><div><p className="text-sm font-bold uppercase tracking-[0.18em] text-amber-700">Leistungserfassung</p><h2 className="mt-2 text-2xl font-bold text-slate-950">{entry ? "Eintrag bearbeiten" : "Leistung erfassen"}</h2></div><button type="button" className="text-sm font-semibold text-slate-600" onClick={onCancel}>Schließen</button></div>
    <div className="mt-6 grid gap-5 sm:grid-cols-2">
      <label className="text-sm font-semibold text-slate-800">Projekt<select className={inputClass} value={form.project} onChange={(event) => setForm({ ...form, project: event.target.value, work_package: "" })} required><option value="">Projekt auswählen …</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.project_number} · {project.name}</option>)}</select></label>
      <label className="text-sm font-semibold text-slate-800">Arbeitspaket<select className={inputClass} value={form.work_package} onChange={(event) => setForm({ ...form, work_package: event.target.value })} required><option value="">Arbeitspaket auswählen …</option>{packages.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
      <label className="text-sm font-semibold text-slate-800">Katalogleistung<select className={inputClass} value={form.catalog_item} onChange={(event) => setForm({ ...form, catalog_item: event.target.value })} required><option value="">Leistung auswählen …</option>{catalog.map((item) => <option key={item.id} value={item.id}>{item.item_number} · {item.name}{item.current_price ? ` · ${item.current_price.net_amount} €` : " · aktuell ohne Preis"}</option>)}</select></label>
      <label className="text-sm font-semibold text-slate-800">Menge<input className={inputClass} type="number" min="0.001" step="0.001" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} required /></label>
      <label className="text-sm font-semibold text-slate-800">Leistungsdatum<input className={inputClass} type="date" value={form.service_date} onChange={(event) => setForm({ ...form, service_date: event.target.value })} required /></label>
      <label className="text-sm font-semibold text-slate-800">Beschreibung<input className={inputClass} value={form.description ?? ""} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
      <label className="flex items-center gap-3 rounded-xl bg-slate-50 p-4 text-sm font-semibold text-slate-800 sm:col-span-2"><input type="checkbox" checked={form.billable ?? true} onChange={(event) => setForm({ ...form, billable: event.target.checked })} /> Abrechenbare Leistung</label>
    </div>
    {entry?.billing_status === "billed" && <p className="mt-5 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">Dieser Eintrag wurde bereits abgerechnet und kann nicht mehr geändert werden.</p>}
    {error && <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    <div className="mt-6 flex justify-between">{entry && entry.billing_status !== "billed" ? <button type="button" className="rounded-xl border border-red-200 px-4 py-3 text-sm font-semibold text-red-700" onClick={archive} disabled={busy}>Archivieren</button> : <span />}<button className="rounded-xl bg-amber-700 px-5 py-3 font-semibold text-white disabled:opacity-60" disabled={busy || entry?.billing_status === "billed"}>{busy ? "Wird gespeichert …" : "Speichern"}</button></div>
  </form>;
}

export function ServiceTrackingPage({ user, onBack }: { user: User; onBack: () => void }) {
  const [weekStart, setWeekStart] = useState(() => mondayOf(new Date()));
  const [entries, setEntries] = useState<ServiceEntry[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [editing, setEditing] = useState<ServiceEntry | null | undefined>(undefined);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const weekDays = useMemo(() => Array.from({ length: 7 }, (_, index) => addDays(weekStart, index)), [weekStart]);

  const load = useCallback(() => {
    setLoading(true); setError("");
    Promise.all([
      getServiceEntries({ dateFrom: dateString(weekStart), dateTo: dateString(addDays(weekStart, 6)), employee: String(user.id) }),
      getProjects({ status: "active" }), getCatalogItems({ kind: "service" }),
    ]).then(([serviceResult, projectResult, catalogResult]) => {
      setEntries(serviceResult.results); setProjects(projectResult.results); setCatalog(catalogResult.results);
    }).catch((reason) => setError(reason instanceof Error ? reason.message : "Leistungen konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }, [weekStart, user.id]);
  useEffect(() => { load(); }, [load]);

  const totalValue = entries.filter((entry) => entry.billable).reduce((sum, entry) => sum + Number(entry.total_net), 0);
  if (editing !== undefined) return <main className="mx-auto max-w-4xl px-6 py-10"><ServiceForm entry={editing} projects={projects} catalog={catalog} onCancel={() => setEditing(undefined)} onSaved={() => { setEditing(undefined); load(); }} /></main>;

  return <main className="mx-auto max-w-7xl px-6 py-10">
    <button className="text-sm font-semibold text-amber-700 hover:text-amber-900" onClick={onBack}>← Zurück zum Dashboard</button>
    <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-sm font-bold uppercase tracking-[0.18em] text-amber-700">Mitarbeiterportal</p><h1 className="mt-2 text-3xl font-bold text-slate-950">Meine Leistungen</h1><p className="mt-2 text-sm text-slate-600">{dateString(weekStart)} bis {dateString(addDays(weekStart, 6))} · {entries.length} Einträge · {totalValue.toFixed(2)} € abrechenbar</p></div><button className="rounded-xl bg-amber-700 px-5 py-3 font-semibold text-white" onClick={() => setEditing(null)}>+ Leistung erfassen</button></div>
    <div className="mt-6 flex items-center justify-between rounded-2xl bg-white p-4 shadow-sm"><button className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold" onClick={() => setWeekStart(addDays(weekStart, -7))}>← Vorwoche</button><button className="text-sm font-semibold text-amber-700" onClick={() => setWeekStart(mondayOf(new Date()))}>Aktuelle Woche</button><button className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold" onClick={() => setWeekStart(addDays(weekStart, 7))}>Folgewoche →</button></div>
    {error && <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    <div className="mt-5 grid gap-4 lg:grid-cols-7">{weekDays.map((day) => { const key = dateString(day); const dayEntries = entries.filter((entry) => entry.service_date === key); return <section key={key} className="min-h-44 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><div><p className="text-xs font-bold uppercase text-amber-700">{new Intl.DateTimeFormat("de-DE", { weekday: "short" }).format(day)}</p><p className="mt-1 font-bold text-slate-950">{new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit" }).format(day)}</p></div><div className="mt-4 space-y-2">{dayEntries.map((entry) => <button key={entry.id} className="w-full rounded-xl bg-amber-50 p-3 text-left hover:bg-amber-100" onClick={() => setEditing(entry)}><strong className="block text-sm text-slate-950">{entry.catalog_item_name_snapshot}</strong><span className="mt-1 block text-xs text-slate-600">{entry.project_name} · {entry.work_package_title}</span><span className="mt-2 block text-xs font-bold text-amber-900">{entry.quantity} × {entry.unit_price_snapshot} € = {entry.total_net} €</span></button>)}{!dayEntries.length && !loading && <p className="py-5 text-center text-xs text-slate-400">Keine Leistung</p>}</div></section>; })}</div>
    {loading && <p className="mt-5 text-center text-sm text-slate-500">Woche wird geladen …</p>}
  </main>;
}
