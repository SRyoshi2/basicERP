import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  archiveTimeEntry, createTimeEntry, getProjects, getTimeEntries, getWorkPackages,
  updateTimeEntry, type Project, type TimeEntry, type TimeEntryInput, type User,
  type WorkPackage,
} from "./api";

const inputClass = "mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 font-normal outline-none transition focus:border-teal-600 focus:ring-4 focus:ring-teal-100";

function dateString(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function mondayOf(value: Date): Date {
  const result = new Date(value.getFullYear(), value.getMonth(), value.getDate());
  result.setDate(result.getDate() - ((result.getDay() + 6) % 7));
  return result;
}

function addDays(value: Date, days: number): Date {
  const result = new Date(value);
  result.setDate(result.getDate() + days);
  return result;
}

function emptyEntry(): TimeEntryInput {
  return {
    project: "", work_package: "", work_date: dateString(new Date()),
    duration_minutes: 60, description: "", billable: true,
  };
}

function entryToInput(entry: TimeEntry): TimeEntryInput {
  return {
    project: entry.project, work_package: entry.work_package, work_date: entry.work_date,
    duration_minutes: entry.duration_minutes, description: entry.description,
    billable: entry.billable,
  };
}

function EntryForm({ entry, projects, onCancel, onSaved }: {
  entry: TimeEntry | null; projects: Project[]; onCancel: () => void; onSaved: () => void;
}) {
  const [form, setForm] = useState<TimeEntryInput>(() => entry ? entryToInput(entry) : emptyEntry());
  const [durationHours, setDurationHours] = useState(() => String((entry?.duration_minutes ?? 60) / 60));
  const [packages, setPackages] = useState<WorkPackage[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!form.project) { setPackages([]); return; }
    getWorkPackages(form.project).then((result) => setPackages(result.results)).catch(() => setPackages([]));
  }, [form.project]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const minutes = Math.round(Number(durationHours) * 60);
    if (!Number.isFinite(minutes) || minutes < 1 || minutes > 1440) {
      setError("Die Dauer muss zwischen 0,01 und 24 Stunden liegen."); return;
    }
    setBusy(true); setError("");
    try {
      const data = { ...form, duration_minutes: minutes };
      if (entry) await updateTimeEntry(entry, data); else await createTimeEntry(data);
      onSaved();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Zeiteintrag konnte nicht gespeichert werden.");
    } finally { setBusy(false); }
  }

  async function archive() {
    if (!entry || !window.confirm("Diesen Zeiteintrag wirklich archivieren?")) return;
    setBusy(true); setError("");
    try { await archiveTimeEntry(entry); onSaved(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Zeiteintrag konnte nicht archiviert werden."); }
    finally { setBusy(false); }
  }

  return <form className="rounded-[2rem] border border-teal-200 bg-white p-6 shadow-sm sm:p-8" onSubmit={submit}>
    <div className="flex items-center justify-between"><div><p className="text-sm font-bold uppercase tracking-[0.18em] text-teal-700">Zeiterfassung</p><h2 className="mt-2 text-2xl font-bold text-slate-950">{entry ? "Eintrag bearbeiten" : "Zeit erfassen"}</h2></div><button type="button" className="text-sm font-semibold text-slate-600" onClick={onCancel}>Schließen</button></div>
    <div className="mt-6 grid gap-5 sm:grid-cols-2">
      <label className="text-sm font-semibold text-slate-800">Projekt<select className={inputClass} value={form.project} onChange={(event) => setForm({ ...form, project: event.target.value, work_package: "" })} required><option value="">Projekt auswählen …</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.project_number} · {project.name}</option>)}</select></label>
      <label className="text-sm font-semibold text-slate-800">Arbeitspaket<select className={inputClass} value={form.work_package} onChange={(event) => setForm({ ...form, work_package: event.target.value })} required><option value="">Arbeitspaket auswählen …</option>{packages.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
      <label className="text-sm font-semibold text-slate-800">Datum<input className={inputClass} type="date" value={form.work_date} onChange={(event) => setForm({ ...form, work_date: event.target.value })} required /></label>
      <label className="text-sm font-semibold text-slate-800">Dauer in Stunden<input className={inputClass} type="number" min="0.01" max="24" step="0.25" value={durationHours} onChange={(event) => setDurationHours(event.target.value)} required /></label>
      <label className="text-sm font-semibold text-slate-800 sm:col-span-2">Tätigkeitsbeschreibung<textarea className={`${inputClass} min-h-24`} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} required /></label>
      <label className="flex items-center gap-3 rounded-xl bg-slate-50 p-4 text-sm font-semibold text-slate-800 sm:col-span-2"><input type="checkbox" checked={form.billable ?? true} onChange={(event) => setForm({ ...form, billable: event.target.checked })} /> Abrechenbare Arbeitszeit</label>
    </div>
    {entry?.billing_status === "billed" && <p className="mt-5 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">Dieser Eintrag wurde bereits abgerechnet und kann nicht mehr geändert werden.</p>}
    {error && <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    <div className="mt-6 flex justify-between">{entry && entry.billing_status !== "billed" ? <button type="button" className="rounded-xl border border-red-200 px-4 py-3 text-sm font-semibold text-red-700" onClick={archive} disabled={busy}>Archivieren</button> : <span />}<button className="rounded-xl bg-teal-700 px-5 py-3 font-semibold text-white disabled:opacity-60" disabled={busy || entry?.billing_status === "billed"}>{busy ? "Wird gespeichert …" : "Speichern"}</button></div>
  </form>;
}

