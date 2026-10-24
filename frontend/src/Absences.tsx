import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  cancelAbsence, createAbsence, getAbsences, getLeaveBalance, getProjectAssignees,
  reviewAbsence, setLeaveEntitlement, updateAbsence, type AbsenceInput,
  type AbsenceRequest, type AssigneeOption, type LeaveBalance, type User,
} from "./api";

const inputClass = "mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 font-normal outline-none transition focus:border-rose-600 focus:ring-4 focus:ring-rose-100";
const kindLabels = { vacation: "Urlaub", sickness: "Krankheit", other: "Sonstiges" } as const;
const statusColors = { requested: "bg-amber-100 text-amber-900", approved: "bg-emerald-100 text-emerald-900", rejected: "bg-red-100 text-red-900", cancelled: "bg-slate-100 text-slate-700" } as const;

function dateString(value: Date): string {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

function emptyAbsence(): AbsenceInput {
  const today = dateString(new Date());
  return { kind: "vacation", start_date: today, end_date: today, note: "" };
}

function absenceToInput(item: AbsenceRequest): AbsenceInput {
  return { kind: item.kind, start_date: item.start_date, end_date: item.end_date, note: item.note };
}

function AbsenceForm({ item, onCancel, onSaved }: {
  item: AbsenceRequest | null; onCancel: () => void; onSaved: () => void;
}) {
  const [form, setForm] = useState<AbsenceInput>(() => item ? absenceToInput(item) : emptyAbsence());
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { if (item) await updateAbsence(item, form); else await createAbsence(form); onSaved(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Abwesenheit konnte nicht gespeichert werden."); }
    finally { setBusy(false); }
  }

  return <form className="rounded-[2rem] border border-rose-200 bg-white p-6 shadow-sm sm:p-8" onSubmit={submit}>
    <div className="flex items-center justify-between"><div><p className="text-sm font-bold uppercase tracking-[0.18em] text-rose-700">Mitarbeiterportal</p><h2 className="mt-2 text-2xl font-bold text-slate-950">{item ? "Antrag bearbeiten" : "Abwesenheit beantragen"}</h2></div><button type="button" className="text-sm font-semibold text-slate-600" onClick={onCancel}>Schließen</button></div>
    <div className="mt-6 grid gap-5 sm:grid-cols-2">
      <label className="text-sm font-semibold text-slate-800">Art<select className={inputClass} value={form.kind} onChange={(event) => setForm({ ...form, kind: event.target.value as AbsenceInput["kind"] })}>{Object.entries(kindLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><span />
      <label className="text-sm font-semibold text-slate-800">Von<input className={inputClass} type="date" value={form.start_date} onChange={(event) => setForm({ ...form, start_date: event.target.value })} required /></label>
      <label className="text-sm font-semibold text-slate-800">Bis einschließlich<input className={inputClass} type="date" value={form.end_date} onChange={(event) => setForm({ ...form, end_date: event.target.value })} required /></label>
      <label className="text-sm font-semibold text-slate-800 sm:col-span-2">Hinweis<textarea className={`${inputClass} min-h-24`} value={form.note ?? ""} onChange={(event) => setForm({ ...form, note: event.target.value })} /></label>
    </div>
    <p className="mt-4 text-sm text-slate-500">Arbeitstage werden zunächst Montag bis Freitag gezählt; gesetzliche Feiertage folgen in einem späteren Ausbau.</p>
    {error && <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    <div className="mt-6 flex justify-end gap-3"><button type="button" className="rounded-xl border border-slate-300 px-4 py-3 font-semibold" onClick={onCancel}>Abbrechen</button><button className="rounded-xl bg-rose-700 px-5 py-3 font-semibold text-white disabled:opacity-60" disabled={busy}>{busy ? "Wird gespeichert …" : "Antrag speichern"}</button></div>
  </form>;
}

function BalanceCard({ balance }: { balance: LeaveBalance | null }) {
  if (!balance) return <div className="rounded-2xl bg-white p-6 shadow-sm"><p className="text-sm text-slate-500">Urlaubskonto wird geladen …</p></div>;
  return <div className="grid gap-3 rounded-2xl border border-rose-100 bg-white p-5 shadow-sm sm:grid-cols-4"><div><p className="text-xs font-bold uppercase text-slate-500">Anspruch + Übertrag</p><strong className="mt-2 block text-xl">{Number(balance.entitlement_days) + Number(balance.carryover_days)} Tage</strong></div><div><p className="text-xs font-bold uppercase text-slate-500">Genehmigt</p><strong className="mt-2 block text-xl">{balance.approved_days} Tage</strong></div><div><p className="text-xs font-bold uppercase text-slate-500">Beantragt</p><strong className="mt-2 block text-xl">{balance.pending_days} Tage</strong></div><div><p className="text-xs font-bold uppercase text-slate-500">Resturlaub</p><strong className={`mt-2 block text-xl ${Number(balance.remaining_days) < 0 ? "text-red-700" : "text-emerald-700"}`}>{balance.remaining_days} Tage</strong></div></div>;
}

export function AbsencesPage({ user, onBack }: { user: User; onBack: () => void }) {
  const [year, setYear] = useState(new Date().getFullYear());
  const [items, setItems] = useState<AbsenceRequest[]>([]);
  const [pending, setPending] = useState<AbsenceRequest[]>([]);
  const [balance, setBalance] = useState<LeaveBalance | null>(null);
  const [people, setPeople] = useState<AssigneeOption[]>([]);
  const [entitlementEmployee, setEntitlementEmployee] = useState("");
  const [entitlementDays, setEntitlementDays] = useState("30.00");
  const [carryoverDays, setCarryoverDays] = useState("0.00");
  const [entitlementVersion, setEntitlementVersion] = useState<number | null>(null);
  const [editing, setEditing] = useState<AbsenceRequest | null | undefined>(undefined);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setError("");
    const requests: Promise<unknown>[] = [getAbsences({ year, employee: String(user.id) }), getLeaveBalance(year)];
    if (user.role === "admin") requests.push(getAbsences({ year, status: "requested" }), getProjectAssignees());
    Promise.all(requests).then((results) => {
      setItems((results[0] as Awaited<ReturnType<typeof getAbsences>>).results);
      setBalance(results[1] as LeaveBalance);
      if (user.role === "admin") {
        setPending((results[2] as Awaited<ReturnType<typeof getAbsences>>).results);
        setPeople(results[3] as AssigneeOption[]);
      }
    }).catch((reason) => setError(reason instanceof Error ? reason.message : "Abwesenheiten konnten nicht geladen werden."));
  }, [user.id, user.role, year]);
  useEffect(() => { load(); }, [load]);

  async function cancel(item: AbsenceRequest) {
    if (!window.confirm("Diesen Antrag wirklich stornieren?")) return;
    try { await cancelAbsence(item); load(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Antrag konnte nicht storniert werden."); }
  }

  async function review(item: AbsenceRequest, decision: "approved" | "rejected") {
    const note = window.prompt(decision === "approved" ? "Optionaler Genehmigungshinweis" : "Begründung der Ablehnung") ?? "";
    try { await reviewAbsence(item, decision, note); load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Entscheidung konnte nicht gespeichert werden."); }
  }

  async function chooseEntitlement(employee: string) {
    setEntitlementEmployee(employee);
    if (!employee) return;
    try {
      const result = await getLeaveBalance(year, employee);
      setEntitlementDays(result.entitlement_days); setCarryoverDays(result.carryover_days); setEntitlementVersion(result.version);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Urlaubskonto konnte nicht geladen werden."); }
  }

  async function saveEntitlement(event: FormEvent) {
    event.preventDefault();
    try {
      await setLeaveEntitlement({ employee: entitlementEmployee, year, entitlement_days: entitlementDays, carryover_days: carryoverDays, version: entitlementVersion });
      await chooseEntitlement(entitlementEmployee); load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Urlaubsanspruch konnte nicht gespeichert werden."); }
  }

  if (editing !== undefined) return <main className="mx-auto max-w-4xl px-6 py-10"><AbsenceForm item={editing} onCancel={() => setEditing(undefined)} onSaved={() => { setEditing(undefined); load(); }} /></main>;

  return <main className="mx-auto max-w-6xl px-6 py-10">
    <button className="text-sm font-semibold text-rose-700 hover:text-rose-900" onClick={onBack}>← Zurück zum Dashboard</button>
    <div className="mt-6 flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm font-bold uppercase tracking-[0.18em] text-rose-700">Mitarbeiterportal</p><h1 className="mt-2 text-3xl font-bold text-slate-950">Abwesenheiten</h1></div><div className="flex gap-3"><select className="rounded-xl border border-slate-300 px-4 py-3" value={year} onChange={(event) => setYear(Number(event.target.value))}>{[year - 1, year, year + 1].map((value) => <option key={value}>{value}</option>)}</select><button className="rounded-xl bg-rose-700 px-5 py-3 font-semibold text-white" onClick={() => setEditing(null)}>+ Antrag</button></div></div>
    <div className="mt-6"><BalanceCard balance={balance} /></div>
    {error && <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><h2 className="text-xl font-bold text-slate-950">Meine Anträge</h2><div className="mt-4 space-y-3">{items.map((item) => <article key={item.id} className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-200 p-4"><div><strong>{item.kind_label}</strong><p className="mt-1 text-sm text-slate-600">{item.start_date} bis {item.end_date} · {item.working_days} Arbeitstage</p>{item.decision_note && <p className="mt-1 text-sm text-slate-500">Hinweis: {item.decision_note}</p>}</div><div className="flex items-center gap-2"><span className={`rounded-full px-3 py-1 text-xs font-bold ${statusColors[item.status]}`}>{item.status_label}</span>{item.status === "requested" && <><button className="text-sm font-semibold text-rose-700" onClick={() => setEditing(item)}>Bearbeiten</button><button className="text-sm font-semibold text-red-700" onClick={() => cancel(item)}>Stornieren</button></>}</div></article>)}{!items.length && <p className="py-5 text-center text-sm text-slate-500">Noch keine Anträge in diesem Jahr.</p>}</div></section>
    {user.role === "admin" && <><section className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-6"><h2 className="text-xl font-bold text-slate-950">Offene Genehmigungen</h2><div className="mt-4 space-y-3">{pending.map((item) => <article key={item.id} className="flex flex-wrap items-center justify-between gap-4 rounded-xl bg-white p-4"><div><strong>{item.employee_name} · {item.kind_label}</strong><p className="text-sm text-slate-600">{item.start_date} bis {item.end_date} · {item.working_days} Arbeitstage</p></div><div className="flex gap-2"><button className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white" onClick={() => review(item, "approved")}>Genehmigen</button><button className="rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white" onClick={() => review(item, "rejected")}>Ablehnen</button></div></article>)}{!pending.length && <p className="text-sm text-slate-600">Keine offenen Anträge.</p>}</div></section><form className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" onSubmit={saveEntitlement}><h2 className="text-xl font-bold text-slate-950">Jahresanspruch pflegen</h2><div className="mt-4 grid gap-4 sm:grid-cols-3"><label className="text-sm font-semibold">Mitarbeiter<select className={inputClass} value={entitlementEmployee} onChange={(event) => chooseEntitlement(event.target.value)} required><option value="">Auswählen …</option>{people.map((person) => <option key={person.id} value={person.id}>{person.display_name}</option>)}</select></label><label className="text-sm font-semibold">Anspruch<input className={inputClass} type="number" min="0" step="0.5" value={entitlementDays} onChange={(event) => setEntitlementDays(event.target.value)} /></label><label className="text-sm font-semibold">Übertrag<input className={inputClass} type="number" min="0" step="0.5" value={carryoverDays} onChange={(event) => setCarryoverDays(event.target.value)} /></label></div><button className="mt-5 rounded-xl bg-slate-950 px-5 py-3 font-semibold text-white">Urlaubskonto speichern</button></form></>}
  </main>;
}
