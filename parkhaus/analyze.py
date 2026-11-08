"""
Format-Analyse für Parkhaus-Ticketnummern.

Ziel: Aus mehreren Beispiel-Tickets automatisch herausfinden, wie die
Barcode-Nummer aufgebaut ist – ohne die alte Doku.

Benutzung:
    1. samples.csv ausfuellen (mindestens 4-5 Tickets).
    2.  python3 parkhaus/analyze.py samples.csv

Das Programm meldet:
    * feste Stellen (bei allen Tickets gleich)  -> z. B. Anlagen-/Kassen-ID
    * variable Stellen                          -> laufende Nummer / Zeit
    * ob eine Mod-10- oder Luhn-Pruefziffer am Ende passt
    * ob Datum/Uhrzeit in der Nummer steckt (sucht gaengige Formate)
    * ob ein Feld fortlaufend hochzaehlt
"""

from __future__ import annotations

import csv
import sys
from datetime import datetime

from itf import luhn_is_valid, mod10_is_valid


def load_samples(path: str) -> list[dict]:
    rows: list[dict] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            barcode = (raw.get("barcode") or "").strip()
            if not barcode or barcode.startswith("#"):
                continue
            rows.append(
                {
                    "barcode": barcode,
                    "klartext": (raw.get("klartext") or "").strip(),
                    "datum": (raw.get("datum") or "").strip(),
                    "uhrzeit": (raw.get("uhrzeit") or "").strip(),
                }
            )
    return rows


def analyse_positions(barcodes: list[str]) -> None:
    lengths = {len(b) for b in barcodes}
    print(f"  Anzahl Tickets:     {len(barcodes)}")
    print(f"  Laengen:            {sorted(lengths)}")
    if len(lengths) != 1:
        print("  ! Unterschiedliche Laengen -> Stellen-Analyse uebersprungen.")
        return

    n = lengths.pop()
    constant, variable = [], []
    for pos in range(n):
        values = {b[pos] for b in barcodes}
        if len(values) == 1:
            constant.append((pos, values.pop()))
        else:
            variable.append(pos)

    mask = ["."] * n
    for pos, c in constant:
        mask[pos] = c
    print(f"  Feste Stellen:      {''.join(mask)}")
    print(f"                      (Punkt = aendert sich von Ticket zu Ticket)")
    print(f"  Variable Positionen:{[p for p in variable]}")


def analyse_checkdigit(barcodes: list[str]) -> None:
    mod10 = sum(mod10_is_valid(b) for b in barcodes)
    luhn = sum(luhn_is_valid(b) for b in barcodes)
    total = len(barcodes)
    print(f"  Mod-10-Pruefziffer passt bei {mod10}/{total} Tickets", end="")
    print("  <-- sehr wahrscheinlich!" if mod10 == total and total > 1 else "")
    print(f"  Luhn-Pruefziffer   passt bei {luhn}/{total} Tickets", end="")
    print("  <-- sehr wahrscheinlich!" if luhn == total and total > 1 else "")


def _date_candidates(dt: datetime) -> dict[str, str]:
    """Verschiedene uebliche Datums-/Zeit-Schreibweisen als Ziffernfolge."""
    return {
        "DDMMYY": dt.strftime("%d%m%y"),
        "DDMMYYYY": dt.strftime("%d%m%Y"),
        "YYMMDD": dt.strftime("%y%m%d"),
        "YYYYMMDD": dt.strftime("%Y%m%d"),
        "HHMM": dt.strftime("%H%M"),
        "HHMMSS": dt.strftime("%H%M%S"),
        "YYMMDDHHMM": dt.strftime("%y%m%d%H%M"),
    }


def analyse_datetime(rows: list[dict]) -> None:
    parsed = []
    for r in rows:
        dt = _parse_dt(r["datum"], r["uhrzeit"])
        if dt:
            parsed.append((r["barcode"], dt))
    if not parsed:
        print("  (kein/ungueltiges Datum angegeben -> uebersprungen)")
        return

    # Fuer jedes Format: steckt es bei ALLEN Tickets an der gleichen Stelle?
    any_hit = False
    sample_formats = _date_candidates(parsed[0][1]).keys()
    for fmt in sample_formats:
        offsets = []
        for barcode, dt in parsed:
            needle = _date_candidates(dt)[fmt]
            offsets.append(barcode.find(needle))
        if all(o >= 0 for o in offsets):
            where = f"Position {offsets[0]}" if len(set(offsets)) == 1 else f"Positionen {offsets}"
            print(f"  Datum/Zeit als {fmt:10} gefunden bei allen Tickets ({where})")
            any_hit = True
    if not any_hit:
        print("  Kein gaengiges Datums-/Zeitformat in der Nummer gefunden.")
        print("  (Zeit ist evtl. codiert/verschluesselt oder nicht enthalten.)")


def analyse_counter(rows: list[dict]) -> None:
    parsed = []
    for r in rows:
        dt = _parse_dt(r["datum"], r["uhrzeit"])
        parsed.append((r["barcode"], dt))
    if not all(dt for _, dt in parsed) or len({len(b) for b, _ in parsed}) != 1:
        print("  (Zaehler-Suche braucht gleiche Laenge + gueltige Zeiten)")
        return
    parsed.sort(key=lambda x: x[1])
    n = len(parsed[0][0])
    # Suche kurze Ziffernblocks, die ueber die Zeit monoton steigen
    for width in (3, 4, 5):
        for start in range(0, n - width + 1):
            vals = [int(b[start:start + width]) for b, _ in parsed]
            if all(b < a for b, a in zip(vals, vals[1:])):
                print(f"  Moegliche laufende Nummer an Position {start}-{start+width-1}: {vals}")
                return
    print("  Keine eindeutig hochzaehlende laufende Nummer erkannt.")


def _parse_dt(datum: str, uhrzeit: str):
    if not datum:
        return None
    for dfmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
        try:
            d = datetime.strptime(datum, dfmt)
            break
        except ValueError:
            continue
    else:
        return None
    if uhrzeit:
        for tfmt in ("%H:%M", "%H:%M:%S"):
            try:
                t = datetime.strptime(uhrzeit, tfmt)
                return d.replace(hour=t.hour, minute=t.minute, second=t.second)
            except ValueError:
                continue
    return d


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "samples.csv"
    rows = load_samples(path)
    if not rows:
        print(f"Keine Tickets in {path} gefunden. Bitte Beispiele eintragen.")
        return
    barcodes = [r["barcode"] for r in rows]

    print("=" * 60)
    print("PARKHAUS – FORMAT-ANALYSE")
    print("=" * 60)
    print("\n[1] Stellen-Aufbau")
    analyse_positions(barcodes)
    print("\n[2] Pruefziffer")
    analyse_checkdigit(barcodes)
    print("\n[3] Datum / Uhrzeit in der Nummer")
    analyse_datetime(rows)
    print("\n[4] Laufende Nummer")
    analyse_counter(rows)
    print("\n" + "=" * 60)
    print("Ergebnis an Claude zurueckgeben -> daraus bauen wir Generator + Pruefung.")


if __name__ == "__main__":
    main()
