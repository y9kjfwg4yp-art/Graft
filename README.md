# Parkhaus-System – Neuaufbau

Rekonstruktion und Neuprogrammierung der Ticket-Logik für das eigene
Parkhaus. Ausgangslage: Es gibt rund 200 vorgedruckte **Ausfahrtstickets**
(„Auslaßticket"), die Kunden gegen Bezahlung und Abgabe des Einfahrttickets
erhalten. Das ursprüngliche Erstellungsverfahren ist nicht mehr dokumentiert
und wird aus vorhandenen Tickets rekonstruiert.

## Was auf einem Ticket steht

| Feld        | Beispiel              | Bedeutung (Annahme)            |
|-------------|-----------------------|--------------------------------|
| Typ         | `Auslaßticket`        | Ausfahrtticket                 |
| Klartext-Nr | `0223/0007/701  iHVE` | Anlage / lfd. Nr. / ? / Kürzel |
| Datum/Zeit  | `08.11.2026 12:02`    | Ausstellung                    |
| Barcode     | `02477721355017016312433770` (26 Ziffern) | vermutlich Interleaved 2 of 5 |

## Nächster Schritt: Format bestimmen (braucht 4–5 Tickets)

Mit **einem** Ticket lässt sich das Muster nicht sicher bestimmen. Sobald
mehrere Beispiele vorliegen:

1. In `samples.csv` je Ticket eine Zeile eintragen.
2. Analyse starten:
   ```bash
   python3 parkhaus/analyze.py samples.csv
   ```
3. Das Tool meldet: feste Stellen, laufende Nummer, eingebettetes
   Datum/Uhrzeit und ob eine Mod-10- oder Luhn-Prüfziffer passt.

Das Ergebnis zeigt uns, wie der Generator die Nummer bauen muss.

## Dateien

| Datei               | Zweck                                             |
|---------------------|---------------------------------------------------|
| `parkhaus/itf.py`   | ITF-Barcode als SVG zeichnen + Prüfziffer-Helfer  |
| `parkhaus/analyze.py` | Ticketnummern analysieren (Formaterkennung)     |
| `samples.csv`       | Beispiel-Tickets zum Eintragen                    |

Alles läuft mit reinem Python 3 (keine Zusatzpakete).

## Hinweis Prüfziffer (Einzel-Ticket)

Beim bisher einzigen Ticket passt weder Mod-10 noch Luhn auf die ganze
26-stellige Zahl. Das ist **kein** verlässliches Ergebnis – es kann sein,
dass die Prüfziffer nur über einen Teil der Nummer läuft oder dass gar keine
im Barcode steckt und die Schranke gegen eine Liste prüft. Das klärt sich
mit mehreren Beispielen.

## Offene Punkte

- [ ] 4–5 weitere Tickets erfassen und analysieren
- [ ] Barcode-Symbologie bestätigen (meldet der Scanner „ITF / 2 of 5"?)
- [ ] Klären: prüft die Schranke gegen eine Datenbank oder nur per Prüfziffer?
- [ ] Generator für neue Tickets im erkannten Format
- [ ] Prüf-/Scan-Logik für die Ausfahrt
