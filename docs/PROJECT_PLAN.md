# basicERP – Projektplan

**Stand:** 05.10.2026
**Status:** Freigegeben; Phase 0 zu etwa 95 % umgesetzt
**Quelle:** [`ROADMAP.md`](../ROADMAP.md)

## 1. Zielbild

basicERP wird als quelloffenes, selbst gehostetes Klein-ERP für Freelancer,
Einzelunternehmen und kleine Unternehmen in Deutschland entwickelt. Der erste
vollständige Wertstrom lautet:

> Kunde und Leistung anlegen → Projekt und Zeiten erfassen → Rechnung
> festschreiben → rechtskonformes Artefakt erzeugen → versenden → Zahlung und
> gegebenenfalls Mahnung nachverfolgen → Beleg unveränderbar aufbewahren.

Das Produkt bleibt bis Version 1.0 bewusst ein Single-Tenant-System. Es enthält
keine Finanzbuchhaltung, Lohnabrechnung, Warenwirtschaft oder Bankanbindung.

## 2. Planungsannahmen

Die Aufwandsschätzungen sind Größenordnungen, keine Terminversprechen.

| Annahme | Planungswert |
|---|---|
| Team | Ein Projektinhaber; Codex setzt die Schritte um |
| Vorgehen | Zweiwöchige Iterationen, vertikale Produktinkremente |
| Zielbetrieb | Eine Firma je Docker-Compose-Installation; Windows mit Docker Desktop/Linux-Containern und Ubuntu mit Docker Engine |
| Initiale Last | Bis etwa 100 Benutzer, 25 gleichzeitig aktive Benutzer, 1 Mio. Zeiteinträge, 100.000 Belege |
| Verfügbarkeit | Solider Geschäftsbetrieb; kein hochverfügbarer 24/7-Cluster in 1.0 |
| Aufwand | In Personenwochen inklusive Implementierung, Tests und technischer Dokumentation |
| Fachprüfung | Steuer-/Rechtsanforderungen werden vor einem öffentlichen Release extern geprüft |

Ändern sich Team, Zieltermin oder Lastprofil deutlich, wird dieser Plan neu
baselined.

## 3. Priorisierte Lieferstrategie

Die Phasen der Roadmap bleiben erhalten, mit einer compliancebedingten
Anpassung: Der E-Rechnungsempfang wird als kleiner Baustein vorgezogen und die
Erzeugung strukturierter E-Rechnungen folgt direkt auf den Rechnungskern – vor
dem Vorlagen-Editor.

Grund: Inländische Unternehmen müssen E-Rechnungen bereits seit dem 01.01.2025
empfangen können. Für die Ausstellung laufen Übergangsregelungen grundsätzlich
bis Ende 2026 und für Aussteller mit höchstens 800.000 EUR Vorjahresumsatz bis
Ende 2027. Ein 2026 begonnenes ERP sollte diesen Kern nicht bis hinter einen
Design-Editor verschieben.

## 4. Release- und Phasenplan

