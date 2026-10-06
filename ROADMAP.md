# basicERP — Fahrplan zur Umsetzung

**Stand:** 06.10.2026 · **Status:** Phase 0 abgeschlossen, Phase 1 zu etwa 80 % umgesetzt

> Der fortlaufend aktualisierte Fahrplan mit Umsetzungsstand und Testanleitung
> liegt in [`ROADMAP.html`](ROADMAP.html). Dieses Dokument bleibt die fachliche
> Ausgangsroadmap; Lieferreihenfolge und Architektur werden in
> [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) konkretisiert.

Quelloffenes Klein-ERP für Freelancer, Einzelunternehmer und kleine Unternehmen.
Self-Hosted per Docker, API-first, Zielmarkt Deutschland.

---

## 1. Grundsatzentscheidungen (festgelegt)

| Thema | Entscheidung |
|---|---|
| Backend | Django 5.x + Django REST Framework, PostgreSQL, Celery + Redis für Hintergrundjobs (PDF, E-Mail, Mahnläufe) |
| Frontend | React + TypeScript (Vite), TailwindCSS; SPA konsumiert ausschließlich die DRF-API |
| API-Doku | drf-spectacular → OpenAPI 3, Swagger-UI mitgeliefert |
| Tenancy | Single-Tenant: eine Docker-Installation = eine Firma |
| Compliance | Deutschland: XRechnung + ZUGFeRD, GoBD-Archivierung, deutsches Mahnrecht, §14/§19 UStG |
| Design-Tool | Block-Editor: vordefinierte Blöcke in feste Zonen (kein freies Canvas) |
| PDF-Erzeugung | WeasyPrint (HTML→PDF, serverseitig), pikepdf für PDF/A-3-Einbettung (ZUGFeRD) |
| Lizenz | Open Source — Vorschlag: AGPL-3.0 (schützt vor Closed-SaaS-Forks) oder MIT (maximal offen), vor Phase 1 festlegen |
| Sprache | UI Deutsch zuerst, i18n-Struktur (Django + react-i18next) von Anfang an, damit Englisch später nachrüstbar ist |

**Architekturprinzip API-first:** Jede Funktion existiert zuerst als API-Endpunkt, die eigene SPA ist "nur" der erste API-Konsument. Damit sind Anbindungen rein (Drittsysteme legen Kontakte, Zeiten, Belege an) und raus (Webhooks bei Ereignissen wie `invoice.paid`) kein Nachrüstthema, sondern Nebenprodukt.

---

## 2. Modul-Landkarte

```
basicERP
├── core          Auth, Benutzer, Rollen, Firmeneinstellungen, Nummernkreise
├── crm           Kontakte (Firmen/Personen), Adressen, Notizen, Aktivitäten
├── catalog       Artikel/Leistungen, Preise, Steuersätze, Einheiten
├── projects      Projekte, Arbeitspakete, Budgets, Controlling
├── timetracking  Zeiterfassung, Leistungserfassung, Abwesenheiten
├── hr            Personalstamm, Personalakte (Dokumente), Urlaubskonten
├── documents     Angebote, Rechnungen, Gutschriften; PDF + E-Rechnung
├── templates     Block-Editor-Vorlagen für Dokumente
├── dunning       Mahnwesen (Zahlungserinnerung, Mahnstufen, Verzugszinsen)
├── archive       GoBD-Archiv (unveränderbare Ablage, Aufbewahrungsfristen)
└── integrations  API-Keys, Webhooks, Import/Export (CSV, DATEV-Export später)
```

---

## 3. Phasenplan

Versionierung: jede Phase endet mit einem lauffähigen, per Docker startbaren Zwischenstand.

### Phase 0 — Fundament (v0.1)
**Ziel:** Leeres, aber produktionsartig laufendes Gerüst.

