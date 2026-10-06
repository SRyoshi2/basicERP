# basicERP

Quelloffenes, API-first Klein-ERP für Freelancer, Einzelunternehmen und kleine
Unternehmen in Deutschland. Das Projekt befindet sich in **Phase 0**.

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

Die aktuelle Planung steht in [`ROADMAP.html`](ROADMAP.html), der ausführliche
Projektplan in [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) und die technische
Architektur in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Lizenz

basicERP wird unter **AGPL-3.0-or-later** entwickelt. Der vollständige
Lizenztext liegt in [`LICENSE`](LICENSE).
