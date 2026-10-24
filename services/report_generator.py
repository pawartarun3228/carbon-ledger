"""Report Generation Service.
Generates institutional, publication-grade PDF reports via ReportLab
and structured CSV exports for external auditing and data management.
Strictly disclaims regulatory or legal verification status.
"""

import io
import csv
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from services.factor_registry import kg_to_tonnes, load_registry_file

# UN-inspired institutional color palette
PRIMARY_BLUE = colors.HexColor('#004f98')
DEEP_NAVY = colors.HexColor('#0b2545')
SLATE_GRAY = colors.HexColor('#334155')
LIGHT_BG = colors.HexColor('#f8fafc')
BORDER_COLOR = colors.HexColor('#cbd5e1')
MUTED_TEXT = colors.HexColor('#64748b')
TEAL_ACCENT = colors.HexColor('#0d9488')
WHITE = colors.white

def generate_pdf_report(summary_data, org_name="Academic Facility Prototype", user_email="sustainability@university.edu"):
    """Builds a comprehensive, publication-grade PDF report using ReportLab.
    
    Args:
        summary_data (dict): Dict containing 'records', 'aggregation', 'target', 'scenarios', 'recommendations', 'forecast'.
        org_name (str): Organization / facility title
        user_email (str): Contact email
        
    Returns:
        io.BytesIO: Buffer containing the rendered PDF binary.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=DEEP_NAVY,
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=MUTED_TEXT,
        spaceAfter=15
    )
    h2_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=PRIMARY_BLUE,
        spaceBefore=12,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=SLATE_GRAY
    )
    bold_body_style = ParagraphStyle(
        'BoldBodyDark',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=DEEP_NAVY
    )
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=7.5,
        leading=10,
        textColor=MUTED_TEXT
    )

    elements = []

    # 1. Header Banner
    header_table_data = [
        [
            Paragraph("<b>CARBON LEDGER</b><br/><font size=8>GLOBAL SUSTAINABILITY & EMISSIONS INVENTORY</font>", ParagraphStyle('H1', fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=WHITE)),
            Paragraph(f"<b>REPORT DATE:</b> {datetime.now().strftime('%Y-%m-%d')}<br/><b>SYSTEM:</b> Academic Project Prototype", ParagraphStyle('H2', fontName='Helvetica', fontSize=8, leading=11, textColor=WHITE, alignment=2))
        ]
    ]
    header_table = Table(header_table_data, colWidths=[340, 200])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DEEP_NAVY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 15))

    # 2. Title & Metadata
    elements.append(Paragraph("Greenhouse Gas Emissions & Decarbonization Assessment", title_style))
    elements.append(Paragraph(
        f"<b>Facility / Entity:</b> {org_name} &nbsp;|&nbsp; <b>Boundary:</b> Scope 1 (Direct Fuel), Scope 2 (Grid Electricity), Scope 3 (Travel/Commuting) &nbsp;|&nbsp; <b>Status:</b> Unverified Demonstration Dataset",
        subtitle_style
    ))
    elements.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceAfter=12))

    # 3. Executive Summary KPI Table
    agg = summary_data.get('aggregation', {})
    total_kg = agg.get('total_kg', 0.0)
    total_t = agg.get('total_tonnes', 0.0)
    highest_cat = agg.get('highest_category', 'None')
    highest_pct = agg.get('highest_category_pct', 0.0)
    groups = agg.get('groups', {})

    kpi_data = [
        [
            Paragraph(f"<b>TOTAL EMISSIONS</b><br/><font size=14 color='#004f98'><b>{total_kg:,.1f} kg</b></font><br/><font size=8 color='#64748b'>({total_t:.3f} tonnes CO2e)</font>", body_style),
            Paragraph(f"<b>ELECTRICITY (Scope 2)</b><br/><font size=14 color='#004f98'><b>{groups.get('electricity', 0.0):,.1f} kg</b></font><br/><font size=8 color='#64748b'>({kg_to_tonnes(groups.get('electricity', 0.0)):.2f} tonnes)</font>", body_style),
            Paragraph(f"<b>FUEL & TRANSPORT</b><br/><font size=14 color='#004f98'><b>{(groups.get('fuel', 0.0) + groups.get('transportation', 0.0)):,.1f} kg</b></font><br/><font size=8 color='#64748b'>({kg_to_tonnes(groups.get('fuel', 0.0) + groups.get('transportation', 0.0)):.2f} tonnes)</font>", body_style),
            Paragraph(f"<b>PRIMARY DRIVER</b><br/><font size=12 color='#004f98'><b>{highest_cat}</b></font><br/><font size=8 color='#64748b'>({highest_pct:.1f}% of total)</font>", body_style),
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[135, 135, 135, 135])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BG),
        ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(kpi_table)
    elements.append(Spacer(1, 14))

    # 4. Category Breakdown Table
    elements.append(Paragraph("1. Emission Inventory Breakdown by Activity Category", h2_style))
    cat_rows = [
        [
            Paragraph("<b>Category</b>", bold_body_style),
            Paragraph("<b>Scope</b>", bold_body_style),
            Paragraph("<b>Total Quantity</b>", bold_body_style),
            Paragraph("<b>Emission Factor</b>", bold_body_style),
            Paragraph("<b>Emissions (kg CO2e)</b>", bold_body_style),
            Paragraph("<b>Share (%)</b>", bold_body_style),
        ]
    ]
    for cat_key, cat_data in agg.get('categories', {}).items():
        cat_rows.append([
            Paragraph(cat_data.get('name', cat_key), body_style),
            Paragraph(cat_data.get('scope', 'Scope 1'), body_style),
            Paragraph(f"{cat_data.get('count', 0)} entries", body_style),
            Paragraph(f"{cat_data.get('unit', '')}", body_style),
            Paragraph(f"{cat_data.get('kg_co2e', 0.0):,.1f}", body_style),
            Paragraph(f"{cat_data.get('percentage', 0.0):.1f}%", body_style),
        ])
    if len(cat_rows) == 1:
        cat_rows.append([Paragraph("No activity records available.", body_style)] + [Paragraph("", body_style)]*5)

    cat_table = Table(cat_rows, colWidths=[130, 60, 80, 80, 110, 80])
    cat_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#f1f5f9')),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(cat_table)
    elements.append(Spacer(1, 14))

    # 5. Factor Provenance & Reference Standards
    elements.append(Paragraph("2. Emission Factor Registry & Traceability", h2_style))
    registry = load_registry_file()
    factor_rows = [
        [
            Paragraph("<b>Category</b>", bold_body_style),
            Paragraph("<b>Factor Value & Unit</b>", bold_body_style),
            Paragraph("<b>Standard / Source Reference</b>", bold_body_style),
            Paragraph("<b>Region & Year</b>", bold_body_style),
            Paragraph("<b>Version / Status</b>", bold_body_style),
        ]
    ]
    for cat_k, finfo in list(registry.items())[:6]: # Show top 6 relevant
        factor_rows.append([
            Paragraph(finfo.get('name', cat_k), body_style),
            Paragraph(f"{finfo.get('factor')} {finfo.get('factor_unit')}", body_style),
            Paragraph(finfo.get('source', '')[:65] + ("..." if len(finfo.get('source', '')) > 65 else ""), body_style),
            Paragraph(f"{finfo.get('region', '')} ({finfo.get('year', '')})", body_style),
            Paragraph(f"{finfo.get('version', '')} - {finfo.get('status', 'Active')}", body_style),
        ])
    factor_table = Table(factor_rows, colWidths=[110, 110, 170, 80, 70])
    factor_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#f1f5f9')),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(factor_table)
    elements.append(Spacer(1, 14))

    # 6. Net-Zero & Scenario Planning Summary
    target = summary_data.get('target')
    if target:
        elements.append(Paragraph("3. Net-Zero Target & Simulated Decarbonization Pathways", h2_style))
        target_info_data = [
            [
                Paragraph("<b>Baseline Emissions:</b>", bold_body_style),
                Paragraph(f"{target.get('baseline_emission', 0):,.1f} kg CO2e", body_style),
                Paragraph("<b>Target Year:</b>", bold_body_style),
                Paragraph(f"{target.get('target_year', 'N/A')}", body_style),
            ],
            [
                Paragraph("<b>Required Reduction:</b>", bold_body_style),
                Paragraph(f"{target.get('target_reduction_percentage', 0)}% ({target.get('baseline_emission', 0) - target.get('target_emission', 0):,.1f} kg)", body_style),
                Paragraph("<b>Target Allowance:</b>", bold_body_style),
                Paragraph(f"{target.get('target_emission', 0):,.1f} kg CO2e", body_style),
            ]
        ]
        target_table = Table(target_info_data, colWidths=[120, 150, 120, 150])
        target_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BG),
            ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(target_table)
        elements.append(Spacer(1, 10))

    # 7. Recommendations Summary
    recs = summary_data.get('recommendations', [])
    if recs:
        elements.append(Paragraph("4. Prioritized Abatement Interventions", h2_style))
        rec_rows = [
            [
                Paragraph("<b>Priority</b>", bold_body_style),
                Paragraph("<b>Category / Source</b>", bold_body_style),
                Paragraph("<b>Observed Evidence</b>", bold_body_style),
                Paragraph("<b>Est. Savings Potential</b>", bold_body_style),
                Paragraph("<b>Implementation Difficulty</b>", bold_body_style),
            ]
        ]
        for r in recs[:4]:
            rec_rows.append([
                Paragraph(f"<b>{r.get('priority', 'MEDIUM')}</b>", body_style),
                Paragraph(r.get('source', ''), body_style),
                Paragraph(r.get('observed_evidence', r.get('explanation', ''))[:80] + "...", body_style),
                Paragraph(f"{r.get('estimated_savings_kg', 0):,.1f} kg ({r.get('estimated_savings_pct', 0):.0f}%)", body_style),
                Paragraph(r.get('difficulty', 'Medium'), body_style),
            ])
        rec_table = Table(rec_rows, colWidths=[65, 95, 200, 100, 80])
        rec_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
            ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#f1f5f9')),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(rec_table)
        elements.append(Spacer(1, 12))

    # 8. Machine Learning Forecasting Benchmark Metrics (if run)
    forecast_info = summary_data.get('forecast')
    if forecast_info and forecast_info.get('has_sufficient_data'):
        elements.append(Paragraph("5. Predictive Analytics & Forecasting Experiment Benchmark", h2_style))
        exp_rows = [
            [
                Paragraph("<b>Model Evaluated</b>", bold_body_style),
                Paragraph("<b>Features</b>", bold_body_style),
                Paragraph("<b>MAE (kg)</b>", bold_body_style),
                Paragraph("<b>RMSE (kg)</b>", bold_body_style),
                Paragraph("<b>R² Score</b>", bold_body_style),
                Paragraph("<b>Status</b>", bold_body_style),
            ]
        ]
        for m in forecast_info.get('models', []):
            is_best_label = "<b>Selected Best</b>" if m.get('is_best') else "Baseline"
            r2_val = f"{m.get('r2'):.2f}" if m.get('r2') is not None else "N/A"
            exp_rows.append([
                Paragraph(m.get('model_name', ''), body_style),
                Paragraph(m.get('features', ''), body_style),
                Paragraph(f"{m.get('mae', 0.0):.2f}", body_style),
                Paragraph(f"{m.get('rmse', 0.0):.2f}", body_style),
                Paragraph(r2_val, body_style),
                Paragraph(is_best_label, body_style),
            ])
        exp_table = Table(exp_rows, colWidths=[130, 140, 70, 70, 60, 70])
        exp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
            ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#f1f5f9')),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(exp_table)
        elements.append(Spacer(1, 12))

    # 9. Institutional Disclaimer & Data Quality Notice
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_COLOR, spaceAfter=8))
    elements.append(Paragraph(
        "<b>Institutional Data Quality & Research Notice:</b><br/>"
        "This sustainability assessment document was generated by the Carbon Ledger academic prototype platform. "
        "Calculations are performed in accordance with standard GHG Protocol corporate accounting principles using illustrative "
        "emission factors derived from CEA (India), IPCC 2006, and UK DEFRA benchmarks. "
        "This document does not constitute an officially audited greenhouse gas declaration, regulatory compliance certificate, "
        "or legally binding net-zero assurance. Model forecasts represent experimental statistical projections and should be "
        "supplemented with physical building management telemetry.",
        disclaimer_style
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_csv_records_export(records):
    """Exports all activity records to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'ID', 'Date', 'Category', 'Activity_Quantity', 'Unit', 
        'Emission_Factor', 'CO2e_kg', 'CO2e_tonnes', 'Data_Source', 
        'Factor_Source', 'Factor_Version', 'Is_Demo', 'Notes'
    ])
    for r in records:
        co2e_kg = float(r.get('co2e', 0.0))
        writer.writerow([
            r.get('id', ''),
            r.get('date', ''),
            r.get('category', ''),
            r.get('activity', ''),
            r.get('unit', ''),
            r.get('emission_factor', ''),
            round(co2e_kg, 4),
            kg_to_tonnes(co2e_kg),
            r.get('data_source', 'Manual Entry'),
            r.get('factor_source', ''),
            r.get('factor_version', ''),
            'Yes' if r.get('is_demo') else 'No',
            r.get('notes', '')
        ])
    return output.getvalue()

