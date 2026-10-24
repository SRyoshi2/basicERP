import { FormEvent, useEffect, useState } from "react";
import {
  getProjectAssignees, getProjects, getTimeReport, timeReportExportUrl,
  type AssigneeOption, type Project, type TimeReport, type TimeReportFilters, type User,
} from "./api";

const inputClass = "mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 font-normal outline-none transition focus:border-indigo-600 focus:ring-4 focus:ring-indigo-100";

function localDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function initialFilters(): TimeReportFilters {
  const today = new Date();
  return {
    dateFrom: localDate(new Date(today.getFullYear(), today.getMonth(), 1)),
    dateTo: localDate(today), project: "", employee: "",
  };
}

function number(value: string, digits = 2): string {
  return new Intl.NumberFormat("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value));
}

function money(value: string): string {
  return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(Number(value));
}

export function ReportsPage({ user, onBack }: { user: User; onBack: () => void }) {
  const [filters, setFilters] = useState<TimeReportFilters>(initialFilters);
  const [appliedFilters, setAppliedFilters] = useState<TimeReportFilters>(initialFilters);
  const [report, setReport] = useState<TimeReport | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [employees, setEmployees] = useState<AssigneeOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load(nextFilters = filters) {
    setLoading(true); setError("");
    try { setReport(await getTimeReport(nextFilters)); setAppliedFilters(nextFilters); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Bericht konnte nicht geladen werden."); }
    finally { setLoading(false); }
  }

  useEffect(() => {
    const lookups = [getProjects()];
    Promise.all(lookups).then(([projectResult]) => setProjects(projectResult.results)).catch(() => undefined);
    if (user.role === "admin") getProjectAssignees().then(setEmployees).catch(() => undefined);
    void load(initialFilters());
    // Initial load only; filters are submitted explicitly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user.role]);

  function submit(event: FormEvent) { event.preventDefault(); void load(); }

  return <main className="mx-auto max-w-7xl px-6 py-10">
    <button className="text-sm font-semibold text-indigo-700 hover:text-indigo-900" onClick={onBack}>← Zurück zum Dashboard</button>
    <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div><p className="text-sm font-bold uppercase tracking-[0.18em] text-indigo-700">Controlling</p><h1 className="mt-2 text-3xl font-bold text-slate-950">Zeit- und Leistungsbericht</h1><p className="mt-2 text-sm text-slate-600">Auswertung auf Basis der historisch gespeicherten Stunden- und Leistungspreise.</p></div>
      <a className="rounded-xl border border-indigo-200 bg-white px-5 py-3 text-center font-semibold text-indigo-800 shadow-sm hover:bg-indigo-50" href={timeReportExportUrl(appliedFilters)}>CSV für Excel exportieren</a>
    </div>

    <form className="mt-6 grid gap-4 rounded-2xl bg-white p-5 shadow-sm md:grid-cols-5" onSubmit={submit}>
      <label className="text-sm font-semibold text-slate-800">Von<input className={inputClass} type="date" value={filters.dateFrom} onChange={(event) => setFilters({ ...filters, dateFrom: event.target.value })} required /></label>
      <label className="text-sm font-semibold text-slate-800">Bis<input className={inputClass} type="date" value={filters.dateTo} onChange={(event) => setFilters({ ...filters, dateTo: event.target.value })} required /></label>
      <label className="text-sm font-semibold text-slate-800">Projekt<select className={inputClass} value={filters.project} onChange={(event) => setFilters({ ...filters, project: event.target.value })}><option value="">Alle Projekte</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.project_number} · {project.name}</option>)}</select></label>
      {user.role === "admin" ? <label className="text-sm font-semibold text-slate-800">Mitarbeiter<select className={inputClass} value={filters.employee} onChange={(event) => setFilters({ ...filters, employee: event.target.value })}><option value="">Alle Mitarbeiter</option>{employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.display_name}</option>)}</select></label> : <div className="rounded-xl bg-indigo-50 px-4 py-3 text-sm text-indigo-900 md:mt-7">Nur eigene Einträge</div>}
      <button className="mt-7 rounded-xl bg-indigo-700 px-5 py-3 font-semibold text-white hover:bg-indigo-800 disabled:opacity-60" disabled={loading}>{loading ? "Wird geladen …" : "Auswerten"}</button>
    </form>

    {error && <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    {report && <>
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <section className="rounded-2xl bg-slate-950 p-5 text-white"><p className="text-xs font-bold uppercase tracking-wider text-indigo-300">Gesamtwert</p><p className="mt-2 text-2xl font-bold">{money(report.summary.total_value)}</p></section>
        <section className="rounded-2xl border border-slate-200 bg-white p-5"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Arbeitszeit</p><p className="mt-2 text-2xl font-bold text-slate-950">{number(report.summary.total_hours)} Std.</p><p className="mt-1 text-xs text-slate-500">{number(report.summary.billable_hours)} abrechenbar · {report.summary.time_entry_count} Einträge</p></section>
        <section className="rounded-2xl border border-slate-200 bg-white p-5"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Zeitwert</p><p className="mt-2 text-2xl font-bold text-slate-950">{money(report.summary.time_value)}</p></section>
        <section className="rounded-2xl border border-slate-200 bg-white p-5"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Leistungswert</p><p className="mt-2 text-2xl font-bold text-slate-950">{money(report.summary.service_value)}</p><p className="mt-1 text-xs text-slate-500">{report.summary.service_entry_count} Einträge</p></section>
      </div>

      <div className="mt-6 overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500"><tr>{["Datum", "Art", "Mitarbeiter", "Projekt", "Arbeitspaket", "Beschreibung", "Menge / Zeit", "Nettowert", "Status"].map((label) => <th key={label} className="px-4 py-3">{label}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-100">{report.rows.map((row, index) => <tr key={`${row.entry_type}-${row.date}-${index}`} className="align-top">
            <td className="whitespace-nowrap px-4 py-4">{new Intl.DateTimeFormat("de-DE").format(new Date(`${row.date}T00:00:00`))}</td><td className="px-4 py-4"><span className={`rounded-full px-2 py-1 text-xs font-bold ${row.entry_type === "time" ? "bg-teal-50 text-teal-800" : "bg-amber-50 text-amber-800"}`}>{row.entry_type === "time" ? "Zeit" : "Leistung"}</span></td><td className="px-4 py-4">{row.employee_name}</td><td className="px-4 py-4"><strong>{row.project_number}</strong><span className="block text-xs text-slate-500">{row.project_name}</span></td><td className="px-4 py-4">{row.work_package_title}</td><td className="max-w-xs px-4 py-4">{row.description}</td><td className="whitespace-nowrap px-4 py-4">{row.hours !== null ? `${number(row.hours)} Std.` : `${number(row.quantity ?? "0", 3)} ${row.unit}`}</td><td className="whitespace-nowrap px-4 py-4">{row.net_value === null ? "–" : money(row.net_value)}</td><td className="whitespace-nowrap px-4 py-4">{row.billable ? row.billing_status : "Nicht abrechenbar"}</td>
          </tr>)}</tbody></table>
        {!report.rows.length && <p className="px-6 py-12 text-center text-sm text-slate-500">Im gewählten Zeitraum wurden keine Einträge gefunden.</p>}
      </div>
    </>}
  </main>;
}
