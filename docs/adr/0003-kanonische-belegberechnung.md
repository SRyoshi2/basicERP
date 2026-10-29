# ADR-0003: Kanonische Berechnung für Belegentwürfe

**Status:** Angenommen  
**Datum:** 29.10.2026  
**Entscheider:** Projektinhaber, technischer Lead; fachliche Prüfung vor v0.5-Freigabe ausstehend

## Kontext

Angebote, Rechnungen, spätere PDF- und E-Rechnungsartefakte müssen dieselben
Netto-, Steuer- und Bruttowerte ausgeben. Geldwerte dürfen nicht über binäre
Gleitkommazahlen berechnet werden. Für Rechnungen verlangt § 14 Abs. 4 UStG
unter anderem nach Steuersätzen aufgeschlüsselte Entgelte und Steuerbeträge.
Rabatte und Rundung können sonst zu Abweichungen zwischen API, Oberfläche, PDF
und EN-16931-XML führen.

Der erste Phase-4-Schnitt umfasst ausschließlich editierbare Entwürfe. Eine
fortlaufende Nummer, der unveränderliche Snapshot und Artefakte entstehen erst
beim späteren Festschreiben gemäß ADR-0002.

## Entscheidung

Eine zentrale, seiteneffektfreie Berechnungsfunktion ist die einzige Quelle
für alle Belegwerte:

1. Menge, Einzelpreis, Rabatt und Steuersatz werden als `Decimal` verarbeitet.
2. Der Nettozeilenbetrag wird kaufmännisch (`ROUND_HALF_UP`) auf zwei
   Dezimalstellen gerundet.
3. Gerundete Nettozeilen werden je Steuersatz gruppiert.
4. Der Steuerbetrag wird einmal je Steuergruppe berechnet und auf zwei
   Dezimalstellen gerundet.
5. Beleg-Netto ist die Summe der gerundeten Zeilen; Brutto ist Netto plus
   gruppierte Steuer.

Entwürfe speichern Eingaben und Katalogreferenzen, nicht redundante Summen.
Beim Festschreiben werden Eingaben, berechnete Summen, Steuergruppen sowie
Aussteller-/Empfängerdaten in einen versionierten Snapshot kopiert.

## Betrachtete Optionen

### Option A: Steuer je Steuersatzgruppe

| Dimension | Bewertung |
|---|---|
| Nachvollziehbarkeit | Hoch |
| PDF-/XML-Konsistenz | Hoch |
| Implementierung | Mittel |
| Rundungsdifferenzen | Zentral sichtbar |

**Vorteile:** Entspricht der geforderten Aufschlüsselung nach Steuersätzen;
eine Steuergruppe kann direkt in PDF und EN-16931 abgebildet werden.

**Nachteile:** Die Steuer einer einzelnen Zeile ist bei mehreren gleich
besteuerten Zeilen nicht zwingend additiv darstellbar und wird deshalb im
Entwurf nicht als autoritativer Wert ausgegeben.

### Option B: Steuer je Position und anschließend summieren

| Dimension | Bewertung |
|---|---|
| Nachvollziehbarkeit | Mittel |
| PDF-/XML-Konsistenz | Mittel |
| Implementierung | Niedrig |
| Rundungsdifferenzen | Auf viele Zeilen verteilt |

**Vorteile:** Jede Position hat einen unmittelbar sichtbaren Steuerbetrag.

**Nachteile:** Die Summe der positionsweise gerundeten Steuer kann von der
Steuer auf die Steuerbemessungsgrundlage abweichen; spätere Formate benötigen
zusätzliche Ausgleichslogik.

### Option C: Summen und Steuern als editierbare Daten speichern

| Dimension | Bewertung |
|---|---|
| Nachvollziehbarkeit | Niedrig |
| Konsistenz | Niedrig |
| Implementierung | Anfangs niedrig |
| Wartbarkeit | Niedrig |

**Vorteile:** Beliebige manuelle Korrekturen wären möglich.

**Nachteile:** Eingaben und Summen können auseinanderlaufen; API, PDF und XML
hätten keine verlässliche gemeinsame Quelle.

## Trade-off-Analyse

Option A priorisiert reproduzierbare Beleg- und Steuergruppensummen. Die
zusätzliche Berechnungsfunktion ist klein und unabhängig testbar. Manuelle
Rundungskorrekturen werden nicht als heimliche Summenänderung zugelassen;
fachlich nötige Ausgleichspositionen müssen als sichtbare Position modelliert
werden.

## Konsequenzen

- API und UI erhalten Geldwerte als Dezimalstrings.
- Entwürfe bleiben vollständig neu berechenbar.
- Festgeschriebene Snapshots speichern die Version des Rechenmodells.
- Währungen mit anderer Nachkommastellenzahl sind in v0.5 nicht vorgesehen;
  der unterstützte Umfang bleibt EUR mit zwei Nachkommastellen.
- Steuerbefreiungen und Kleinunternehmerfälle brauchen einen begründenden
  Rechnungshinweis und eigene Golden-Master-Tests.
- Die fachliche Freigabe durch eine Rechnungs-/Steuerfachperson bleibt Release-
  Gate für v0.5; diese Entscheidung ist keine Steuerberatung.

## Maßnahmen

1. [x] Rechenkern und Grenzfalltests vor Festschreibungslogik implementieren.
2. [ ] §19-, 0-%-, 7-%-, 19-%-, Rabatt- und gemischte Steuerfälle fachlich prüfen.
3. [ ] Beim Festschreiben Rechenmodellversion und Steuergruppen mitspeichern.
4. [ ] PDF und E-Rechnung ausschließlich aus demselben Snapshot erzeugen.

## Fachliche Quellen

- [§ 14 Abs. 4 UStG](https://www.gesetze-im-internet.de/ustg_1980/__14.html)
- [§ 31 UStDV](https://www.gesetze-im-internet.de/ustdv_1980/__31.html)
- [§ 33 UStDV](https://www.gesetze-im-internet.de/ustdv_1980/__33.html)
