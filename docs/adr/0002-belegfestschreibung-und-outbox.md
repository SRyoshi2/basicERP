# ADR-0002: Belegfestschreibung mit Snapshot und transaktionaler Outbox

**Status:** Angenommen
**Datum:** 05.10.2026
**Entscheider:** Projektinhaber, technischer Lead, fachlicher Prüfer Rechnungswesen

## Kontext

Eine Rechnung darf nach der Festschreibung nicht still geändert werden. Ihre
Nummer, Steuerberechnung, Adressen, Texte und Artefakte müssen reproduzierbar
bleiben. PDF-/XML-Erzeugung, E-Mail und Webhooks sind jedoch fehleranfällige
Nebenwirkungen, die nicht zuverlässig innerhalb einer kurzen HTTP-Transaktion
abgeschlossen werden können.

Ein direkt nach dem Datenbank-Commit publizierter Celery-Task kann verloren
gehen. Ein vor dem Commit publizierter Task kann Daten lesen, die anschließend
zurückgerollt werden. Direkte synchrone PDF-Erzeugung hält den Nummernkreis und
die Web-Anfrage zu lange offen.

## Entscheidung

Beim Festschreiben erzeugt eine Datenbanktransaktion:

1. eine unter Row Lock vergebene Dokumentnummer,
2. einen versionierten, unveränderlichen Rechnungssnapshot,
3. einen Audit-Eintrag und
4. ein Outbox-Ereignis mit eindeutiger ID.

Der Beleg wechselt in `Finalizing` und ist ab diesem Moment fachlich
unveränderlich. Ein Dispatcher übergibt das Outbox-Ereignis an idempotente
Worker. Diese erzeugen und validieren PDF/XML, speichern neue unveränderliche
Artefakte und setzen anschließend `Finalized`. Fehler führen zu
`ArtifactFailed`; ein Retry verwendet dieselbe Nummer und denselben Snapshot.
Versand ist erst aus `Finalized` erlaubt.

## Betrachtete Optionen

### Option A: Snapshot + Outbox + idempotente Worker

| Dimension | Bewertung |
|---|---|
| Komplexität | Mittel |
| Konsistenz | Hoch |
| Fehlertoleranz | Hoch |
| Antwortzeit | Kurz; Arbeit asynchron |
| Nachvollziehbarkeit | Hoch |

**Vorteile:** Kein Dual-Write-Fenster, reproduzierbare Artefakte, sichere
Retries, klare technische Fehlerzustände.

**Nachteile:** Zusätzliche Outbox-/Dispatcherlogik, Eventbereinigung und
Monitoring nötig; kurzzeitiger Zwischenstatus ist sichtbar.

### Option B: Alles synchron in einer HTTP-/DB-Transaktion

| Dimension | Bewertung |
|---|---|
| Komplexität | Anfangs niedrig |
| Konsistenz | Mittel |
| Fehlertoleranz | Niedrig bis mittel |
| Antwortzeit | Lang und timeoutgefährdet |
| Nachvollziehbarkeit | Mittel |

**Vorteile:** Einfaches mentales Modell; bei Erfolg sofortiges Artefakt.

**Nachteile:** Lange Sperren am Nummernkreis, externe Fehler innerhalb einer
Transaktion, schlechte Skalierung und unklare Recovery bei Prozessabbruch.

### Option C: Direktes Task-Publishing nach dem Commit

| Dimension | Bewertung |
|---|---|
| Komplexität | Niedrig |
| Konsistenz | Niedrig |
| Fehlertoleranz | Mittel |
| Antwortzeit | Kurz |
| Nachvollziehbarkeit | Mittel |

**Vorteile:** Wenig Infrastruktur und asynchrone Verarbeitung.

**Nachteile:** Zwischen Commit und Broker-Publish können Jobs dauerhaft
verloren gehen; eine Reparatur ist nur über Sonderläufe möglich.

### Option D: Vollständiges Event Sourcing

| Dimension | Bewertung |
|---|---|
| Komplexität | Sehr hoch |
| Konsistenz | Hoch |
| Fehlertoleranz | Hoch |
| Antwortzeit | Gut |
| Nachvollziehbarkeit | Sehr hoch |

**Vorteile:** Vollständige Historie und Projektionen aus Events.

**Nachteile:** Für Team, Produktgröße und breite CRUD-Anteile überdimensioniert;
Migrationen und fachliche Abfragen werden anspruchsvoller.

## Trade-off-Analyse

Option A ergänzt das relationale Domänenmodell genau dort um zuverlässige
Ereignisse, wo externe Nebenwirkungen entstehen. Sie vermeidet sowohl lange
Transaktionen als auch das Dual-Write-Problem, ohne die gesamte Anwendung auf
Event Sourcing umzustellen.

## Konsequenzen

- `Finalizing`/`ArtifactFailed` sind explizite technische Zustände in UI und API.
- Dokumentnummern werden nach einem Artefaktfehler nicht neu vergeben.
- Handler müssen über Event-/Artefaktschlüssel idempotent sein.
- Outboxalter, Versuchszahl und Dead-Letter-Fälle werden überwacht.
- Eine Korrektur erzeugt ein neues, referenzierendes Dokument; sie mutiert nie
  den Originalsnapshot.
- Hashes belegen Integrität, ersetzen aber keine organisatorischen GoBD-
  Pflichten oder unveränderlichen externen Speicher.

## Maßnahmen

1. [ ] Snapshot-Schema und Versionierungsstrategie fachlich freigeben.
2. [ ] Nummernkreis unter Parallelität und Rollback testen.
3. [ ] Outbox-Claiming, Retry, Backoff und Dead-Letter-Sicht implementieren.
4. [ ] Jeder Worker erhält Deduplizierungs- und Crash-Recovery-Tests.
5. [ ] UI zeigt Finalisierung, Retry und Supporthinweis verständlich an.
6. [ ] Versand verweigern, solange Pflichtartefakte nicht erfolgreich validiert sind.
