# ADR-0001: Modularer Monolith als Ausgangsarchitektur

**Status:** Angenommen
**Datum:** 05.10.2026
**Entscheider:** Projektinhaber, technischer Lead

## Kontext

basicERP deckt mehrere Domänen ab, besitzt aber einen stark transaktionalen
Kern: Zeiten werden abgerechnet, Nummernkreise vergeben, Belege festgeschrieben,
Artefakte archiviert und Ereignisse versendet. Zielgruppe und Team sind klein;
Self-Hosting per Docker soll einfach bleiben. Gleichzeitig darf das System
nicht zu einem unstrukturierten Django-Projekt werden.

## Entscheidung

Wir bauen einen modularen Monolithen in einem Monorepo. Django-Apps bilden
fachliche Module mit klarer Daten- und Serviceverantwortung. Web und Celery-
Worker sind getrennte Prozesse aus demselben Backend-Artefakt. PostgreSQL ist
die gemeinsame transaktionale Datenbank. React bleibt ein separater API-Client.

Modulübergreifende synchrone Änderungen laufen über veröffentlichte
Anwendungsservices. Asynchrone Reaktionen laufen über versionierte Ereignisse
und eine transaktionale Outbox. Architekturtests verhindern verbotene
Abhängigkeiten.

## Betrachtete Optionen

### Option A: Modularer Monolith

| Dimension | Bewertung |
|---|---|
| Komplexität | Niedrig bis mittel |
| Betriebskosten | Niedrig |
| Skalierung | Für Zielgruppe ausreichend; Web/Worker horizontal skalierbar |
| Teamvertrautheit | Hoch bei Django |
| Transaktionssicherheit | Hoch |

**Vorteile**

- Einfache lokale Entwicklung, Installation, Migration und Sicherung.
- ACID-Transaktionen über Rechnungs-, Zeit- und Archivmetadaten.
- Weniger Netzwerk-, Deployment- und Versionskomplexität.
- Fachliche Grenzen können trotzdem explizit getestet werden.

**Nachteile**

- Grenzen werden nicht durch getrennte Deployments erzwungen.
- Datenbank und Release-Zyklus bleiben gemeinsam.
- Einzelne Module lassen sich nur mit Vorarbeit extrahieren.

### Option B: Microservices von Beginn an

| Dimension | Bewertung |
|---|---|
| Komplexität | Hoch |
| Betriebskosten | Hoch |
| Skalierung | Sehr flexibel, aktuell nicht benötigt |
| Teamvertrautheit | Zusätzliche verteilte-systemische Expertise nötig |
| Transaktionssicherheit | Aufwendig; Sagas/Idempotenz überall |

**Vorteile**

- Harte technische Grenzen und unabhängige Skalierung/Deployments.
- Fehler und Ressourcenverbrauch können stärker isoliert werden.

**Nachteile**

- Verteilte Transaktionen erschweren gerade den Rechnungsdurchstich.
- Mehr Infrastruktur, Observability, Verträge und Fehlermodi.
- Für ein Kleinteam und Single-Tenant-Installationen unverhältnismäßig.

### Option C: Unstrukturierter Django-Monolith

| Dimension | Bewertung |
|---|---|
| Komplexität | Anfangs niedrig, später hoch |
| Betriebskosten | Niedrig |
| Skalierung | Technisch ausreichend |
| Teamvertrautheit | Hoch |
| Wartbarkeit | Sinkend mit jeder Phase |

**Vorteile**

- Schnellster Start und wenig Konventionen.

**Nachteile**

- Zyklen, fachfremde Modellupdates und schwer testbare Geschäftslogik werden
  bei zehn Modulen sehr wahrscheinlich.
- Spätere Extraktion oder sichere Änderungen werden teuer.

## Trade-off-Analyse

Die fachliche Konsistenz und der geringe Self-Hosting-Aufwand wiegen für 1.0
schwerer als unabhängige Skalierung. Ein modularer Monolith liefert diese
Vorteile, ohne die Domänenstruktur aufzugeben. Die fehlende harte Isolation wird
durch Ownership-Regeln, öffentliche Services, Outbox-Ereignisse und
Architekturtests kompensiert.

## Konsequenzen

- Ein Repository, eine primäre Datenbank und ein Backend-Release.
- Web und Worker dürfen separat skaliert werden.
- Direkte Schreibzugriffe auf Modelle anderer Module sind verboten.
- Öffentliche Modulverträge und Events werden versioniert.
- Es gibt keine vorsorglichen Microservices in 1.0.
- Extraktion wird nur nach gemessenem Engpass oder organisatorischem Bedarf per
  neuem ADR entschieden.

## Maßnahmen

1. [ ] Modul-Ownership und erlaubte Abhängigkeiten als Architekturtest codieren.
2. [ ] Öffentliche Anwendungsservices pro Modul benennen.
3. [ ] Outbox-Infrastruktur in v0.1 anlegen, erstmals am PDF-Job vollständig nutzen.
4. [ ] Metriken für Web- und Worker-Ressourcen getrennt erfassen.
5. [ ] ADR bei Multi-Tenant-, HA- oder Extraktionsbedarf neu bewerten.