export function TimeTrackingPage({ user, onBack }: { user: User; onBack: () => void }) {
  const [weekStart, setWeekStart] = useState(() => mondayOf(new Date()));
  const [entries, setEntries] = useState<TimeEntry[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [editing, setEditing] = useState<TimeEntry | null | undefined>(undefined);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const weekDays = useMemo(() => Array.from({ length: 7 }, (_, index) => addDays(weekStart, index)), [weekStart]);

  const load = useCallback(() => {
    setLoading(true); setError("");
    Promise.all([
      getTimeEntries({ dateFrom: dateString(weekStart), dateTo: dateString(addDays(weekStart, 6)), employee: user.id }),
      getProjects({ status: "active" }),
    ]).then(([timeResult, projectResult]) => { setEntries(timeResult.results); setProjects(projectResult.results); })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Zeiten konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }, [weekStart, user.id]);
  useEffect(() => { load(); }, [load]);

  const totalMinutes = entries.reduce((sum, entry) => sum + entry.duration_minutes, 0);
  const billableMinutes = entries.filter((entry) => entry.billable).reduce((sum, entry) => sum + entry.duration_minutes, 0);

  if (editing !== undefined) return <main className="mx-auto max-w-4xl px-6 py-10"><EntryForm entry={editing} projects={projects} onCancel={() => setEditing(undefined)} onSaved={() => { setEditing(undefined); load(); }} /></main>;

  return <main className="mx-auto max-w-7xl px-6 py-10">
    <button className="text-sm font-semibold text-teal-700 hover:text-teal-900" onClick={onBack}>← Zurück zum Dashboard</button>
    <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-sm font-bold uppercase tracking-[0.18em] text-teal-700">Mitarbeiterportal</p><h1 className="mt-2 text-3xl font-bold text-slate-950">Meine Woche</h1><p className="mt-2 text-sm text-slate-600">{dateString(weekStart)} bis {dateString(addDays(weekStart, 6))} · {(totalMinutes / 60).toFixed(2)} Std., davon {(billableMinutes / 60).toFixed(2)} abrechenbar</p></div><button className="rounded-xl bg-teal-700 px-5 py-3 font-semibold text-white" onClick={() => setEditing(null)}>+ Zeit erfassen</button></div>
    <div className="mt-6 flex items-center justify-between rounded-2xl bg-white p-4 shadow-sm"><button className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold" onClick={() => setWeekStart(addDays(weekStart, -7))}>← Vorwoche</button><button className="text-sm font-semibold text-teal-700" onClick={() => setWeekStart(mondayOf(new Date()))}>Aktuelle Woche</button><button className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold" onClick={() => setWeekStart(addDays(weekStart, 7))}>Folgewoche →</button></div>
    {error && <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    <div className="mt-5 grid gap-4 lg:grid-cols-7">{weekDays.map((day) => {
      const key = dateString(day); const dayEntries = entries.filter((entry) => entry.work_date === key); const minutes = dayEntries.reduce((sum, entry) => sum + entry.duration_minutes, 0);
      return <section key={key} className="min-h-44 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><div className="flex items-start justify-between gap-2"><div><p className="text-xs font-bold uppercase text-teal-700">{new Intl.DateTimeFormat("de-DE", { weekday: "short" }).format(day)}</p><p className="mt-1 font-bold text-slate-950">{new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit" }).format(day)}</p></div><span className="text-xs font-semibold text-slate-500">{(minutes / 60).toFixed(2)} h</span></div><div className="mt-4 space-y-2">{dayEntries.map((entry) => <button key={entry.id} className="w-full rounded-xl bg-teal-50 p-3 text-left hover:bg-teal-100" onClick={() => setEditing(entry)}><strong className="block text-sm text-slate-950">{entry.project_name}</strong><span className="mt-1 block text-xs text-slate-600">{entry.work_package_title}</span><span className="mt-2 block text-xs font-bold text-teal-800">{entry.duration_hours} Std. · {entry.billable ? "abrechenbar" : "intern"}</span></button>)}{!dayEntries.length && !loading && <p className="py-5 text-center text-xs text-slate-400">Keine Zeit</p>}</div></section>;
    })}</div>
    {loading && <p className="mt-5 text-center text-sm text-slate-500">Woche wird geladen …</p>}
  </main>;
}