- Monorepo-Struktur: `backend/` (Django), `frontend/` (React), `docker/`
- Docker-Compose von Tag 1: `web` (gunicorn), `worker` (Celery), `db` (PostgreSQL), `redis`, `nginx` (serviert SPA-Build + proxied `/api`)
- Django-Projekt mit Custom-User-Modell (E-Mail-Login), Session- + Token-Auth (SPA: Session mit CSRF; API-Clients: Token/API-Key)
- Rollenmodell: Admin, Mitarbeiter (Portal), später erweiterbar
- DRF + drf-spectacular eingerichtet, `/api/docs/` liefert Swagger
- React-App mit Routing, Login, Layout-Grundgerüst (Sidebar/Topbar, responsive)
- CI (GitHub Actions): Lint (ruff, eslint), Tests (pytest, vitest), Docker-Build
- Firmeneinstellungen-Modell: Name, Anschrift, USt-IdNr./Steuernummer, Bankverbindung, Kleinunternehmer-Flag (§19 UStG), Logo-Upload

**Fertig wenn:** `docker compose up` → Login → leeres Dashboard, Swagger erreichbar.

### Phase 1 — CRM & Katalog (v0.2)
**Ziel:** Stammdaten, auf denen alles andere aufbaut.

- Kontakte: Firma oder Person, mehrere Adressen (Rechnungs-/Lieferadresse), Ansprechpartner, E-Mail/Telefon, Kundennummer (Nummernkreis)
- Notizen & Aktivitäten am Kontakt (Anruf, E-Mail, Termin — einfache Timeline)
- Katalog: Artikel/Leistungen mit Einheit (Std., Tag, Stück, pauschal), Netto-Preis, Steuersatz (19/7/0 %, §19-Hinweis)
- Listen mit Suche, Filter, Pagination — als wiederverwendbares SPA-Muster bauen (wird in jedem Modul gebraucht)
- CSV-Import für Kontakte (Erstbefüllung aus altem System)

**Fertig wenn:** Kunden und Leistungen vollständig über UI und API pflegbar.

### Phase 2 — Projekte & Arbeitspakete (v0.3)
**Ziel:** Projektstruktur als Rückgrat für Zeiten und spätere Abrechnung.

- Projekt: Kunde, Status (Angebot/aktiv/pausiert/abgeschlossen), Zeitraum, Budget (Betrag und/oder Stunden), Stundensatz-Logik (Projekt-Standard, pro Arbeitspaket überschreibbar)
- Arbeitspakete: Titel, Beschreibung, Status, geplanter Aufwand, Zuordnung Mitarbeiter
- Projektübersicht: Fortschritt, Budgetverbrauch (füllt sich ab Phase 3 mit echten Zeiten)
- Einfaches Board (Arbeitspakete nach Status) + Listenansicht

**Fertig wenn:** Projektstruktur steht; Controlling-Zahlen zeigen zunächst Plandaten.

### Phase 3 — Zeit- & Leistungserfassung + Mitarbeiterportal (v0.4)
**Ziel:** Der tägliche Erfassungs-Workflow — bewusst vor der Rechnungserstellung, damit "Zeiten → Rechnung" später durchgängig ist.

- Zeiteintrag: Datum, Dauer (oder Start/Stopp-Timer), Projekt, Arbeitspaket, Tätigkeitsbeschreibung, abrechenbar ja/nein
- Leistungserfassung: mengenbasierte Einträge aus dem Katalog (z. B. 3 × Beratungspauschale) zusätzlich zu Zeiten
- Mitarbeiterportal als eigener, reduzierter SPA-Bereich (eigene Route/Rolle): eigene Zeiten erfassen, Wochenansicht, Abwesenheiten beantragen — mobiltauglich zuerst
- Abwesenheiten: Urlaub, Krankheit, Sonstiges; Genehmigungs-Workflow (beantragt → genehmigt/abgelehnt), Urlaubskonto mit Jahresanspruch
- Projektcontrolling wird echt: Ist-Stunden vs. Budget, abrechenbar/nicht abrechenbar, noch nicht abgerechnete Zeiten pro Projekt
- Auswertungen: Zeiten pro Projekt/Mitarbeiter/Zeitraum, CSV-Export

**Fertig wenn:** Ein Mitarbeiter kann seinen Arbeitstag komplett im Portal erfassen; das Projekt zeigt live Budget vs. Ist.

