"""
Interleaved 2 of 5 (ITF) – Encoder und Prüfziffer-Helfer.

Reiner Standard-Python-Code, keine Zusatzpakete nötig.

ITF kann nur Ziffern und braucht eine GERADE Anzahl Stellen. Die Ziffern
werden paarweise verschachtelt: die erste Ziffer eines Paares bildet die
Balken, die zweite die Lücken.

Dieses Modul kann:
  * eine Nummer als SVG-Barcode zeichnen (zum Drucken),
  * die Mod-10-Prüfziffer (wie bei EAN/ITF-14) berechnen und prüfen,
  * die Luhn-Prüfziffer berechnen und prüfen.

Welche Prüfziffer Ihre alte Anlage verwendet, finden wir morgen mit
analyze.py aus den Beispiel-Tickets heraus.
"""

from __future__ import annotations

# Balken/Lücken-Muster je Ziffer: 1 = breit, 0 = schmal (5 Elemente)
_PATTERNS = {
    "0": "00110",
    "1": "10001",
    "2": "01001",
    "3": "11000",
    "4": "00101",
    "5": "10100",
    "6": "01100",
    "7": "00011",
    "8": "10010",
    "9": "01010",
}


# ---------------------------------------------------------------------------
# Prüfziffern
# ---------------------------------------------------------------------------

def mod10_checkdigit(digits: str) -> int:
    """Mod-10-Prüfziffer (EAN/ITF-14-Verfahren) für die gegebenen Ziffern.

    Von rechts nach links abwechselnd x3 / x1.
    """
    _require_digits(digits)
    total = 0
    for i, ch in enumerate(reversed(digits)):
        weight = 3 if i % 2 == 0 else 1
        total += int(ch) * weight
    return (10 - (total % 10)) % 10


def mod10_is_valid(number: str) -> bool:
    """True, wenn die letzte Stelle die korrekte Mod-10-Prüfziffer ist."""
    _require_digits(number)
    if len(number) < 2:
        return False
    body, check = number[:-1], int(number[-1])
    return mod10_checkdigit(body) == check


def luhn_checkdigit(digits: str) -> int:
    """Luhn-Prüfziffer (wie bei Kreditkarten) für die gegebenen Ziffern."""
    _require_digits(digits)
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 0:           # Position direkt vor der Prüfziffer wird verdoppelt
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - (total % 10)) % 10


def luhn_is_valid(number: str) -> bool:
    """True, wenn die Nummer inkl. letzter Stelle Luhn-gültig ist."""
    _require_digits(number)
    if len(number) < 2:
        return False
    body, check = number[:-1], int(number[-1])
    return luhn_checkdigit(body) == check


# ---------------------------------------------------------------------------
# Barcode als SVG
# ---------------------------------------------------------------------------

def to_svg(
    number: str,
    *,
    narrow: int = 2,
    wide: int = 5,
    height: int = 120,
    margin: int = 20,
    show_text: bool = True,
) -> str:
    """Gibt die Nummer als ITF-Barcode im SVG-Format zurück.

    narrow / wide : Breite schmaler bzw. breiter Elemente in Pixeln.
    Ergebnis in eine .svg-Datei schreiben und drucken.
    """
    _require_digits(number)
    if len(number) % 2 != 0:
        raise ValueError(
            f"ITF braucht eine gerade Stellenzahl – {number!r} hat {len(number)}. "
            "Ggf. vorne eine 0 ergänzen oder eine Prüfziffer anhängen."
        )

    # Elementbreiten-Folge aufbauen: (ist_balken, breite_in_px)
    elements: list[tuple[bool, int]] = []

    # Startzeichen: schmal Balken, schmal Lücke, schmal Balken, schmal Lücke
    for i in range(4):
        elements.append((i % 2 == 0, narrow))

    # Nutzdaten paarweise verschachteln
    for a, b in zip(number[::2], number[1::2]):
        bars = _PATTERNS[a]
        spaces = _PATTERNS[b]
        for bar_w, space_w in zip(bars, spaces):
            elements.append((True, wide if bar_w == "1" else narrow))
            elements.append((False, wide if space_w == "1" else narrow))

    # Stoppzeichen: breit Balken, schmal Lücke, schmal Balken
    elements.append((True, wide))
    elements.append((False, narrow))
    elements.append((True, narrow))

    total_width = margin * 2 + sum(w for _, w in elements)
    text_space = 28 if show_text else 0
    svg_height = height + text_space

    rects: list[str] = []
    x = margin
    for is_bar, w in elements:
        if is_bar:
            rects.append(
                f'<rect x="{x}" y="0" width="{w}" height="{height}" fill="#000"/>'
            )
        x += w

    text_el = ""
    if show_text:
        text_el = (
            f'<text x="{total_width / 2}" y="{height + 20}" '
            f'font-family="monospace" font-size="18" text-anchor="middle" '
            f'fill="#000">{number}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" '
        f'height="{svg_height}" viewBox="0 0 {total_width} {svg_height}">'
        f'<rect width="{total_width}" height="{svg_height}" fill="#fff"/>'
        f'{"".join(rects)}{text_el}</svg>'
    )


# ---------------------------------------------------------------------------
# intern
# ---------------------------------------------------------------------------

def _require_digits(s: str) -> None:
    if not s or not s.isdigit():
        raise ValueError(f"Nur Ziffern erlaubt, bekommen: {s!r}")


if __name__ == "__main__":
    import sys

    nr = sys.argv[1] if len(sys.argv) > 1 else "02477721355017016312433770"
    print(f"Nummer:              {nr}")
    print(f"Mod-10 gültig?       {mod10_is_valid(nr)}")
    print(f"Luhn gültig?         {luhn_is_valid(nr)}")
    print(f"Mod-10-Prüfziffer*:  {mod10_checkdigit(nr[:-1])} (letzte Stelle ist {nr[-1]})")
    out = f"{nr}.svg"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(to_svg(nr))
    print(f"Barcode geschrieben: {out}")
