"""Generate realistic oil & gas equipment PDFs into sample_docs/.

Phase 2 of the POC. Documents share equipment codes so the demo shows a
lifecycle (e.g. PMP-0041 appears in a PO, a service record, and a spec sheet),
and layouts vary between documents of the same type to prove the extraction
handles format drift.

Dates are chosen relative to a fixed "today" so the seeded fleet produces at
least one green, one orange, and one red equipment when run through the status
engine (Phase 4).
"""
from __future__ import annotations

import os
from datetime import date, timedelta

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# The POC's reference "today". Keep in sync with demo narration.
TODAY = date(2026, 7, 16)
OUT_DIR = os.path.join(os.path.dirname(__file__), "sample_docs")

styles = getSampleStyleSheet()
H_COMPANY = ParagraphStyle(
    "Company", parent=styles["Title"], fontSize=18, spaceAfter=2, alignment=TA_LEFT
)
H_SUB = ParagraphStyle(
    "Sub", parent=styles["Normal"], fontSize=8, textColor=colors.grey
)
H_DOCTITLE = ParagraphStyle(
    "DocTitle", parent=styles["Heading1"], fontSize=15, alignment=TA_RIGHT
)
BODY = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, leading=13)
SMALL = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, leading=11)
RIGHT = ParagraphStyle("Right", parent=BODY, alignment=TA_RIGHT)
CENTER = ParagraphStyle("Center", parent=BODY, alignment=TA_CENTER)
LABEL = ParagraphStyle(
    "Label", parent=SMALL, textColor=colors.HexColor("#555555"), fontName="Helvetica-Bold"
)


def _iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _long(d: date) -> str:
    return d.strftime("%B %d, %Y")


def _build(filename: str, flowables: list) -> None:
    path = os.path.join(OUT_DIR, filename)
    doc = SimpleDocTemplate(
        path,
        pagesize=LETTER,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )
    doc.build(flowables)
    print(f"  wrote {filename}")


def _signature_block(names: list[tuple[str, str]]):
    """Signature lines: list of (role, printed_name)."""
    cells = []
    for role, name in names:
        cells.append(
            [
                Paragraph("_______________________________", BODY),
                Paragraph(f"<b>{role}</b>: {name}", SMALL),
            ]
        )
    rows = [[c[0] for c in cells], [c[1] for c in cells]]
    t = Table(rows, colWidths=[3.2 * inch] * len(cells))
    t.setStyle(TableStyle([("TOPPADDING", (0, 1), (-1, 1), 2)]))
    return t


# --------------------------------------------------------------------------- #
# Purchase Orders (3) — varied layouts. One (PO-0012) sells outright.
# --------------------------------------------------------------------------- #

def po_0012():
    """Boxed header, sale of equipment outright (ownership transfer)."""
    header = Table(
        [
            [
                Paragraph("APEX OILFIELD EQUIPMENT CO.", H_COMPANY),
                Paragraph("SALES ORDER", H_DOCTITLE),
            ],
            [
                Paragraph("1450 Refinery Rd, Midland, TX 79701<br/>(432) 555-0142", H_SUB),
                Paragraph("PO # PO-2026-0012", RIGHT),
            ],
        ],
        colWidths=[3.6 * inch, 3.4 * inch],
    )
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    meta = Table(
        [
            [Paragraph("SOLD TO", LABEL), Paragraph("ORDER DATE", LABEL), Paragraph("TERMS", LABEL)],
            [
                Paragraph("Permian Basin Drilling LLC<br/>2200 W County Rd, Odessa, TX", SMALL),
                Paragraph(_long(date(2026, 2, 3)), SMALL),
                Paragraph("Net 30 — Outright Sale", SMALL),
            ],
        ],
        colWidths=[3.0 * inch, 2.0 * inch, 2.0 * inch],
    )
    meta.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    line_items = Table(
        [
            ["Equipment Code", "Description", "Qty", "Unit Price", "Amount"],
            ["PMP-0041", "Centrifugal Pump, 6x4x13, API 610", "1", "$42,000.00", "$42,000.00"],
            ["VLV-0210", "Gate Valve, 6in 900# WCB Trim", "2", "$3,150.00", "$6,300.00"],
        ],
        colWidths=[1.2 * inch, 3.0 * inch, 0.5 * inch, 1.1 * inch, 1.2 * inch],
    )
    line_items.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    totals = Table(
        [["Subtotal", "$48,300.00"], ["Tax (0%)", "$0.00"], ["TOTAL (USD)", "$48,300.00"]],
        colWidths=[1.3 * inch, 1.2 * inch],
        hAlign="RIGHT",
    )
    totals.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
                ("LINEABOVE", (0, 2), (-1, 2), 0.5, colors.black),
            ]
        )
    )

    return [
        header,
        HRFlowable(width="100%", thickness=1.2, color=colors.HexColor("#1f3a5f")),
        Spacer(1, 10),
        meta,
        Spacer(1, 14),
        Paragraph("<b>This order transfers full ownership of the listed equipment to the buyer.</b>", SMALL),
        Spacer(1, 6),
        line_items,
        Spacer(1, 8),
        totals,
        Spacer(1, 30),
        _signature_block([("Authorized By", "R. Castillo"), ("Customer", "T. Reyes")]),
    ]


