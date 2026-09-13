import base64
import html
import io
import os
import zipfile
from datetime import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from models.compliance import ScanRecord


FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont("DejaVu", FONT_PATH))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", FONT_BOLD_PATH))
FONT = "DejaVu" if os.path.exists(FONT_PATH) else "Helvetica"
FONT_BOLD = "DejaVu-Bold" if os.path.exists(FONT_BOLD_PATH) else "Helvetica-Bold"


def _image_bytes(data_url: str) -> bytes:
    return base64.b64decode(data_url.split(",", 1)[1])


def build_pdf(scan: ScanRecord) -> bytes:
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=14 * mm, leftMargin=14 * mm, topMargin=14 * mm, bottomMargin=14 * mm, title=f"Inspection {scan.id}")
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TitleLM", parent=styles["Title"], fontName=FONT_BOLD, fontSize=18, textColor=colors.HexColor("#0F172A"), alignment=TA_CENTER)
    heading = ParagraphStyle("HeadingLM", parent=styles["Heading2"], fontName=FONT_BOLD, fontSize=11, textColor=colors.HexColor("#1E3A8A"), spaceBefore=8, spaceAfter=6)
    body = ParagraphStyle("BodyLM", parent=styles["BodyText"], fontName=FONT, fontSize=8.5, leading=11)
    story = [Paragraph("Legal Metrology Compliance Checker", title), Paragraph("Department of Consumer Affairs · Inspection Evidence Report", body), Spacer(1, 6 * mm)]
    meta = [
        ["Inspection ID", scan.id, "Date/time", scan.scanned_at.astimezone(timezone.utc).strftime("%d %b %Y %H:%M UTC")],
        ["Product", scan.product_name, "Brand", scan.brand or "Not detected"],
        ["Category", scan.category, "Overall status", scan.status.replace("_", " ").upper()],
        ["Manufacturer", scan.manufacturer, "Inspector", scan.inspector],
    ]
    meta_table = Table(meta, colWidths=[28 * mm, 58 * mm, 28 * mm, 58 * mm])
    meta_table.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FONT), ("FONTSIZE", (0, 0), (-1, -1), 8), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EFF6FF")), ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#EFF6FF")), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 5)]))
    story += [meta_table, Paragraph("Uploaded image evidence", heading)]
    image_cells = []
    for image in scan.images:
        try:
            flow = Image(io.BytesIO(_image_bytes(image.data_url)), width=48 * mm, height=36 * mm, kind="proportional")
            image_cells.append([flow, Paragraph(f"{html.escape(image.face_label)}<br/><font size='7'>{html.escape(image.file_name)}</font>", body)])
        except Exception:
            image_cells.append([Paragraph("Image unavailable", body), Paragraph(html.escape(image.face_label), body)])
    if image_cells:
        image_table = Table(image_cells, colWidths=[52 * mm, 112 * mm])
        image_table.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FONT), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("PADDING", (0, 0), (-1, -1), 4)]))
        story.append(image_table)
    story.append(Paragraph("Extracted product information", heading))
    extracted = scan.extracted_product
    fields = [
        ["Product", extracted.product_name if extracted else scan.product_name, "MRP", extracted.mrp if extracted and extracted.mrp else "Not reliably detected"],
        ["Brand", extracted.brand if extracted and extracted.brand else "Not detected", "Net quantity", extracted.net_quantity if extracted and extracted.net_quantity else "Not detected"],
        ["Manufacturer", extracted.manufacturer if extracted and extracted.manufacturer else scan.manufacturer, "Mfg/Packing date", extracted.mfg_date if extracted and extracted.mfg_date else "Not detected"],
        ["Batch/Lot", extracted.batch_lot if extracted and extracted.batch_lot else "Not detected", "Consumer care", extracted.consumer_care if extracted and extracted.consumer_care else "Not detected"],
    ]
    info_table = Table(fields, colWidths=[28 * mm, 58 * mm, 30 * mm, 56 * mm])
    info_table.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FONT), ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 5)]))
    story += [info_table, PageBreak(), Paragraph("Rule-by-rule evaluation", heading)]
    rows = [["Rule", "Requirement", "Extracted value", "Status", "Severity", "Explanation"]]
    for result in scan.rule_results:
        rows.append([Paragraph(result.rule_number, body), Paragraph(html.escape(result.requirement), body), Paragraph(html.escape(result.extracted_value or "—"), body), Paragraph(result.status.replace("_", " ").upper(), body), Paragraph(result.severity.upper(), body), Paragraph(html.escape(result.explanation), body)])
    rules_table = Table(rows, repeatRows=1, colWidths=[12 * mm, 42 * mm, 28 * mm, 28 * mm, 18 * mm, 46 * mm])
    rules_table.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FONT), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 7), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 3)]))
    story += [rules_table, Paragraph("Review notes", heading), Paragraph(html.escape(scan.remarks or scan.consumer_review or "No notes recorded."), body)]
    doc.build(story)
    return output.getvalue()


def build_docx(scan: ScanRecord) -> bytes:
    lines = ["LEGAL METROLOGY COMPLIANCE REPORT", f"Inspection ID: {scan.id}", f"Product: {scan.product_name}", f"Brand: {scan.brand or 'Not detected'}", f"Category: {scan.category}", f"Status: {scan.status}", "", "RULE RESULTS"]
    lines.extend(f"Rule {r.rule_number} — {r.rule_title}: {r.status}. {r.explanation}" for r in scan.rule_results)
    body = "".join(f"<w:p><w:r><w:t>{html.escape(line)}</w:t></w:r></w:p>" for line in lines)
    document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}<w:sectPr/></w:body></w:document>'
    content_types = '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
    rels = '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
    return output.getvalue()