# basicERP – Backup und Wiederherstellung

**Stand:** 21.10.2026

Ein Backup besteht aus einem PostgreSQL-Custom-Dump, dem Archiv-Volume, dem
Medien-Volume, einem Manifest und SHA-256-Prüfsummen. Die Redis-Warteschlange
ist kurzlebig und wird nicht gesichert. Die `.env` enthält Geheimnisse und muss
getrennt an einem geschützten Ort verwahrt werden.

Während einer Sicherung stoppen die Skripte `web`, `worker` und `nginx` kurz,
damit Datenbank und Dateien einen konsistenten Stand bilden. Anschließend werden
genau die zuvor laufenden Dienste wieder gestartet.

## Windows

```powershell
# Backup mit automatisch erzeugtem Ziel unter backups/
powershell -ExecutionPolicy Bypass -File .\scripts\backup-windows.ps1

# Optionales explizites Ziel
powershell -ExecutionPolicy Bypass -File .\scripts\backup-windows.ps1 `
  -OutputDirectory D:\basicERP-Backups\2026-10-21

# Restore; verlangt die Eingabe RESTORE und erzeugt vorher ein Sicherheitsbackup
powershell -ExecutionPolicy Bypass -File .\scripts\restore-windows.ps1 `
  -BackupDirectory D:\basicERP-Backups\2026-10-21
```

## Ubuntu

```bash
chmod +x scripts/backup-ubuntu.sh scripts/restore-ubuntu.sh
./scripts/backup-ubuntu.sh

# Restore; verlangt die Eingabe RESTORE und erzeugt vorher ein Sicherheitsbackup
./scripts/restore-ubuntu.sh --backup /srv/backups/basicerp-20261021-120000
```

## Sicherheitsregeln

- Ein Restore überschreibt die Zieldatenbank sowie Archiv- und Medien-Volume.
- Ohne `-ConfirmRestore` beziehungsweise `--confirm-restore` ist die exakte
  Eingabe `RESTORE` erforderlich.
- Vor einem normalen Restore wird automatisch ein Backup unter
  `backups/pre-restore-*` erstellt.
- `-SkipSafetyBackup` beziehungsweise `--skip-safety-backup` ist ausschließlich
  für ein isoliertes Testprojekt vorgesehen.
- Vor dem Import werden alle drei SHA-256-Prüfsummen geprüft.
- Nach dem Import laufen Migrationen und der Django-Systemcheck.
- Backups sind nicht verschlüsselt. Das Zielmedium muss durch
  Betriebssystemrechte und, falls erforderlich, Datenträgerverschlüsselung
  geschützt werden.

## Regelmäßiger Restore-Test

Mindestens quartalsweise sollte ein Backup in ein separates Compose-Projekt
wiederhergestellt werden. Der Test darf nie denselben Projektnamen wie die
Produktivinstallation verwenden. Danach sind mindestens zu vergleichen:

- Anzahlen zentraler Fachobjekte,
- SHA-256-Listen von Archiv und Medien,
- Migrationen und Django-Systemcheck,
- Anmeldung und ein kritischer Lesezugriff.

Das Testprojekt wird erst nach erfolgreichem Vergleich mit `docker compose
--project-name <testname> down -v` entfernt.

## Release-Abnahme v0.2.1

**Datum:** 21.10.2026 · **Durchführung:** Codex

- [x] 36 Backend-Tests, Frontend-Lint und Produktionsbuild erfolgreich
- [x] Dependency-Audit ohne bekannte Schwachstellen
- [x] Datenbankmigrationen auf PostgreSQL ausgeführt
- [x] Backup mit Prüfsummen und Manifest erzeugt
- [x] Restore in eigenem Compose-Projekt und eigenen Volumes ausgeführt
- [x] Objektzahlen von Quelle und Restore identisch
- [x] Datei-Hashes von Archiv und Medien identisch
- [x] Migrationen und Systemcheck im Restore erfolgreich
- [x] Produktivnahe lokale Installation nach dem Test wieder healthy
- [x] Rückfallweg: automatisches `pre-restore-*`-Backup dokumentiert

Rollback-Auslöser sind eine fehlerhafte Prüfsumme, ein fehlgeschlagener
`pg_restore`, abweichende Objektzahlen oder Datei-Hashes sowie ein nicht
erfolgreicher Systemcheck. In diesen Fällen wird der Zielbetrieb nicht
freigegeben und der Stand aus `pre-restore-*` wiederhergestellt.