def po_0018():
    """Minimal, left-aligned invoice style — different look from PO-0012."""
    return [
        Paragraph("Lone Star Rotating Equipment", H_COMPANY),
        Paragraph("Purchase Order &nbsp;•&nbsp; PO-2026-0018", styles["Heading2"]),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Spacer(1, 8),
        Paragraph(
            f"<b>Customer:</b> Gulf Coast Energy Services<br/>"
            f"<b>Order Date:</b> {_iso(date(2026, 4, 18))}<br/>"
            f"<b>Ship To:</b> Corpus Christi Terminal, Dock 4<br/>"
            f"<b>Currency:</b> USD",
            BODY,
        ),
        Spacer(1, 12),
        Table(
            [
                ["Item", "Code", "Description", "Qty", "Unit", "Line Total"],
                ["1", "CMP-0102", "Reciprocating Compressor, 200HP", "1", "$88,500.00", "$88,500.00"],
                ["2", "CMP-0103", "Rotary Screw Compressor, 150HP", "1", "$61,250.00", "$61,250.00"],
            ],
            colWidths=[0.4 * inch, 1.0 * inch, 2.7 * inch, 0.5 * inch, 1.1 * inch, 1.2 * inch],
            style=TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
                    ("LINEBELOW", (0, -1), (-1, -1), 0.25, colors.lightgrey),
                    ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                ]
            ),
        ),
        Spacer(1, 10),
        Paragraph("Order Total: <b>$149,750.00 USD</b>", RIGHT),
        Spacer(1, 40),
        Paragraph("Approved: _____________________  (K. Nwosu, Procurement)", SMALL),
    ]


def po_0021():
    """Two-column card layout."""
    left = Paragraph(
        "<b>DELTA WELL SERVICES</b><br/>Equipment Sales Division<br/>"
        "Houston, TX • sales@deltawell.example",
        BODY,
    )
    right = Paragraph(
        f"<b>PURCHASE ORDER</b><br/>No. PO-2026-0021<br/>Date: {_iso(date(2026, 5, 27))}<br/>"
        "Buyer: Anadarko Field Operations",
        RIGHT,
    )
    head = Table([[left, right]], colWidths=[3.5 * inch, 3.5 * inch])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    items = Table(
        [
            ["Equipment Code", "Description", "Qty", "Unit Price", "Amount"],
            ["VLV-0211", "Ball Valve, 4in 600# Full Bore", "4", "$1,875.00", "$7,500.00"],
            ["PMP-0042", "Centrifugal Pump, 4x3x10, API 610", "1", "$36,900.00", "$36,900.00"],
        ],
        colWidths=[1.3 * inch, 2.9 * inch, 0.5 * inch, 1.1 * inch, 1.2 * inch],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8a1c1c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f2f2")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        ),
    )
    return [
        head,
        Spacer(1, 12),
        items,
        Spacer(1, 8),
        Paragraph("<b>Total: $44,400.00 USD</b>", RIGHT),
        Spacer(1, 36),
        _signature_block([("Seller", "M. Okafor"), ("Buyer", "J. Whitfield")]),
    ]


