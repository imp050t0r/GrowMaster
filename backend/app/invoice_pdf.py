from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


FONT_DIR = Path(reportlab.__file__).resolve().parent / "fonts"
pdfmetrics.registerFont(TTFont("GrowMaster", FONT_DIR / "Vera.ttf"))
pdfmetrics.registerFont(TTFont("GrowMaster-Bold", FONT_DIR / "VeraBd.ttf"))


def _paragraph(value: str | None, style: ParagraphStyle) -> Paragraph:
    text = escape(value or "—").replace("\n", "<br/>")
    return Paragraph(text, style)


def _party_block(title: str, lines: list[str | None], style: ParagraphStyle) -> Paragraph:
    visible = [escape(line) for line in lines if line]
    content = (
        f'<font name="GrowMaster-Bold" color="#287A52" size="7.5">'
        f"{escape(title)}</font><br/><br/>" + "<br/>".join(visible)
    )
    return Paragraph(content, style)


def build_invoice_pdf(invoice, credit_note=None) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=18 * mm,
        title=(credit_note.number if credit_note else invoice.number),
        author=invoice.seller_name,
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "Body", parent=styles["BodyText"], fontName="GrowMaster", fontSize=9,
        leading=13, textColor=colors.HexColor("#24342D")
    )
    small = ParagraphStyle(
        "Small", parent=body, fontSize=7.5, leading=10, textColor=colors.HexColor("#53655D")
    )
    heading = ParagraphStyle(
        "Heading", parent=body, fontName="GrowMaster-Bold", fontSize=17,
        leading=21, alignment=TA_RIGHT, textColor=colors.HexColor("#173D2B")
    )
    label = ParagraphStyle(
        "Label", parent=small, fontName="GrowMaster-Bold", textColor=colors.HexColor("#287A52")
    )
    right = ParagraphStyle("Right", parent=body, alignment=TA_RIGHT)
    right_bold = ParagraphStyle("RightBold", parent=right, fontName="GrowMaster-Bold")
    right_total = ParagraphStyle(
        "RightTotal", parent=right_bold, textColor=colors.white
    )

    is_credit = credit_note is not None
    document_number = credit_note.number if is_credit else invoice.number
    issued_on = credit_note.issued_on if is_credit else invoice.issued_on
    title = "DOBROPIS" if is_credit else "RAČUN"
    total = -credit_note.total_eur if is_credit else invoice.total_eur

    story = [
        Table(
            [[
                _paragraph("GROWMASTER", label),
                Paragraph(f"{escape(title)}<br/>{escape(document_number)}", heading),
            ]],
            colWidths=[65 * mm, 105 * mm],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, colors.HexColor("#287A52")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]),
        ),
        Spacer(1, 8 * mm),
        Table(
            [[
                _party_block("PRODAJALEC", [
                    invoice.seller_name,
                    invoice.seller_address,
                    f"Davčna št.: {invoice.seller_tax_number}" if invoice.seller_tax_number else None,
                    f"Matična št.: {invoice.seller_registration_number}" if invoice.seller_registration_number else None,
                    f"IBAN: {invoice.seller_iban}" if invoice.seller_iban else None,
                ], body),
                _party_block("KUPEC", [
                    invoice.customer_name,
                    invoice.customer_address,
                    f"Davčna št.: {invoice.customer_tax_number}" if invoice.customer_tax_number else None,
                ], body),
            ]],
            colWidths=[85 * mm, 85 * mm],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#C7D6CE")),
                ("INNERGRID", (0, 0), (-1, -1), .5, colors.HexColor("#C7D6CE")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F8F5")),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]),
        ),
        Spacer(1, 7 * mm),
    ]

    metadata = [
        ["Datum izdaje", issued_on.strftime("%d. %m. %Y")],
        ["Datum dobave", invoice.supply_date.strftime("%d. %m. %Y")],
    ]
    if is_credit:
        metadata.extend([["Popravlja račun", invoice.number], ["Razlog", credit_note.reason]])
    else:
        metadata.extend([
            ["Rok plačila", invoice.due_date.strftime("%d. %m. %Y")],
            ["Način plačila", {"bank_transfer": "Nakazilo", "cash": "Gotovina", "card": "Kartica"}.get(invoice.payment_method, invoice.payment_method)],
        ])
    story.extend([
        Table(
            [[_paragraph(key, label), _paragraph(value, body)] for key, value in metadata],
            colWidths=[42 * mm, 128 * mm],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -2), .3, colors.HexColor("#DCE6E0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]),
        ),
        Spacer(1, 7 * mm),
    ])

    rows = [[
        _paragraph("Opis", label), _paragraph("Količina", label),
        _paragraph("Cena/enoto", label), _paragraph("Znesek", label),
    ]]
    sign = -1 if is_credit else 1
    for line in invoice.lines:
        rows.append([
            _paragraph(line.description, body),
            _paragraph(f"{line.quantity:g} {line.unit}", right),
            _paragraph(f"{line.unit_price_eur:.2f} €", right),
            _paragraph(f"{sign * line.line_total_eur:.2f} €", right),
        ])
    rows.append([
        _paragraph("SKUPAJ", right_total), "", "", _paragraph(f"{total:.2f} €", right_total)
    ])
    story.extend([
        Table(
            rows,
            colWidths=[87 * mm, 28 * mm, 28 * mm, 27 * mm],
            repeatRows=1,
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6F1EA")),
                ("LINEBELOW", (0, 0), (-1, 0), .8, colors.HexColor("#287A52")),
                ("LINEBELOW", (0, 1), (-1, -2), .3, colors.HexColor("#DCE6E0")),
                ("SPAN", (0, -1), (2, -1)),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#173D2B")),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]),
        ),
        Spacer(1, 6 * mm),
    ])
    if invoice.vat_note:
        story.append(_paragraph(invoice.vat_note, small))
    if invoice.fiscal_confirmation_required:
        fiscal_source = credit_note if is_credit else invoice
        story.extend([
            Spacer(1, 4 * mm),
            _paragraph(f"EOR: {fiscal_source.eor}", small),
            _paragraph(f"ZOI: {fiscal_source.zoi}" if fiscal_source.zoi else None, small),
        ])

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("GrowMaster", 7)
        canvas.setFillColor(colors.HexColor("#708078"))
        canvas.drawString(18 * mm, 10 * mm, f"{title} {document_number} · arhivski izvod")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Stran {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