### Phase 4 — Rechnungen & Angebote, Teil 1: Kernprozess (v0.5)
**Ziel:** Rechtskonforme Angebote und Rechnungen als PDF — das Herzstück.

- Dokumentmodell: Angebot, Rechnung, Gutschrift/Korrekturrechnung; Positionen (Katalog-Referenz oder Freitext, Menge, Einheit, Einzelpreis, Rabatt, Steuersatz)
- Pflichtangaben §14 UStG vollständig; Kleinunternehmer-Variante (§19-Hinweis, keine USt)
- Nummernkreise: fortlaufend, lückenlos, konfigurierbares Format (z. B. `RE-2026-0001`); Rechnung nach Festschreibung unveränderbar → Änderungen nur per Korrekturrechnung
- Statusfluss: Entwurf → festgeschrieben/versendet → bezahlt (Teilzahlungen) / storniert; Angebote: offen → angenommen/abgelehnt → in Rechnung überführen
- **Aus dem Projekt heraus:** nicht abgerechnete Zeiten/Leistungen auswählen → Rechnungsentwurf mit gruppierten Positionen (pro Arbeitspaket oder pro Tag); abgerechnete Einträge werden verknüpft und gesperrt
- PDF via WeasyPrint aus einer soliden Standard-HTML-Vorlage (der Block-Editor kommt in Phase 5 — hier zählt Korrektheit)
- Versand per E-Mail (SMTP-Einstellungen) mit PDF-Anhang, Versandprotokoll am Dokument
- Zahlungseingang manuell erfassen (Bankanbindung ist bewusst außerhalb des Scopes, siehe §7)

**Fertig wenn:** Kompletter Durchstich: Projektzeiten → Rechnung → PDF → E-Mail-Versand → als bezahlt markiert.

### Phase 5 — Vorlagen-Editor (Block-Editor) (v0.6)
**Ziel:** Laientaugliches Design-Tool für Angebots-/Rechnungsvorlagen.

- Vorlage = feste Zonenstruktur (Kopf, Absender/Empfänger, Metablock, Positionsbereich, Summenblock, Textblöcke vor/nach Positionen, Fußzeile) — Blöcke per Drag-and-Drop (dnd-kit) in Zonen anordnen
- Blocktypen: Logo (Position/Größe), Textblock mit Platzhaltern (`{{kunde.name}}`, `{{rechnung.nummer}}` …), Positionstabelle (Spalten wählbar), Summenblock, Zahlungsinfo/QR, Freitext, Trennlinie
- Gestaltung: Schriftart (kuratierte Auswahl), Farben, Ränder, Briefpapier-Hintergrund (PDF/Bild hinterlegen)
- Live-Vorschau mit Beispieldaten; Rendering-Pfad identisch mit dem echten PDF-Renderer (eine HTML/CSS-Quelle für Vorschau und WeasyPrint — sonst driftet die Vorschau vom PDF weg)
- Mehrere Vorlagen, Standard je Dokumenttyp; Textbausteine (Einleitung, Schlusstext, Zahlungsbedingungen) als wiederverwendbare Snippets

**Fertig wenn:** Ein Laie baut ohne Doku eine eigene Vorlage, und PDF = Vorschau.

### Phase 6 — E-Rechnung (v0.7)
**Ziel:** Gesetzeskonforme E-Rechnungsformate (B2B-Pflicht in DE).

- XRechnung: UBL- und CII-XML-Erzeugung aus dem Rechnungsmodell, Leitweg-ID am Kundenkontakt
- ZUGFeRD 2.x (Profil EN 16931): PDF/A-3 mit eingebettetem XML — Bibliothek: `drafthorse` (XML) + pikepdf (Einbettung); WeasyPrint-Ausgabe nach PDF/A konvertieren
- Validierung gegen offizielle Schematron/KoSIT-Validator im CI und optional beim Festschreiben
- E-Rechnungs-**Empfang** (Basisversion): XRechnung/ZUGFeRD-Datei hochladen → Daten extrahieren → als Eingangsbeleg im Archiv ablegen (kein volles Kreditoren-Modul, nur Erfassung + Archiv)
- Export je Rechnung: PDF, PDF+ZUGFeRD, XRechnung-XML — pro Kunde als Standard hinterlegbar

