import { FormEvent, useCallback, useEffect, useState } from "react";
import { getIncomingInvoices, uploadIncomingInvoice, type IncomingInvoice, type ManualIncomingInvoiceInput } from "./api";

const formatLabels = {
  standard_pdf: "Normale PDF-Rechnung",
  xrechnung_ubl: "XRechnung UBL",
  xrechnung_cii: "XRechnung CII",
  zugferd: "ZUGFeRD",
  unknown: "Unbekannt",
} as const;

function InvoiceDetail({ invoice, onBack }: { invoice: IncomingInvoice; onBack: () => void }) {
  const successfulLabel = invoice.format === "standard_pdf" ? "Vollständig erfasst" : "Basisprüfung bestanden";
  return <main className="mx-auto max-w-5xl px-6 py-10">
    <button className="text-sm font-semibold text-blue-700" onClick={onBack}>← Zurück zum Rechnungseingang</button>
    <section className="mt-6 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><p className="text-sm font-bold uppercase tracking-[0.18em] text-blue-700">{formatLabels[invoice.format]}</p><h1 className="mt-2 text-3xl font-bold text-slate-950">{invoice.invoice_number || invoice.original_name}</h1><p className="mt-2 text-sm text-slate-600">Original: {invoice.original_name}</p></div><span className={`w-fit rounded-full px-3 py-1 text-xs font-bold ${invoice.status === "valid" ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"}`}>{invoice.status === "valid" ? successfulLabel : "Prüfung fehlgeschlagen"}</span></div>
      <dl className="mt-7 grid gap-4 rounded-2xl bg-slate-50 p-5 sm:grid-cols-2"><div><dt className="text-xs font-bold uppercase text-slate-500">Rechnungsdatum</dt><dd className="mt-1 font-semibold text-slate-900">{invoice.issue_date ? new Intl.DateTimeFormat("de-DE").format(new Date(`${invoice.issue_date}T00:00:00`)) : "—"}</dd></div><div><dt className="text-xs font-bold uppercase text-slate-500">Zahlbetrag</dt><dd className="mt-1 font-semibold text-slate-900">{invoice.payable_amount ? `${invoice.payable_amount} ${invoice.currency}` : "—"}</dd></div><div><dt className="text-xs font-bold uppercase text-slate-500">Verkäufer</dt><dd className="mt-1 font-semibold text-slate-900">{invoice.seller_name || "—"}</dd></div><div><dt className="text-xs font-bold uppercase text-slate-500">Käufer</dt><dd className="mt-1 font-semibold text-slate-900">{invoice.buyer_name || "—"}</dd></div></dl>
      <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm leading-6 text-amber-950"><strong>Prüfumfang:</strong> {invoice.validation_report.scope}</div>
      {invoice.validation_report.errors.length > 0 && <div className="mt-6"><h2 className="font-bold text-slate-950">Prüfhinweise</h2><ul className="mt-3 space-y-2">{invoice.validation_report.errors.map((entry, index) => <li key={`${entry.code}-${index}`} className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{entry.message}</li>)}</ul></div>}
      <div className="mt-7 grid gap-3 text-xs text-slate-500 sm:grid-cols-2"><p><strong>SHA-256 Original:</strong><br /><code className="break-all">{invoice.sha256}</code></p>{invoice.embedded_xml_sha256 && <p><strong>SHA-256 eingebettete XML:</strong><br /><code className="break-all">{invoice.embedded_xml_sha256}</code></p>}<p><strong>Dateigröße:</strong> {new Intl.NumberFormat("de-DE").format(invoice.size)} Bytes</p><p><strong>Hochgeladen von:</strong> {invoice.uploaded_by ?? "unbekannt"}</p></div>
      <div className="mt-7 flex justify-end"><a className="rounded-xl bg-blue-700 px-5 py-3 font-semibold text-white" href={invoice.download_url}>Unverändertes Original herunterladen</a></div>
    </section>
  </main>;
}

export function IncomingInvoicesPage({ onBack }: { onBack: () => void }) {
  const [invoices, setInvoices] = useState<IncomingInvoice[]>([]);
  const [count, setCount] = useState(0);
  const [selected, setSelected] = useState<IncomingInvoice | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploadMode, setUploadMode] = useState<"automatic" | "standard_pdf">("automatic");
  const [manual, setManual] = useState<ManualIncomingInvoiceInput>({ invoice_number: "", issue_date: "", seller_name: "", buyer_name: "", currency: "EUR", payable_amount: "" });
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"valid" | "invalid" | "">("");
  const [format, setFormat] = useState<"standard_pdf" | "xrechnung_ubl" | "xrechnung_cii" | "zugferd" | "unknown" | "">("");
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true); setError("");
    getIncomingInvoices({ search, status, format, page })
      .then((result) => { setInvoices(result.results); setCount(result.count); setHasNext(Boolean(result.next)); setHasPrevious(Boolean(result.previous)); })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Rechnungseingang konnte nicht geladen werden."))
      .finally(() => setLoading(false));
  }, [search, status, format, page]);

  useEffect(() => { load(); }, [load]);

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true); setError("");
    try {
      const invoice = await uploadIncomingInvoice(file, uploadMode === "standard_pdf" ? manual : undefined);
      setFile(null);
      setSelected(invoice);
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Rechnung konnte nicht hochgeladen werden.");
    } finally {
      setBusy(false);
    }
  }

  if (selected) return <InvoiceDetail invoice={selected} onBack={() => setSelected(null)} />;

  return <main className="mx-auto max-w-7xl px-6 py-10">
    <button className="text-sm font-semibold text-blue-700" onClick={onBack}>← Zurück zum Dashboard</button>
    <div className="mt-6"><p className="text-sm font-bold uppercase tracking-[0.18em] text-blue-700">Phase 1a</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Rechnungseingang</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Normale PDF-Rechnungen manuell erfassen oder XRechnung und ZUGFeRD automatisch auslesen. Jedes Original wird unverändert und SHA-256-dedupliziert archiviert.</p></div>
    <div className="mt-7 flex gap-2 rounded-xl bg-slate-200 p-1 sm:w-fit"><button type="button" className={`rounded-lg px-4 py-2 text-sm font-semibold ${uploadMode === "automatic" ? "bg-white text-blue-800 shadow-sm" : "text-slate-600"}`} onClick={() => { setUploadMode("automatic"); setFile(null); }}>E-Rechnung automatisch</button><button type="button" className={`rounded-lg px-4 py-2 text-sm font-semibold ${uploadMode === "standard_pdf" ? "bg-white text-blue-800 shadow-sm" : "text-slate-600"}`} onClick={() => { setUploadMode("standard_pdf"); setFile(null); }}>Normale PDF-Rechnung</button></div>
    <form className="mt-3 rounded-2xl border border-blue-200 bg-blue-50 p-5" onSubmit={upload}>
      <label className="block text-sm font-semibold text-slate-800">{uploadMode === "automatic" ? "XML- oder PDF-Datei" : "PDF-Datei"}, maximal 20 MB<input className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-4 py-3 font-normal" type="file" accept={uploadMode === "automatic" ? ".xml,.pdf,application/xml,application/pdf" : ".pdf,application/pdf"} onChange={(event) => setFile(event.target.files?.[0] ?? null)} required /></label>
      {uploadMode === "standard_pdf" && <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <label className="text-sm font-semibold text-slate-800">Rechnungsnummer<input className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 font-normal" value={manual.invoice_number} onChange={(event) => setManual({ ...manual, invoice_number: event.target.value })} required /></label>
        <label className="text-sm font-semibold text-slate-800">Rechnungsdatum<input className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 font-normal" type="date" value={manual.issue_date} onChange={(event) => setManual({ ...manual, issue_date: event.target.value })} required /></label>
        <label className="text-sm font-semibold text-slate-800">Verkäufer<input className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 font-normal" value={manual.seller_name} onChange={(event) => setManual({ ...manual, seller_name: event.target.value })} required /></label>
        <label className="text-sm font-semibold text-slate-800">Käufer<input className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 font-normal" value={manual.buyer_name} onChange={(event) => setManual({ ...manual, buyer_name: event.target.value })} required /></label>
        <label className="text-sm font-semibold text-slate-800">Zahlbetrag<input className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 font-normal" type="number" min="0" step="0.01" value={manual.payable_amount} onChange={(event) => setManual({ ...manual, payable_amount: event.target.value })} required /></label>
        <label className="text-sm font-semibold text-slate-800">Währung<input className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 font-normal uppercase" maxLength={3} pattern="[A-Za-z]{3}" value={manual.currency} onChange={(event) => setManual({ ...manual, currency: event.target.value.toUpperCase() })} required /></label>
      </div>}
      <div className="mt-5 flex justify-end"><button className="rounded-xl bg-blue-700 px-5 py-3 font-semibold text-white disabled:opacity-50" disabled={!file || busy}>{busy ? "Wird gespeichert …" : uploadMode === "automatic" ? "E-Rechnung prüfen & archivieren" : "PDF-Rechnung erfassen & archivieren"}</button></div>
    </form>
    <p className="mt-3 rounded-xl bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-900">Normale PDF-Rechnungen werden mit den manuell eingegebenen Daten erfasst, aber nicht inhaltlich geprüft. Bei E-Rechnungen erfolgt eine technische Basisprüfung; eine vollständige KoSIT-/Schematron- oder Rechtsprüfung folgt später.</p>
    <form className="mt-7 grid gap-3 rounded-2xl bg-white p-4 shadow-sm lg:grid-cols-[1fr_190px_190px_auto]" onSubmit={(event) => { event.preventDefault(); setPage(1); setSearch(searchInput.trim()); }}><input className="rounded-xl border border-slate-300 px-4 py-3" placeholder="Nummer, Datei, Verkäufer oder Käufer" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} /><select className="rounded-xl border border-slate-300 px-4 py-3" value={status} onChange={(event) => { setStatus(event.target.value as typeof status); setPage(1); }}><option value="">Alle Prüfergebnisse</option><option value="valid">Bestanden</option><option value="invalid">Fehlgeschlagen</option></select><select className="rounded-xl border border-slate-300 px-4 py-3" value={format} onChange={(event) => { setFormat(event.target.value as typeof format); setPage(1); }}><option value="">Alle Formate</option>{Object.entries(formatLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><button className="rounded-xl bg-slate-950 px-5 py-3 font-semibold text-white">Suchen</button></form>
    {error && <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    <div className="mt-5 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">{loading ? <p className="p-6 text-sm text-slate-500">Rechnungseingang wird geladen …</p> : invoices.length ? invoices.map((invoice) => <button key={invoice.id} className="grid w-full gap-2 border-b border-slate-100 p-5 text-left last:border-0 hover:bg-blue-50 sm:grid-cols-[130px_1fr_1fr_150px_auto] sm:items-center" onClick={() => setSelected(invoice)}><span className={`w-fit rounded-full px-3 py-1 text-xs font-bold ${invoice.status === "valid" ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"}`}>{invoice.status === "valid" ? invoice.format === "standard_pdf" ? "Erfasst" : "Bestanden" : "Fehler"}</span><span><strong className="block text-slate-950">{invoice.invoice_number || invoice.original_name}</strong><small className="text-slate-500">{formatLabels[invoice.format]}</small></span><span className="text-sm text-slate-600">{invoice.seller_name || "Keine Verkäuferdaten"}</span><span className="text-sm font-semibold text-slate-900">{invoice.payable_amount ? `${invoice.payable_amount} ${invoice.currency}` : "—"}</span><span className="text-sm font-semibold text-blue-700">Details →</span></button>) : <p className="p-8 text-center text-sm text-slate-500">Noch keine Rechnungen eingegangen.</p>}</div>
    <div className="mt-5 flex items-center justify-between"><button className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold disabled:opacity-40" disabled={!hasPrevious} onClick={() => setPage((value) => value - 1)}>← Zurück</button><span className="text-sm text-slate-500">{count} Einträge · Seite {page}</span><button className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold disabled:opacity-40" disabled={!hasNext} onClick={() => setPage((value) => value + 1)}>Weiter →</button></div>
  </main>;
}
