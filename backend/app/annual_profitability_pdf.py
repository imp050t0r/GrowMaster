"""Printable yearly management summary using the existing profitability calculation."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FONT_DIR = Path(reportlab.__file__).resolve().parent / "fonts"
if "GrowMasterAnnual" not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(TTFont("GrowMasterAnnual", FONT_DIR / "Vera.ttf"))
    pdfmetrics.registerFont(TTFont("GrowMasterAnnualBold", FONT_DIR / "VeraBd.ttf"))


def build_annual_profitability_pdf(report: dict, year: int) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                                 leftMargin=14 * mm, rightMargin=14 * mm,
                                 topMargin=14 * mm, bottomMargin=14 * mm,
                                 title=f"GrowMaster – letno poročilo {year}", author="GrowMaster")
    body = ParagraphStyle("AnnualBody", fontName="GrowMasterAnnual", fontSize=8, leading=11)
    title = ParagraphStyle("AnnualTitle", parent=body, fontName="GrowMasterAnnualBold", fontSize=16, leading=20)
    small = ParagraphStyle("AnnualSmall", parent=body, fontSize=7, leading=10)
    cell = ParagraphStyle("AnnualCell", parent=body, fontSize=7, leading=9)
    money = lambda value: f"{value:,.2f} €".replace(",", " ")
    p = lambda value: Paragraph(escape(str(value)).replace("\n", "<br/>"), cell)
    summary = report["summary"]
    story = [Paragraph(f"GrowMaster · Letno poročilo {year}", title), Spacer(1, 3 * mm),
             Paragraph(f"Obdobje: {report['range']['start']} – {report['range']['end']}", body),
             Paragraph("Prihodki sledijo datumu prodaje; stroški datumu vnosa. Rezultat ni denarni tok ali davčni obračun.", small),
             Spacer(1, 5 * mm), Paragraph("Rezultat celotne kmetije", title), Spacer(1, 2 * mm)]
    totals = [["Neto prihodki", "Neposredni stroški", "Material", "Delo", "Splošni stroški", "Vsi stroški", "Rezultat"],
              [money(summary[k]) for k in ("net_revenue_eur", "direct_costs_eur", "material_costs_eur", "labor_costs_eur", "overhead_costs_eur", "costs_eur", "profit_eur")]]
    totals_table = Table([[p(x) for x in row] for row in totals], colWidths=[38 * mm] * 7, repeatRows=1)
    totals_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5f0e8")),
                                       ("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#c6d6c9")),
                                       ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 7),
                                       ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [totals_table, Spacer(1, 5 * mm), Paragraph("Rezultat po gredicah", title), Spacer(1, 2 * mm)]
    headers = ["Gredica / posevki", "Površina", "Žetev", "Neto prihodki", "Neposredni", "Material", "Delo", "Stroški skupaj", "Rezultat", "€/m²"]
    rows = [[p(x) for x in headers]]
    for row in report["by_bed"]:
        rows.append([p(row["bed"] + ("\n" + ", ".join(row["crops"]) if row["crops"] else "")),
                     p(f'{row["area_m2"]:.2f} m²'), p(f'{row["harvested_kg"]:.2f} kg'),
                     p(money(row["net_revenue_eur"])), p(money(row["direct_costs_eur"])),
                     p(money(row["material_costs_eur"])), p(money(row["labor_costs_eur"])),
                     p(money(row["costs_eur"])), p(money(row["profit_eur"])),
                     p(money(row["profit_eur_m2"]) if row["profit_eur_m2"] is not None else "—")])
    if len(rows) == 1:
        rows.append([p("Ni evidentiranih rezultatov po gredicah.")] + [p("")] * 9)
    table = Table(rows, colWidths=[100, 52, 55, 78, 73, 63, 63, 76, 76, 52], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5f0e8")),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f8f5")]),
                               ("LINEBELOW", (0, 0), (-1, 0), .5, colors.HexColor("#326b47")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 5),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [table, Spacer(1, 4 * mm),
              Paragraph("Rezultat gredice ne vsebuje splošnih stroškov kmetije. Ti so vključeni samo v skupnem rezultatu; zato se vsota rezultatov gredic lahko razlikuje od rezultata kmetije.", small),
              Paragraph(f"Nepripisani stroški in splošni stroški skupaj: {money(summary['unallocated_costs_eur'])}. Za podrobne vnose uporabi CSV izvoz.", small)]
    story += [PageBreak(), Paragraph("Prihodki in rezultat po kulturah", title), Spacer(1, 2 * mm)]
    crop_headers = ["Kultura", "Žetev kg", "Prodano kg", "Bruto prihodki", "Dobropisi", "Neto prihodki", "Neposredni", "Material", "Delo", "Stroški", "Rezultat"]
    crop_rows = [[p(x) for x in crop_headers]]
    for row in report["by_crop"]:
        crop_rows.append([p(row["crop"]), p(f'{row["harvested_kg"]:.2f}'),
                          p(f'{row["sold_kg"]:.2f}'), p(money(row["gross_revenue_eur"])),
                          p(money(row["credit_notes_eur"])), p(money(row["net_revenue_eur"])),
                          p(money(row["direct_costs_eur"])), p(money(row["material_costs_eur"])),
                          p(money(row["labor_costs_eur"])), p(money(row["costs_eur"])),
                          p(money(row["profit_eur"]))])
    if len(crop_rows) == 1:
        crop_rows.append([p("Ni evidentiranih rezultatov po kulturah.")] + [p("")] * 10)
    crops_table = Table(crop_rows, colWidths=[95, 48, 48, 75, 63, 75, 70, 62, 62, 70, 70], repeatRows=1, hAlign="LEFT")
    crops_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5f0e8")),
                                     ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f8f5")]),
                                     ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 6),
                                     ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [crops_table, Spacer(1, 4 * mm),
              Paragraph("Kulturi se pripišejo prodaja in stroški, povezani z evidentirano setvijo. Stroški brez povezave s setvijo in splošni stroški niso razdeljeni med kulture; vsota rezultatov po kulturah zato ni nujno enaka rezultatu kmetije.", small)]
    def page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("GrowMasterAnnual", 7)
        canvas.setFillColor(colors.HexColor("#63766a"))
        canvas.drawRightString(283 * mm, 9 * mm, f"GrowMaster · {year} · stran {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=page_number, onLaterPages=page_number)
    return buffer.getvalue()
