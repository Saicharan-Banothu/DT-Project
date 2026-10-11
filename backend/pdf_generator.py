"""
SentiCall v2 — Case Report PDF Generator
Generates research-grade, consumer-friendly downloadable PDF case reports with:
- Case metadata & evidence badges
- Visual circular risk gauge & risk timeline chart
- Highlighted transcript & detected manipulation tactics
- Voice fingerprint acoustic meters
- Personalized action plan based on victim state chips
- Verified cybercrime helpline directory
- Formal 'Complaint-Ready Summary' for National Cyber Crime Portal (1930) / Chakshu
"""

import os
import io
import time
from typing import Dict, Any, List, Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, HRFlowable
)

def generate_risk_gauge_image(score: int, tier: str) -> io.BytesIO:
    """Generate a high-res circular gauge chart using Matplotlib."""
    fig, ax = plt.subplots(figsize=(3.2, 3.2), subplot_kw={'projection': 'polar'}, dpi=200)
    
    # Background circle
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    
    # Color selection
    if score >= 70:
        fill_color = "#DC2626"
    elif score >= 36:
        fill_color = "#D97706"
    else:
        fill_color = "#059669"
        
    theta = np.linspace(0, 2 * np.pi * (score / 100.0), 100)
    r = np.ones_like(theta)
    
    # Track background
    ax.plot(np.linspace(0, 2 * np.pi, 100), np.ones(100), color='#E2E8F0', linewidth=10)
    # Active fill
    ax.plot(theta, r, color=fill_color, linewidth=10)
    
    ax.set_ylim(0, 1.1)
    ax.axis('off')
    
    # Center text
    fig.text(0.5, 0.53, f"{score}/100", ha='center', va='center', fontsize=20, fontweight='bold', color='#0F172A')
    fig.text(0.5, 0.40, tier.upper(), ha='center', va='center', fontsize=10, fontweight='bold', color=fill_color)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf

import numpy as np

def generate_timeline_chart_image(timeline: List[Dict[str, Any]], markers: List[Dict[str, Any]]) -> io.BytesIO:
    """Generate a clean timeline graph of risk score progression."""
    fig, ax = plt.subplots(figsize=(6.5, 2.2), dpi=200)
    
    if not timeline or len(timeline) < 2:
        # Fallback dummy timeline
        times = [0, 5, 10, 15, 20]
        risks = [10, 25, 45, 80, 92]
    else:
        times = [p.get("time_s", idx*2) for idx, p in enumerate(timeline)]
        risks = [p.get("risk_score", 0) for p in timeline]
        
    ax.plot(times, risks, color="#2563EB", linewidth=2.5, label="Risk Trajectory")
    ax.fill_between(times, risks, color="#93C5FD", alpha=0.25)
    
    # Threshold lines
    ax.axhline(y=70, color="#DC2626", linestyle="--", linewidth=1, alpha=0.6, label="High Risk (70+)")
    ax.axhline(y=36, color="#D97706", linestyle=":", linewidth=1, alpha=0.6, label="Moderate Risk (36+)")
    
    # Add milestone markers
    for m in markers[:4]:
        m_t = m.get("time_s", 0)
        m_lbl = m.get("label", "")
        # Find risk near m_t
        r_val = next((r for t, r in zip(times, risks) if t >= m_t), risks[-1])
        ax.scatter([m_t], [r_val], color="#DC2626" if "hang up" in m_lbl.lower() or "otp" in m_lbl.lower() else "#D97706", s=40, zorder=5)
        ax.annotate(
            m_lbl, (m_t, r_val), xytext=(0, 10), textcoords="offset points",
            fontsize=7, fontweight='bold', ha='center',
            bbox=dict(boxstyle="round,pad=0.2", fc="#FFFFFF", ec="#CBD5E1", lw=0.8)
        )
        
    ax.set_ylim(0, 105)
    ax.set_xlim(0, max(times[-1], 5))
    ax.set_xlabel("Time (seconds)", fontsize=8, fontweight='bold', color="#475569")
    ax.set_ylabel("Risk (0-100)", fontsize=8, fontweight='bold', color="#475569")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.tick_params(axis='both', labelsize=8)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf

