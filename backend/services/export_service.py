import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
import os


def _register_chinese_font():
    """注册中文字体，优先使用系统自带字体。"""
    font_paths = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("Chinese", path))
                return "Chinese"
            except Exception:
                continue
    return "Helvetica"


def generate_pdf(result: dict, title: str) -> bytes:
    """生成 PDF 字节流。"""
    buffer = io.BytesIO()
    font_name = _register_chinese_font()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title_CN", parent=styles["Title"], fontName=font_name, fontSize=18, spaceAfter=12
    )
    heading_style = ParagraphStyle(
        "Heading_CN", parent=styles["Heading2"], fontName=font_name, fontSize=14, spaceAfter=8
    )
    body_style = ParagraphStyle(
        "Body_CN", parent=styles["BodyText"], fontName=font_name, fontSize=11, leading=18
    )
    bullet_style = ParagraphStyle(
        "Bullet_CN", parent=body_style, leftIndent=20, bulletIndent=10
    )

    elements = []

    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 12))

    summary = result.get("summary", "")
    if summary:
        elements.append(Paragraph("摘要", heading_style))
        elements.append(Paragraph(summary, body_style))
        elements.append(Spacer(1, 8))

    highlights = result.get("highlights", [])
    if highlights:
        elements.append(Paragraph("亮点", heading_style))
        for h in highlights:
            ts = h.get("timestamp", "")
            point = h.get("point", "")
            elements.append(Paragraph(f"[{ts}] {point}", bullet_style))
        elements.append(Spacer(1, 8))

    terms = result.get("terms", [])
    if terms:
        elements.append(Paragraph("术语解释", heading_style))
        for t in terms:
            term = t.get("term", "")
            exp = t.get("explanation", "")
            elements.append(Paragraph(f"<b>{term}</b>: {exp}", bullet_style))
        elements.append(Spacer(1, 8))

    qa = result.get("qa", [])
    if qa:
        elements.append(Paragraph("思考", heading_style))
        for i, q in enumerate(qa, 1):
            elements.append(Paragraph(f"{i}. {q.get('question', '')}", body_style))
            elements.append(Paragraph(q.get("answer", ""), bullet_style))
            elements.append(Spacer(1, 4))

    doc.build(elements)
    return buffer.getvalue()
