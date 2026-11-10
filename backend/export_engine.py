"""
SmartBus Export Engine
Generates downloadable analytical CSVs, executive PDF reports for government meetings,
and strictly verified source data exports containing exactly the original 10 columns.

Rules:
- Source-data exports must contain exactly the original 10 columns in the required order.
- Never add an 11th column to source exports.
- Derived analytical summaries are stored and exported separately.
"""

import os
import io
import csv
from typing import Dict, Any, Optional
import pandas as pd
from backend.data_engine import DataEngine, EXACT_SOURCE_SCHEMA
from backend.analytics_engine import AnalyticsEngine
from backend.intelligence_engine import IntelligenceEngine

class ExportEngine:
    def __init__(
        self,
        data_engine: Optional[DataEngine] = None,
        analytics_engine: Optional[AnalyticsEngine] = None,
        intelligence_engine: Optional[IntelligenceEngine] = None
    ):
        self.data_engine = data_engine or DataEngine()
        self.analytics_engine = analytics_engine or AnalyticsEngine(self.data_engine)
        self.intelligence_engine = intelligence_engine or IntelligenceEngine(self.data_engine, self.analytics_engine)

    def export_source_data_csv(self, dataset_id: Optional[str] = None) -> str:
        """
        Exports the verified raw source dataset containing EXACTLY the 10 immutable columns:
        1. Waybill Number
        2. Ticket Number
        3. From Stop
        4. To Stop
        5. Date
        6. Time
        7. Total Psgr
        8. Coll Amt
        9. Uncoll Amt
        10. Unnamed: 9
        Zero extra columns, zero modified columns.
        """
        df = self.data_engine.get_raw_dataframe(dataset_id)
        # Ensure exact column list and order
        df_exact = df[EXACT_SOURCE_SCHEMA]
        output = io.StringIO()
        df_exact.to_csv(output, index=False)
        return output.getvalue()

    def export_od_csv(self, dataset_id: Optional[str] = None) -> str:
        """Exports the Origin-Destination analytical summary as a clean CSV string."""
        od_data = self.analytics_engine.get_origin_destination_intelligence(dataset_id, limit=1000)
        movements = od_data.get("high_volume_movements", [])
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["From Stop", "To Stop", "Movement", "Transaction Count", "Recorded Passenger Quantity", "Recorded Collection Amount (Coll Amt)", "Avg Collection Per Passenger"])
        
        for m in movements:
            writer.writerow([
                m.get("from_stop", ""),
                m.get("to_stop", ""),
                m.get("movement", ""),
                m.get("transaction_count", 0),
                m.get("passenger_quantity", 0),
                m.get("collection_amount", 0.0),
                m.get("avg_collection_per_passenger", 0.0)
            ])
        return output.getvalue()

    def export_waybill_csv(self, dataset_id: Optional[str] = None) -> str:
        """Exports the Waybill analytical metrics as a clean CSV string."""
        wb_data = self.analytics_engine.get_waybill_analytics(dataset_id, limit=1000)
        waybills = wb_data.get("waybills", [])

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Waybill Number", "Record Count", "Recorded Passenger Quantity", "Recorded Collection Amount (Coll Amt)", "Recorded Uncollected Amount (Uncoll Amt)", "Active Hours Count", "First Transaction Time", "Last Transaction Time", "Avg Collection Per Ticket"])

        for w in waybills:
            writer.writerow([
                w.get("waybill_number", ""),
                w.get("record_count", 0),
                w.get("passenger_quantity", 0),
                w.get("collection_amount", 0.0),
                w.get("uncollected_amount", 0.0),
                w.get("active_hours_count", 0),
                w.get("first_transaction_time", ""),
                w.get("last_transaction_time", ""),
                w.get("avg_collection_per_ticket", 0.0)
            ])
        return output.getvalue()

    def export_hourly_csv(self, dataset_id: Optional[str] = None) -> str:
        """Exports hourly time trends as CSV."""
        t_data = self.analytics_engine.get_time_based_analytics(dataset_id)
        trends = t_data.get("hourly_trends", [])

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Hour", "Ticket Transactions", "Recorded Passenger Quantity", "Recorded Collection Amount (Coll Amt)", "Recorded Uncollected Amount (Uncoll Amt)"])

        for t in trends:
            writer.writerow([
                t.get("hour", ""),
                t.get("transaction_count", 0),
                t.get("passenger_quantity", 0),
                t.get("collection_amount", 0.0),
                t.get("uncollected_amount", 0.0)
            ])
        return output.getvalue()

    def generate_executive_pdf(self, dataset_id: Optional[str] = None) -> bytes:
        """
        Generates an official Executive Analytics Report PDF using ReportLab.
        Uses dynamic dates, dataset name, and neutral financial terminology.
        """
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'GovTitle',
            parent=styles['Heading1'],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor('#0b2545'),
            spaceAfter=4
        )
        subtitle_style = ParagraphStyle(
            'GovSubtitle',
            parent=styles['Normal'],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=12
        )
        section_style = ParagraphStyle(
            'GovSection',
            parent=styles['Heading2'],
            fontSize=12,
            leading=15,
            textColor=colors.HexColor('#0b2545'),
            spaceBefore=10,
            spaceAfter=5
        )
        body_style = ParagraphStyle(
            'GovBody',
            parent=styles['Normal'],
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor('#1e293b')
        )

        active = self.data_engine.get_active_dataset()
        filename = active.get("filename", "Active Dataset") if active else "Active Dataset"
        dates = active.get("dates", []) if active else []
        date_str = ", ".join(dates) if dates else "Recorded Time Period"
        is_demo = active.get("is_demo", False) if active else False
        dtype_str = "Demo / Benchmark Dataset" if is_demo else "Official Department Upload"

        kpis = self.analytics_engine.get_executive_kpis(dataset_id)
        insights = self.intelligence_engine.generate_automated_insights(dataset_id)
        time_data = self.analytics_engine.get_time_based_analytics(dataset_id)

        # Header
        story.append(Paragraph("SMARTBUS – KARNATAKA INTELLIGENT BUS TRANSPORT", title_style))
        story.append(Paragraph(f"Executive Operational Briefing | File: {filename} ({dtype_str}) | Dates: {date_str}", subtitle_style))
        story.append(Spacer(1, 8))

        # KPI Summary Table
        story.append(Paragraph("1. Executive Operational Summary", section_style))
        kpi_table_data = [
            ["Metric", "Value", "Metric", "Value"],
            ["Total Ticket Records", f"{kpis.get('total_records', 0):,}", "Distinct Ticket Identifiers", f"{kpis.get('distinct_tickets', 0):,}"],
            ["Recorded Passenger Quantity", f"{kpis.get('recorded_passenger_quantity', 0):,}", "Active Waybill Duty Units", f"{kpis.get('distinct_waybills', 0):,}"],
            ["Recorded Collection (Coll Amt)", f"{kpis.get('recorded_collection_amount', 0):,.2f}", "Recorded Uncollected (Uncoll Amt)", f"{kpis.get('recorded_uncollected_amount', 0):,.2f}"],
            ["Distinct Origin Stops", f"{kpis.get('distinct_origin_stops', 0)}", "Distinct Destination Stops", f"{kpis.get('distinct_destination_stops', 0)}"],
            ["Avg Collection / Ticket", f"{kpis.get('avg_collection_per_ticket', 0):.2f}", "Avg Passengers / Ticket", f"{kpis.get('avg_passengers_per_ticket', 0):.2f}"]
        ]
        t = Table(kpi_table_data, colWidths=[140, 130, 140, 130])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0b2545')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
        ]))
        story.append(t)
        story.append(Spacer(1, 10))

        # Peak Hour Analysis
        story.append(Paragraph("2. Temporal & Dynamic Peak Hours", section_style))
        m_stats = time_data.get("morning_peak_stats", {})
        e_stats = time_data.get("evening_peak_stats", {})
        prim_stats = time_data.get("primary_peak_window", {})
        time_text = (
            f"<b>Overall Peak Transaction Hour:</b> {time_data.get('peak_transaction_hour', 'N/A')}<br/>"
            f"<b>Primary 3-Hour Peak Window ({prim_stats.get('hours', 'N/A')}):</b> {prim_stats.get('total_passengers', 0):,} recorded passengers (Collection: {prim_stats.get('total_collection', 0):,.2f}) — <i>{prim_stats.get('selection_basis', '')}</i><br/>"
            f"<b>Dynamic Morning Window ({m_stats.get('hours', 'N/A')}):</b> {m_stats.get('total_passengers', 0):,} passengers | Collection: {m_stats.get('total_collection', 0):,.2f}<br/>"
            f"<b>Dynamic Evening Window ({e_stats.get('hours', 'N/A')}):</b> {e_stats.get('total_passengers', 0):,} passengers | Collection: {e_stats.get('total_collection', 0):,.2f}"
        )
        story.append(Paragraph(time_text, body_style))
        story.append(Spacer(1, 10))

        # Automated Insights
        story.append(Paragraph("3. Verified Empirical Findings", section_style))
        for ins in insights[:4]:
            p_text = f"<b>[{ins['category']}] {ins['finding']}</b><br/><i>Supporting:</i> {ins['supporting_metric']} | <i>Scope:</i> {ins['dataset_scope']}"
            story.append(Paragraph(p_text, body_style))
            story.append(Spacer(1, 5))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