# --------------------------------------------------------------------------- #
# Rental Contracts (2)
# --------------------------------------------------------------------------- #

def rc_0007():
    """Rental due back within 7 days of TODAY -> triggers due-back alert."""
    due_back = TODAY + timedelta(days=4)  # 2026-07-20
    return [
        Paragraph("WEST TEXAS EQUIPMENT RENTALS", H_COMPANY),
        Paragraph("EQUIPMENT RENTAL AGREEMENT", styles["Heading2"]),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2f6f3e")),
        Spacer(1, 8),
        Table(
            [
                [Paragraph("Contract No.", LABEL), Paragraph("RC-2026-0007", SMALL)],
                [Paragraph("Lessee", LABEL), Paragraph("West Texas Wireline Inc.", SMALL)],
                [Paragraph("Start Date", LABEL), Paragraph(_long(date(2026, 6, 20)), SMALL)],
                [Paragraph("Due Back Date", LABEL), Paragraph(_long(due_back), SMALL)],
                [Paragraph("Monthly Rate", LABEL), Paragraph("$4,200.00 USD", SMALL)],
            ],
            colWidths=[1.6 * inch, 4.0 * inch],
            style=TableStyle(
                [
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            ),
        ),
        Spacer(1, 12),
        Paragraph("<b>Equipment on Rent</b>", BODY),
        Table(
            [["Equipment Code", "Description"], ["ASM-0333", "Wellhead Assembly, 7-1/16in 10K"]],
            colWidths=[1.6 * inch, 4.0 * inch],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2f6f3e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                ]
            ),
        ),
        Spacer(1, 10),
        Paragraph(
            "Lessee agrees to return the above equipment on or before the Due Back Date "
            "in good working condition, normal wear excepted.",
            SMALL,
        ),
        Spacer(1, 30),
        _signature_block([("Lessor", "West Texas Rentals"), ("Lessee", "D. Barrera")]),
    ]


def rc_0009():
    """Different layout: paragraph-style contract."""
    return [
        Paragraph("Bakken Equipment Leasing Co.", H_COMPANY),
        Spacer(1, 4),
        Paragraph("RENTAL CONTRACT RC-2026-0009", styles["Heading3"]),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Spacer(1, 10),
        Paragraph(
            f"This agreement, dated {_long(date(2026, 5, 1))}, is entered into between "
            f"Bakken Equipment Leasing Co. (\"Lessor\") and <b>Bakken Drilling Partners</b> "
            f"(\"Lessee\").",
            BODY,
        ),
        Spacer(1, 8),
        Paragraph(
            "<b>Term.</b> Rental commences on <b>2026-05-01</b> and equipment is due back "
            "on <b>2026-09-01</b>.",
            BODY,
        ),
        Paragraph("<b>Rate.</b> $2,750.00 per month, invoiced monthly (USD).", BODY),
        Paragraph(
            "<b>Equipment.</b> One (1) unit — code <b>CMP-0103</b>, Rotary Screw Compressor 150HP.",
            BODY,
        ),
        Spacer(1, 36),
        _signature_block([("Lessor", "H. Sorenson"), ("Lessee", "P. Amundson")]),
    ]


# --------------------------------------------------------------------------- #
# Rental Return (1)
# --------------------------------------------------------------------------- #

