import { FormEvent, useEffect, useState } from "react";
import {
  changePassword,
  currentUser,
  getCompanyProfile,
  signIn,
  signOut,
  updateCompanyProfile,
  type CompanyProfile,
  type User,
} from "./api";

function Brand() {
  return (
    <div className="flex items-center gap-3">
      <div className="grid size-11 place-items-center rounded-2xl bg-slate-950 text-lg font-black text-white shadow-lg shadow-slate-900/20">
        bE
      </div>
      <div>
        <p className="m-0 text-lg font-bold tracking-tight text-slate-950">basicERP</p>
        <p className="m-0 text-xs font-medium uppercase tracking-[0.2em] text-slate-500">Phase 0</p>
      </div>
    </div>
  );
}

function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [identifier, setIdentifier] = useState("admin");
  const [password, setPassword] = useState("admin");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onLogin(await signIn(identifier, password));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Anmeldung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[radial-gradient(circle_at_top_left,_#dbeafe,_transparent_35%),radial-gradient(circle_at_bottom_right,_#ccfbf1,_transparent_30%),#f8fafc] px-5 py-12">
      <section className="w-full max-w-md rounded-[2rem] border border-white/80 bg-white/90 p-8 shadow-2xl shadow-slate-900/10 backdrop-blur">
        <Brand />
        <div className="mt-10">
          <h1 className="text-3xl font-bold tracking-tight text-slate-950">Willkommen zurück</h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">Melde dich an, um basicERP einzurichten.</p>
        </div>
        <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
          <strong>Erstanmeldung:</strong> admin / admin. Das Passwort muss direkt danach geändert werden.
        </div>
        <form className="mt-6 space-y-5" onSubmit={submit}>
          <label className="block text-sm font-semibold text-slate-800">
            Benutzername oder E-Mail
            <input className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 outline-none transition focus:border-blue-600 focus:ring-4 focus:ring-blue-100" value={identifier} onChange={(event) => setIdentifier(event.target.value)} autoComplete="username" required />
          </label>
          <label className="block text-sm font-semibold text-slate-800">
            Passwort
            <input className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 outline-none transition focus:border-blue-600 focus:ring-4 focus:ring-blue-100" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required />
          </label>
          {error && <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
          <button className="w-full rounded-xl bg-slate-950 px-4 py-3 font-semibold text-white transition hover:bg-blue-700 disabled:cursor-wait disabled:opacity-60" disabled={busy}>
            {busy ? "Anmeldung läuft …" : "Anmelden"}
          </button>
        </form>
      </section>
    </main>
  );
}

function PasswordChange({ user, onChanged }: { user: User; onChanged: (user: User) => void }) {
  const [currentPassword, setCurrentPassword] = useState("admin");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      setError("Die neuen Passwörter stimmen nicht überein.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      onChanged(await changePassword(currentPassword, newPassword));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Passwortwechsel fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-slate-950 px-5 py-12">
      <section className="w-full max-w-lg rounded-[2rem] bg-white p-8 shadow-2xl">
        <Brand />
        <p className="mt-10 inline-flex rounded-full bg-amber-100 px-3 py-1 text-xs font-bold uppercase tracking-wider text-amber-900">Sicherheitsschritt erforderlich</p>
        <h1 className="mt-4 text-3xl font-bold tracking-tight text-slate-950">Hallo {user.username}, bitte ändere dein Passwort.</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">Das Installationspasswort ist öffentlich bekannt. Andere Bereiche bleiben bis zur Änderung gesperrt.</p>
        <form className="mt-8 space-y-5" onSubmit={submit}>
          <label className="block text-sm font-semibold text-slate-800">Aktuelles Passwort<input className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3" type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} autoComplete="current-password" required /></label>
          <label className="block text-sm font-semibold text-slate-800">Neues Passwort<input className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3" type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} autoComplete="new-password" minLength={8} required /></label>
          <label className="block text-sm font-semibold text-slate-800">Neues Passwort bestätigen<input className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3" type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} autoComplete="new-password" minLength={8} required /></label>
          {error && <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
          <button className="w-full rounded-xl bg-blue-700 px-4 py-3 font-semibold text-white hover:bg-blue-800 disabled:opacity-60" disabled={busy}>{busy ? "Wird gespeichert …" : "Passwort ändern"}</button>
        </form>
      </section>
    </main>
  );
}

const companyFields: Array<{
  key: Exclude<keyof CompanyProfile, "logo_url" | "updated_at">;
  label: string;
  type?: string;
  placeholder?: string;
}> = [
  { key: "name", label: "Kurzname", placeholder: "Musterbüro" },
  { key: "legal_name", label: "Rechtlicher Name", placeholder: "Musterbüro GmbH" },
  { key: "street", label: "Straße und Hausnummer", placeholder: "Musterstraße 1" },
  { key: "postal_code", label: "Postleitzahl", placeholder: "10115" },
  { key: "city", label: "Ort", placeholder: "Berlin" },
  { key: "country_code", label: "Ländercode", placeholder: "DE" },
  { key: "vat_id", label: "USt-IdNr.", placeholder: "DE123456789" },
  { key: "tax_number", label: "Steuernummer", placeholder: "12/345/67890" },
  { key: "email", label: "E-Mail", type: "email", placeholder: "kontakt@example.de" },
  { key: "phone", label: "Telefon", type: "tel", placeholder: "+49 30 123456" },
  { key: "website", label: "Website", type: "url", placeholder: "https://example.de" },
];

function CompanySettings({ user, onBack }: { user: User; onBack: () => void }) {
  const [company, setCompany] = useState<CompanyProfile | null>(null);
  const [logo, setLogo] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const canEdit = user.role === "admin";

  useEffect(() => {
    getCompanyProfile()
      .then(setCompany)
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Firmenprofil konnte nicht geladen werden."));
  }, []);

  function updateField(key: Exclude<keyof CompanyProfile, "logo_url" | "updated_at">, value: string) {
    setCompany((current) => (current ? { ...current, [key]: value } : current));
    setSaved(false);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!company || !canEdit) return;
    if (logo && logo.size > 2 * 1024 * 1024) {
      setError("Das Logo darf höchstens 2 MB groß sein.");
      return;
    }

    const data = new FormData();
    for (const field of companyFields) data.append(field.key, company[field.key]);
    if (logo) data.append("logo", logo);

    setBusy(true);
    setError("");
    setSaved(false);
    try {
      setCompany(await updateCompanyProfile(data));
      setLogo(null);
      setSaved(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Firmenprofil konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <button className="text-sm font-semibold text-blue-700 hover:text-blue-900" onClick={onBack}>← Zurück zum Dashboard</button>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-bold uppercase tracking-[0.18em] text-blue-700">Stammdaten</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Firmeneinstellungen</h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">Diese Angaben bilden später die Grundlage für Angebote und Rechnungen.</p>
        </div>
        <span className="w-fit rounded-full bg-slate-200 px-3 py-1 text-xs font-bold text-slate-700">
          {canEdit ? "Administrator · Bearbeitung erlaubt" : "Mitarbeiter · Nur Lesen"}
        </span>
      </div>

      {!company && !error && <p className="mt-8 rounded-2xl bg-white p-6 text-sm text-slate-600 shadow-sm">Firmenprofil wird geladen …</p>}
      {company && (
        <form className="mt-8 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm sm:p-8" onSubmit={submit}>
          <div className="grid gap-5 sm:grid-cols-2">
            {companyFields.map((field) => (
              <label className={field.key === "street" || field.key === "legal_name" ? "sm:col-span-2 text-sm font-semibold text-slate-800" : "text-sm font-semibold text-slate-800"} key={field.key}>
                {field.label}
                <input
                  className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 font-normal outline-none transition focus:border-blue-600 focus:ring-4 focus:ring-blue-100 disabled:bg-slate-100 disabled:text-slate-600"
                  type={field.type ?? "text"}
                  placeholder={field.placeholder}
                  value={company[field.key]}
                  onChange={(event) => updateField(field.key, event.target.value)}
                  disabled={!canEdit}
                  maxLength={field.key === "country_code" ? 2 : undefined}
                />
              </label>
            ))}
          </div>

          <div className="mt-8 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5">
            <p className="text-sm font-semibold text-slate-900">Firmenlogo</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">PNG, JPEG oder WebP, maximal 2 MB. SVG wird aus Sicherheitsgründen nicht angenommen.</p>
            {company.logo_url && <img className="mt-4 max-h-24 max-w-64 rounded-lg bg-white object-contain p-2 shadow-sm" src={company.logo_url} alt="Aktuelles Firmenlogo" />}
            {canEdit && <input className="mt-4 block w-full text-sm text-slate-700 file:mr-4 file:rounded-lg file:border-0 file:bg-blue-100 file:px-4 file:py-2 file:font-semibold file:text-blue-800" type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => { setLogo(event.target.files?.[0] ?? null); setSaved(false); }} />}
          </div>

          {error && <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
          {saved && <p className="mt-5 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800">Firmeneinstellungen wurden gespeichert.</p>}
          {canEdit && (
            <div className="mt-6 flex justify-end">
              <button className="rounded-xl bg-blue-700 px-5 py-3 font-semibold text-white hover:bg-blue-800 disabled:opacity-60" disabled={busy}>
                {busy ? "Wird gespeichert …" : "Einstellungen speichern"}
              </button>
            </div>
          )}
        </form>
      )}
    </main>
  );
}

function Dashboard({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [view, setView] = useState<"dashboard" | "company">("dashboard");

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <Brand />
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-slate-500 sm:inline">{user.role === "admin" ? "Administrator" : "Mitarbeiter"}</span>
            <button className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50" onClick={onLogout}>Abmelden</button>
          </div>
        </div>
      </header>
      {view === "company" ? <CompanySettings user={user} onBack={() => setView("dashboard")} /> : (
      <main className="mx-auto max-w-7xl px-6 py-10">
        <div className="rounded-[2rem] bg-slate-950 p-8 text-white shadow-xl">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-cyan-300">Fundament aktiv</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight">Hallo {user.username}.</h1>
          <p className="mt-4 max-w-2xl leading-7 text-slate-300">basicERP läuft. Login, Passwortwechsel, API-Dokumentation, PostgreSQL, Redis und Worker bilden den ersten Phase-0-Durchstich.</p>
        </div>
        <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-4">
          <button onClick={() => setView("company")} className="rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm transition hover:-translate-y-1 hover:shadow-lg">
            <p className="text-sm font-bold uppercase tracking-wider text-blue-700">Firma</p>
            <p className="mt-3 font-semibold text-slate-900">Firmeneinstellungen {user.role === "admin" ? "bearbeiten" : "ansehen"}</p>
          </button>
          {[["API", "/api/docs/", "OpenAPI-Dokumentation öffnen"], ["System", "/api/v1/health/ready/", "Readiness prüfen"], ["Fahrplan", "/roadmap/", "Projektstand ansehen"]].map(([title, href, text]) => (
            <a key={title} href={href} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-lg"><p className="text-sm font-bold uppercase tracking-wider text-blue-700">{title}</p><p className="mt-3 font-semibold text-slate-900">{text}</p></a>
          ))}
        </div>
      </main>
      )}
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    currentUser().then(setUser).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <main className="grid min-h-screen place-items-center bg-slate-950 text-sm font-semibold text-white">basicERP wird geladen …</main>;
  }
  if (!user) {
    return <Login onLogin={setUser} />;
  }
  if (user.must_change_password) {
    return <PasswordChange user={user} onChanged={setUser} />;
  }
  return <Dashboard user={user} onLogout={async () => { await signOut(); setUser(null); }} />;
}
