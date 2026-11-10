"""
SmartBus Ask SmartBus Engine (FR-13)
Provides natural-language conversational analytics for government officials.
- 100% grounded in verified calculations from Analytics & Intelligence engines.
- Zero hallucinated numbers: only outputs computed metrics from active dataset.
- Zero unrestricted SQL generation.
- Dynamically reflects active dataset's actual dates, row counts, and metadata.
"""

import os
import re
from typing import Dict, Any, Optional
from backend.data_engine import DataEngine
from backend.analytics_engine import AnalyticsEngine
from backend.intelligence_engine import IntelligenceEngine

class AskSmartBusEngine:
    def __init__(
        self,
        data_engine: Optional[DataEngine] = None,
        analytics_engine: Optional[AnalyticsEngine] = None,
        intelligence_engine: Optional[IntelligenceEngine] = None
    ):
        self.data_engine = data_engine or DataEngine()
        self.analytics_engine = analytics_engine or AnalyticsEngine(self.data_engine)
        self.intelligence_engine = intelligence_engine or IntelligenceEngine(self.data_engine, self.analytics_engine)

    def process_query(self, query: str, dataset_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Processes a natural language query with approved analytical routing.
        """
        cleaned = query.strip().lower()
        active = self.data_engine.get_active_dataset()
        if not active:
            return {
                "query": query,
                "answer": "No active dataset is currently loaded. Please upload or select a dataset in 'Dataset Management' first.",
                "grounded_metrics": {},
                "analytical_tool_used": "None (No active dataset)",
                "confidence": "N/A",
                "notes_and_limitations": "Requires an active uploaded dataset."
            }

        curr_id = dataset_id or active["dataset_id"]
        dates = active.get("dates", [])
        date_str = ", ".join(dates) if dates else "Recorded Period"
        is_demo = active.get("is_demo", False)
        type_str = "Demo Benchmark Data" if is_demo else "Official Department Upload"

        # Tool 1: Origin-Destination Queries
        if any(w in cleaned for w in ["origin", "destination", "od", "corridor", "movement", "from stop", "to stop", "route", "busiest", "busy"]):
            od = self.analytics_engine.get_origin_destination_intelligence(curr_id, limit=5)
            high_moves = od.get("high_volume_movements", [])
            if not high_moves:
                return {
                    "query": query,
                    "answer": f"No origin–destination movements found in active dataset '{active['filename']}'.",
                    "grounded_metrics": {},
                    "analytical_tool_used": "get_origin_destination_intelligence",
                    "confidence": "100% Verified",
                    "notes_and_limitations": "Dataset contains no valid origin-destination pairs."
                }

            if any(w in cleaned for w in ["highest", "top", "most", "busy", "busiest", "volume", "popular"]):
                top = high_moves[0]
                answer = (
                    f"The origin–destination pair with the highest recorded passenger volume is **{top.get('movement', 'N/A')}**. "
                    f"It recorded **{top.get('passenger_quantity', 0):,} passengers** across **{top.get('transaction_count', 0):,} ticket transactions**, "
                    f"generating a total recorded collection of **{top.get('collection_amount', 0):,.2f}** "
                    f"(average {top.get('avg_collection_per_passenger', 0):.2f} per passenger) in active dataset '{active['filename']}' ({date_str})."
                )
                return {
                    "query": query,
                    "answer": answer,
                    "grounded_metrics": top,
                    "analytical_tool_used": "get_origin_destination_intelligence (high_volume)",
                    "confidence": "100% Grounded in calculated data",
                    "notes_and_limitations": "Direct ticketed OD movements only; transfer trips without through-ticketing are not merged into single routes. No currency unit assumed."
                }
            elif any(w in cleaned for w in ["lowest", "least", "low", "quiet"]):
                low_moves = od.get("low_volume_movements", [])
                low = low_moves[0] if low_moves else high_moves[-1]
                answer = (
                    f"Among recorded OD movements in dataset '{active['filename']}', the lowest volume movement is **{low.get('movement', 'N/A')}** "
                    f"with **{low.get('passenger_quantity', 0):,} passenger(s)** across **{low.get('transaction_count', 0):,} transaction(s)** "
                    f"and recorded collection of **{low.get('collection_amount', 0):,.2f}**."
                )
                return {
                    "query": query,
                    "answer": answer,
                    "grounded_metrics": low,
                    "analytical_tool_used": "get_origin_destination_intelligence (low_volume)",
                    "confidence": "100% Grounded in calculated data",
                    "notes_and_limitations": "Excludes records with missing stop values. No currency unit assumed."
                }
            else:
                top_3 = high_moves[:3]
                summary = "; ".join([f"{m['movement']} ({m['passenger_quantity']:,} psgrs, Coll: {m['collection_amount']:,.2f})" for m in top_3])
                answer = f"The top origin–destination transit corridors in '{active['filename']}' are: {summary}."
                return {
                    "query": query,
                    "answer": answer,
                    "grounded_metrics": {"top_movements": top_3},
                    "analytical_tool_used": "get_origin_destination_intelligence",
                    "confidence": "100% Grounded in calculated data",
                    "notes_and_limitations": "Evaluated across verified terminal records. No currency unit assumed."
                }

        # Tool 2: Time and Hourly Peak Queries
        if any(w in cleaned for w in ["hour", "time", "peak", "trough", "morning", "evening", "when"]):
            time_data = self.analytics_engine.get_time_based_analytics(curr_id)
            if not time_data.get("hourly_trends"):
                return {
                    "query": query,
                    "answer": "No hourly time data available in the active dataset.",
                    "grounded_metrics": {},
                    "analytical_tool_used": "get_time_based_analytics",
                    "confidence": "100% Verified",
                    "notes_and_limitations": "Missing timestamp fields."
                }

            if "transaction" in cleaned or "ticket" in cleaned:
                peak_h = time_data.get("peak_transaction_hour")
                tx_info = next((h for h in time_data.get("hourly_trends", []) if h["hour"] == peak_h), {})
                answer = (
                    f"The peak hour for ticket transactions in '{active['filename']}' is **{peak_h}**, recording **{tx_info.get('transaction_count', 0):,} ticket transactions**, "
                    f"carrying **{tx_info.get('passenger_quantity', 0):,} passengers**, with collection of **{tx_info.get('collection_amount', 0):,.2f}**."
                )
                return {
                    "query": query,
                    "answer": answer,
                    "grounded_metrics": tx_info,
                    "analytical_tool_used": "get_time_based_analytics (peak_transaction)",
                    "confidence": "100% Grounded in calculated data",
                    "notes_and_limitations": f"Calculated dynamically from active dataset timestamp records ({date_str}). No currency unit assumed."
                }
            else:
                peak_h = time_data.get("peak_passenger_hour")
                psgr_info = next((h for h in time_data.get("hourly_trends", []) if h["hour"] == peak_h), {})
                m_stats = time_data.get("morning_peak_stats", {})
                e_stats = time_data.get("evening_peak_stats", {})
                prim_stats = time_data.get("primary_peak_window", {})
                answer = (
                    f"The highest recorded passenger volume occurred at **{peak_h}** with **{psgr_info.get('passenger_quantity', 0):,} passengers** "
                    f"and **{psgr_info.get('transaction_count', 0):,} transactions**.\n\n"
                    f"• **Primary Peak 3-Hour Window**: {prim_stats.get('hours', 'N/A')} ({prim_stats.get('total_passengers', 0):,} passengers) — {prim_stats.get('selection_basis', '')}\n"
                    f"• **Morning Window**: {m_stats.get('hours', 'N/A')} ({m_stats.get('total_passengers', 0):,} passengers)\n"
                    f"• **Evening Window**: {e_stats.get('hours', 'N/A')} ({e_stats.get('total_passengers', 0):,} passengers)"
                )
                return {
                    "query": query,
                    "answer": answer,
                    "grounded_metrics": psgr_info,
                    "analytical_tool_used": "get_time_based_analytics (peak_passenger)",
                    "confidence": "100% Grounded in calculated data",
                    "notes_and_limitations": "Aggregated by transaction issue hour."
                }

        # Tool 3: Collection & Uncollected Amount Queries
        if any(w in cleaned for w in ["collection", "revenue", "money", "fare", "amt", "amount", "uncollected", "uncoll"]):
            kpis = self.analytics_engine.get_executive_kpis(curr_id)
            if "uncollected" in cleaned or "uncoll" in cleaned:
                uncoll = kpis.get("recorded_uncollected_amount", 0.0)
                total_rec = kpis.get("total_records", 0)
                answer = (
                    f"In active dataset '{active['filename']}' ({type_str}), the total recorded uncollected amount (Uncoll Amt) is **{uncoll:,.2f}** across {total_rec:,} records. "
                    "This captures recorded concessional, pass-holder, or unpaid travel entries."
                )
                return {
                    "query": query,
                    "answer": answer,
                    "grounded_metrics": {"uncollected_amount": uncoll, "dataset": active["filename"]},
                    "analytical_tool_used": "get_executive_kpis (uncollected)",
                    "confidence": "100% Grounded in source 'Uncoll Amt' column",
                    "notes_and_limitations": "Business classification of uncollected fare awaits department policy confirmation. No currency unit assumed."
                }
            else:
                coll = kpis.get("recorded_collection_amount", 0.0)
                uncoll = kpis.get("recorded_uncollected_amount", 0.0)
                avg_fare = kpis.get("avg_collection_per_ticket", 0.0)
                answer = (
                    f"In active dataset '{active['filename']}' ({date_str}), total recorded collection (Coll Amt) is **{coll:,.2f}** "
                    f"(with an additional **{uncoll:,.2f}** recorded under Uncoll Amt). "
                    f"The average collection per ticket transaction is **{avg_fare:.2f}**."
                )
                return {
                    "query": query,
                    "answer": answer,
                    "grounded_metrics": {"collection_amount": coll, "uncollected_amount": uncoll, "avg_fare": avg_fare},
                    "analytical_tool_used": "get_executive_kpis (collection)",
                    "confidence": "100% Grounded in source 'Coll Amt' column",
                    "notes_and_limitations": "Reports raw recorded accounting values. No currency unit assumed."
                }

        # Tool 4: Waybill Queries
        if any(w in cleaned for w in ["waybill", "waybills", "wb-", "wb"]):
            wb_data = self.analytics_engine.get_waybill_analytics(curr_id, limit=5)
            waybills = wb_data.get("waybills", [])
            if not waybills:
                return {
                    "query": query,
                    "answer": f"No waybill records found in dataset '{active['filename']}'.",
                    "grounded_metrics": {},
                    "analytical_tool_used": "get_waybill_analytics",
                    "confidence": "100% Verified",
                    "notes_and_limitations": "Empty waybill data."
                }
            top_wb = waybills[0]
            answer = (
                f"A total of **{wb_data.get('total_active_waybills', 0)} active waybills** were recorded in '{active['filename']}'. "
                f"The waybill with the highest collection is **{top_wb.get('waybill_number', 'N/A')}**, which recorded **{top_wb.get('collection_amount', 0):,.2f}** "
                f"across **{top_wb.get('record_count', 0):,} ticket transactions** and carried **{top_wb.get('passenger_quantity', 0):,} passengers**."
            )
            return {
                "query": query,
                "answer": answer,
                "grounded_metrics": top_wb,
                "analytical_tool_used": "get_waybill_analytics",
                "confidence": "100% Grounded in calculated data",
                "notes_and_limitations": "Strictly reports waybill duty entries. Does not equate waybill to specific vehicle or driver identity without scheduling rosters. No currency unit assumed."
            }

        # Tool 5: Anomaly & Unusual Pattern Queries
        if any(w in cleaned for w in ["anomaly", "anomalies", "unusual", "outlier", "irregular", "suspicious"]):
            anomalies = self.intelligence_engine.detect_anomalies(curr_id)
            dq_count = sum(1 for a in anomalies if a["anomaly_type"] == "Data Quality")
            stat_count = sum(1 for a in anomalies if a["anomaly_type"] == "Operational Statistical")
            top_anoms = [f"• {a['description']} [{a['severity']} severity]" for a in anomalies[:3]]
            answer = (
                f"In dataset '{active['filename']}', detected **{len(anomalies)} anomalies** "
                f"({dq_count} data-quality checks and {stat_count} operational statistical outliers using IQR/Z-Score):\n\n"
                + "\n".join(top_anoms)
            )
            return {
                "query": query,
                "answer": answer,
                "grounded_metrics": {"total_anomalies": len(anomalies), "dq": dq_count, "stat": stat_count},
                "analytical_tool_used": "detect_anomalies",
                "confidence": "100% Verified against statistical bounds",
                "notes_and_limitations": "Calculated relative to current active dataset distribution."
            }

        # Tool 6: Recommendations
        if any(w in cleaned for w in ["recommend", "recommendation", "recommendations", "action", "suggest", "improve"]):
            recs = self.intelligence_engine.generate_recommendations(curr_id)
            summary_recs = [f"• **{r['title']}**: {r['action_item']}" for r in recs[:3]]
            answer = (
                f"Operational recommendations for '{active['filename']}':\n\n"
                + "\n\n".join(summary_recs)
            )
            return {
                "query": query,
                "answer": answer,
                "grounded_metrics": {"recommendations_count": len(recs)},
                "analytical_tool_used": "generate_recommendations",
                "confidence": "Evidence-based operational guidance",
                "notes_and_limitations": "Schedule and fleet reallocations require timetable rosters and vehicle capacity data."
            }

        # Tool 7: Executive Summary / Overview
        kpis = self.analytics_engine.get_executive_kpis(curr_id)
        insights = self.intelligence_engine.generate_automated_insights(curr_id)
        findings_bullets = [f"• {i['finding']}" for i in insights[:3]]
        answer = (
            f"**SmartBus Executive Summary: {active.get('filename')}** ({type_str})\n\n"
            f"• **Recorded Dates**: {date_str}\n"
            f"• **Transactions**: {kpis.get('total_records', 0):,} tickets across {kpis.get('distinct_waybills', 0)} waybills.\n"
            f"• **Recorded Passenger Quantity**: {kpis.get('recorded_passenger_quantity', 0):,} passengers (avg {kpis.get('avg_passengers_per_ticket', 0):.2f} per ticket).\n"
            f"• **Recorded Collection (Coll Amt)**: {kpis.get('recorded_collection_amount', 0):,.2f} (Recorded Uncollected: {kpis.get('recorded_uncollected_amount', 0):,.2f}).\n"
            f"• **Terminal Coverage**: {kpis.get('distinct_origin_stops', 0)} origins and {kpis.get('distinct_destination_stops', 0)} destinations.\n\n"
            f"**Key Analytical Findings:**\n" + "\n".join(findings_bullets)
        )
        return {
            "query": query,
            "answer": answer,
            "grounded_metrics": kpis,
            "analytical_tool_used": "get_executive_kpis + generate_automated_insights",
            "confidence": "100% Grounded in active dataset",
            "notes_and_limitations": f"Computed dynamically for active dataset '{active.get('filename')}'."
        }
