"""
SmartBus Analytics Engine
Executes verified SQL and vector aggregations for Executive KPIs, Passenger/Ticket Analytics,
Revenue/Collection, Origin-Destination Movements, Hourly Time Trends, and Waybill Intelligence.

Principles:
- Strict separation of ticket transaction counts from recorded passenger quantities.
- Neutral terminology: 'Recorded Collection Amount (Coll Amt)' and 'Recorded Uncollected Amount (Uncoll Amt)'.
- Dynamic peak-window detection derived from actual recorded hourly distributions.
- No manufactured route names, vehicle identifiers, or driver identities.
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import sqlite3
from backend.data_engine import DataEngine

class AnalyticsEngine:
    def __init__(self, data_engine: Optional[DataEngine] = None):
        self.data_engine = data_engine or DataEngine()

    def get_executive_kpis(self, dataset_id: Optional[str] = None, waybill_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates executive KPIs with strictly verified aggregations (FR-03).
        Guarantees that passenger sums are NOT labeled as unique passengers.
        """
        active_id = dataset_id or (self.data_engine.get_active_dataset() or {}).get("dataset_id")
        if not active_id:
            return {
                "total_records": 0,
                "distinct_tickets": 0,
                "recorded_passenger_quantity": 0,
                "recorded_collection_amount": 0.0,
                "recorded_uncollected_amount": 0.0,
                "distinct_waybills": 0,
                "distinct_origin_stops": 0,
                "distinct_destination_stops": 0,
                "avg_collection_per_ticket": 0.0,
                "avg_passengers_per_ticket": 0.0
            }

        with self.data_engine._get_connection() as conn:
            cursor = conn.cursor()
            
            where_clause = "WHERE dataset_id = ?"
            params: List[Any] = [active_id]
            if waybill_filter:
                where_clause += " AND waybill_number = ?"
                params.append(waybill_filter)

            query = f"""
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT ticket_number) as distinct_tickets,
                SUM(total_psgr) as recorded_passenger_quantity,
                SUM(coll_amt) as recorded_collection_amount,
                SUM(uncoll_amt) as recorded_uncollected_amount,
                COUNT(DISTINCT waybill_number) as distinct_waybills,
                COUNT(DISTINCT from_stop) as distinct_origin_stops,
                COUNT(DISTINCT to_stop) as distinct_destination_stops
            FROM raw_tickets
            {where_clause}
            """
            cursor.execute(query, params)
            row = cursor.fetchone()

            total_records = row["total_records"] or 0
            distinct_tickets = row["distinct_tickets"] or 0
            recorded_psgr = row["recorded_passenger_quantity"] or 0
            coll_amt = round(row["recorded_collection_amount"] or 0.0, 2)
            uncoll_amt = round(row["recorded_uncollected_amount"] or 0.0, 2)
            distinct_wb = row["distinct_waybills"] or 0
            distinct_orig = row["distinct_origin_stops"] or 0
            distinct_dest = row["distinct_destination_stops"] or 0

            avg_coll_per_ticket = round(coll_amt / total_records, 2) if total_records > 0 else 0.0
            avg_psgr_per_ticket = round(recorded_psgr / total_records, 2) if total_records > 0 else 0.0

            return {
                "total_records": total_records,
                "distinct_tickets": distinct_tickets,
                "recorded_passenger_quantity": recorded_psgr,
                "recorded_collection_amount": coll_amt,
                "recorded_uncollected_amount": uncoll_amt,
                "distinct_waybills": distinct_wb,
                "distinct_origin_stops": distinct_orig,
                "distinct_destination_stops": distinct_dest,
                "avg_collection_per_ticket": avg_coll_per_ticket,
                "avg_passengers_per_ticket": avg_psgr_per_ticket
            }

    def get_passenger_analytics(self, dataset_id: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """
        Analyzes passenger quantities and ticket distributions (FR-04).
        """
        active_id = dataset_id or (self.data_engine.get_active_dataset() or {}).get("dataset_id")
        if not active_id:
            return {
                "passenger_count_distribution": {},
                "top_origins_by_passengers": [],
                "top_destinations_by_passengers": [],
                "top_movements_by_passengers": [],
                "transactions_vs_passengers_ratio": 0.0
            }

        with self.data_engine._get_connection() as conn:
            cursor = conn.cursor()

            # Passenger count per ticket distribution
            cursor.execute("""
            SELECT total_psgr, COUNT(*) as ticket_count
            FROM raw_tickets
            WHERE dataset_id = ?
            GROUP BY total_psgr
            ORDER BY total_psgr ASC
            """, (active_id,))
            psgr_dist_rows = cursor.fetchall()
            psgr_dist = {str(r["total_psgr"]): r["ticket_count"] for r in psgr_dist_rows}

            # Top origins by recorded passenger volume
            cursor.execute("""
            SELECT from_stop as stop_name, SUM(total_psgr) as total_passengers, COUNT(*) as ticket_count
            FROM raw_tickets
            WHERE dataset_id = ? AND from_stop IS NOT NULL AND trim(from_stop) != ''
            GROUP BY from_stop
            ORDER BY total_passengers DESC
            LIMIT ?
            """, (active_id, limit))
            top_origins = [dict(r) for r in cursor.fetchall()]

            # Top destinations by recorded passenger volume
            cursor.execute("""
            SELECT to_stop as stop_name, SUM(total_psgr) as total_passengers, COUNT(*) as ticket_count
            FROM raw_tickets
            WHERE dataset_id = ? AND to_stop IS NOT NULL AND trim(to_stop) != ''
            GROUP BY to_stop
            ORDER BY total_passengers DESC
            LIMIT ?
            """, (active_id, limit))
            top_destinations = [dict(r) for r in cursor.fetchall()]

            # Top OD movements by passengers
            cursor.execute("""
            SELECT from_stop, to_stop, 
                   (from_stop || ' ➔ ' || to_stop) as movement,
                   SUM(total_psgr) as total_passengers,
                   COUNT(*) as ticket_count
            FROM raw_tickets
            WHERE dataset_id = ? AND from_stop IS NOT NULL AND to_stop IS NOT NULL
            GROUP BY from_stop, to_stop
            ORDER BY total_passengers DESC
            LIMIT ?
            """, (active_id, limit))
            top_movements = [dict(r) for r in cursor.fetchall()]

            # Ratio of passengers to tickets
            cursor.execute("""
            SELECT COUNT(*) as t_count, SUM(total_psgr) as p_sum FROM raw_tickets WHERE dataset_id = ?
            """, (active_id,))
            totals = cursor.fetchone()
            t_count = totals["t_count"] or 0
            p_sum = totals["p_sum"] or 0
            ratio = round(p_sum / t_count, 2) if t_count > 0 else 0.0

            return {
                "passenger_count_distribution": psgr_dist,
                "top_origins_by_passengers": top_origins,
                "top_destinations_by_passengers": top_destinations,
                "top_movements_by_passengers": top_movements,
                "transactions_vs_passengers_ratio": ratio
            }

    def get_revenue_analytics(self, dataset_id: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """
        Analyzes recorded collection and uncollected amounts (FR-05).
        Uses neutral source column terminology (Coll Amt / Uncoll Amt).
        """
        active_id = dataset_id or (self.data_engine.get_active_dataset() or {}).get("dataset_id")
        if not active_id:
            return {
                "total_collection": 0.0,
                "total_uncollected": 0.0,
                "collection_distribution": {},
                "top_movements_by_collection": [],
                "top_waybills_by_collection": [],
                "uncollected_by_waybill": []
            }

        with self.data_engine._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
            SELECT SUM(coll_amt) as total_coll, SUM(uncoll_amt) as total_uncoll
            FROM raw_tickets WHERE dataset_id = ?
            """, (active_id,))
            totals = cursor.fetchone()
            total_coll = round(totals["total_coll"] or 0.0, 2)
            total_uncoll = round(totals["total_uncoll"] or 0.0, 2)

            # Ticket collection denomination brackets (Source units, assumed INR)
            cursor.execute("""
            SELECT 
                SUM(CASE WHEN coll_amt <= 10 THEN 1 ELSE 0 END) as b_0_10,
                SUM(CASE WHEN coll_amt > 10 AND coll_amt <= 20 THEN 1 ELSE 0 END) as b_11_20,
                SUM(CASE WHEN coll_amt > 20 AND coll_amt <= 30 THEN 1 ELSE 0 END) as b_21_30,
                SUM(CASE WHEN coll_amt > 30 AND coll_amt <= 50 THEN 1 ELSE 0 END) as b_31_50,
                SUM(CASE WHEN coll_amt > 50 THEN 1 ELSE 0 END) as b_51_plus
            FROM raw_tickets
            WHERE dataset_id = ?
            """, (active_id,))
            bracket_row = cursor.fetchone()
            brackets = {
                "0 - 10": bracket_row["b_0_10"] or 0,
                "11 - 20": bracket_row["b_11_20"] or 0,
                "21 - 30": bracket_row["b_21_30"] or 0,
                "31 - 50": bracket_row["b_31_50"] or 0,
                "51+": bracket_row["b_51_plus"] or 0
            }

            # Top movements by recorded collection
            cursor.execute("""
            SELECT from_stop, to_stop,
                   (from_stop || ' ➔ ' || to_stop) as movement,
                   ROUND(SUM(coll_amt), 2) as collection_amount,
                   SUM(total_psgr) as total_passengers,
                   COUNT(*) as ticket_count
            FROM raw_tickets
            WHERE dataset_id = ? AND from_stop IS NOT NULL AND to_stop IS NOT NULL
            GROUP BY from_stop, to_stop
            ORDER BY collection_amount DESC
            LIMIT ?
            """, (active_id, limit))
            top_movements = [dict(r) for r in cursor.fetchall()]

            # Top waybills by recorded collection
            cursor.execute("""
            SELECT waybill_number,
                   ROUND(SUM(coll_amt), 2) as collection_amount,
                   ROUND(SUM(uncoll_amt), 2) as uncollected_amount,
                   SUM(total_psgr) as total_passengers,
                   COUNT(*) as ticket_count
            FROM raw_tickets
            WHERE dataset_id = ?
            GROUP BY waybill_number
            ORDER BY collection_amount DESC
            LIMIT ?
            """, (active_id, limit))
            top_waybills = [dict(r) for r in cursor.fetchall()]

            # Top uncollected amounts by waybill
            cursor.execute("""
            SELECT waybill_number,
                   ROUND(SUM(uncoll_amt), 2) as uncollected_amount,
                   ROUND(SUM(coll_amt), 2) as collection_amount,
                   COUNT(*) as ticket_count
            FROM raw_tickets
            WHERE dataset_id = ? AND uncoll_amt > 0
            GROUP BY waybill_number
            ORDER BY uncollected_amount DESC
            LIMIT ?
            """, (active_id, limit))
            uncoll_waybills = [dict(r) for r in cursor.fetchall()]

            return {
                "total_collection": total_coll,
                "total_uncollected": total_uncoll,
                "collection_distribution": brackets,
                "top_movements_by_collection": top_movements,
                "top_waybills_by_collection": top_waybills,
                "uncollected_by_waybill": uncoll_waybills
            }

    def get_origin_destination_intelligence(self, dataset_id: Optional[str] = None, limit: int = 15) -> Dict[str, Any]:
        """
        Origin-Destination (OD) movements, volumes, and flows (FR-06).
        Does not manufacture fake route numbers or fake coordinates.
        """
        active_id = dataset_id or (self.data_engine.get_active_dataset() or {}).get("dataset_id")
        if not active_id:
            return {
                "high_volume_movements": [],
                "low_volume_movements": [],
                "net_flows": []
            }

        with self.data_engine._get_connection() as conn:
            cursor = conn.cursor()

            # Top high volume movements
            cursor.execute("""
            SELECT 
                from_stop, 
                to_stop,
                (from_stop || ' ➔ ' || to_stop) as movement,
                COUNT(*) as transaction_count,
                SUM(total_psgr) as passenger_quantity,
                ROUND(SUM(coll_amt), 2) as collection_amount,
                ROUND(SUM(coll_amt) / CAST(MAX(1, SUM(total_psgr)) AS REAL), 2) as avg_collection_per_passenger
            FROM raw_tickets
            WHERE dataset_id = ? AND from_stop IS NOT NULL AND to_stop IS NOT NULL
            GROUP BY from_stop, to_stop
            ORDER BY passenger_quantity DESC
            LIMIT ?
            """, (active_id, limit))
            high_volume_movements = [dict(r) for r in cursor.fetchall()]

            # Low volume movements
            cursor.execute("""
            SELECT 
                from_stop, 
                to_stop,
                (from_stop || ' ➔ ' || to_stop) as movement,
                COUNT(*) as transaction_count,
                SUM(total_psgr) as passenger_quantity,
                ROUND(SUM(coll_amt), 2) as collection_amount,
                ROUND(SUM(coll_amt) / CAST(MAX(1, SUM(total_psgr)) AS REAL), 2) as avg_collection_per_passenger
            FROM raw_tickets
            WHERE dataset_id = ? AND from_stop IS NOT NULL AND to_stop IS NOT NULL
            GROUP BY from_stop, to_stop
            ORDER BY passenger_quantity ASC, transaction_count ASC
            LIMIT ?
            """, (active_id, limit))
            low_volume_movements = [dict(r) for r in cursor.fetchall()]

            # Net passenger flows at terminals (Departures vs Arrivals)
            cursor.execute("""
            SELECT stop_name, 
                   SUM(departed) as departed_passengers, 
                   SUM(arrived) as arrived_passengers,
                   (SUM(departed) - SUM(arrived)) as net_passenger_flow
            FROM (
                SELECT from_stop as stop_name, SUM(total_psgr) as departed, 0 as arrived
                FROM raw_tickets WHERE dataset_id = ? AND from_stop IS NOT NULL AND trim(from_stop) != '' GROUP BY from_stop
                UNION ALL
                SELECT to_stop as stop_name, 0 as departed, SUM(total_psgr) as arrived
                FROM raw_tickets WHERE dataset_id = ? AND to_stop IS NOT NULL AND trim(to_stop) != '' GROUP BY to_stop
            )
            GROUP BY stop_name
            ORDER BY (SUM(departed) + SUM(arrived)) DESC
            LIMIT 15
            """, (active_id, active_id))
            net_flows = [dict(r) for r in cursor.fetchall()]

            return {
                "high_volume_movements": high_volume_movements,
                "low_volume_movements": low_volume_movements,
                "net_flows": net_flows
            }

    def get_time_based_analytics(self, dataset_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Hourly ticket, passenger, and collection trends (FR-07).
        Dynamically detects peak operating windows based on actual recorded distribution
        without hardcoded time ranges.
        """
        active_id = dataset_id or (self.data_engine.get_active_dataset() or {}).get("dataset_id")
        if not active_id:
            return {
                "hourly_trends": [],
                "peak_transaction_hour": "N/A",
                "peak_passenger_hour": "N/A",
                "peak_collection_hour": "N/A",
                "trough_hour": "N/A",
                "morning_peak_stats": {},
                "evening_peak_stats": {}
            }

        with self.data_engine._get_connection() as conn:
            cursor = conn.cursor()

            # Group by hour substring (time_str HH:MM:SS)
            cursor.execute("""
            SELECT 
                SUBSTR(time_str, 1, 2) as hour_str,
                COUNT(*) as transaction_count,
                SUM(total_psgr) as passenger_quantity,
                ROUND(SUM(coll_amt), 2) as collection_amount,
                ROUND(SUM(uncoll_amt), 2) as uncollected_amount
            FROM raw_tickets
            WHERE dataset_id = ? AND time_str IS NOT NULL AND LENGTH(time_str) >= 2
            GROUP BY SUBSTR(time_str, 1, 2)
            ORDER BY hour_str ASC
            """, (active_id,))
            rows = cursor.fetchall()
            
            hourly_data = []
            for r in rows:
                h_str = r["hour_str"]
                h_int = int(h_str) if h_str.isdigit() else 0
                label = f"{h_int:02d}:00"
                hourly_data.append({
                    "hour": label,
                    "hour_int": h_int,
                    "transaction_count": r["transaction_count"],
                    "passenger_quantity": r["passenger_quantity"],
                    "collection_amount": r["collection_amount"],
                    "uncollected_amount": r["uncollected_amount"]
                })

            if not hourly_data:
                return {
                    "hourly_trends": [],
                    "peak_transaction_hour": "N/A",
                    "peak_passenger_hour": "N/A",
                    "peak_collection_hour": "N/A",
                    "trough_hour": "N/A",
                    "morning_peak_stats": {},
                    "evening_peak_stats": {}
                }

            sorted_by_tx = sorted(hourly_data, key=lambda x: x["transaction_count"], reverse=True)
            sorted_by_psgr = sorted(hourly_data, key=lambda x: x["passenger_quantity"], reverse=True)
            sorted_by_coll = sorted(hourly_data, key=lambda x: x["collection_amount"], reverse=True)
            sorted_by_trough = sorted(hourly_data, key=lambda x: x["transaction_count"])

            peak_tx_hour = sorted_by_tx[0]["hour"] if sorted_by_tx else "N/A"
            peak_psgr_hour = sorted_by_psgr[0]["hour"] if sorted_by_psgr else "N/A"
            peak_coll_hour = sorted_by_coll[0]["hour"] if sorted_by_coll else "N/A"
            trough_hour = sorted_by_trough[0]["hour"] if sorted_by_trough else "N/A"

            # Dynamic Peak Window Detection (FR-07):
            # Window selection is calculated strictly based on recorded passenger quantity.
            # Ties are resolved deterministically: higher collection amount breaks ties, then earlier chronological start hour.
            hourly_map = {h["hour_int"]: h for h in hourly_data}

            def evaluate_window(start_h: int):
                # Evaluates 3 consecutive hours: start_h, start_h+1, start_h+2
                hours = [start_h, start_h + 1, start_h + 2]
                psgr_sum = sum(hourly_map.get(h, {}).get("passenger_quantity", 0) for h in hours)
                coll_sum = sum(hourly_map.get(h, {}).get("collection_amount", 0.0) for h in hours)
                tx_sum = sum(hourly_map.get(h, {}).get("transaction_count", 0) for h in hours)
                return {
                    "start_hour": start_h,
                    "hours": f"{start_h:02d}:00 - {start_h+3:02d}:00",
                    "detected_hours": hours,
                    "total_passengers": psgr_sum,
                    "total_collection": round(coll_sum, 2),
                    "total_transactions": tx_sum
                }

            # 1. Primary Peak Window across the entire 24-hour day
            best_primary = None
            for h in range(0, 22):
                w = evaluate_window(h)
                if best_primary is None:
                    best_primary = w
                elif w["total_passengers"] > best_primary["total_passengers"]:
                    best_primary = w
                elif w["total_passengers"] == best_primary["total_passengers"]:
                    if w["total_collection"] > best_primary["total_collection"]:
                        best_primary = w

            if best_primary and best_primary["total_passengers"] > 0:
                h_start = best_primary["start_hour"]
                classification = (
                    "Morning" if 5 <= h_start and h_start + 2 <= 11
                    else "Afternoon" if 12 <= h_start and h_start + 2 <= 16
                    else "Evening" if 17 <= h_start and h_start + 2 <= 22
                    else "Night / Off-Peak"
                )
                best_primary["is_applicable"] = True
                best_primary["time_classification"] = classification
                best_primary["selection_basis"] = (
                    f"Selected because this 3-hour window recorded the highest passenger quantity "
                    f"({best_primary['total_passengers']:,} passengers) across the entire operational timeline."
                )
            else:
                best_primary = {
                    "hours": "N/A", "detected_hours": [], "total_passengers": 0, "total_collection": 0.0,
                    "is_applicable": False, "selection_basis": "No operational passenger activity recorded."
                }

            # 2. Morning Window (05:00 - 12:00)
            morning_hours_in_data = [h for h in hourly_data if 5 <= h["hour_int"] <= 12 and h["passenger_quantity"] > 0]
            if morning_hours_in_data:
                best_morning = None
                for h in range(5, 10):  # 5..7, 6..8, 7..9, 8..10, 9..11 (all within 5..12)
                    w = evaluate_window(h)
                    if best_morning is None or w["total_passengers"] > best_morning["total_passengers"]:
                        best_morning = w
                    elif w["total_passengers"] == best_morning["total_passengers"] and w["total_collection"] > best_morning["total_collection"]:
                        best_morning = w
                morning_stats = best_morning
                morning_stats["is_applicable"] = True
                morning_stats["selection_basis"] = (
                    f"Selected because this 3-hour window recorded the highest passenger quantity "
                    f"({morning_stats['total_passengers']:,} passengers) among morning operational hours (05:00 - 12:00)."
                )
            else:
                morning_stats = {
                    "hours": "No Morning Trips Recorded",
                    "detected_hours": [],
                    "total_passengers": 0,
                    "total_collection": 0.0,
                    "total_transactions": 0,
                    "is_applicable": False,
                    "selection_basis": "Operational dataset contains no passenger transactions during morning hours (05:00 - 12:00)."
                }

            # 3. Evening Window (15:00 - 22:00)
            evening_hours_in_data = [h for h in hourly_data if 15 <= h["hour_int"] <= 22 and h["passenger_quantity"] > 0]
            if evening_hours_in_data:
                best_evening = None
                for h in range(15, 20):  # 15..17, 16..18, 17..19, 18..20, 19..21 (all within 15..22)
                    w = evaluate_window(h)
                    if best_evening is None or w["total_passengers"] > best_evening["total_passengers"]:
                        best_evening = w
                    elif w["total_passengers"] == best_evening["total_passengers"] and w["total_collection"] > best_evening["total_collection"]:
                        best_evening = w
                evening_stats = best_evening
                evening_stats["is_applicable"] = True
                evening_stats["selection_basis"] = (
                    f"Selected because this 3-hour window recorded the highest passenger quantity "
                    f"({evening_stats['total_passengers']:,} passengers) among evening operational hours (15:00 - 22:00)."
                )
            else:
                evening_stats = {
                    "hours": "No Evening Trips Recorded",
                    "detected_hours": [],
                    "total_passengers": 0,
                    "total_collection": 0.0,
                    "total_transactions": 0,
                    "is_applicable": False,
                    "selection_basis": "Operational dataset contains no passenger transactions during evening hours (15:00 - 22:00)."
                }

            return {
                "hourly_trends": hourly_data,
                "peak_transaction_hour": peak_tx_hour,
                "peak_passenger_hour": peak_psgr_hour,
                "peak_collection_hour": peak_coll_hour,
                "trough_hour": trough_hour,
                "primary_peak_window": best_primary,
                "morning_peak_stats": morning_stats,
                "evening_peak_stats": evening_stats
            }

    def get_waybill_analytics(self, dataset_id: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """
        Waybill-specific operational metrics (FR-08).
        Strictly labels results as waybill records without assuming driver or vehicle identities.
        """
        active_id = dataset_id or (self.data_engine.get_active_dataset() or {}).get("dataset_id")
        if not active_id:
            return {
                "waybills": [],
                "total_active_waybills": 0,
                "avg_records_per_waybill": 0.0,
                "avg_collection_per_waybill": 0.0
            }

        with self.data_engine._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
            SELECT 
                waybill_number,
                COUNT(*) as record_count,
                SUM(total_psgr) as passenger_quantity,
                ROUND(SUM(coll_amt), 2) as collection_amount,
                ROUND(SUM(uncoll_amt), 2) as uncollected_amount,
                COUNT(DISTINCT SUBSTR(time_str, 1, 2)) as active_hours_count,
                MIN(time_str) as first_transaction_time,
                MAX(time_str) as last_transaction_time,
                ROUND(SUM(coll_amt) / CAST(MAX(1, COUNT(*)) AS REAL), 2) as avg_collection_per_ticket
            FROM raw_tickets
            WHERE dataset_id = ?
            GROUP BY waybill_number
            ORDER BY collection_amount DESC
            LIMIT ?
            """, (active_id, limit))
            waybills = [dict(r) for r in cursor.fetchall()]

            cursor.execute("""
            SELECT 
                COUNT(DISTINCT waybill_number) as total_waybills,
                AVG(record_count) as avg_records_per_waybill,
                AVG(coll_amt_sum) as avg_collection_per_waybill
            FROM (
                SELECT waybill_number, COUNT(*) as record_count, SUM(coll_amt) as coll_amt_sum
                FROM raw_tickets WHERE dataset_id = ? GROUP BY waybill_number
            )
            """, (active_id,))
            wb_summary = cursor.fetchone()

            return {
                "waybills": waybills,
                "total_active_waybills": wb_summary["total_waybills"] or 0,
                "avg_records_per_waybill": round(wb_summary["avg_records_per_waybill"] or 0.0, 1),
                "avg_collection_per_waybill": round(wb_summary["avg_collection_per_waybill"] or 0.0, 2)
            }