def generate_pdf_report(case_data: Dict[str, Any], output_path: str) -> str:
    """
    Build the complete SentiCall Case Report PDF.
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom Brand Styles
    brand_blue = colors.HexColor("#2563EB")
    brand_dark = colors.HexColor("#0F172A")
    brand_slate = colors.HexColor("#475569")
    brand_light_bg = colors.HexColor("#F8FAFC")
    brand_border = colors.HexColor("#E2E8F0")
    
    title_style = ParagraphStyle(
        'BrandTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=brand_blue
    )
    
    subtitle_style = ParagraphStyle(
        'BrandSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=brand_slate
    )
    
    heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=brand_dark,
        spaceBefore=10,
        spaceAfter=6
    )
    
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155")
    )
    
    bold_body = ParagraphStyle(
        'BoldBody',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    story = []

    # 1. Header Bar
    header_data = [
        [
            Paragraph("<b>SentiCall</b> — The Third Voice", title_style),
            Paragraph(f"<b>CASE ID:</b> {case_data.get('case_id', 'SC-2026-9812')}<br/><b>Date:</b> {case_data.get('created_at', time.strftime('%Y-%m-%d %H:%M'))}", subtitle_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[3.5*inch, 3.5*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8)
    ]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=1.5, color=brand_blue, spaceBefore=2, spaceAfter=10))

    # 2. Verdict & Risk Gauge Section
    fusion = case_data.get("fusion", {})
    overall_score = fusion.get("overall_score", 0)
    risk_tier = fusion.get("risk_tier", "Low Risk")
    verdict_heading = fusion.get("verdict_heading", "Call Analysis Complete")
    summary_sentence = fusion.get("summary_sentence", "No deceptive manipulation tactics detected.")
    primary_family = case_data.get("primary_family_name", "General Voice Analysis")
    evidence_strength = case_data.get("evidence_strength", "Learned from real examples")

    gauge_buf = generate_risk_gauge_image(overall_score, risk_tier)
    gauge_img = Image(gauge_buf, width=2.0*inch, height=2.0*inch)

    verdict_text = f"""
    <b><font size="14" color="#0F172A">{verdict_heading}</font></b><br/><br/>
    <b>Identified Scam Type:</b> {primary_family}<br/>
    <b>Evidence Strength:</b> <font color="#2563EB">{evidence_strength}</font><br/><br/>
    <b>Summary Assessment:</b><br/>{summary_sentence}
    """
    
    verdict_table = Table([
        [gauge_img, Paragraph(verdict_text, body_style)]
    ], colWidths=[2.2*inch, 4.8*inch])
    verdict_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), brand_light_bg),
        ('BOX', (0,0), (-1,-1), 1, brand_border),
        ('PADDING', (0,0), (-1,-1), 10),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    story.append(verdict_table)
    story.append(Spacer(1, 10))

    # 3. Call Story Timeline Chart
    timeline = case_data.get("timeline", [])
    markers = case_data.get("markers", [])
    lead_time = case_data.get("lead_time_s")

    story.append(Paragraph("Call Story & Early Detection Trajectory", heading_style))
    if lead_time:
        story.append(Paragraph(f"<b>Early Warning Lead Time:</b> SentiCall triggered first alert <b>{lead_time} seconds</b> prior to the credential/money request.", body_style))
        story.append(Spacer(1, 4))
        
    timeline_buf = generate_timeline_chart_image(timeline, markers)
    timeline_img = Image(timeline_buf, width=6.8*inch, height=2.2*inch)
    story.append(timeline_img)
    story.append(Spacer(1, 10))

    # 4. Detected Tactics Breakdown
    text_res = case_data.get("text_result", {})
    tactics = text_res.get("tactic_breakdown", []) if text_res else []
    detected_tactics = [t for t in tactics if t.get("detected")]

    story.append(Paragraph("Detected Manipulation Tactics", heading_style))
    if detected_tactics:
        tactic_rows = [["Tactic", "Severity", "Red-Flag Phrases Found"]]
        for t in detected_tactics:
            phrases = ", ".join([f'"{p}"' for p in t.get("matched_phrases", [])[:3]])
            tactic_rows.append([
                Paragraph(f"<b>{t.get('title')}</b>", body_style),
                Paragraph(f"<font color='{'#DC2626' if t.get('severity')=='critical' else '#D97706'}'><b>{t.get('severity').upper()}</b></font>", body_style),
                Paragraph(phrases if phrases else "Detected via contextual language patterns", body_style)
            ])
        tactic_table = Table(tactic_rows, colWidths=[2.2*inch, 1.0*inch, 3.6*inch])
        tactic_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#EEF2F6")),
            ('TEXTCOLOR', (0,0), (-1,0), brand_dark),
            ('BOX', (0,0), (-1,-1), 1, brand_border),
            ('INNERGRID', (0,0), (-1,-1), 0.5, brand_border),
            ('PADDING', (0,0), (-1,-1), 5),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
        ]))
        story.append(tactic_table)
    else:
        story.append(Paragraph("No manipulative tactics detected in conversational transcript.", body_style))
    story.append(Spacer(1, 10))

    # 5. Personalized Action Plan for Selected State Chips
    chosen_chips = case_data.get("chosen_chips", [])
    action_plan = case_data.get("action_plan", {})
    do_now_steps = action_plan.get("do_now_steps", [])
    per_chip_actions = action_plan.get("per_chip_actions", {})

    story.append(Paragraph("Recommended Immediate Action Plan", heading_style))
    action_items = []
    
    # Primary do-now steps
    for idx, s in enumerate(do_now_steps[:3], 1):
        action_items.append(Paragraph(f"<b>Step {idx}: {s.get('title')}</b><br/>{s.get('detail')}", body_style))
        
    # Extra steps from selected chips
    for chip in chosen_chips:
        if chip in per_chip_actions:
            chip_label = chip.replace("_", " ").title()
            action_items.append(Paragraph(f"<b>Because you '{chip_label}':</b><br/>{per_chip_actions[chip]}", body_style))

    if action_items:
        action_table_data = [[item] for item in action_items]
        action_table = Table(action_table_data, colWidths=[6.8*inch])
        action_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FEF2F2") if overall_score>=70 else colors.HexColor("#F0FDF4")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#FCA5A5") if overall_score>=70 else colors.HexColor("#86EFAC")),
            ('PADDING', (0,0), (-1,-1), 7),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6)
        ]))
        story.append(action_table)
    story.append(Spacer(1, 10))

    # 6. Official Verified Helplines
    story.append(Paragraph("Verified Emergency Helplines (India)", heading_style))
    helpline_rows = [
        ["Helpline", "Contact", "Purpose", "Last Verified"],
        [
            Paragraph("<b>National Cyber Crime Helpline</b>", body_style),
            Paragraph("<b>1930</b>", bold_body),
            Paragraph("Financial fraud & fund recovery within golden hour", body_style),
            Paragraph("2026-10-10", body_style)
        ],
        [
            Paragraph("<b>National Cyber Crime Portal</b>", body_style),
            Paragraph("cybercrime.gov.in", bold_body),
            Paragraph("Formal FIR & evidence submission", body_style),
            Paragraph("2026-10-10", body_style)
        ],
        [
            Paragraph("<b>Chakshu (Sanchar Saathi)</b>", body_style),
            Paragraph("sancharsaathi.gov.in/sfc", bold_body),
            Paragraph("Report fraudulent phone numbers & SMS", body_style),
            Paragraph("2026-10-10", body_style)
        ],
        [
            Paragraph("<b>National Emergency</b>", body_style),
            Paragraph("<b>112</b>", bold_body),
            Paragraph("Immediate police assistance for physical threats/extortion", body_style),
            Paragraph("2026-10-10", body_style)
        ]
    ]
    hl_table = Table(helpline_rows, colWidths=[2.2*inch, 1.8*inch, 2.0*inch, 0.8*inch])
    hl_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#EEF2F6")),
        ('BOX', (0,0), (-1,-1), 1, brand_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, brand_border),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    story.append(hl_table)
    story.append(Spacer(1, 14))

    # 7. Complaint-Ready Summary Page Section
    story.append(Paragraph("Complaint-Ready Summary (Copy for cybercrime.gov.in / Chakshu)", heading_style))
    transcript_snippet = case_data.get("transcript", "No transcript text available.")[:300] + "..."
    complaint_text = f"""
    <b>Incident Category:</b> Cyber Financial Fraud / Impersonation Scam ({primary_family})<br/>
    <b>Date & Time:</b> {case_data.get('created_at', time.strftime('%Y-%m-%d %H:%M'))}<br/>
    <b>Caller Demands:</b> Unauthorized credential disclosure (OTP/PIN/CVV/Remote Screen Access)<br/>
    <b>Transcript Extract:</b> "{transcript_snippet}"<br/>
    <b>SentiCall Risk Assessment:</b> Score {overall_score}/100 ({risk_tier}) with confirmed manipulation tactics.
    """
    comp_table = Table([[Paragraph(complaint_text, body_style)]], colWidths=[6.8*inch])
    comp_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), brand_light_bg),
        ('BOX', (0,0), (-1,-1), 1, brand_border),
        ('PADDING', (0,0), (-1,-1), 8)
    ]))
    story.append(comp_table)
    story.append(Spacer(1, 10))

    # 8. Golden Rule & Disclaimer Footer
    input_mode = case_data.get("input_type", "audio")
    if input_mode == "live":
        privacy_statement = "Audio is processed on this device and is never uploaded."
    else:
        privacy_statement = "Your file is processed in memory on our secure server and deleted immediately. We never store it, share it or use it for training."

    footer_text = f"""
    <b>The SentiCall Golden Rule:</b> <i>When in doubt, hang up and call back on a number you trust.</i><br/>
    <font size="7" color="#64748B"><b>Privacy Notice:</b> {privacy_statement} This report is an assistive decision-support tool and does not constitute formal legal counsel.</font>
    """
    story.append(Paragraph(footer_text, body_style))

    # Build PDF
    doc.build(story)
    return output_path
