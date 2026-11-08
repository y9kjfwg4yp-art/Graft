"""
Ausfahrtsticket ("Auslassticket") als druckbares SVG rendern.

Setzt die Ticket-Optik (Kopf, Klartext-Nummer, Datum/Uhrzeit) mit dem
ITF-Barcode aus itf.py zusammen. Layout angelehnt an das vorhandene Ticket.

ACHTUNG: Die hier erzeugte Barcode-Nummer ist nur so gut wie das uebergebene
Format. Solange das echte Anlagenformat nicht bestaetigt ist, sind damit
erzeugte Tickets reine MUSTER und oeffnen keine Schranke.
"""

from __future__ import annotations

from datetime import datetime

from itf import to_svg as barcode_svg, mod10_checkdigit


def render_ticket(
    *,
    barcode_number: str,
    klartext: str,
    zeitpunkt: datetime,
    typ: str = "Auslassticket",
    muster: bool = True,
) -> str:
    """Komplettes Ausfahrtsticket als SVG-String."""
    width, height = 520, 320
    datum = zeitpunkt.strftime("%d.%m.%Y")
    uhrzeit = zeitpunkt.strftime("%H:%M")

    # Barcode separat erzeugen und als verschachteltes <svg> einbetten.
    inner = barcode_svg(barcode_number, narrow=2, wide=5, height=90, margin=10)
    # Breite des Barcodes aus dem erzeugten SVG lesen:
    bc_w = int(inner.split('width="', 1)[1].split('"', 1)[0])
    bc_x = (width - bc_w) / 2

    muster_band = ""
    if muster:
        muster_band = (
            f'<rect x="0" y="0" width="{width}" height="26" fill="#c0392b"/>'
            f'<text x="{width/2}" y="18" font-family="monospace" font-size="15" '
            f'font-weight="bold" text-anchor="middle" fill="#fff">'
            f'*** MUSTER / TEST - OEFFNET KEINE SCHRANKE ***</text>'
        )

    top = 26 if muster else 0

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}" font-family="monospace">
  <rect width="{width}" height="{height}" fill="#fff" stroke="#000" stroke-width="2"/>
  {muster_band}
  <text x="20" y="{top+40}" font-size="24" font-weight="bold" fill="#000">{typ}</text>
  <text x="20" y="{top+72}" font-size="18" fill="#000">{klartext}</text>
  <text x="20" y="{top+98}" font-size="18" fill="#000">{datum}  {uhrzeit}</text>
  <svg x="{bc_x}" y="{top+120}">{_strip_outer(inner)}</svg>
</svg>"""


def _strip_outer(svg: str) -> str:
    """Inhalt eines <svg>...</svg> ohne die aeussere Huelle (zum Einbetten)."""
    start = svg.index(">", svg.index("<svg")) + 1
    end = svg.rindex("</svg>")
    return svg[start:end]


def demo() -> str:
    """Ein klar gekennzeichnetes Musterticket erzeugen und speichern."""
    now = datetime(2026, 11, 8, 18, 30)
    # Frei erfundene Demo-Nummer: fester Demo-Praefix + Datum + lfd. Nr.,
    # am Ende eine Mod-10-Pruefziffer. NICHT das echte Anlagenformat!
    body = "9999" + now.strftime("%y%m%d%H%M") + "0042"
    number = body + str(mod10_checkdigit(body))
    if len(number) % 2:                       # ITF braucht gerade Stellenzahl
        number = "0" + number
    svg = render_ticket(
        barcode_number=number,
        klartext="9999/0042/701  TEST",
        zeitpunkt=now,
        muster=True,
    )
    out = "musterticket.svg"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"Demo-Nummer:    {number}  ({len(number)} Stellen)")
    print(f"Ticket gespeichert: {out}")
    return out


if __name__ == "__main__":
    demo()