**Fertig wenn:** Erzeugte Rechnungen bestehen den KoSIT-Validator; Versand wahlweise als ZUGFeRD oder XRechnung.

### Phase 7 — Mahnwesen & GoBD-Archiv (v0.8)
**Ziel:** Offene-Posten-Verfolgung und revissionssichere Ablage.

- Offene-Posten-Liste: fällige Rechnungen mit Alter (0–30, 31–60, >60 Tage)
- Mahnstufen konfigurierbar: Zahlungserinnerung → 1. Mahnung → 2. Mahnung; je Stufe: Frist, Textvorlage, Mahngebühr, Verzugszinsen (§288 BGB: Basiszins + 5/9 Prozentpunkte, B2C/B2B)
- Mahnlauf: Vorschlagsliste (Celery-Job täglich) → manuelle Freigabe → PDF/E-Mail-Versand; Mahnhistorie am Kunden und an der Rechnung; Kunden vom Mahnlauf ausschließbar
- Archiv: jede festgeschriebene Ausgangsrechnung + hochgeladene Belege landen unveränderbar im Archiv (Original-Datei + SHA-256-Hash + Zeitstempel, Objektspeicher-Struktur im Docker-Volume)
- Aufbewahrungsfristen (8/10 Jahre) mit Löschsperre; Verfahrensdokumentations-Vorlage (Markdown) liegt dem Projekt bei
- Belegarchiv auch für sonstige Dokumente (Verträge, Eingangsrechnungen) mit Tags und Volltextsuche (PostgreSQL FTS)

**Fertig wenn:** Kein festgeschriebener Beleg ist lösch- oder änderbar; Mahnlauf läuft mit Freigabe-Schritt durch.

### Phase 8 — Personalstamm & Personalakte (v0.9)
**Ziel:** HR-Basis für kleine Teams.

- Personalstamm: Stammdaten, Eintritt/Austritt, Wochenarbeitszeit, Urlaubsanspruch, Stundensatz (intern/extern), Notfallkontakt
- Digitale Personalakte: Dokumentenablage je Mitarbeiter (Vertrag, Zeugnisse, Bescheinigungen) mit Kategorien — Zugriff strikt rollenbasiert (nur Admin/HR; technisch getrennt vom übrigen Dokumentenspeicher)
- Verknüpfung mit Phase 3: Urlaubskonto speist sich aus Anspruch + genehmigten Abwesenheiten; Arbeitszeitkonto (Soll/Ist) einfach gehalten
- Mitarbeiterportal-Ausbau: eigene Stammdaten einsehen, Lohnabrechnungen/Dokumente abrufen (sofern freigegeben), Resturlaub sehen
- DSGVO: Export der eigenen Daten, Löschkonzept nach Austritt + Fristen

**Fertig wenn:** Mitarbeiter vollständig verwaltbar, Akte sauber abgeschottet, Portal zeigt Urlaub + Dokumente.

### Phase 9 — Integrationen & Release 1.0
**Ziel:** Die "sehr guten Anbindungsmöglichkeiten" produktreif machen + Politur.

- API-Keys mit Scopes (z. B. nur `timetracking:write`), Rate-Limiting
- Webhooks: Ereignisse (`contact.created`, `invoice.finalized`, `invoice.paid`, `time_entry.created`, `dunning.sent` …) mit Signatur (HMAC), Retry-Logik, Zustell-Log
- OpenAPI-Spec versioniert (`/api/v1/`), Beispiel-Clients (Python/JS-Snippets in der Doku)
- Exporte: CSV überall, DATEV-kompatibler Buchungsstapel-Export (CSV-Format EXTF) für den Steuerberater
- Import-Endpunkte für gängige Szenarien: Zeiten aus Dritt-Trackern, Kontakte, Belege ins Archiv
- Härtung: Backup-/Restore-Anleitung (pg_dump + Volumes), Healthchecks, Sentry-Anbindung optional, Update-Pfad (Migrations beim Container-Start)
- Doku: Installations-Guide (Docker Compose, .env-Referenz, Reverse-Proxy/TLS), Admin-Handbuch, API-Doku
- Security-Review (OWASP-Basics, Berechtigungen modulweise durchtesten)

