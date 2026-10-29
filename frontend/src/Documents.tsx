import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  archiveBusinessDocument, createBusinessDocument, finalizeBusinessDocument,
  getBillableProjectItems, getBusinessDocuments, getCatalogItems,
  getContacts, getProjects, updateBusinessDocument, type BusinessDocument,
  type BillableProjectItem, type BusinessDocumentInput, type CatalogItem, type Contact,
  type DocumentLineInput, type Project,
} from "./api";

const inputClass = "mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 font-normal outline-none transition focus:border-fuchsia-600 focus:ring-4 focus:ring-fuchsia-100";
const kindLabels = { quote: "Angebot", invoice: "Rechnung" } as const;
const statusLabels = {
  draft: "Entwurf",
  finalizing: "Festgeschrieben · PDF ausstehend",
  finalized: "Finalisiert",
  artifact_failed: "PDF-Erzeugung wird wiederholt",
} as const;
const unitLabels = { hour: "Stunde", day: "Tag", piece: "Stück", flat: "Pauschal" } as const;

function today(): string { return new Date().toISOString().slice(0, 10); }
function addDays(value: string, days: number): string {
  const date = new Date(`${value}T00:00:00`); date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}
function money(value: string): string {
  return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(Number(value));
}
function emptyLine(): DocumentLineInput {
  return {
    catalog_item: null, description: "", quantity: "1.000", unit: "piece",
    unit_price_net: "0.00", discount_percent: "0.00", tax_rate: "19.00", tax_note: "",
    source_time_entry: null, source_service_entry: null,
  };
}
function emptyDocument(): BusinessDocumentInput {
  const issueDate = today();
  return {
    kind: "invoice", customer: "", project: null, issue_date: issueDate,
    service_date_from: issueDate, service_date_to: issueDate, due_date: addDays(issueDate, 14),
    tax_mode: "standard", tax_exemption_note: "", introduction: "Vielen Dank für Ihren Auftrag.",
    closing_text: "Mit freundlichen Grüßen", payment_terms: "Zahlbar innerhalb von 14 Tagen.",
    lines: [emptyLine()],
  };
}
function documentToInput(document: BusinessDocument): BusinessDocumentInput {
  return {
    kind: document.kind, customer: document.customer, project: document.project ?? null,
    issue_date: document.issue_date, service_date_from: document.service_date_from ?? null,
    service_date_to: document.service_date_to ?? null, due_date: document.due_date ?? null,
    tax_mode: document.tax_mode ?? "standard",
    tax_exemption_note: document.tax_exemption_note ?? "", introduction: document.introduction ?? "",
    closing_text: document.closing_text ?? "", payment_terms: document.payment_terms ?? "",
    lines: document.lines.map((line) => ({
      catalog_item: line.catalog_item ?? null, description: line.description,
      source_time_entry: line.source_time_entry ?? null,
      source_service_entry: line.source_service_entry ?? null,
      quantity: line.quantity, unit: line.unit, unit_price_net: line.unit_price_net,
      discount_percent: line.discount_percent ?? "0.00",
      tax_rate: Number(line.tax_rate).toFixed(2) as DocumentLineInput["tax_rate"],
      tax_note: line.tax_note ?? "",
    })),
  };
}

