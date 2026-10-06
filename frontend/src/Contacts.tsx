import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  archiveContact,
  createContact,
  getContacts,
  updateContact,
  type Contact,
  type ContactAddressInput,
  type ContactInput,
  type ContactPersonInput,
  type User,
} from "./api";

const inputClass = "mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 font-normal outline-none transition focus:border-blue-600 focus:ring-4 focus:ring-blue-100";

function emptyContact(): ContactInput {
  return {
    kind: "organization",
    company_name: "",
    salutation: "",
    title: "",
    first_name: "",
    last_name: "",
    email: "",
    phone: "",
    website: "",
    vat_id: "",
    leitweg_id: "",
    addresses: [],
    contact_persons: [],
  };
}

function contactToInput(contact: Contact): ContactInput {
  return {
    kind: contact.kind,
    company_name: contact.company_name,
    salutation: contact.salutation,
    title: contact.title,
    first_name: contact.first_name,
    last_name: contact.last_name,
    email: contact.email,
    phone: contact.phone,
    website: contact.website,
    vat_id: contact.vat_id,
    leitweg_id: contact.leitweg_id,
    addresses: contact.addresses.map((address) => ({
      kind: address.kind,
      label: address.label,
      street: address.street,
      postal_code: address.postal_code,
      city: address.city,
      country_code: address.country_code,
      is_default: address.is_default,
    })),
    contact_persons: contact.contact_persons.map((person) => ({
      salutation: person.salutation,
      title: person.title,
      first_name: person.first_name,
      last_name: person.last_name,
      role: person.role,
      email: person.email,
      phone: person.phone,
      is_primary: person.is_primary,
    })),
  };
}