**Fertig wenn:** Ein Fremder installiert basicERP anhand der Doku in < 30 Minuten und bindet ein Drittsystem per API-Key + Webhook an.

---

## 4. Reihenfolge-Begründung (kurz)

1. **Zeiterfassung vor Rechnungen:** Der Kern-Workflow "Zeiten → Rechnung aus Projekt" braucht echte Zeitdaten; so wird Phase 4 direkt am echten Durchstich getestet.
2. **Standard-PDF vor Block-Editor:** Rechtliche Korrektheit (§14 UStG, Nummernkreise, Festschreibung) ist Pflicht, hübsche Vorlagen sind Kür. Der Editor baut dann auf dem fertigen Rendering-Pfad auf.
3. **E-Rechnung als eigene Phase:** XRechnung/ZUGFeRD + PDF/A-3 + Validierung ist ein eigenes, gut abgrenzbares Gewerk — nicht mit dem Kernprozess vermischen.
4. **HR spät:** Personalakte ist wichtig, blockiert aber nichts anderes; Abwesenheiten (früh gebraucht fürs Portal) sind deshalb schon in Phase 3.

## 5. Querschnittsthemen (gelten in jeder Phase)

- **API-first:** kein Feature ohne dokumentierten Endpunkt; SPA nutzt ausschließlich die öffentliche API
- **Tests:** pytest für Modelle/Services/API (Schwerpunkt: Nummernkreise, Steuerberechnung, Festschreibung, Mahnfristen — dort sind Fehler teuer), vitest/Playwright für kritische UI-Flows
- **Responsive:** Mitarbeiterportal mobile-first; Verwaltungs-UI mindestens tablet-tauglich
- **Migrationen:** immer vorwärtskompatibel, Container führt `migrate` beim Start aus
- **Audit-Log:** Wer hat wann was geändert — ab Phase 4 für alle Belege Pflicht

## 6. Risiken & Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|---|---|
| Block-Editor frisst das Projekt | Strikte Zonen-Architektur statt freiem Canvas; Editor erst nach stabilem PDF-Pfad (Phase 5 nach 4) |
| Vorschau ≠ PDF | Eine gemeinsame HTML/CSS-Quelle für Browser-Vorschau und WeasyPrint, Pixel-Vergleichstests |
| E-Rechnungs-Validierungsfehler | KoSIT-Validator im CI, Testkorpus echter Rechnungsfälle (Rabatte, §19, Gutschrift, mehrere Steuersätze) |
| GoBD "revisionssicher" wird überversprochen | Sauber dokumentieren, was basicERP leistet (Unveränderbarkeit, Protokollierung) und was Organisationspflicht des Nutzers bleibt (Verfahrensdoku) |
| Scope-Creep Richtung FiBu | Klare Grenze: basicERP macht Belege + OPOS + Export an den Steuerberater, keine doppelte Buchführung |

## 7. Bewusst NICHT im Scope von 1.0

- Bankanbindung/Kontoabgleich (FinTS/EBICS) → Kandidat 1.1, bis dahin manueller Zahlungsabgleich + CSV-Import
- Volle Kreditorenbuchhaltung / Eingangsrechnungs-Workflow mit Freigaben
- Lohnabrechnung (nur Ablage der Abrechnungen in der Akte)
- Lager/Warenwirtschaft, Bestellungen, Lieferscheine
- Multi-Tenant/SaaS-Betrieb, Mehrwährungsfähigkeit (EUR only)
- Peppol-Versand (Empfang/Erzeugung der Formate ja, Netzwerk-Versand später)

---

*Dieser Fahrplan wird nach jeder größeren Anpassung aktualisiert (Status je Phase pflegen).*