function DocumentForm({ document, onCancel, onSaved }: {
  document: BusinessDocument | null; onCancel: () => void; onSaved: () => void;
}) {
  const [form, setForm] = useState<BusinessDocumentInput>(() => document ? documentToInput(document) : emptyDocument());
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [billableItems, setBillableItems] = useState<BillableProjectItem[]>([]);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [sourcesLoading, setSourcesLoading] = useState(false);

  useEffect(() => {
    Promise.all([getContacts(), getProjects(), getCatalogItems()])
      .then(([contactResult, projectResult, catalogResult]) => {
        setContacts(contactResult.results); setProjects(projectResult.results); setCatalog(catalogResult.results);
      }).catch(() => setError("Stammdaten konnten nicht vollständig geladen werden."));
  }, []);

  useEffect(() => {
    if (!form.project) {
      setBillableItems([]); setSelectedSources([]); return;
    }
    setSourcesLoading(true);
    getBillableProjectItems(form.project, document?.id)
      .then(setBillableItems)
      .catch((reason) => setError(
        reason instanceof Error ? reason.message : "Projektleistungen konnten nicht geladen werden.",
      ))
      .finally(() => setSourcesLoading(false));
  }, [document?.id, form.project]);

  function field<K extends keyof BusinessDocumentInput>(key: K, value: BusinessDocumentInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }
  function lineField(index: number, key: keyof DocumentLineInput, value: string | null) {
    setForm((current) => ({
      ...current,
      lines: current.lines.map((line, lineIndex) => lineIndex === index ? { ...line, [key]: value } : line),
    }));
  }
  function applyCatalog(index: number, itemId: string) {
    const item = catalog.find((candidate) => candidate.id === itemId);
    if (!item) { lineField(index, "catalog_item", null); return; }
    setForm((current) => ({
      ...current,
      lines: current.lines.map((line, lineIndex) => lineIndex === index ? {
        ...line, catalog_item: item.id, description: item.name, unit: item.unit,
        unit_price_net: item.current_price?.net_amount ?? line.unit_price_net,
        tax_rate: current.tax_mode === "small_business" ? "0.00" : item.tax_rate,
        tax_note: current.tax_mode === "small_business"
          ? "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet." : item.tax_note,
      } : line),
    }));
  }
  function changeTaxMode(value: "standard" | "small_business") {
    const note = value === "small_business" ? "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet." : "";
    setForm((current) => ({
      ...current, tax_mode: value, tax_exemption_note: note,
      lines: current.lines.map((line) => value === "small_business"
        ? { ...line, tax_rate: "0.00", tax_note: note }
        : { ...line, tax_rate: "19.00", tax_note: "" }),
    }));
  }
  function changeProject(value: string) {
    setForm((current) => {
      const manualLines = current.lines.filter(
        (line) => !line.source_time_entry && !line.source_service_entry,
      );
      return { ...current, project: value || null, lines: manualLines.length ? manualLines : [emptyLine()] };
    });
    setSelectedSources([]);
  }
  function addSelectedSources() {
    const chosen = billableItems.filter((item) => selectedSources.includes(item.id));
    const existingSourceIds = new Set(form.lines.flatMap((line) => [
      line.source_time_entry, line.source_service_entry,
    ]).filter((value): value is string => Boolean(value)));
    const imported = chosen.filter((item) => !existingSourceIds.has(item.id)).map((item) => {
      const smallBusiness = form.tax_mode === "small_business";
      return {
        catalog_item: item.catalog_item ?? null,
        source_time_entry: item.source_type === "time" ? item.id : null,
        source_service_entry: item.source_type === "service" ? item.id : null,
        description: item.description,
        quantity: item.quantity,
        unit: item.unit,
        unit_price_net: item.unit_price_net,
        discount_percent: "0.00",
        tax_rate: smallBusiness ? "0.00" : Number(item.tax_rate).toFixed(2),
        tax_note: smallBusiness
          ? form.tax_exemption_note ?? "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet."
          : item.tax_note ?? "",
      } as DocumentLineInput;
    });
    const placeholderOnly = form.lines.length === 1
      && !form.lines[0].description && Number(form.lines[0].unit_price_net) === 0;
    const dates = chosen.map((item) => item.date).sort();
    setForm((current) => ({
      ...current,
      lines: [...(placeholderOnly ? [] : current.lines), ...imported],
      service_date_from: dates[0] ?? current.service_date_from,
      service_date_to: dates.at(-1) ?? current.service_date_to,
    }));
    setSelectedSources([]);
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      if (document) await updateBusinessDocument(document, form);
      else await createBusinessDocument(form);
      onSaved();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Belegentwurf konnte nicht gespeichert werden.");
    } finally { setBusy(false); }
  }
  async function archive() {
    if (!document || !window.confirm("Diesen Entwurf wirklich archivieren?")) return;
    setBusy(true); setError("");
    try { await archiveBusinessDocument(document); onSaved(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Entwurf konnte nicht archiviert werden."); }
    finally { setBusy(false); }
  }
  async function finalize() {
    if (!document || document.kind !== "invoice") return;
    if (!window.confirm("Rechnung jetzt endgültig festschreiben? Danach sind Inhalt und Rechnungsnummer unveränderbar.")) return;
    setBusy(true); setError("");
    try { await finalizeBusinessDocument(document); onSaved(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Rechnung konnte nicht festgeschrieben werden."); }
    finally { setBusy(false); }
  }

  const matchingProjects = projects.filter((project) => !form.customer || project.customer === form.customer);
  return <form className="rounded-[2rem] border border-fuchsia-200 bg-white p-6 shadow-sm sm:p-8" onSubmit={submit}>
    <div className="flex items-start justify-between gap-4"><div><p className="text-sm font-bold uppercase tracking-[0.18em] text-fuchsia-700">{document ? "Entwurf bearbeiten" : "Neuer Belegentwurf"}</p><h1 className="mt-2 text-3xl font-bold text-slate-950">{kindLabels[form.kind]}</h1></div><button type="button" className="text-sm font-semibold text-slate-600" onClick={onCancel}>Schließen</button></div>
    <div className="mt-7 grid gap-5 md:grid-cols-2">
      <label className="text-sm font-semibold text-slate-800">Belegart<select className={inputClass} value={form.kind} onChange={(event) => field("kind", event.target.value as "quote" | "invoice")}><option value="quote">Angebot</option><option value="invoice">Rechnung</option></select></label>
      <label className="text-sm font-semibold text-slate-800">Besteuerung<select className={inputClass} value={form.tax_mode} onChange={(event) => changeTaxMode(event.target.value as "standard" | "small_business")}><option value="standard">Regelbesteuerung</option><option value="small_business">Kleinunternehmer (§ 19 UStG)</option></select></label>
      <label className="text-sm font-semibold text-slate-800">Kunde<select className={inputClass} value={form.customer} onChange={(event) => setForm({ ...form, customer: event.target.value, project: null })} required><option value="">Kunde auswählen …</option>{contacts.map((contact) => <option key={contact.id} value={contact.id}>{contact.customer_number} · {contact.display_name}</option>)}</select></label>
      <label className="text-sm font-semibold text-slate-800">Projekt (optional)<select className={inputClass} value={form.project ?? ""} onChange={(event) => changeProject(event.target.value)}><option value="">Ohne Projekt</option>{matchingProjects.map((project) => <option key={project.id} value={project.id}>{project.project_number} · {project.name}</option>)}</select></label>
      <label className="text-sm font-semibold text-slate-800">Belegdatum<input className={inputClass} type="date" value={form.issue_date} onChange={(event) => field("issue_date", event.target.value)} required /></label>
      <label className="text-sm font-semibold text-slate-800">{form.kind === "invoice" ? "Fällig am" : "Gültig bis"}<input className={inputClass} type="date" value={form.due_date ?? ""} onChange={(event) => field("due_date", event.target.value || null)} /></label>
      <label className="text-sm font-semibold text-slate-800">Leistung von<input className={inputClass} type="date" value={form.service_date_from ?? ""} onChange={(event) => field("service_date_from", event.target.value || null)} /></label>
      <label className="text-sm font-semibold text-slate-800">Leistung bis<input className={inputClass} type="date" value={form.service_date_to ?? ""} onChange={(event) => field("service_date_to", event.target.value || null)} /></label>
      <label className="text-sm font-semibold text-slate-800 md:col-span-2">Einleitung<textarea className={`${inputClass} min-h-20`} value={form.introduction ?? ""} onChange={(event) => field("introduction", event.target.value)} /></label>
    </div>

    {form.project && <section className="mt-7 rounded-2xl border border-sky-200 bg-sky-50 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-sm font-bold uppercase tracking-wider text-sky-800">Offene Projektleistungen</p><p className="mt-1 text-sm text-sky-900">Ausgewählte Zeiten und Mengenleistungen werden mit ihrem erfassten Preis als Belegpositionen reserviert.</p></div><button type="button" className="rounded-xl bg-sky-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" onClick={addSelectedSources} disabled={!selectedSources.length}>Auswahl übernehmen</button></div>
      {sourcesLoading && <p className="mt-4 text-sm text-sky-800">Projektleistungen werden geladen …</p>}
      {!sourcesLoading && !billableItems.length && <p className="mt-4 text-sm text-sky-800">Keine offenen abrechenbaren Einträge vorhanden.</p>}
      <div className="mt-4 grid gap-2">{billableItems.map((item) => {
        const alreadyAdded = form.lines.some((line) => line.source_time_entry === item.id || line.source_service_entry === item.id);
        return <label key={`${item.source_type}-${item.id}`} className="flex items-start gap-3 rounded-xl bg-white p-3 text-sm text-slate-800"><input className="mt-1" type="checkbox" checked={alreadyAdded || selectedSources.includes(item.id)} disabled={alreadyAdded} onChange={(event) => setSelectedSources((current) => event.target.checked ? [...current, item.id] : current.filter((id) => id !== item.id))} /><span className="flex-1"><strong>{item.source_type === "time" ? "Zeit" : "Leistung"} · {item.date} · {item.work_package}</strong><span className="mt-1 block text-slate-600">{item.description} · {item.quantity} {item.unit_label} × {money(item.unit_price_net)} · {item.employee}</span></span><strong>{money(item.net_amount)}</strong></label>;
      })}</div>
    </section>}

    <div className="mt-8 flex items-center justify-between"><div><p className="text-sm font-bold uppercase tracking-wider text-fuchsia-700">Positionen</p><p className="mt-1 text-sm text-slate-500">Summen werden verbindlich auf dem Server berechnet.</p></div><button type="button" className="rounded-xl border border-fuchsia-200 px-4 py-2 text-sm font-semibold text-fuchsia-800" onClick={() => field("lines", [...form.lines, emptyLine()])}>+ Position</button></div>
    <div className="mt-4 space-y-4">{form.lines.map((line, index) => <section key={index} className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
      <div className="flex items-center justify-between"><strong className="text-slate-900">Position {index + 1}</strong>{form.lines.length > 1 && <button type="button" className="text-sm font-semibold text-red-700" onClick={() => field("lines", form.lines.filter((_, lineIndex) => lineIndex !== index))}>Entfernen</button>}</div>
      <div className="mt-4 grid gap-4 md:grid-cols-6">
        <label className="text-xs font-bold uppercase tracking-wider text-slate-600 md:col-span-2">Katalog (optional)<select className={inputClass} value={line.catalog_item ?? ""} disabled={Boolean(line.source_time_entry || line.source_service_entry)} onChange={(event) => applyCatalog(index, event.target.value)}><option value="">Freie Position</option>{catalog.map((item) => <option key={item.id} value={item.id}>{item.item_number} · {item.name}</option>)}</select></label>
        <label className="text-xs font-bold uppercase tracking-wider text-slate-600 md:col-span-4">Beschreibung<input className={inputClass} value={line.description} onChange={(event) => lineField(index, "description", event.target.value)} required /></label>
        <label className="text-xs font-bold uppercase tracking-wider text-slate-600">Menge<input className={inputClass} type="number" min="0.000001" step="0.000001" value={line.quantity} disabled={Boolean(line.source_time_entry || line.source_service_entry)} onChange={(event) => lineField(index, "quantity", event.target.value)} required /></label>
        <label className="text-xs font-bold uppercase tracking-wider text-slate-600">Einheit<select className={inputClass} value={line.unit} disabled={Boolean(line.source_time_entry || line.source_service_entry)} onChange={(event) => lineField(index, "unit", event.target.value)}>{Object.entries(unitLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label className="text-xs font-bold uppercase tracking-wider text-slate-600 md:col-span-2">Einzelpreis netto<input className={inputClass} type="number" min="0" step="0.01" value={line.unit_price_net} disabled={Boolean(line.source_time_entry || line.source_service_entry)} onChange={(event) => lineField(index, "unit_price_net", event.target.value)} required /></label>
        <label className="text-xs font-bold uppercase tracking-wider text-slate-600">Rabatt %<input className={inputClass} type="number" min="0" max="100" step="0.01" value={line.discount_percent} disabled={Boolean(line.source_time_entry || line.source_service_entry)} onChange={(event) => lineField(index, "discount_percent", event.target.value)} required /></label>
        <label className="text-xs font-bold uppercase tracking-wider text-slate-600">Steuer<select className={inputClass} value={line.tax_rate} disabled={form.tax_mode === "small_business" || Boolean(line.source_time_entry || line.source_service_entry)} onChange={(event) => lineField(index, "tax_rate", event.target.value)}><option value="19.00">19 %</option><option value="7.00">7 %</option><option value="0.00">0 %</option></select></label>
        {line.tax_rate === "0.00" && <label className="text-xs font-bold uppercase tracking-wider text-slate-600 md:col-span-6">Steuerhinweis<input className={inputClass} value={line.tax_note ?? ""} onChange={(event) => lineField(index, "tax_note", event.target.value)} required /></label>}
      </div>
    </section>)}</div>

    {form.tax_mode === "small_business" && <label className="mt-5 block text-sm font-semibold text-slate-800">Hinweis zur Steuerbefreiung<textarea className={`${inputClass} min-h-20`} value={form.tax_exemption_note ?? ""} onChange={(event) => field("tax_exemption_note", event.target.value)} required /></label>}
    <div className="mt-5 grid gap-5 md:grid-cols-2"><label className="text-sm font-semibold text-slate-800">Schlusstext<textarea className={`${inputClass} min-h-20`} value={form.closing_text ?? ""} onChange={(event) => field("closing_text", event.target.value)} /></label><label className="text-sm font-semibold text-slate-800">Zahlungsbedingungen<textarea className={`${inputClass} min-h-20`} value={form.payment_terms ?? ""} onChange={(event) => field("payment_terms", event.target.value)} /></label></div>
    {error && <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    <div className="mt-7 flex flex-wrap items-center justify-between gap-3">
      {document ? <button type="button" className="rounded-xl border border-red-200 px-4 py-3 text-sm font-semibold text-red-700" onClick={archive} disabled={busy}>Archivieren</button> : <span />}
      <div className="flex flex-wrap justify-end gap-3">
        {document?.kind === "invoice" && <button type="button" className="rounded-xl border border-emerald-300 bg-emerald-50 px-5 py-3 font-semibold text-emerald-800 disabled:opacity-60" onClick={finalize} disabled={busy}>Endgültig festschreiben</button>}
        <button className="rounded-xl bg-fuchsia-700 px-5 py-3 font-semibold text-white hover:bg-fuchsia-800 disabled:opacity-60" disabled={busy}>{busy ? "Wird gespeichert …" : "Entwurf speichern"}</button>
      </div>
    </div>
    {document?.kind === "invoice" && <p className="mt-3 text-right text-xs text-slate-500">Beim Festschreiben werden Pflichtangaben geprüft, eine fortlaufende Nummer vergeben und ein unveränderlicher Snapshot erzeugt.</p>}
  </form>;
}

export function DocumentsPage({ onBack }: { onBack: () => void }) {
  const [documents, setDocuments] = useState<BusinessDocument[]>([]);
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState<"quote" | "invoice" | "">("");
  const [editing, setEditing] = useState<BusinessDocument | null | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true); setError("");
    getBusinessDocuments({ search, kind }).then((result) => setDocuments(result.results))
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Belege konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }, [kind, search]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!documents.some((document) => ["finalizing", "artifact_failed"].includes(document.status ?? ""))) return;
    const timer = window.setInterval(load, 5000);
    return () => window.clearInterval(timer);
  }, [documents, load]);

  if (editing !== undefined) return <main className="mx-auto max-w-6xl px-6 py-10"><DocumentForm document={editing} onCancel={() => setEditing(undefined)} onSaved={() => { setEditing(undefined); load(); }} /></main>;

  return <main className="mx-auto max-w-7xl px-6 py-10">
    <button className="text-sm font-semibold text-fuchsia-700" onClick={onBack}>← Zurück zum Dashboard</button>
    <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-sm font-bold uppercase tracking-[0.18em] text-fuchsia-700">Dokumentkern · Phase 4</p><h1 className="mt-2 text-3xl font-bold text-slate-950">Angebote &amp; Ausgangsrechnungen</h1><p className="mt-2 text-sm text-slate-600">Entwürfe werden serverseitig berechnet. Nach der Festschreibung entsteht das Standard-PDF automatisch aus dem unveränderlichen Snapshot.</p></div><button className="rounded-xl bg-fuchsia-700 px-5 py-3 font-semibold text-white" onClick={() => setEditing(null)}>+ Belegentwurf</button></div>
    <div className="mt-6 grid gap-4 rounded-2xl bg-white p-4 shadow-sm sm:grid-cols-[1fr_220px]"><input className="rounded-xl border border-slate-300 px-4 py-3" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Kunde oder Projekt suchen" /><select className="rounded-xl border border-slate-300 px-4 py-3" value={kind} onChange={(event) => setKind(event.target.value as typeof kind)}><option value="">Alle Belegarten</option><option value="quote">Angebote</option><option value="invoice">Rechnungen</option></select></div>
    {error && <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    <div className="mt-6 grid gap-4 lg:grid-cols-2">{documents.map((document) => <article key={document.id} className="rounded-2xl border border-slate-200 bg-white p-5 text-left shadow-sm"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wider text-fuchsia-700">{kindLabels[document.kind]} · {statusLabels[document.status ?? "draft"]}</p><h2 className="mt-2 text-xl font-bold text-slate-950">{document.document_number ?? document.customer_name}</h2>{document.document_number && <p className="mt-1 font-semibold text-slate-800">{document.customer_name}</p>}<p className="mt-1 text-sm text-slate-500">{document.project_number ? `${document.project_number} · ${document.project_name}` : "Ohne Projekt"}</p></div><strong className="text-xl text-slate-950">{money(document.gross_total)}</strong></div><div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-600"><span>{document.issue_date}</span><span>Netto {money(document.net_total)}</span><span>Steuer {money(document.tax_total)}</span><span>Version {document.version}</span>{document.snapshot && <span title={document.snapshot.sha256}>Snapshot v{document.snapshot.schema_version}</span>}</div><div className="mt-5 flex flex-wrap justify-end gap-3">{document.status === "draft" && <button className="rounded-xl border border-fuchsia-200 px-4 py-2 text-sm font-semibold text-fuchsia-800" onClick={() => setEditing(document)}>Entwurf bearbeiten</button>}{document.artifact && <a className="rounded-xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white" href={document.artifact.download_url}>PDF herunterladen</a>}</div></article>)}</div>
    {!documents.length && !loading && !error && <p className="mt-6 rounded-2xl bg-white px-6 py-12 text-center text-sm text-slate-500">Noch keine passenden Belegentwürfe vorhanden.</p>}
    {loading && <p className="mt-6 text-center text-sm text-slate-500">Belege werden geladen …</p>}
  </main>;
}
