"""Generate sample pharmaceutical MedInfo FAQ PDF documents."""

import json
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY


def get_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='DocTitle', fontSize=18, leading=22,
        alignment=TA_CENTER, spaceAfter=6, textColor=colors.HexColor('#1a3c6e'), fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='DocSubtitle', fontSize=11, leading=14,
        alignment=TA_CENTER, spaceAfter=20, textColor=colors.HexColor('#555555')))
    styles.add(ParagraphStyle(name='QStyle', fontSize=11, leading=14,
        spaceBefore=14, spaceAfter=4, textColor=colors.HexColor('#1a3c6e'), fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='AStyle', fontSize=10, leading=13,
        spaceAfter=10, textColor=colors.HexColor('#333333'), alignment=TA_JUSTIFY))
    styles.add(ParagraphStyle(name='SectionHead', fontSize=13, leading=16,
        spaceBefore=20, spaceAfter=8, textColor=colors.HexColor('#2c5f8a'), fontName='Helvetica-Bold'))
    return styles


def make_table(headers, rows):
    data = [headers] + rows
    t = Table(data, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3c6e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f5f8fc'), colors.white]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return t


def build_pdf(filename, title, subtitle, sections, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    doc = SimpleDocTemplate(path, pagesize=letter,
        topMargin=0.75*inch, bottomMargin=0.75*inch,
        leftMargin=0.85*inch, rightMargin=0.85*inch)
    styles = get_styles()
    story = []
    story.append(Paragraph(title, styles['DocTitle']))
    story.append(Paragraph(subtitle, styles['DocSubtitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#1a3c6e')))
    story.append(Spacer(1, 12))

    q_num = 1
    for section in sections:
        story.append(Paragraph(section['heading'], styles['SectionHead']))
        for qa in section['qas']:
            story.append(Paragraph(f"Q{q_num}. {qa['q']}", styles['QStyle']))
            story.append(Paragraph(f"A: {qa['a']}", styles['AStyle']))
            if 'table' in qa:
                story.append(make_table(qa['table']['headers'], qa['table']['rows']))
                story.append(Spacer(1, 8))
            q_num += 1

    doc.build(story)
    print(f"  ✅ Created: {path} ({q_num-1} Q-A pairs)")
    return path


if __name__ == '__main__':
    from faq_data import ALL_DOCS
    output_dir = os.path.join(os.path.dirname(__file__), 'faq_documents')
    for d in ALL_DOCS:
        build_pdf(d['filename'], d['title'], d['subtitle'], d['sections'], output_dir)
    print(f"\nDone! {len(ALL_DOCS)} PDFs generated in {output_dir}/")