def rr_0003():
    return [
        Paragraph("WEST TEXAS EQUIPMENT RENTALS", H_COMPANY),
        Paragraph("EQUIPMENT RETURN RECORD", styles["Heading2"]),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2f6f3e")),
        Spacer(1, 10),
        Table(
            [
                [Paragraph("Return Doc No.", LABEL), Paragraph("RR-2026-0003", SMALL)],
                [Paragraph("Against Contract", LABEL), Paragraph("RC-2026-0009", SMALL)],
                [Paragraph("Return Date", LABEL), Paragraph(_long(date(2026, 6, 28)), SMALL)],
                [Paragraph("Equipment Returned", LABEL), Paragraph("CMP-0103", SMALL)],
            ],
            colWidths=[1.8 * inch, 4.0 * inch],
            style=TableStyle(
                [
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            ),
        ),
        Spacer(1, 12),
        Paragraph(
            "<b>Condition Notes:</b> Unit returned early. Minor surface corrosion on frame; "
            "oil level nominal. No functional defects observed on intake inspection.",
            BODY,
        ),
        Spacer(1, 30),
        _signature_block([("Received By", "L. Okoro"), ("Returned By", "P. Amundson")]),
    ]


# --------------------------------------------------------------------------- #
# Service Records (3): recent->green, ~5mo->orange, overdue->red
# --------------------------------------------------------------------------- #

def sr_0051():
    """PMP-0041 — recent service -> GREEN. Tabular layout."""
    svc = date(2026, 7, 1)
    nxt = svc + timedelta(days=180)  # 2026-12-28
    return [
        Paragraph("APEX FIELD SERVICE DIVISION", H_COMPANY),
        Paragraph("SERVICE RECORD", styles["Heading2"]),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1f3a5f")),
        Spacer(1, 10),
        Table(
            [
                ["Record No.", "SR-2026-0051"],
                ["Equipment Code", "PMP-0041"],
                ["Service Date", _iso(svc)],
                ["Service Type", "180-Day Preventive Maintenance"],
                ["Technician", "J. Alvarez (Cert #TX-4471)"],
                ["Next Service Due", _iso(nxt)],
            ],
            colWidths=[1.8 * inch, 4.2 * inch],
            style=TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2f7")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]
            ),
        ),
        Spacer(1, 12),
        Paragraph(
            "<b>Findings:</b> Mechanical seals replaced, bearings re-greased, alignment "
            "verified within tolerance. Vibration readings nominal. Unit released to service.",
            BODY,
        ),
        Spacer(1, 28),
        _signature_block([("Technician", "J. Alvarez"), ("QA Reviewer", "S. Kim")]),
    ]


def sr_0052():
    """CMP-0102 — ~5 months old, next due ~24 days out -> ORANGE."""
    svc = date(2026, 2, 10)
    nxt = svc + timedelta(days=180)  # 2026-08-09
    return [
        Paragraph("Lone Star Rotating Equipment — Service Dept.", H_COMPANY),
        Spacer(1, 4),
        Paragraph("Field Service Report", styles["Heading3"]),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Spacer(1, 10),
        Paragraph(
            f"<b>Report #:</b> SR-2026-0052 &nbsp;&nbsp; <b>Equipment:</b> CMP-0102<br/>"
            f"<b>Serviced:</b> {_long(svc)} &nbsp;&nbsp; <b>Type:</b> Semi-Annual PM<br/>"
            f"<b>Technician:</b> R. Delgado<br/>"
            f"<b>Next Due:</b> {_iso(nxt)}",
            BODY,
        ),
        Spacer(1, 10),
        Paragraph(
            "<b>Findings:</b> Valve clearances adjusted, intake filter replaced, crankcase "
            "oil changed. Cylinder compression within spec. Recommend re-inspection at next "
            "interval.",
            BODY,
        ),
        Spacer(1, 30),
        Paragraph("Signed: __________________  R. Delgado", SMALL),
    ]


def sr_0055():
    """VLV-0210 — overdue service -> RED. Deliberately messy fields to
    lower extraction confidence and land in the review queue."""
    svc = date(2025, 12, 1)
    nxt = svc + timedelta(days=180)  # 2026-05-30 (past)
    messy = ParagraphStyle(
        "Messy", parent=BODY, textColor=colors.HexColor("#333333"), fontName="Courier"
    )
    return [
        Paragraph("Anadarko Field Ops — Maintenance Log", H_COMPANY),
        Spacer(1, 6),
        Paragraph("SERVICE / INSPECTION SLIP  (handwritten transcription)", SMALL),
        HRFlowable(width="100%", thickness=0.75, color=colors.grey),
        Spacer(1, 10),
        Paragraph("Rec# SR-2026-0055", messy),
        Paragraph("Equip:  VLV-0210   (gate valve, 6in)", messy),
        Paragraph(f"Svc dt:  {_iso(svc)}   type: leak-test / seat lap", messy),
        Paragraph("Tech:   ~illegible~ (badge partially smudged)", messy),
        Paragraph(f"Next due:  {_iso(nxt)}  <font color='#8a1c1c'>[OVERDUE]</font>", messy),
        Spacer(1, 10),
        Paragraph(
            "Notes: seat showed pitting, temporary lap performed in field. Follow-up "
            "overhaul REQUIRED — unit past due for full service. Do not return to high-"
            "pressure service until re-certified.",
            SMALL,
        ),
        Spacer(1, 26),
        Paragraph("Logged by: (signature illegible)", SMALL),
    ]