| Release | Ergebnis | Hauptumfang | Abhängigkeiten | Schätzung | Abnahmekriterium |
|---|---|---|---|---:|---|
| v0.1 – Fundament | Produktionsnahes leeres System | Monorepo, Compose, Django/DRF, React, Auth, Firmenprofil, CI, Observability-Basis | Entscheidungen D1–D3 | 3–5 PW | Login, leeres Dashboard und OpenAPI laufen nach einem dokumentierten Startbefehl |
| v0.2 – CRM & Katalog | Belastbare Stammdaten | Kontakte, Adressen, Aktivitäten, Katalog, Listenmuster, CSV-Import | v0.1 | 4–6 PW | Stammdaten sind vollständig über UI und API pflegbar; Import ist wiederholbar und protokolliert |
| v0.2.1 – E-Rechnungseingang light | Empfangene E-Rechnung sicher übernehmen | Upload von XML/ZUGFeRD, Formatprüfung, Original unverändert speichern, Metadaten extrahieren, Download | Archiv-Skelett aus v0.1/v0.2 | 2–3 PW | Original und Prüfergebnis sind reproduzierbar; fehlerhafte Dateien werden verständlich abgewiesen |
| v0.3 – Projekte | Projektstruktur steht | Projekte, Arbeitspakete, Budgets, Sätze, Board und Plancontrolling | v0.2 | 3–5 PW | Projekt und Arbeitspakete sind in API, Liste und Board konsistent nutzbar |
| v0.4 – Zeit & Portal | Täglicher Arbeitsfluss | Zeit/Leistung, Timer, minimales HR-/Abwesenheitsskelett, Genehmigung, Ist-Controlling, Exporte | v0.3 | 6–9 PW | Mitarbeiter kann einen Arbeitstag mobil erfassen; Budget und offene Leistungen stimmen |
| v0.5 – Dokumentkern | Vollständiger Rechnungsdurchstich | Angebote, Rechnung/Korrektur, Nummernkreise, Steuern, Festschreibung, Standard-PDF, E-Mail, Zahlungen | v0.4 | 8–12 PW | Projektzeiten → festgeschriebene Rechnung → PDF → E-Mail → Zahlung funktioniert mit Audit-Trail |
| v0.6 – E-Rechnungsausgang | Maschinenlesbare, validierte Rechnung | XRechnung UBL/CII, ZUGFeRD EN 16931, PDF/A-3, KoSIT-Validierung, Kundenpräferenz | v0.5 | 6–9 PW | Testkorpus besteht den offiziellen Validator; PDF/XML stammen aus demselben Snapshot |
| v0.7 – Vorlagen-Editor | Anpassbare, kontrollierte Gestaltung | Zonen/Blöcke, Platzhalter, Snippets, gemeinsame Renderquelle, Vorschau-Tests | v0.5; kompatibel mit v0.6 | 7–10 PW | Fachanwender baut ohne Code eine Vorlage; Vorschau und PDF bestehen Vergleichstests |
| v0.8 – Mahnen & Archiv | OPOS und nachvollziehbare Aufbewahrung | Fälligkeiten, Mahnlauf mit Freigabe, Gebühren/Zinsen, unveränderbare Ablage, Suche, Verfahrensdoku | v0.5/v0.6 | 6–9 PW | Kein festgeschriebenes Artefakt ist per Anwendung änder-/löschbar; Restore und Mahnlauf sind getestet |
| v0.9 – HR | Abgeschottete Personalbasis | Personalstamm, Akte, Konten, Portal, DSGVO-Export-/Löschkonzept | v0.4, Rollenmodell | 5–8 PW | Rollenmatrix und Isolationstests verhindern fachfremden Zugriff auf Personalakten |
| v1.0 – Integrationen & Härtung | Installierbares, integrierbares Release | API-Keys/Scopes, Webhooks, DATEV-Export, Backup/Restore, Security-Review, Handbücher | alle vorherigen | 5–8 PW | Neuinstallation <30 Minuten; API- und Webhook-Durchstich sowie Restore erfolgreich |

**Gesamtgröße:** etwa 55–84 Personenwochen, zuzüglich 15–20 % Reserve für
Fachkorrekturen, Abhängigkeiten und Release-Härtung. Der Wert ist erst nach v0.2
neu zu schätzen; dann liegen reale Durchsatzdaten vor.

### Mögliche Kalenderbilder

| Effektive Kapazität | Grobe Dauer bis 1.0 |
|---|---|
| 1 Vollzeitentwickler | etwa 16–24 Monate |
| 2 Vollzeitentwickler | etwa 9–14 Monate |
| 3 Vollzeitentwickler | etwa 7–11 Monate |

Die Dauer sinkt nicht linear: Rechnungsrecht, E-Rechnung, Security und
Abnahmetests benötigen gemeinsame Entscheidungen und teilweise externe Prüfung.

## 5. Nächste sechs Iterationen

### Iteration 0 – Entscheidungen und Arbeitsgrundlage (abgeschlossen)