function ContactForm({
  contact,
  user,
  onCancel,
  onSaved,
}: {
  contact: Contact | null;
  user: User;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<ContactInput>(() => contact ? contactToInput(contact) : emptyContact());
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function field(key: keyof ContactInput, value: string) {
    setForm((current) => ({
      ...current,
      [key]: value,
      ...(key === "kind" && value === "person" ? { contact_persons: [] } : {}),
    } as ContactInput));
  }

  function updateAddress(index: number, patch: Partial<ContactAddressInput>) {
    setForm((current) => ({
      ...current,
      addresses: current.addresses.map((address, itemIndex) =>
        itemIndex === index ? { ...address, ...patch } : address
      ),
    }));
  }

  function updatePerson(index: number, patch: Partial<ContactPersonInput>) {
    setForm((current) => ({
      ...current,
      contact_persons: current.contact_persons.map((person, itemIndex) =>
        itemIndex === index ? { ...person, ...patch } : person
      ),
    }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (contact) await updateContact(contact, form);
      else await createContact(form);
      onSaved();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Kontakt konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  async function archive() {
    if (!contact || !window.confirm(`${contact.display_name} wirklich archivieren?`)) return;
    setBusy(true);
    setError("");
    try {
      await archiveContact(contact);
      onSaved();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Kontakt konnte nicht archiviert werden.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm sm:p-8" onSubmit={submit}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-bold uppercase tracking-[0.18em] text-blue-700">{contact ? contact.customer_number : "Neuer Kontakt"}</p>
          <h2 className="mt-2 text-2xl font-bold text-slate-950">{contact ? contact.display_name : "Kontakt anlegen"}</h2>
        </div>
        <button type="button" className="text-sm font-semibold text-slate-600 hover:text-slate-950" onClick={onCancel}>Schließen</button>
      </div>

      <div className="mt-7 grid gap-5 sm:grid-cols-2">
        <label className="text-sm font-semibold text-slate-800">Typ
          <select className={inputClass} value={form.kind} onChange={(event) => field("kind", event.target.value)}>
            <option value="organization">Firma</option><option value="person">Person</option>
          </select>
        </label>
        {form.kind === "organization" ? (
          <label className="text-sm font-semibold text-slate-800">Firmenname<input className={inputClass} value={form.company_name ?? ""} onChange={(event) => field("company_name", event.target.value)} required /></label>
        ) : (
          <>
            <label className="text-sm font-semibold text-slate-800">Vorname<input className={inputClass} value={form.first_name ?? ""} onChange={(event) => field("first_name", event.target.value)} required /></label>
            <label className="text-sm font-semibold text-slate-800">Nachname<input className={inputClass} value={form.last_name ?? ""} onChange={(event) => field("last_name", event.target.value)} required /></label>
          </>
        )}
        <label className="text-sm font-semibold text-slate-800">E-Mail<input className={inputClass} type="email" value={form.email ?? ""} onChange={(event) => field("email", event.target.value)} /></label>
        <label className="text-sm font-semibold text-slate-800">Telefon<input className={inputClass} value={form.phone ?? ""} onChange={(event) => field("phone", event.target.value)} /></label>
        <label className="text-sm font-semibold text-slate-800">Website<input className={inputClass} type="url" value={form.website ?? ""} onChange={(event) => field("website", event.target.value)} /></label>
        <label className="text-sm font-semibold text-slate-800">USt-IdNr.<input className={inputClass} value={form.vat_id ?? ""} onChange={(event) => field("vat_id", event.target.value)} /></label>
        <label className="text-sm font-semibold text-slate-800">Leitweg-ID<input className={inputClass} value={form.leitweg_id ?? ""} onChange={(event) => field("leitweg_id", event.target.value)} /></label>
      </div>

      <section className="mt-8 border-t border-slate-200 pt-7">
        <div className="flex items-center justify-between"><div><h3 className="font-bold text-slate-950">Adressen</h3><p className="mt-1 text-sm text-slate-500">Rechnungs-, Liefer- oder weitere Anschriften</p></div><button type="button" className="rounded-lg bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700" onClick={() => setForm((current) => ({ ...current, addresses: [...current.addresses, { kind: "billing", label: "", street: "", postal_code: "", city: "", country_code: "DE", is_default: current.addresses.length === 0 }] }))}>+ Adresse</button></div>
        <div className="mt-4 space-y-4">
          {form.addresses.map((address, index) => (
            <div key={index} className="grid gap-3 rounded-2xl bg-slate-50 p-4 sm:grid-cols-7">
              <select className="rounded-xl border border-slate-300 px-3 py-2" value={address.kind ?? "billing"} onChange={(event) => updateAddress(index, { kind: event.target.value as ContactAddressInput["kind"] })}><option value="billing">Rechnung</option><option value="shipping">Lieferung</option><option value="other">Sonstige</option></select>
              <input className="rounded-xl border border-slate-300 px-3 py-2 sm:col-span-2" placeholder="Straße" value={address.street} onChange={(event) => updateAddress(index, { street: event.target.value })} required />
              <input className="rounded-xl border border-slate-300 px-3 py-2" placeholder="PLZ" value={address.postal_code} onChange={(event) => updateAddress(index, { postal_code: event.target.value })} required />
              <input className="rounded-xl border border-slate-300 px-3 py-2" placeholder="Ort" value={address.city} onChange={(event) => updateAddress(index, { city: event.target.value })} required />
              <input className="rounded-xl border border-slate-300 px-3 py-2" placeholder="Land" value={address.country_code} maxLength={2} onChange={(event) => updateAddress(index, { country_code: event.target.value.toUpperCase() })} required />
              <button type="button" className="text-sm font-semibold text-red-700" onClick={() => setForm((current) => ({ ...current, addresses: current.addresses.filter((_, itemIndex) => itemIndex !== index) }))}>Entfernen</button>
              <label className="flex items-center gap-2 text-sm text-slate-600 sm:col-span-2"><input type="checkbox" checked={address.is_default ?? false} onChange={(event) => updateAddress(index, { is_default: event.target.checked })} /> Standardadresse</label>
            </div>
          ))}
          {!form.addresses.length && <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">Noch keine Adresse hinterlegt.</p>}
        </div>
      </section>

      {form.kind === "organization" && <section className="mt-8 border-t border-slate-200 pt-7">
        <div className="flex items-center justify-between"><div><h3 className="font-bold text-slate-950">Ansprechpartner</h3><p className="mt-1 text-sm text-slate-500">Personen innerhalb dieser Firma</p></div><button type="button" className="rounded-lg bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700" onClick={() => setForm((current) => ({ ...current, contact_persons: [...current.contact_persons, { first_name: "", last_name: "", role: "", email: "", phone: "", is_primary: current.contact_persons.length === 0 }] }))}>+ Ansprechpartner</button></div>
        <div className="mt-4 space-y-4">
          {form.contact_persons.map((person, index) => (
            <div key={index} className="grid gap-3 rounded-2xl bg-slate-50 p-4 sm:grid-cols-7">
              <input className="rounded-xl border border-slate-300 px-3 py-2" placeholder="Vorname" value={person.first_name} onChange={(event) => updatePerson(index, { first_name: event.target.value })} required />
              <input className="rounded-xl border border-slate-300 px-3 py-2" placeholder="Nachname" value={person.last_name} onChange={(event) => updatePerson(index, { last_name: event.target.value })} required />
              <input className="rounded-xl border border-slate-300 px-3 py-2" placeholder="Rolle" value={person.role ?? ""} onChange={(event) => updatePerson(index, { role: event.target.value })} />
              <input className="rounded-xl border border-slate-300 px-3 py-2 sm:col-span-2" type="email" placeholder="E-Mail" value={person.email ?? ""} onChange={(event) => updatePerson(index, { email: event.target.value })} />
              <input className="rounded-xl border border-slate-300 px-3 py-2" placeholder="Telefon" value={person.phone ?? ""} onChange={(event) => updatePerson(index, { phone: event.target.value })} />
              <button type="button" className="text-sm font-semibold text-red-700" onClick={() => setForm((current) => ({ ...current, contact_persons: current.contact_persons.filter((_, itemIndex) => itemIndex !== index) }))}>Entfernen</button>
              <label className="flex items-center gap-2 text-sm text-slate-600 sm:col-span-2"><input type="checkbox" checked={person.is_primary ?? false} onChange={(event) => updatePerson(index, { is_primary: event.target.checked })} /> Primär</label>
            </div>
          ))}
          {!form.contact_persons.length && <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">Noch kein Ansprechpartner hinterlegt.</p>}
        </div>
      </section>}

      {error && <p className="mt-6 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
      <div className="mt-7 flex flex-wrap items-center justify-between gap-3">
        {contact && user.role === "admin" ? <button type="button" className="rounded-xl border border-red-200 px-4 py-3 text-sm font-semibold text-red-700 hover:bg-red-50" onClick={archive} disabled={busy}>Archivieren</button> : <span />}
        <div className="flex gap-3"><button type="button" className="rounded-xl border border-slate-300 px-4 py-3 font-semibold text-slate-700" onClick={onCancel}>Abbrechen</button><button className="rounded-xl bg-blue-700 px-5 py-3 font-semibold text-white hover:bg-blue-800 disabled:opacity-60" disabled={busy}>{busy ? "Wird gespeichert …" : "Speichern"}</button></div>
      </div>
    </form>
  );
}

export function ContactsPage({ user, onBack }: { user: User; onBack: () => void }) {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [count, setCount] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState<"organization" | "person" | "">("");
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [selected, setSelected] = useState<Contact | null | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    getContacts({ search, kind, page })
      .then((result) => { setContacts(result.results); setCount(result.count); setHasNext(Boolean(result.next)); setHasPrevious(Boolean(result.previous)); })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Kontakte konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }, [search, kind, page]);

  useEffect(() => { load(); }, [load]);

  if (selected !== undefined) {
    return <main className="mx-auto max-w-6xl px-6 py-10"><ContactForm contact={selected} user={user} onCancel={() => setSelected(undefined)} onSaved={() => { setSelected(undefined); load(); }} /></main>;
  }

  return (
    <main className="mx-auto max-w-7xl px-6 py-10">
      <button className="text-sm font-semibold text-blue-700 hover:text-blue-900" onClick={onBack}>← Zurück zum Dashboard</button>
      <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-sm font-bold uppercase tracking-[0.18em] text-blue-700">CRM</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Kontakte</h1><p className="mt-2 text-sm text-slate-600">{count} aktive Kontakte</p></div><button className="rounded-xl bg-blue-700 px-5 py-3 font-semibold text-white hover:bg-blue-800" onClick={() => setSelected(null)}>+ Kontakt anlegen</button></div>
      <form className="mt-7 grid gap-3 rounded-2xl bg-white p-4 shadow-sm sm:grid-cols-[1fr_180px_auto]" onSubmit={(event) => { event.preventDefault(); setPage(1); setSearch(searchInput.trim()); }}><input className="rounded-xl border border-slate-300 px-4 py-3" placeholder="Name, E-Mail oder Kundennummer" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} /><select className="rounded-xl border border-slate-300 px-4 py-3" value={kind} onChange={(event) => { setKind(event.target.value as typeof kind); setPage(1); }}><option value="">Alle Typen</option><option value="organization">Firmen</option><option value="person">Personen</option></select><button className="rounded-xl bg-slate-950 px-5 py-3 font-semibold text-white">Suchen</button></form>
      {error && <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
      <div className="mt-5 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        {loading ? <p className="p-6 text-sm text-slate-500">Kontakte werden geladen …</p> : contacts.length ? contacts.map((contact) => <button key={contact.id} className="grid w-full gap-2 border-b border-slate-100 p-5 text-left transition last:border-0 hover:bg-blue-50 sm:grid-cols-[130px_1fr_1fr_auto] sm:items-center" onClick={() => setSelected(contact)}><span className="font-mono text-sm font-semibold text-slate-500">{contact.customer_number}</span><span><strong className="block text-slate-950">{contact.display_name}</strong><small className="text-slate-500">{contact.kind === "organization" ? "Firma" : "Person"}</small></span><span className="text-sm text-slate-600">{contact.email || "Keine E-Mail"}</span><span className="text-sm font-semibold text-blue-700">Bearbeiten →</span></button>) : <p className="p-8 text-center text-sm text-slate-500">Keine Kontakte gefunden.</p>}
      </div>
      <div className="mt-5 flex items-center justify-between"><button className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold disabled:opacity-40" disabled={!hasPrevious} onClick={() => setPage((value) => value - 1)}>← Zurück</button><span className="text-sm text-slate-500">Seite {page}</span><button className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold disabled:opacity-40" disabled={!hasNext} onClick={() => setPage((value) => value + 1)}>Weiter →</button></div>
    </main>
  );
}