# --------------------------------------------------------------------------- #
# Spec Sheet (1)
# --------------------------------------------------------------------------- #

def spec_pmp_0041():
    return [
        Paragraph("APEX OILFIELD EQUIPMENT CO.", H_COMPANY),
        Paragraph("EQUIPMENT SPECIFICATION SHEET", styles["Heading2"]),
        HRFlowable(width="100%", thickness=1.2, color=colors.HexColor("#1f3a5f")),
        Spacer(1, 8),
        Paragraph(
            "<b>Equipment Code:</b> PMP-0041 &nbsp;•&nbsp; <b>Model:</b> Centrifugal Pump 6x4x13",
            BODY,
        ),
        Spacer(1, 10),
        Table(
            [
                ["Parameter", "Value"],
                ["Type", "Horizontal centrifugal, single-stage (API 610 OH2)"],
                ["Rated Flow", "1,200 GPM"],
                ["Rated Head", "410 ft"],
                ["Max Discharge Pressure", "285 psig"],
                ["Design Temperature", "-20 F to 350 F"],
                ["Casing Material", "ASTM A216 WCB carbon steel"],
                ["Impeller Material", "CA6NM stainless (12Cr)"],
                ["Shaft Seal", "Mechanical seal, API Plan 11"],
                ["Bearing Type", "Anti-friction, oil lubricated"],
                ["Driver", "150 HP, 3560 RPM, TEFC motor"],
                ["Service Interval", "180 days"],
            ],
            colWidths=[2.4 * inch, 4.0 * inch],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef2f7")]),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            ),
        ),
        Spacer(1, 12),
        Paragraph("<b>Assembly Parts List</b>", BODY),
        Table(
            [
                ["Item", "Part No.", "Description", "Qty"],
                ["1", "APX-6413-CAS", "Casing, WCB", "1"],
                ["2", "APX-6413-IMP", "Impeller, CA6NM", "1"],
                ["3", "APX-SEAL-11", "Mechanical Seal Cartridge", "1"],
                ["4", "APX-BRG-SET", "Bearing Set (radial + thrust)", "1"],
                ["5", "APX-BP-6413", "Base Plate, fabricated steel", "1"],
            ],
            colWidths=[0.5 * inch, 1.4 * inch, 3.5 * inch, 0.5 * inch],
            style=TableStyle(
                [
                    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("ALIGN", (3, 0), (3, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                ]
            ),
        ),
    ]


DOCS = {
    "po_2026_0012_permian_sale.pdf": po_0012,
    "po_2026_0018_gulfcoast.pdf": po_0018,
    "po_2026_0021_anadarko.pdf": po_0021,
    "rc_2026_0007_westtexas.pdf": rc_0007,
    "rc_2026_0009_bakken.pdf": rc_0009,
    "rr_2026_0003_return.pdf": rr_0003,
    "sr_2026_0051_pmp0041_green.pdf": sr_0051,
    "sr_2026_0052_cmp0102_orange.pdf": sr_0052,
    "sr_2026_0055_vlv0210_red.pdf": sr_0055,
    "spec_pmp_0041.pdf": spec_pmp_0041,
}


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"Generating {len(DOCS)} sample PDFs into {OUT_DIR} ...")
    for filename, builder in DOCS.items():
        _build(filename, builder())
    print("Done.")


if __name__ == "__main__":
    main()