def generate_csv_monthly_summary(monthly_series):
    """Exports monthly aggregated emissions to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Reporting_Month', 'Total_kg_CO2e', 'Total_tonnes_CO2e', 
        'Electricity_kg', 'Fuel_kg', 'Transportation_kg', 'Other_kg'
    ])
    for m in monthly_series:
        writer.writerow([
            m.get('month', ''),
            m.get('total_kg', 0.0),
            m.get('total_tonnes', 0.0),
            m.get('electricity_kg', 0.0),
            m.get('fuel_kg', 0.0),
            m.get('transportation_kg', 0.0),
            m.get('other_kg', 0.0)
        ])
    return output.getvalue()

def generate_csv_template():
    """Generates a downloadable CSV import template with sample records."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['date', 'category', 'activity', 'unit', 'data_source', 'notes'])
    writer.writerow(['2024-01', 'electricity', '3150.0', 'kWh', 'Utility Bill', 'Administrative block main meter'])
    writer.writerow(['2024-01', 'petrol', '420.0', 'litre', 'Fuel Receipt', 'Department shuttle fleet'])
    writer.writerow(['2024-01', 'diesel', '280.0', 'litre', 'Fuel Receipt', 'Campus backup power generator test'])
    writer.writerow(['2024-01', 'transport_bus', '3800.0', 'km', 'Commute Survey', 'Student commuter bus passes'])
    return output.getvalue()
