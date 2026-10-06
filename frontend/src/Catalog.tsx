import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  archiveCatalogItem,
  createCatalogItem,
  getCatalogItems,
  updateCatalogItem,
  type CatalogItem,
  type CatalogItemInput,
  type CatalogPriceInput,
  type User,
} from "./api";

const inputClass = "mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 font-normal outline-none transition focus:border-blue-600 focus:ring-4 focus:ring-blue-100";
const units = { hour: "Stunde", day: "Tag", piece: "Stück", flat: "Pauschal" } as const;

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function emptyItem(): CatalogItemInput {
  return {
    kind: "service",
    name: "",
    description: "",
    unit: "hour",
    tax_rate: "19.00",
    tax_note: "",
    prices: [{ net_amount: "0.00", valid_from: today(), valid_until: null }],
  };
}

function itemToInput(item: CatalogItem): CatalogItemInput {
  return {
    kind: item.kind,
    name: item.name,
    description: item.description,
    unit: item.unit,
    tax_rate: item.tax_rate,
    tax_note: item.tax_note,
    prices: item.prices.map(({ net_amount, valid_from, valid_until }) => ({ net_amount, valid_from, valid_until })),
  };
}

function CatalogForm({ item, user, onCancel, onSaved }: {
  item: CatalogItem | null;
  user: User;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<CatalogItemInput>(() => item ? itemToInput(item) : emptyItem());
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function field<K extends keyof CatalogItemInput>(key: K, value: CatalogItemInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function updatePrice(index: number, patch: Partial<CatalogPriceInput>) {
    setForm((current) => ({
      ...current,
      prices: current.prices.map((price, priceIndex) => priceIndex === index ? { ...price, ...patch } : price),
    }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (item) await updateCatalogItem(item, form);
      else await createCatalogItem(form);
      onSaved();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Katalogeintrag konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  async function archive() {
    if (!item || !window.confirm(`${item.name} wirklich archivieren?`)) return;
    setBusy(true);
    setError("");
    try {
      await archiveCatalogItem(item);
      onSaved();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Katalogeintrag konnte nicht archiviert werden.");
    } finally {
      setBusy(false);
    }
  }

  return <form className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm sm:p-8" onSubmit={submit}>
    <div className="flex items-start justify-between gap-4"><div><p className="text-sm font-bold uppercase tracking-[0.18em] text-blue-700">{item?.item_number ?? "Neuer Katalogeintrag"}</p><h2 className="mt-2 text-2xl font-bold text-slate-950">{item?.name ?? "Artikel oder Leistung anlegen"}</h2></div><button type="button" className="text-sm font-semibold text-slate-600" onClick={onCancel}>Schließen</button></div>
    <div className="mt-7 grid gap-5 sm:grid-cols-2">
      <label className="text-sm font-semibold text-slate-800">Typ<select className={inputClass} value={form.kind} onChange={(event) => field("kind", event.target.value as CatalogItemInput["kind"])}><option value="service">Leistung</option><option value="product">Artikel</option></select></label>
      <label className="text-sm font-semibold text-slate-800">Name<input className={inputClass} value={form.name} onChange={(event) => field("name", event.target.value)} required /></label>
      <label className="text-sm font-semibold text-slate-800">Einheit<select className={inputClass} value={form.unit} onChange={(event) => field("unit", event.target.value as CatalogItemInput["unit"])}>{Object.entries(units).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label className="text-sm font-semibold text-slate-800">Steuersatz<select className={inputClass} value={form.tax_rate} onChange={(event) => field("tax_rate", event.target.value as CatalogItemInput["tax_rate"])}><option value="19.00">19 %</option><option value="7.00">7 %</option><option value="0.00">0 %</option></select></label>
      <label className="text-sm font-semibold text-slate-800 sm:col-span-2">Beschreibung<textarea className={inputClass} rows={3} value={form.description ?? ""} onChange={(event) => field("description", event.target.value)} /></label>
      <label className="text-sm font-semibold text-slate-800 sm:col-span-2">Steuerhinweis<input className={inputClass} placeholder="z. B. Steuerbefreiung oder §19-Hinweis" value={form.tax_note ?? ""} onChange={(event) => field("tax_note", event.target.value)} /></label>
    </div>
    <section className="mt-8 border-t border-slate-200 pt-7">
      <div className="flex items-center justify-between gap-4"><div><h3 className="font-bold text-slate-950">Nettopreise</h3><p className="mt-1 text-sm text-slate-500">Zeiträume dürfen sich nicht überschneiden.</p></div><button type="button" className="rounded-lg bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700" onClick={() => setForm((current) => ({ ...current, prices: [...current.prices, { net_amount: "0.00", valid_from: today(), valid_until: null }] }))}>+ Preis</button></div>
      <div className="mt-4 space-y-3">{form.prices.map((price, index) => <div key={index} className="grid gap-3 rounded-2xl bg-slate-50 p-4 sm:grid-cols-[1fr_1fr_1fr_auto] sm:items-end">
        <label className="text-xs font-semibold text-slate-600">Netto in EUR<input className={inputClass} type="number" min="0" step="0.01" value={price.net_amount} onChange={(event) => updatePrice(index, { net_amount: event.target.value })} required /></label>
        <label className="text-xs font-semibold text-slate-600">Gültig ab<input className={inputClass} type="date" value={price.valid_from} onChange={(event) => updatePrice(index, { valid_from: event.target.value })} required /></label>
        <label className="text-xs font-semibold text-slate-600">Gültig bis<input className={inputClass} type="date" value={price.valid_until ?? ""} onChange={(event) => updatePrice(index, { valid_until: event.target.value || null })} /></label>
        <button type="button" className="pb-3 text-sm font-semibold text-red-700 disabled:opacity-40" disabled={form.prices.length === 1} onClick={() => setForm((current) => ({ ...current, prices: current.prices.filter((_, priceIndex) => priceIndex !== index) }))}>Entfernen</button>
      </div>)}</div>
    </section>
    {error && <p className="mt-6 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    <div className="mt-7 flex flex-wrap items-center justify-between gap-3">{item && user.role === "admin" ? <button type="button" className="rounded-xl border border-red-200 px-4 py-3 text-sm font-semibold text-red-700" onClick={archive} disabled={busy}>Archivieren</button> : <span />}<div className="flex gap-3"><button type="button" className="rounded-xl border border-slate-300 px-4 py-3 font-semibold text-slate-700" onClick={onCancel}>Abbrechen</button><button className="rounded-xl bg-blue-700 px-5 py-3 font-semibold text-white disabled:opacity-60" disabled={busy}>{busy ? "Wird gespeichert …" : "Speichern"}</button></div></div>
  </form>;
}

export function CatalogPage({ user, onBack }: { user: User; onBack: () => void }) {
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [count, setCount] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState<"product" | "service" | "">("");
  const [unit, setUnit] = useState<"hour" | "day" | "piece" | "flat" | "">("");
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [selected, setSelected] = useState<CatalogItem | null | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true); setError("");
    getCatalogItems({ search, kind, unit, page })
      .then((result) => { setItems(result.results); setCount(result.count); setHasNext(Boolean(result.next)); setHasPrevious(Boolean(result.previous)); })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Katalog konnte nicht geladen werden."))
      .finally(() => setLoading(false));
  }, [search, kind, unit, page]);

  useEffect(() => { load(); }, [load]);

  if (selected !== undefined) return <main className="mx-auto max-w-6xl px-6 py-10"><CatalogForm item={selected} user={user} onCancel={() => setSelected(undefined)} onSaved={() => { setSelected(undefined); load(); }} /></main>;

  return <main className="mx-auto max-w-7xl px-6 py-10">
    <button className="text-sm font-semibold text-blue-700" onClick={onBack}>← Zurück zum Dashboard</button>
    <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-sm font-bold uppercase tracking-[0.18em] text-blue-700">Katalog</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Artikel &amp; Leistungen</h1><p className="mt-2 text-sm text-slate-600">{count} aktive Einträge</p></div><button className="rounded-xl bg-blue-700 px-5 py-3 font-semibold text-white" onClick={() => setSelected(null)}>+ Eintrag anlegen</button></div>
    <form className="mt-7 grid gap-3 rounded-2xl bg-white p-4 shadow-sm lg:grid-cols-[1fr_170px_170px_auto]" onSubmit={(event) => { event.preventDefault(); setPage(1); setSearch(searchInput.trim()); }}><input className="rounded-xl border border-slate-300 px-4 py-3" placeholder="Name, Beschreibung oder Nummer" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} /><select className="rounded-xl border border-slate-300 px-4 py-3" value={kind} onChange={(event) => { setKind(event.target.value as typeof kind); setPage(1); }}><option value="">Alle Typen</option><option value="product">Artikel</option><option value="service">Leistungen</option></select><select className="rounded-xl border border-slate-300 px-4 py-3" value={unit} onChange={(event) => { setUnit(event.target.value as typeof unit); setPage(1); }}><option value="">Alle Einheiten</option>{Object.entries(units).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><button className="rounded-xl bg-slate-950 px-5 py-3 font-semibold text-white">Suchen</button></form>
    {error && <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    <div className="mt-5 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">{loading ? <p className="p-6 text-sm text-slate-500">Katalog wird geladen …</p> : items.length ? items.map((item) => <button key={item.id} className="grid w-full gap-2 border-b border-slate-100 p-5 text-left last:border-0 hover:bg-blue-50 sm:grid-cols-[130px_1fr_150px_140px_auto] sm:items-center" onClick={() => setSelected(item)}><span className="font-mono text-sm font-semibold text-slate-500">{item.item_number}</span><span><strong className="block text-slate-950">{item.name}</strong><small className="text-slate-500">{item.kind === "service" ? "Leistung" : "Artikel"}</small></span><span className="text-sm text-slate-600">{units[item.unit]}</span><span className="text-sm font-semibold text-slate-900">{item.current_price ? `${item.current_price.net_amount} € netto` : "Kein aktueller Preis"}</span><span className="text-sm font-semibold text-blue-700">Bearbeiten →</span></button>) : <p className="p-8 text-center text-sm text-slate-500">Keine Katalogeinträge gefunden.</p>}</div>
    <div className="mt-5 flex items-center justify-between"><button className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold disabled:opacity-40" disabled={!hasPrevious} onClick={() => setPage((value) => value - 1)}>← Zurück</button><span className="text-sm text-slate-500">Seite {page}</span><button className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold disabled:opacity-40" disabled={!hasNext} onClick={() => setPage((value) => value + 1)}>Weiter →</button></div>
  </main>;
}