- Lizenz AGPL-3.0-or-later sowie Windows-/Ubuntu-Support bestätigt.
- Git-Repository initialisiert; Branch-/Review-Regeln folgen mit dem Remote.
- Architekturentscheidungen als ADRs bestätigt.
- Priorisierte User Journeys und Domänenglossar anlegen.
- Für v0.1 Epics, Akzeptanzkriterien und Teststrategie schneiden.

### Iteration 1 – Laufender Stack

- Verzeichnisstruktur `backend/`, `frontend/`, `docker/`, `docs/`.
- Docker Compose mit PostgreSQL, Redis, Web, Worker und Nginx.
- Django 5.2 LTS auf aktuellem Patchstand und React/TypeScript-Grundgerüst.
- Healthchecks, strukturierte Logs und lokale Entwicklerbefehle.
- CI: Lint, Unit-Tests, Build und Migrationscheck.

### Iteration 2 – Identität und Firmenkontext

- Custom User vor der ersten Migration, E-Mail-Login, Session/CSRF.
- Rollenbasis und zentrale Berechtigungstests.
- Firmeneinstellungen inklusive sicherer Dateiuploads.
- OpenAPI und ein einheitliches API-Fehlerformat.
- Login, App-Shell und leeres Dashboard.

### Iteration 3 – CRM-Vertikalschnitt

- Kontakt, Firma/Person, Adressen und Ansprechpartner.
- API, Formulare, Suche, Filter und Pagination als wiederverwendbares Muster.
- Änderungsprotokoll und Berechtigungstests.

### Iteration 4 – Katalog und Import

- Artikel/Leistung, Einheit, Preis und Steuersatz mit Gültigkeit.
- Robuster CSV-Import: Vorschau, Validierung, idempotente Übernahme, Fehlerbericht.
- CRM-Aktivitäten und Notizen abrunden.

### Iteration 5 – Compliance-Slice und v0.2-Abnahme

- Unveränderliches Dateiobjekt mit SHA-256 und Storage-Abstraktion.
- E-Rechnungsupload inklusive Basisvalidierung und Metadatenextraktion.
- Installations-, Backup- und Restore-Smoke-Test.
- Retrospektive und Neuschätzung der Folgephasen.

## 6. Arbeitsweise und Qualitätsregeln

### Definition of Ready

Ein Backlog-Eintrag startet erst, wenn Nutzerziel, Akzeptanzkriterien,
Berechtigungen, Daten-/Migrationsfolgen und Testidee verständlich sind. Bei
Compliance-Funktionen ist außerdem die fachliche Quelle benannt.

### Definition of Done

- API und UI liefern denselben fachlichen Umfang; keine direkte SPA-Sonderlogik.
- Domain-, API- und relevante UI-Tests sind grün.
- Migrationen sind vorwärtskompatibel und auf realistischen Daten getestet.
- Berechtigungen haben positive und negative Tests.
- OpenAPI, Nutzertext und Betriebsdokumentation sind aktualisiert.
- Logs enthalten keine Geheimnisse oder unnötigen personenbezogenen Daten.
- Das Inkrement ist per Docker Compose startbar und zurücksicherbar.

### Release-Gates

1. **v0.1:** reproduzierbarer Build, Secret-/Dependency-Scan, Restore-Smoke-Test.
2. **v0.4:** mobiler Portal-E2E-Test und belastbare Zeit-/Budgetberechnung.
3. **v0.5:** Steuerfall-Testmatrix und fachliche Prüfung der Pflichtangaben.
4. **v0.6:** offizieller Validator im CI; keine Freigabe bei Validierungsfehlern.
5. **v0.8:** dokumentierter Restore, Integritätsprüfung und Verfahrensdoku.
6. **v1.0:** Security-Review, Upgrade-Test von letzter Vorversion, Neuinstallation durch Dritten.

## 7. Kritischer Pfad

```text
Fundament
  → CRM/Katalog
    → Projekte
      → Zeiten/Leistungen
        → Rechnungs-Snapshot + Festschreibung
          → E-Rechnungsausgang
            → Mahnwesen/Archiv
              → Integrationen + Release-Härtung
```

