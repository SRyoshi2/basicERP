# basicERP

Quelloffenes, API-first Klein-ERP für Freelancer, Einzelunternehmen und kleine
Unternehmen in Deutschland. **v0.2 / Phase 1** ist abgeschlossen; der
funktionale Kern von **v0.2.1 / Phase 1a** liefert zusätzlich einen sicheren
E-Rechnungseingang.

Repository: https://github.com/SRyoshi2/basicERP

## Schnellstart unter Windows

Voraussetzung: Docker Desktop ist installiert, gestartet und verwendet
Linux-Container.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1
```

Das Skript fragt Domain, lokalen Port, Docker-Projektnamen und einen optionalen
externen HTTPS-Reverse-Proxy ab. Es erzeugt `.env` mit zufälligen Secrets,
baut die Images, migriert die Datenbank und legt den initialen Benutzer an:

```text
Benutzer: admin
Passwort: admin
```

Die Anwendung erzwingt direkt nach der ersten Anmeldung einen Passwortwechsel.
Anschließend können Administratoren über **Firma → Firmeneinstellungen** die
Unternehmensdaten und ein PNG-, JPEG- oder WebP-Logo hinterlegen. Mitarbeiter
können diese Stammdaten lesen, aber nicht verändern.

Unter **CRM → Kontakte** lassen sich Firmen und Personen mit Kundennummer,
Adressen und Ansprechpartnern anlegen, suchen und bearbeiten. Archivieren ist
Administratoren vorbehalten; konkurrierende Bearbeitungen werden erkannt.
Über **CSV importieren** können UTF-8-Dateien zunächst zeilenweise geprüft und
anschließend idempotent übernommen werden; fehlerhafte Zeilen bleiben sichtbar,
ohne teilweise Kontakte anzulegen.
Eine passende Beispieldatei liegt unter `docs/examples/contacts-import.csv`.
In der Bearbeitungsansicht eines Kontakts können außerdem Notizen, Anrufe,
E-Mails und Termine in einer gemeinsamen Timeline dokumentiert werden.

Unter **Katalog → Artikel & Leistungen** lassen sich Artikel und Leistungen mit
Einheit, Steuersatz und zeitlich gültigen Nettopreisen verwalten. Überlappende
Preiszeiträume werden abgewiesen; Archivieren ist Administratoren vorbehalten.

Unter **Rechnungseingang** können normale PDF-Rechnungen mit Rechnungsnummer,
Datum, Verkäufer, Käufer, Betrag und Währung manuell erfasst werden. Zusätzlich
lassen sich XRechnung-XMLs in UBL/CII sowie ZUGFeRD-PDFs mit eingebetteter
Rechnungs-XML automatisch auslesen. Das Original landet unverändert und
SHA-256-dedupliziert im separaten Archiv-Volume. Der Umfang ist keine
vollständige KoSIT-/Schematron- oder Rechtsprüfung. Für einen Selbsttest steht
`docs/examples/incoming-invoice-ubl.xml` bereit.

## Schnellstart unter Ubuntu

Voraussetzung: Docker Engine, das Docker-Compose-Plugin, OpenSSL und curl sind
installiert; der aktuelle Benutzer darf Docker verwenden.

```bash
chmod +x ./scripts/install-ubuntu.sh
./scripts/install-ubuntu.sh
```

## Selbsttest

Nach der Installation bei Standardwerten:

- Anwendung: http://localhost:8080/
- Fahrplan und ausführliche Testhilfe: http://localhost:8080/roadmap/
- Readiness: http://localhost:8080/api/v1/health/ready/
- API-Dokumentation: http://localhost:8080/api/docs/

```powershell
docker compose ps
docker compose logs --tail 100
```

Der versionierte API-Vertrag liegt in `docs/openapi.yaml`. Mit installiertem
Node.js prüft folgender Befehl, ob OpenAPI-Dokument und generierte
Frontend-Typen synchron sind:

```powershell
cd frontend
npm run api:check
```

Die aktuelle Planung steht in [`ROADMAP.html`](ROADMAP.html), der ausführliche
Projektplan in [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) und die technische
Architektur in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Lizenz

basicERP wird unter **AGPL-3.0-or-later** entwickelt. Der vollständige
Lizenztext liegt in [`LICENSE`](LICENSE).