Vorlagen-Editor und HR können nach Stabilisierung ihrer Grundlagen teilweise
parallel laufen. Rechnungsberechnung, Festschreibung und E-Rechnung bleiben auf
dem kritischen Pfad und dürfen nicht zugunsten von UI-Politur verkürzt werden.

## 8. Hauptrisiken und Steuerung

| Risiko | Frühindikator | Maßnahme |
|---|---|---|
| Steuer-/E-Rechnungsfälle sind komplexer als geplant | Viele Sonderfälle ändern das Rechnungsmodell | Testkorpus vor Implementierung; Fachreview vor Schema-Freeze |
| Vorlagen-Editor wächst zum freien DTP-System | Wünsche nach beliebigen Positionen/Skripten | Versioniertes Zonen-/Blockschema, Whitelist, klare Nicht-Ziele |
| „Revisionssicher“ wird zu stark versprochen | Nur Hash und Datenbanksperre vorhanden | Fähigkeiten präzise dokumentieren; optional WORM-Speicher; Betriebs- und Verfahrenspflichten benennen |
| Modulgrenzen erodieren | Zirkuläre Imports, direkte Fremdmodell-Updates | Architekturtests; Schreibzugriffe nur über Anwendungsservices des Eigentümermoduls |
| Celery-Aufträge gehen verloren/doppelt | Versandstatus passt nicht zum Ereignis | Transactional Outbox, idempotente Handler, Retry/Dead-Letter-Sicht |
| Solo-/Kleinteam wird durch Breite überlastet | Viele halbfertige Module | Ein Wertstrom nach dem anderen; WIP-Limit; keine 1.0-Nichtziele vorziehen |

## 9. Entscheidungen und offene Punkte

| ID | Entscheidung | Ergebnis/Empfehlung | Status |
|---|---|---|---|
| D1 | Lizenz | **AGPL-3.0-or-later** | Entschieden 05.10.2026 |
| D2 | Team und Zieltermin | Ein Projektinhaber, Umsetzung durch Codex, kein Fixtermin; nach jeder Phase neu planen | Entschieden 05.10.2026 |
| D3 | Unterstützter Docker-Betrieb | Windows/Docker Desktop mit Linux-Containern und Ubuntu/Docker Engine; kein Kubernetes-Versprechen | Entschieden 05.10.2026 |
| D4 | Dateispeicher | Lokales Volume als Default, Storage-Schnittstelle von Anfang an, S3-kompatibler/WORM-Speicher später | Offen bis v0.1 Datenmodell |
| D5 | Öffentlicher Beta-Umfang | Beta erst ab v0.6, damit Rechnungs- und E-Rechnungskern zusammen getestet werden | Offen bis v0.5 |
| D6 | Fachliche Freigabe | Steuerberater/Rechnungsfachperson für Pflichtangaben, Rundung, Korrektur und DATEV einplanen | Offen bis v0.5 |

## 10. Verbindliche Planpflege

- Nach jedem Release: Ist-Aufwand, Abweichungen, Risiken und Folgeschätzung aktualisieren.
- Architekturänderungen mit langfristiger Wirkung erhalten ein ADR unter `docs/adr/`.
- Die Roadmap beschreibt das **Was und Wann**; `ARCHITECTURE.md` beschreibt das
  **Wie und Warum**; Tickets enthalten nur die jeweils ausführbaren Schritte.

## 11. Fachliche Quellen für die Priorisierung

- BMF, FAQ zur E-Rechnung: https://www.bundesfinanzministerium.de/Content/DE/FAQ/e-rechnung.html
- § 147 AO: https://www.gesetze-im-internet.de/ao_1977/__147.html
- § 14b UStG: https://www.gesetze-im-internet.de/ustg_1980/__14b.html
- GoBD, amtliches AO-Handbuch 2026: https://amtliche-handbuecher.bundesfinanzministerium.de/ao/2026/Anhaenge/BMF-Schreiben-und-gleichlautende-Laendererlasse/Anhang-33/inhalt.html
- Django 5.2 LTS Release Notes: https://docs.djangoproject.com/en/5.2/releases/5.2/

Die Quellen ersetzen keine individuelle Rechts- oder Steuerberatung.
